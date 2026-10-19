"""
Gives each silhouette a steady player slot (0..max_players-1) from frame to frame,
so a child keeps their color and score while they move. A slot is freed only
after its silhouette has been gone for a moment, so brief dropouts do not reset it.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass
class _Track:
    position: Point
    last_seen: float


class PlayerTracker:
    def __init__(self, max_players: int = 5, max_jump: float = 0.25, forget_after: float = 1.5):
        """`max_jump` is the farthest a silhouette moves between updates, in the
        units of the positions given; `forget_after` is in seconds."""
        self.max_players = max_players
        self.max_jump = max_jump
        self.forget_after = forget_after
        self._tracks: Dict[int, _Track] = {}

    @property
    def active(self) -> List[int]:
        return sorted(self._tracks)

    def update(self, positions: Sequence[Point], now: float) -> Tuple[List[Optional[int]], List[int]]:
        """Returns the slot for each position (None when every slot is taken)
        and the slots freed by this update."""
        slots: List[Optional[int]] = [None] * len(positions)
        pairs = sorted((math.dist(p, track.position), i, slot)
                       for i, p in enumerate(positions) for slot, track in self._tracks.items())
        taken = set()
        for distance, i, slot in pairs:  # closest pairs first
            if distance > self.max_jump or slots[i] is not None or slot in taken:
                continue
            slots[i] = slot
            taken.add(slot)

        for i, position in enumerate(positions):
            if slots[i] is None:
                free = [s for s in range(self.max_players) if s not in self._tracks]
                if not free:
                    continue
                slots[i] = free[0]
            self._tracks[slots[i]] = _Track(position, now)

        freed = [s for s, track in self._tracks.items() if now - track.last_seen > self.forget_after]
        for slot in freed:
            del self._tracks[slot]
        return slots, freed
