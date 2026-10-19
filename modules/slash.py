"""
Slicing-game rules, independent of rendering and input.

Treats are tossed up from the bottom of the screen; a fast enough swipe of a
hand (a blade) through one slices it for that player's team, as does any other
touch a game reports through `SlashRound.touch`. Skulls cost points.
Rounds are timed; slicing the big start pumpkin begins the next round.
"""
import math
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, List, Optional, Tuple

from .teams import LEFT, RIGHT, side_of

Point = Tuple[float, float]


class Phase(Enum):
    READY = "ready"
    PLAYING = "playing"
    RESULTS = "results"


@dataclass(frozen=True)
class TreatKind:
    name: str
    points: int
    radius: float   # fraction of screen height
    weight: float   # relative chance of being tossed


PUMPKIN = TreatKind("pumpkin", 1, 0.075, 5)
CANDY = TreatKind("candy", 2, 0.05, 3)
GHOST = TreatKind("ghost", 3, 0.065, 2)
SKULL = TreatKind("skull", -5, 0.065, 0)  # chance set by SlashSettings, rising over a round
START = TreatKind("start", 0, 0.14, 0)
TREATS = (PUMPKIN, CANDY, GHOST)


@dataclass
class SlashSettings:
    round_seconds: float = 60.0
    results_seconds: float = 8.0
    gravity: float = 1.5                     # screen heights per second squared
    rise: Tuple[float, float] = (0.55, 0.85)  # how high treats fly, fraction of height
    toss_interval: Tuple[float, float] = (1.0, 0.4)  # seconds between tosses, start -> end of round
    burst_chance: float = 0.25               # chance a toss throws 2-3 treats
    skull_chance: Tuple[float, float] = (0.05, 0.15)
    min_slash_speed: float = 0.8             # screen heights per second
    slash_reach: float = 0.03                # extra hit distance around a treat, fraction of height
    combo_window: float = 0.4                # seconds between slices that keep a combo going
    combo_min: int = 3
    treats: Tuple[TreatKind, ...] = TREATS   # kinds tossed, besides skulls
    treat_scale: float = 1.0                 # multiplies every treat's radius


@dataclass(eq=False)  # each treat is a distinct object, compared by identity
class Treat:
    kind: TreatKind
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    angle: float = 0.0
    spin: float = 0.0


@dataclass
class SliceEvent:
    treat: Treat
    side: str
    points: int
    blade_angle: float  # radians, direction the blade was moving


@dataclass
class Blade:
    side: str
    points: Deque[Tuple[float, float, float]] = field(default_factory=lambda: deque(maxlen=12))  # x, y, t

    @property
    def tip(self) -> Point:
        return self.points[-1][0], self.points[-1][1]


class BladeTracker:
    """Follows each hand across frames so its movement can slice.

    Pointers arrive as an unordered list per camera frame (and are re-read every
    render frame), so samples are matched to the nearest blade and repeats skipped.
    """

    EXPIRE_SECONDS = 0.3

    def __init__(self, width: float, height: float):
        self.width, self.height = width, height
        self.max_jump = 0.45 * height
        self.blades: List[Blade] = []

    def update(self, samples: List[Tuple[float, float, float]], now: float):
        """`samples` are (x, y, timestamp). Returns new swipe segments as
        (blade, start, end, speed in px/s)."""
        segments = []
        claimed = set()
        for x, y, t in samples:
            blade = self._nearest(x, y, claimed)
            if blade is None:
                blade = Blade(side_of(x, self.width))
                blade.points.append((x, y, t))
                self.blades.append(blade)
            else:
                last_x, last_y, last_t = blade.points[-1]
                if t > last_t:
                    blade.points.append((x, y, t))
                    speed = math.dist((x, y), (last_x, last_y)) / (t - last_t)
                    segments.append((blade, (last_x, last_y), (x, y), speed))
            claimed.add(id(blade))
        self.blades = [b for b in self.blades if now - b.points[-1][2] <= self.EXPIRE_SECONDS]
        return segments

    def _nearest(self, x: float, y: float, claimed: set) -> Optional[Blade]:
        best, best_distance = None, self.max_jump
        for blade in self.blades:
            if id(blade) in claimed:
                continue
            distance = math.dist((x, y), blade.tip)
            if distance <= best_distance:
                best, best_distance = blade, distance
        return best


