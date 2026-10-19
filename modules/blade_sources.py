"""
Where the game's blades come from, as interchangeable sources:

- PoseBlades: a pose model finds every child's wrists in the camera image; each
  hand (the wrist, pushed a little further along the forearm) is a blade. Works
  however the children are lit, and the camera may see them from behind.
- ShadowBlades: the children's hand shadows on the wall; a blade is where a
  shadow has just arrived. Needs the camera to see the shadows unblocked.

Each source runs on its own thread and reports blades as screen fractions.
"""
import math
import os
import time
from typing import Callable, Dict, List, Optional, Protocol, Tuple

import numpy as np

from . import config
from .browser_screencast import BrowserScreencast
from .camera_worker import CameraWorker, MapperSource, run_model, torch_device
from .player_tracker import PlayerTracker
from .screen_mapper import ScreenMapper
from .shadow_swipes import Blade, SwipeDetector
from .silhouette import ProjectedImage, ShadowMask, SilhouetteThread
from .threaded_game_state import ThreadSafeGameState

Reading = Tuple[float, List[Blade]]  # (camera frame time, blades)


class BladeSource(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def latest(self) -> Optional[Reading]:
        """Blades from the newest camera frame; the same object until a new frame is analysed."""


class PoseBlades(CameraWorker[Reading]):
    MODEL_PATH = os.path.join(config.MODELS_DIR, "yolo11n-pose.pt")
    IMAGE_SIZE = 480
    PERSON_CONFIDENCE = 0.3
    JOINT_CONFIDENCE = 0.4
    WRISTS_AND_ELBOWS = ((9, 7), (10, 8))  # COCO keypoints: (left wrist, left elbow), (right ...)
    HAND_REACH = 0.35   # hand center beyond the wrist, as a fraction of the forearm
    EDGE_MARGIN = 0.05  # screen fractions outside the projection a hand still counts
    MAX_JUMP = 0.25     # screen fractions a hand moves between camera frames
    FORGET_AFTER = 0.25  # seconds a hand may vanish and still be the same swipe (as in the page)
    MIN_SPEED = 0.25    # screen fractions per second; slower hands (and people in pictures) do not cut

    def __init__(self, game_state: ThreadSafeGameState, mapper_source: MapperSource, max_blades: int = 10):
        super().__init__("PoseBlades", game_state, mapper_source)
        self.tracker = PlayerTracker(max_players=max_blades, max_jump=self.MAX_JUMP, forget_after=self.FORGET_AFTER)
        self._previous: Dict[int, Tuple[float, float, float]] = {}  # slot -> (x, y, time)

    def setup(self) -> None:
        from ultralytics import YOLO

        os.makedirs(config.MODELS_DIR, exist_ok=True)
        self._model = YOLO(self.MODEL_PATH)
        print(f"Hand tracking started ({torch_device()})")

    def process(self, frame: np.ndarray, stamp: float, mapper: ScreenMapper) -> Reading:
        result = run_model(self._model, frame, imgsz=self.IMAGE_SIZE, conf=self.PERSON_CONFIDENCE)
        hands = self._hands(result, frame.shape, mapper)
        slots, _ = self.tracker.update(hands, stamp)
        return stamp, [Blade(slot, x, y) for slot, (x, y) in zip(slots, hands)
                       if slot is not None and self._moving(slot, x, y, stamp)]

    def _moving(self, slot: int, x: float, y: float, stamp: float) -> bool:
        previous = self._previous.get(slot)
        self._previous[slot] = (x, y, stamp)
        if previous is None or stamp - previous[2] > self.FORGET_AFTER:
            return False
        return math.dist((x, y), previous[:2]) >= self.MIN_SPEED * (stamp - previous[2])

    def _hands(self, result, frame_shape, mapper: ScreenMapper) -> List[Tuple[float, float]]:
        """Each confidently seen hand, as screen fractions."""
        if result.keypoints is None or result.keypoints.conf is None:
            return []
        points = result.keypoints.xy.numpy()
        confidence = result.keypoints.conf.numpy()
        frame_h, frame_w = frame_shape[:2]
        hands = []
        for person, person_confidence in zip(points, confidence):
            for wrist, elbow in self.WRISTS_AND_ELBOWS:
                if person_confidence[wrist] < self.JOINT_CONFIDENCE:
                    continue
                hand = person[wrist]
                if person_confidence[elbow] >= self.JOINT_CONFIDENCE:
                    hand = hand + self.HAND_REACH * (person[wrist] - person[elbow])
                sx, sy = mapper.to_screen(hand[0] / frame_w, hand[1] / frame_h)
                x, y = sx / mapper.screen_width, sy / mapper.screen_height
                if -self.EDGE_MARGIN <= x <= 1 + self.EDGE_MARGIN and -self.EDGE_MARGIN <= y <= 1 + self.EDGE_MARGIN:
                    hands.append((float(np.clip(x, 0, 1)), float(np.clip(y, 0, 1))))
        return hands


class ShadowBlades:
    """Moving hand shadows, compared against the game's own frames streamed from Chrome."""

    def __init__(self, game_state: ThreadSafeGameState, mapper_source: MapperSource,
                 screen_size: Tuple[int, int], devtools_port: Callable[[], Optional[int]]):
        projected = ProjectedImage()
        self.silhouettes = SilhouetteThread(ShadowMask(projected), mapper_source, game_state, screen_size)
        self.page_frames = BrowserScreencast(devtools_port, self.silhouettes.grid_size, projected.push)
        self.swipes = SwipeDetector()
        self._mask: Optional[np.ndarray] = None
        self._latest: Optional[Reading] = None

    def start(self) -> None:
        self.page_frames.start()
        self.silhouettes.start()

    def stop(self) -> None:
        self.silhouettes.stop()
        self.page_frames.stop()

    def latest(self) -> Optional[Reading]:
        mask = self.silhouettes.latest_mask()
        if mask is not None and mask is not self._mask:
            self._mask = mask
            self._latest = (time.monotonic(), self.swipes.update(mask))
        return self._latest
