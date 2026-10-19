"""
Turns moving shadows into blades.

A still shadow (a child standing in the light) never cuts. Where a shadow has
just arrived (a hand sweeping across the wall) the newly darkened patch is the
leading edge of the hand; its center is that child's blade tip. Each child keeps
the same blade id while they swipe, up to five at once.
"""
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np

from .player_tracker import PlayerTracker


@dataclass
class Blade:
    id: int
    x: float  # fraction of the screen width
    y: float  # fraction of the screen height


class SwipeDetector:
    THRESHOLD = 0.5           # shadow probability that counts as shadow
    LOOKBACK = 0.12           # seconds; a patch is "new" if it was lit this long ago
    HISTORY_SECONDS = 0.5
    MIN_AREA_FRACTION = 0.0012  # smaller new patches are noise or a twitch
    MAX_AREA_FRACTION = 0.08    # bigger ones are a whole body stepping in, not a swipe
    MAX_JUMP = 0.2              # screen fractions a blade tip moves between camera frames
    FORGET_AFTER = 0.25         # seconds a blade may vanish and still be the same swipe (as in the page)

    def __init__(self, max_blades: int = 5):
        self.tracker = PlayerTracker(max_players=max_blades, max_jump=self.MAX_JUMP, forget_after=self.FORGET_AFTER)
        self._history: Deque[Tuple[float, np.ndarray]] = deque()
        self._kernel = np.ones((3, 3), np.uint8)

    def update(self, mask: np.ndarray, now: Optional[float] = None) -> List[Blade]:
        """`mask` is shadow probability on the analysis grid; returns the current blade tips."""
        now = time.monotonic() if now is None else now
        shadow = (mask > self.THRESHOLD).astype(np.uint8)
        before = self._shadow_before(now - self.LOOKBACK)
        self._remember(now, shadow)
        if before is None or before.shape != shadow.shape:
            return []

        fresh = cv2.morphologyEx(shadow & (1 - before), cv2.MORPH_OPEN, self._kernel)
        count, _, stats, centroids = cv2.connectedComponentsWithStats(fresh, connectivity=8)
        grid_h, grid_w = shadow.shape
        area_min, area_max = self.MIN_AREA_FRACTION * grid_w * grid_h, self.MAX_AREA_FRACTION * grid_w * grid_h
        tips = [(cx / grid_w, cy / grid_h) for (cx, cy), area in zip(centroids[1:], stats[1:, cv2.CC_STAT_AREA])
                if area_min <= area <= area_max]

        slots, _ = self.tracker.update(tips, now)
        return [Blade(slot, x, y) for slot, (x, y) in zip(slots, tips) if slot is not None]

    def _remember(self, now: float, shadow: np.ndarray) -> None:
        self._history.append((now, shadow))
        while self._history and now - self._history[0][0] > self.HISTORY_SECONDS:
            self._history.popleft()

    def _shadow_before(self, moment: float) -> Optional[np.ndarray]:
        """The newest remembered shadow at or before `moment`."""
        found = None
        for stamp, shadow in self._history:
            if stamp > moment:
                break
            found = shadow
        return found