class SlashRound:
    def __init__(self, width: int, height: int, settings: SlashSettings = SlashSettings()):
        self.width, self.height = width, height
        self.s = settings
        self.scores = {LEFT: 0, RIGHT: 0}
        self.treats: List[Treat] = []
        self.phase = Phase.READY
        self.time_left = settings.round_seconds
        self._clock = 0.0
        self._next_toss = 0.0
        self._timer = 0.0
        self._streaks: Dict[str, Tuple[int, float]] = {}  # side -> (count, last slice time)
        self._show_start_pumpkin()

    @property
    def winner(self) -> Optional[str]:
        if self.scores[LEFT] == self.scores[RIGHT]:
            return None
        return LEFT if self.scores[LEFT] > self.scores[RIGHT] else RIGHT

    def start(self) -> None:
        self.scores = {LEFT: 0, RIGHT: 0}
        self.treats = []
        self._streaks = {}
        self.phase = Phase.PLAYING
        self.time_left = self.s.round_seconds
        self._next_toss = self._clock + 0.5

    def reset(self) -> None:
        self.phase = Phase.READY
        self._show_start_pumpkin()

    def touch(self, hits) -> List[tuple]:
        """Slice treats touched by input other than blades, given as
        (treat, side, angle in radians) each. Returns events as `update` does."""
        events: List[tuple] = []
        for treat, side, angle in hits:
            events += self._take(treat, side, angle)
        return events

    def update(self, dt: float, segments=()) -> List[tuple]:
        """Advance by dt seconds and apply swipe segments from BladeTracker.
        Returns events: ("slice", SliceEvent), ("combo", side, count), ("start",), ("end",)."""
        self._clock += dt
        events: List[tuple] = []
        self._move_treats(dt)
        events += self._apply_slashes(segments)

        if self.phase is Phase.PLAYING:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self.phase = Phase.RESULTS
                self._timer = self.s.results_seconds
                self.treats = []
                events.append(("end",))
            elif self._clock >= self._next_toss:
                self._toss()
        elif self.phase is Phase.RESULTS:
            self._timer -= dt
            if self._timer <= 0:
                self.reset()
        return events

    # Treats
    def _show_start_pumpkin(self) -> None:
        radius = START.radius * self.s.treat_scale * self.height
        self.treats = [Treat(START, self.width / 2, self.height * 0.5, 0, 0, radius)]

    def _move_treats(self, dt: float) -> None:
        if self.phase is Phase.READY:
            pumpkin = self.treats[0] if self.treats else None
            if pumpkin:
                pumpkin.y = self.height * (0.5 + 0.03 * math.sin(self._clock * 2.0))
            return
        gravity = self.s.gravity * self.height
        for treat in self.treats:
            treat.vy += gravity * dt
            treat.x += treat.vx * dt
            treat.y += treat.vy * dt
            treat.angle += treat.spin * dt
        self.treats = [t for t in self.treats if not (t.vy > 0 and t.y - t.radius > self.height)]

    def _toss(self) -> None:
        progress = 1 - self.time_left / self.s.round_seconds
        count = random.choice((2, 3)) if random.random() < self.s.burst_chance else 1
        for _ in range(count):
            self.treats.append(self._new_treat(self._pick_kind(progress)))
        start, end = self.s.toss_interval
        self._next_toss = self._clock + start + (end - start) * progress

    def _pick_kind(self, progress: float) -> TreatKind:
        low, high = self.s.skull_chance
        if random.random() < low + (high - low) * progress:
            return SKULL
        return random.choices(self.s.treats, weights=[k.weight for k in self.s.treats])[0]

    def _new_treat(self, kind: TreatKind) -> Treat:
        radius = kind.radius * self.s.treat_scale * self.height
        x = random.uniform(0.12, 0.88) * self.width
        rise = random.uniform(*self.s.rise) * self.height
        flight = 2 * math.sqrt(2 * rise / (self.s.gravity * self.height))
        # Drift toward the middle so treats stay on screen for the whole flight
        target_x = random.uniform(0.25, 0.75) * self.width
        return Treat(kind, x, self.height + radius, (target_x - x) / flight,
                     -math.sqrt(2 * self.s.gravity * self.height * rise), radius,
                     spin=random.uniform(-4, 4))

    # Slicing
    def _apply_slashes(self, segments) -> List[tuple]:
        events: List[tuple] = []
        min_speed = self.s.min_slash_speed * self.height
        reach = self.s.slash_reach * self.height
        for blade, start, end, speed in segments:
            if speed < min_speed:
                continue
            blade_angle = math.atan2(end[1] - start[1], end[0] - start[0])
            for treat in list(self.treats):
                if _segment_distance((treat.x, treat.y), start, end) <= treat.radius + reach:
                    events += self._take(treat, blade.side, blade_angle)
        return events

    def _take(self, treat: Treat, side: str, angle: float) -> List[tuple]:
        if treat not in self.treats:  # already sliced, or cleared by a round starting
            return []
        self.treats.remove(treat)
        return self._slice(treat, side, angle)

    def _slice(self, treat: Treat, side: str, blade_angle: float) -> List[tuple]:
        if treat.kind is START:
            self.start()
            return [("slice", SliceEvent(treat, side, 0, blade_angle)), ("start",)]
        if self.phase is not Phase.PLAYING:
            return []

        events: List[tuple] = []
        points = treat.kind.points
        if points > 0:
            count, last = self._streaks.get(side, (0, -math.inf))
            count = count + 1 if self._clock - last <= self.s.combo_window else 1
            self._streaks[side] = (count, self._clock)
            if count >= self.s.combo_min:
                points += count - 1
                events.append(("combo", side, count))
        else:
            self._streaks[side] = (0, self._clock)
        self.scores[side] = max(0, self.scores[side] + points)
        return [("slice", SliceEvent(treat, side, points, blade_angle))] + events


def _segment_distance(point: Point, start: Point, end: Point) -> float:
    (px, py), (ax, ay), (bx, by) = point, start, end
    abx, aby = bx - ax, by - ay
    length_sq = abx * abx + aby * aby
    f = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / length_sq))
    return math.dist(point, (ax + f * abx, ay + f * aby))
