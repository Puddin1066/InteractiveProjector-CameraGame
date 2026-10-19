"""
Player silhouettes in projector space.

A background thread turns each new camera frame into a silhouette probability
on a reduced grid (screen size / GRID_DIVISOR) for shape analysis. Where the
silhouette comes from is pluggable:

- ShadowMask: the camera faces the wall and finds the players' real shadows,
  i.e. places much darker than what the game just projected there.
- PersonMask: the camera faces the players; MediaPipe's selfie segmenter finds
  their bodies.
"""
import threading
import time
from collections import deque
from typing import Callable, Optional, Protocol, Tuple

import cv2
import numpy as np

from . import config
from .model_files import download_if_missing
from .threaded_game_state import ThreadSafeGameState

GRID_DIVISOR = 4      # analysis grid is a quarter of the screen size per side
MASK_SMOOTHING = 0.55  # weight of the newest mask; lower is steadier but laggier

GridSize = Tuple[int, int]  # (width, height)


class MaskSource(Protocol):
    def grid_mask(self, frame: np.ndarray, to_grid: np.ndarray, grid_size: GridSize) -> np.ndarray:
        """Silhouette probability (0..1) on the grid, rows = grid height."""

    def close(self) -> None:
        ...


class PersonSegmenter:
    """Probability (0..1) that each pixel of a BGR frame belongs to a person."""

    def __init__(self, model_path: str = config.SEGMENTER_MODEL_PATH,
                 model_url: str = config.SEGMENTER_MODEL_URL):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        download_if_missing(model_path, model_url)
        options = vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            output_confidence_masks=True,
            output_category_mask=False,
        )
        self._mp = mp
        self._segmenter = vision.ImageSegmenter.create_from_options(options)
        self._last_timestamp_ms = 0

    def segment(self, frame) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        # VIDEO mode requires strictly increasing timestamps.
        timestamp_ms = max(self._last_timestamp_ms + 1, int(time.monotonic() * 1000))
        self._last_timestamp_ms = timestamp_ms
        result = self._segmenter.segment_for_video(image, timestamp_ms)
        return result.confidence_masks[0].numpy_view().squeeze().astype(np.float32)

    def close(self) -> None:
        self._segmenter.close()


class PersonMask:
    """Players' bodies, seen by a camera facing them."""

    def __init__(self, segmenter: Optional[PersonSegmenter] = None):
        self.segmenter = segmenter or PersonSegmenter()

    def grid_mask(self, frame, to_grid, grid_size):
        return cv2.warpPerspective(self.segmenter.segment(frame), to_grid, grid_size)

    def close(self) -> None:
        self.segmenter.close()


class ProjectedImage:
    """Recently projected frames as luminance (0..1) on the analysis grid.

    The camera sees the wall a few frames late, so a pixel counts as bright only
    if it stayed bright for the whole recent history."""

    HISTORY_SECONDS = 0.35

    def __init__(self):
        self._lock = threading.Lock()
        self._frames: deque = deque()

    def push(self, luminance: np.ndarray) -> None:
        now = time.monotonic()
        with self._lock:
            self._frames.append((now, luminance))
            while self._frames and now - self._frames[0][0] > self.HISTORY_SECONDS:
                self._frames.popleft()

    def expected(self) -> Optional[np.ndarray]:
        with self._lock:
            frames = [luminance for _, luminance in self._frames]
        return np.minimum.reduce(frames) if frames else None


