"""Generic OpenCV video source with Reolink/RTSP support.

This module intentionally keeps the input contract tiny (`read`, `isOpened`,
`release`) so it can be passed to the existing calibration functions.
"""

from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Union

import cv2


VideoInput = Union[int, str]


@dataclass
class VideoSourceConfig:
    source: VideoInput
    width: int = 720
    height: int = 480
    fps: int = 30
    reconnect_seconds: float = 1.0
    buffer_size: int = 1


class VideoSource:
    """Small resilient wrapper around ``cv2.VideoCapture``.

    Local cameras use the platform default backend (AVFoundation on macOS,
    DirectShow on Windows). RTSP streams prefer FFmpeg when OpenCV exposes it.
    """

    def __init__(self, config: VideoSourceConfig):
        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None
        self.last_open_attempt = 0.0
        self.failures = 0
        self._open()

    @staticmethod
    def from_environment(
        fallback_camera_index: int = 0,
        width: int = 720,
        height: int = 480,
        fps: int = 30,
    ) -> "VideoSource":
        """Create a source from environment variables.

        REOLINK_RTSP_URL wins when set. Otherwise CAMERA_INDEX is used.
        """
        rtsp_url = os.getenv("REOLINK_RTSP_URL", "").strip()
        if rtsp_url:
            source: VideoInput = rtsp_url
        else:
            source = int(os.getenv("CAMERA_INDEX", str(fallback_camera_index)))

        return VideoSource(
            VideoSourceConfig(
                source=source,
                width=int(os.getenv("CAMERA_WIDTH", str(width))),
                height=int(os.getenv("CAMERA_HEIGHT", str(height))),
                fps=int(os.getenv("CAMERA_FPS", str(fps))),
            )
        )

    @property
    def is_network_stream(self) -> bool:
        return isinstance(self.config.source, str)

    def _open(self) -> None:
        self.release()
        self.last_open_attempt = time.time()

        if self.is_network_stream:
            # FFmpeg usually provides the most reliable RTSP handling. OpenCV
            # will fall back to its default backend when FFmpeg is unavailable.
            cap = cv2.VideoCapture(self.config.source, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(self.config.source)
        else:
            # Do not force CAP_DSHOW: it is Windows-only and breaks the Mac path.
            cap = cv2.VideoCapture(self.config.source)

        self.cap = cap

        if self.cap.isOpened():
            if not self.is_network_stream:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)

            # Supported by FFmpeg/GStreamer builds; ignored harmlessly elsewhere.
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.config.buffer_size)

    def isOpened(self) -> bool:  # noqa: N802 - OpenCV compatibility
        return bool(self.cap and self.cap.isOpened())

    def read(self) -> Tuple[bool, Optional[object]]:
        if not self.isOpened():
            if time.time() - self.last_open_attempt >= self.config.reconnect_seconds:
                self._open()
            return False, None

        ok, frame = self.cap.read()
        if ok and frame is not None:
            self.failures = 0
            return True, frame

        self.failures += 1
        if self.is_network_stream and self.failures >= 3:
            self._open()
        return False, None

    def release(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            finally:
                self.cap = None

    def describe(self) -> str:
        if self.is_network_stream:
            return "RTSP network camera"
        system = platform.system() or "local"
        return f"local camera {self.config.source} ({system})"
