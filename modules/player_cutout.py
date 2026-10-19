"""
The players cut out of the camera image, with the room around them removed,
mapped onto the screen (mirrored, for a camera facing them) so a game can show
the children inside its scene. Each result is a PNG with transparency.
"""
import os

import cv2
import numpy as np

from . import config
from .camera_worker import CameraWorker, MapperSource, run_model, torch_device
from .screen_mapper import ScreenMapper
from .threaded_game_state import ThreadSafeGameState

PERSON_CLASS = 0  # in the COCO classes the model was trained on


class PlayerCutout(CameraWorker[bytes]):
    MODEL_PATH = os.path.join(config.MODELS_DIR, "yolo11n-seg.pt")
    IMAGE_SIZE = 480
    PERSON_CONFIDENCE = 0.5  # lower also cuts out people in pictures on the wall
    MAX_FPS = 15
    VIEW_SCALE = 0.25        # of the screen size; the browser scales it up
    EDGE_FEATHER = 5         # pixels of soft edge around each child, odd

    def __init__(self, game_state: ThreadSafeGameState, mapper_source: MapperSource, screen_size):
        super().__init__("PlayerCutout", game_state, mapper_source)
        self.view_size = (int(screen_size[0] * self.VIEW_SCALE), int(screen_size[1] * self.VIEW_SCALE))

    def setup(self) -> None:
        from ultralytics import YOLO

        os.makedirs(config.MODELS_DIR, exist_ok=True)
        self._model = YOLO(self.MODEL_PATH)
        print(f"Player cut-out started ({torch_device()})")

    def process(self, frame: np.ndarray, stamp: float, mapper: ScreenMapper) -> bytes:
        result = run_model(self._model, frame, imgsz=self.IMAGE_SIZE, classes=[PERSON_CLASS],
                           conf=self.PERSON_CONFIDENCE, retina_masks=True)
        frame_h, frame_w = frame.shape[:2]
        to_view = np.diag([self.VIEW_SCALE, self.VIEW_SCALE, 1.0]) @ mapper.matrix_for_frame(frame_w, frame_h)
        if result.masks is None:
            alpha = np.zeros(self.view_size[::-1], np.uint8)
        else:
            people = (result.masks.data.max(0).values.numpy() * 255).astype(np.uint8)
            alpha = cv2.warpPerspective(people, to_view, self.view_size)
            alpha = cv2.GaussianBlur(alpha, (self.EDGE_FEATHER, self.EDGE_FEATHER), 0)
        color = cv2.warpPerspective(frame, to_view, self.view_size)
        color[alpha == 0] = 0  # compresses better
        ok, png = cv2.imencode(".png", np.dstack([color, alpha]), [cv2.IMWRITE_PNG_COMPRESSION, 1])
        if not ok:
            raise RuntimeError("could not encode the cut-out")
        return png.tobytes()