class ShadowMask:
    """Real shadows on the wall, seen by a calibrated camera facing it.

    Each pixel's camera brightness is divided by what was projected there and by
    a slowly learned per-pixel gain (projector falloff, wall texture, camera
    vignetting). Pixels far darker than that are shadow."""

    SHADOW_BELOW = 0.4    # relative brightness that is surely shadow
    WALL_ABOVE = 0.65     # relative brightness that is surely lit wall
    MIN_EXPECTED = 0.25   # darker projected content cannot reveal a shadow
    GAIN_LEARN = 0.05     # per-frame gain update on lit wall
    GAIN_LEARN_SHADOW = 0.0005  # very slow, so a still player only fades after about a minute
    LIT_PERCENTILE = 85   # reference brightness; still lit wall while shadows cover most of the screen

    def __init__(self, projected: ProjectedImage):
        self.projected = projected
        self._gain: Optional[np.ndarray] = None
        self._to_grid: Optional[np.ndarray] = None
        self._covered: Optional[np.ndarray] = None

    def grid_mask(self, frame, to_grid, grid_size):
        empty = np.zeros((grid_size[1], grid_size[0]), np.float32)
        expected = self.projected.expected()
        if expected is None or expected.shape != empty.shape:
            return empty

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        if self._to_grid is None or not np.allclose(self._to_grid, to_grid):
            # New calibration: relearn what the lit wall looks like
            self._to_grid, self._gain = to_grid.copy(), None
            self._covered = cv2.warpPerspective(np.ones_like(gray), to_grid, grid_size) > 0.99
        seen = cv2.GaussianBlur(cv2.warpPerspective(gray, to_grid, grid_size), (5, 5), 0)

        valid = self._covered & (expected > self.MIN_EXPECTED)
        if not valid.any():
            return empty
        ratio = seen / np.maximum(expected, self.MIN_EXPECTED)
        if self._gain is None:
            self._gain = np.full_like(ratio, np.percentile(ratio[valid], self.LIT_PERCENTILE))

        relative = ratio / np.maximum(self._gain, 1e-3)
        lit = float(np.percentile(relative[valid], self.LIT_PERCENTILE))
        relative /= max(lit, 1e-3)  # follow camera auto-exposure
        shadow = np.clip((self.WALL_ABOVE - relative) / (self.WALL_ABOVE - self.SHADOW_BELOW), 0.0, 1.0)
        shadow[~valid] = 0.0

        rate = np.where(shadow > 0.5, self.GAIN_LEARN_SHADOW, self.GAIN_LEARN)
        self._gain = np.where(valid, self._gain + rate * (ratio - self._gain), self._gain)
        return shadow

    def close(self) -> None:
        pass


class SilhouetteThread(threading.Thread):
    def __init__(self, source: MaskSource, mapper_source: Callable[[], object],
                 game_state: ThreadSafeGameState, screen_size: Tuple[int, int]):
        """`mapper_source` returns the current screen mapper, so recalibration takes effect."""
        super().__init__(name="Silhouette", daemon=True)
        self.source = source
        self.mapper_source = mapper_source
        self.game_state = game_state
        self.grid_size = (screen_size[0] // GRID_DIVISOR, screen_size[1] // GRID_DIVISOR)
        self.running = True
        self._lock = threading.Lock()
        self._mask: Optional[np.ndarray] = None

    def latest_mask(self) -> Optional[np.ndarray]:
        """Silhouette probability on the analysis grid (rows = grid height), or None."""
        with self._lock:
            return self._mask

    def run(self):
        print("Silhouette thread started")
        last_frame_timestamp = None
        smoothed = None
        scale_to_grid = np.diag([1.0 / GRID_DIVISOR, 1.0 / GRID_DIVISOR, 1.0])

        while self.running and self.game_state.running:
            try:
                mapper = self.mapper_source()
                frame, frame_timestamp = self.game_state.get_current_frame(timeout=0.1)
                if mapper is None or frame is None or frame_timestamp == last_frame_timestamp:
                    time.sleep(0.005)
                    continue
                last_frame_timestamp = frame_timestamp

                frame_h, frame_w = frame.shape[:2]
                to_grid = scale_to_grid @ mapper.matrix_for_frame(frame_w, frame_h)
                mask = self.source.grid_mask(frame, to_grid, self.grid_size)
                smoothed = mask if smoothed is None else (
                    MASK_SMOOTHING * mask + (1 - MASK_SMOOTHING) * smoothed)
                with self._lock:
                    self._mask = smoothed.copy()
            except Exception as e:
                print(f"Error in silhouette thread: {e}")
                time.sleep(0.1)

        self.source.close()
        print("Silhouette thread stopped")

    def stop(self):
        self.running = False
