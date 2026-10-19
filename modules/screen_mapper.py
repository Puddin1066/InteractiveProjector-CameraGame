"""Maps camera-frame positions onto projector pixels.

Detectors report positions normalized to 0..1 of the camera frame, so the
mappings hold for any capture resolution.

- CameraToScreenMapper: the camera watches the wall; a four-corner calibration
  says where the projection is in the camera image.
- PlayerFacingMapper: the camera watches the players; the area they can reach is
  stretched over the whole projection, mirrored like a selfie. No calibration.
"""
from typing import Tuple

import cv2
import numpy as np

from .calibration import Calibration, get_perspective_transform

Region = Tuple[float, float, float, float]  # x0, y0, x1, y1, normalized to the frame
FACING_WALL, FACING_PLAYERS = "wall", "players"  # which way the camera looks


class ScreenMapper:
    def __init__(self, screen_size: Tuple[int, int]):
        self.screen_width, self.screen_height = screen_size

    def contains(self, x: float, y: float, margin: float = 0) -> bool:
        return (-margin <= x <= self.screen_width + margin
                and -margin <= y <= self.screen_height + margin)


def _grow(region: Region, margin: float) -> Region:
    x0, y0, x1, y1 = region
    grow_x, grow_y = (x1 - x0) * margin, (y1 - y0) * margin
    return (max(0.0, x0 - grow_x), max(0.0, y0 - grow_y),
            min(1.0, x1 + grow_x), min(1.0, y1 + grow_y))


class CameraToScreenMapper(ScreenMapper):
    def __init__(self, calibration: Calibration, screen_size: Tuple[int, int]):
        super().__init__(screen_size)
        frame_scale = np.float32([calibration.frame_width, calibration.frame_height])
        self._normalized_corners = np.float32(calibration.points) / frame_scale
        self._normalized_matrix = get_perspective_transform(
            self._normalized_corners, self.screen_width, self.screen_height
        )

    def to_screen(self, x: float, y: float) -> Tuple[float, float]:
        point = np.float32([[[x, y]]])
        sx, sy = cv2.perspectiveTransform(point, self._normalized_matrix)[0][0]
        return float(sx), float(sy)

    def camera_region(self, margin: float) -> Region:
        """Normalized camera box around the projection, grown by `margin` of its size."""
        (x0, y0), (x1, y1) = self._normalized_corners.min(axis=0), self._normalized_corners.max(axis=0)
        return _grow((float(x0), float(y0), float(x1), float(y1)), margin)

    def matrix_for_frame(self, frame_width: int, frame_height: int) -> np.ndarray:
        """Homography from pixel coordinates of a frame of this size to the screen."""
        to_normalized = np.diag([1.0 / frame_width, 1.0 / frame_height, 1.0])
        return self._normalized_matrix @ to_normalized


class PlayerFacingMapper(ScreenMapper):
    def __init__(self, screen_size: Tuple[int, int], reach_zone: Region):
        super().__init__(screen_size)
        self._zone = reach_zone

    def to_screen(self, x: float, y: float) -> Tuple[float, float]:
        x0, y0, x1, y1 = self._zone
        return ((x1 - x) / (x1 - x0) * self.screen_width,
                (y - y0) / (y1 - y0) * self.screen_height)

    def camera_region(self, margin: float) -> Region:
        return _grow(self._zone, margin)

    def matrix_for_frame(self, frame_width: int, frame_height: int) -> np.ndarray:
        x0, y0, x1, y1 = self._zone
        scale_x = self.screen_width / (x1 - x0)
        scale_y = self.screen_height / (y1 - y0)
        return np.array([
            [-scale_x / frame_width, 0.0, x1 * scale_x],
            [0.0, scale_y / frame_height, -y0 * scale_y],
            [0.0, 0.0, 1.0],
        ])
