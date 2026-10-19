"""Pointer detectors: turn one BGR camera frame into pointer positions.

Positions are normalized to 0..1 of the frame. Games never see detector
specifics; they read screen-space pointers from the game state.
"""
import math
import os
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol

import cv2

from . import config
from .model_files import download_if_missing
from .screen_mapper import Region


@dataclass(frozen=True)
class NormalizedPointer:
    x: float
    y: float
    confidence: float


class PointerDetector(Protocol):
    label: str

    def detect(self, frame) -> List[NormalizedPointer]: ...

    def close(self) -> None: ...


class HandDetector:
    """Palm centers of up to ``max_hands`` hands, via MediaPipe Hand Landmarker."""

    label = "Hand"
    # Wrist and the four finger knuckles: stable whether the hand is open or a fist
    PALM_LANDMARKS = (0, 5, 9, 13, 17)

    def __init__(self, model_path: str, model_url: str, max_hands: int, min_confidence: float):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        download_if_missing(model_path, model_url)
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=min_confidence,
            min_hand_presence_confidence=min_confidence,
            min_tracking_confidence=min_confidence,
        )
        self._mp = mp
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_timestamp_ms = 0

    def detect(self, frame) -> List[NormalizedPointer]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        # VIDEO mode requires strictly increasing timestamps.
        timestamp_ms = max(self._last_timestamp_ms + 1, int(time.monotonic() * 1000))
        self._last_timestamp_ms = timestamp_ms
        result = self._landmarker.detect_for_video(image, timestamp_ms)

        pointers = []
        for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
            palm = [landmarks[i] for i in self.PALM_LANDMARKS]
            score = handedness[0].score if handedness else 1.0
            pointers.append(NormalizedPointer(
                sum(p.x for p in palm) / len(palm), sum(p.y for p in palm) / len(palm), score
            ))
        return pointers

    def close(self) -> None:
        self._landmarker.close()


class YoloBallDetector:
    """Centers of balls found by the custom YOLO model (single class: Green Ball)."""

    label = "Green Ball"

    def __init__(self, model_path: str, conf_threshold: float, iou_threshold: float):
        from ultralytics import YOLO

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"YOLO model not found: {model_path}")
        self._model = YOLO(model_path, task="detect", verbose=False)
        self._conf = conf_threshold
        self._iou = iou_threshold

    def detect(self, frame) -> List[NormalizedPointer]:
        height, width = frame.shape[:2]
        results = self._model.predict(
            frame, imgsz=640, conf=self._conf, iou=self._iou, device="cpu", verbose=False
        )
        pointers = []
        for result in results:
            for box in result.boxes or []:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                pointers.append(NormalizedPointer(
                    (x1 + x2) / 2 / width, (y1 + y2) / 2 / height, float(box.conf[0])
                ))
        return pointers

    def close(self) -> None:
        pass


class RegionTiledDetector:
    """Runs a detector on side-by-side crops of a region of the frame.

    Detection models shrink their input to a fixed size, so a hand that fills a
    small part of the frame becomes too small to find. Cropping to the projection
    and splitting it into tiles keeps it large. Each tile gets its own detector
    because video-mode trackers expect one continuous stream.
    """

    TILE_OVERLAP = 0.1      # fraction of the region width shared by neighbouring tiles
    DUPLICATE_RADIUS = 0.03  # normalized distance under which two detections are one

    def __init__(self, make_detector: Callable[[], PointerDetector], tiles: int):
        self._detectors = [make_detector() for _ in range(max(1, tiles))]
        self.label = self._detectors[0].label
        self._region: Region = (0.0, 0.0, 1.0, 1.0)

    def set_region(self, region: Optional[Region]) -> None:
        self._region = region or (0.0, 0.0, 1.0, 1.0)

    def detect(self, frame) -> List[NormalizedPointer]:
        height, width = frame.shape[:2]
        pointers = []
        for detector, (x0, y0, x1, y1) in zip(self._detectors, self._tiles()):
            left, top = int(x0 * width), int(y0 * height)
            right, bottom = int(x1 * width), int(y1 * height)
            if right - left < 2 or bottom - top < 2:
                continue
            crop = frame[top:bottom, left:right]
            for p in detector.detect(crop):
                pointers.append(NormalizedPointer(
                    x0 + p.x * (x1 - x0), y0 + p.y * (y1 - y0), p.confidence
                ))
        return self._merge_duplicates(pointers)

    def close(self) -> None:
        for detector in self._detectors:
            detector.close()

    def _tiles(self) -> List[Region]:
        x0, y0, x1, y1 = self._region
        count = len(self._detectors)
        step = (x1 - x0) / count
        overlap = (x1 - x0) * self.TILE_OVERLAP
        return [(max(x0, x0 + i * step - overlap), y0, min(x1, x0 + (i + 1) * step + overlap), y1)
                for i in range(count)]

    def _merge_duplicates(self, pointers: List[NormalizedPointer]) -> List[NormalizedPointer]:
        kept: List[NormalizedPointer] = []
        for pointer in sorted(pointers, key=lambda p: -p.confidence):
            if all(math.dist((pointer.x, pointer.y), (k.x, k.y)) > self.DUPLICATE_RADIUS for k in kept):
                kept.append(pointer)
        return kept


def create_pointer_detector(mode: str = config.INPUT_MODE,
                            tiles: int = config.DETECTION_TILES) -> RegionTiledDetector:
    if mode == "hand":
        return RegionTiledDetector(
            lambda: HandDetector(config.HAND_MODEL_PATH, config.HAND_MODEL_URL,
                                 config.MAX_HANDS, config.HAND_CONFIDENCE),
            tiles,
        )
    if mode == "ball":
        return RegionTiledDetector(
            lambda: YoloBallDetector(config.MODEL_PATH, config.CONF_THRESHOLD, config.IOU_THRESHOLD),
            tiles=1,
        )
    raise ValueError(f"Unsupported INPUT_MODE={mode!r}; use 'hand' or 'ball'")
