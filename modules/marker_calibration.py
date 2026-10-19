"""
Automatic camera-to-projection calibration.

The game projects ArUco markers at known places on a white screen; the camera
finds them, and a homography from screen to camera gives the camera position of
the projection's four corners: the same Calibration the click-the-corners tool
makes. A grid of markers is used so a few hidden ones (a painting, a person)
do not matter.
"""
import base64
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .calibration import Calibration

ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50
GRID = (4, 3)               # markers across, down
MARKER_HEIGHT_FRACTION = 0.16  # marker side as a share of the screen height
MARGIN = 0.1                # gap from the screen edge to the outer marker centers, per side
MIN_MARKERS = 4
MAX_REPROJECTION_ERROR = 4.0  # camera pixels

Box = Tuple[float, float, float, float]  # left, top, right, bottom as fractions of the screen


@dataclass(frozen=True)
class Marker:
    id: int
    column: int
    row: int
    box: Box


def marker_layout(screen_size: Tuple[int, int]) -> List[Marker]:
    """Square markers in a grid over the screen."""
    width, height = screen_size
    half_w = MARKER_HEIGHT_FRACTION * height / width / 2
    half_h = MARKER_HEIGHT_FRACTION / 2
    columns, rows = GRID
    markers = []
    for row in range(rows):
        for column in range(columns):
            cx = MARGIN + (1 - 2 * MARGIN) * column / (columns - 1)
            cy = MARGIN + (1 - 2 * MARGIN) * row / (rows - 1)
            markers.append(Marker(len(markers), column, row, (cx - half_w, cy - half_h, cx + half_w, cy + half_h)))
    return markers


def marker_image_url(marker_id: int, pixels: int = 240) -> str:
    """The marker as a PNG data URL, for showing in a web page."""
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    image = cv2.aruco.generateImageMarker(dictionary, marker_id, pixels)
    ok, png = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not encode the calibration marker")
    return "data:image/png;base64," + base64.b64encode(png.tobytes()).decode("ascii")


class MarkerCalibrator:
    """Feed it camera frames of the projected markers, then ask for the calibration."""

    def __init__(self, screen_size: Tuple[int, int]):
        self.screen_size = screen_size
        self.markers = {marker.id: marker for marker in marker_layout(screen_size)}
        self._detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY),
                                                 cv2.aruco.DetectorParameters())
        self._seen: Dict[int, List[np.ndarray]] = {}
        self._frame_size: Optional[Tuple[int, int]] = None
        self._last_view: Optional[np.ndarray] = None
        self.problem = "no camera frames yet"

    def page_message(self) -> dict:
        """What the game page needs to show the markers."""
        return {"type": "calibration", "markers": [{"id": m.id, "src": marker_image_url(m.id), "box": m.box}
                                                   for m in self.markers.values()]}

    def add_frame(self, frame: np.ndarray) -> int:
        """Look for markers in a camera frame; returns how many were found."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        self._frame_size = (gray.shape[1], gray.shape[0])
        corners, ids, _ = self._detector.detectMarkers(gray)
        self._last_view = cv2.aruco.drawDetectedMarkers(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), corners, ids)
        found = 0
        for marker_corners, marker_id in zip(corners, [] if ids is None else ids.flatten()):
            if int(marker_id) in self.markers:
                self._seen.setdefault(int(marker_id), []).append(marker_corners.reshape(4, 2))
                found += 1
        return found

    @property
    def markers_seen(self) -> int:
        return len(self._seen)

    def save_last_view(self, path: str) -> None:
        """The last camera frame with the markers found outlined, to check the camera's aim."""
        if self._last_view is not None:
            cv2.imwrite(path, self._last_view)

    def result(self) -> Optional[Calibration]:
        """The calibration, or None (with the reason in `problem`)."""
        seen = {i: np.median(np.stack(c), axis=0) for i, c in self._seen.items()}
        if len(seen) < MIN_MARKERS:
            self.problem = f"the camera saw {len(seen)} of {len(self.markers)} markers (needs {MIN_MARKERS})"
            return None
        if len({self.markers[i].column for i in seen}) < 2 or len({self.markers[i].row for i in seen}) < 2:
            self.problem = "the markers the camera saw are all in one row or column"
            return None

        width, height = self.screen_size
        screen_points, camera_points = [], []
        for marker_id, camera_corners in seen.items():
            left, top, right, bottom = self.markers[marker_id].box
            screen_points += [(left * width, top * height), (right * width, top * height),
                              (right * width, bottom * height), (left * width, bottom * height)]
            camera_points += camera_corners.tolist()
        screen_points, camera_points = np.float32(screen_points), np.float32(camera_points)
        to_camera, _ = cv2.findHomography(screen_points, camera_points, cv2.RANSAC, MAX_REPROJECTION_ERROR)
        if to_camera is None:
            self.problem = "the marker positions did not fit a flat wall"
            return None
        error = np.linalg.norm(cv2.perspectiveTransform(screen_points[None], to_camera)[0] - camera_points, axis=1)
        if float(np.median(error)) > MAX_REPROJECTION_ERROR:
            self.problem = f"the markers fit the wall poorly ({np.median(error):.1f} px off)"
            return None

        screen_corners = np.float32([[[0, 0], [width, 0], [width, height], [0, height]]])
        corners = cv2.perspectiveTransform(screen_corners, to_camera)[0]
        self.problem = ""
        return Calibration(corners.tolist(), *self._frame_size)
