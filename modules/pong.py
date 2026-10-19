"""
Pong rules, independent of rendering and input.
Each side has a round hand that hits the ball. A player's hand follows an (x, y)
target anywhere on that player's half; a side without a target is played by the
computer, which guards its goal line.
"""
import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from .teams import LEFT, RIGHT

DIRECTION = {LEFT: 1, RIGHT: -1}  # the way each side hits the ball


class Phase(Enum):
    SERVING = "serving"
    PLAYING = "playing"
    WON = "won"


@dataclass
class PongSettings:
    winning_score: int = 7
    hand_radius: float = 0.09         # fraction of screen height
    computer_inset: float = 0.06      # computer hand from its goal, fraction of width
    ball_radius: float = 0.045        # fraction of screen height
    serve_speed: float = 0.30         # screen widths per second
    max_speed: float = 0.70
    speedup_per_hit: float = 1.06
    max_bounce_degrees: float = 55
    player_hand_speed: float = 6.0    # screen heights per second; fast enough to feel direct
    computer_hand_speed: float = 0.55
    computer_aim_spread: float = 0.9  # how far off-center the computer meets the ball
    serve_delay: float = 1.2          # seconds
    win_display: float = 5.0


@dataclass
class Hand:
    x: float
    y: float
    radius: float
    home_x: float
    bounds: Tuple[float, float, float, float]  # x_min, x_max, y_min, y_max

    def move_toward(self, target: Tuple[float, float], max_step: float) -> None:
        dx, dy = target[0] - self.x, target[1] - self.y
        distance = math.hypot(dx, dy)
        if distance > max_step:
            dx, dy = dx * max_step / distance, dy * max_step / distance
        x_min, x_max, y_min, y_max = self.bounds
        self.x = max(x_min, min(x_max, self.x + dx))
        self.y = max(y_min, min(y_max, self.y + dy))


@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    radius: float


class PongMatch:
    def __init__(self, width: int, height: int, settings: PongSettings = PongSettings()):
        self.width, self.height = width, height
        self.s = settings
        self.hands = {side: self._make_hand(side) for side in (LEFT, RIGHT)}
        self.ball = Ball(width / 2, height / 2, 0, 0, settings.ball_radius * height)
        self.scores = {LEFT: 0, RIGHT: 0}
        self.winner: Optional[str] = None
        self._computer_aim = {LEFT: 0.0, RIGHT: 0.0}
        self._serve_toward = random.choice([LEFT, RIGHT])
        self._begin_serve()

    def reset(self) -> None:
        self.scores = {LEFT: 0, RIGHT: 0}
        self.winner = None
        self._begin_serve()

    def update(self, dt: float, targets: dict) -> List[str]:
        """Advance by dt seconds. `targets` maps LEFT/RIGHT to a hand (x, y) or None.
        Returns events: "hit", "wall", "score", "win"."""
        self._move_hands(dt, targets)
        self._timer -= dt

        if self.phase is Phase.WON:
            if self._timer <= 0:
                self.reset()
            return []
        if self.phase is Phase.SERVING:
            if self._timer <= 0:
                self._serve()
            return []
        return self._move_ball(dt)

    def _make_hand(self, side: str) -> Hand:
        radius = self.s.hand_radius * self.height
        inset = self.s.computer_inset * self.width
        if side == LEFT:
            home_x, x_range = inset, (radius, self.width / 2 - radius)
        else:
            home_x, x_range = self.width - inset, (self.width / 2 + radius, self.width - radius)
        return Hand(home_x, self.height / 2, radius, home_x,
                    (*x_range, radius, self.height - radius))

    def _move_hands(self, dt: float, targets: dict) -> None:
        for side, hand in self.hands.items():
            target = targets.get(side)
            if target is None:
                target, speed = (hand.home_x, self._computer_target_y(side)), self.s.computer_hand_speed
            else:
                speed = self.s.player_hand_speed
            hand.move_toward(target, speed * self.height * dt)

    def _computer_target_y(self, side: str) -> float:
        approaching = self.ball.vx * DIRECTION[side] < 0
        if not approaching or self.phase is not Phase.PLAYING:
            return self.height / 2
        reach = self.hands[side].radius + self.ball.radius
        return self.ball.y - self._computer_aim[side] * reach

    def _reroll_computer_aim(self) -> None:
        spread = self.s.computer_aim_spread
        self._computer_aim = {side: random.uniform(-spread, spread) for side in (LEFT, RIGHT)}

    def _move_ball(self, dt: float) -> List[str]:
        ball, events = self.ball, []
        ball.x += ball.vx * dt
        ball.y += ball.vy * dt

        if ball.y - ball.radius < 0 or ball.y + ball.radius > self.height:
            ball.y = min(max(ball.y, ball.radius), self.height - ball.radius)
            ball.vy = -ball.vy
            events.append("wall")

        if any(self._bounce_off(side) for side in (LEFT, RIGHT)):
            events.append("hit")

        if ball.x + ball.radius < 0:
            events += self._point_to(RIGHT)
        elif ball.x - ball.radius > self.width:
            events += self._point_to(LEFT)
        return events

    def _bounce_off(self, side: str) -> bool:
        """Send the ball back across, angled by where it touched the hand."""
        ball, hand, direction = self.ball, self.hands[side], DIRECTION[side]
        dx, dy = ball.x - hand.x, ball.y - hand.y
        reach = hand.radius + ball.radius
        distance = math.hypot(dx, dy)
        if distance >= reach or ball.vx * direction > 0:
            return False

        # A ball touched from behind still goes forward, at the steepest allowed angle
        max_angle = math.radians(self.s.max_bounce_degrees)
        angle = max(-max_angle, min(max_angle, math.atan2(dy, abs(dx))))
        speed = min(math.hypot(ball.vx, ball.vy) * self.s.speedup_per_hit, self.s.max_speed * self.width)
        ball.vx = direction * speed * math.cos(angle)
        ball.vy = speed * math.sin(angle)

        if distance > 0:
            ball.x, ball.y = hand.x + dx * reach / distance, hand.y + dy * reach / distance
        else:
            ball.x = hand.x + direction * reach
        self._reroll_computer_aim()
        return True

    def _point_to(self, side: str) -> List[str]:
        self.scores[side] += 1
        self._serve_toward = LEFT if side == RIGHT else RIGHT
        if self.scores[side] >= self.s.winning_score:
            self.winner = side
            self.phase = Phase.WON
            self._timer = self.s.win_display
            self._center_ball()
            return ["score", "win"]
        self._begin_serve()
        return ["score"]

    def _begin_serve(self) -> None:
        self.phase = Phase.SERVING
        self._timer = self.s.serve_delay
        self._center_ball()

    def _center_ball(self) -> None:
        self.ball.x, self.ball.y = self.width / 2, self.height / 2
        self.ball.vx = self.ball.vy = 0

    def _serve(self) -> None:
        angle = math.radians(random.uniform(-25, 25))
        speed = self.s.serve_speed * self.width
        self.ball.vx = -DIRECTION[self._serve_toward] * speed * math.cos(angle)
        self.ball.vy = speed * math.sin(angle)
        self.phase = Phase.PLAYING
        self._reroll_computer_aim()
