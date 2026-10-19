"""
A background thread that analyses each new camera frame once the camera-to-screen
mapping is known, and publishes its latest result.
"""
import threading
import time
from functools import lru_cache
from typing import Callable, Generic, Optional, TypeVar

import numpy as np

from .screen_mapper import ScreenMapper
from .threaded_game_state import ThreadSafeGameState

Result = TypeVar("Result")
MapperSource = Callable[[], Optional[ScreenMapper]]


_GPU_LOCK = threading.Lock()  # PyTorch's Apple GPU backend crashes when two threads use it at once


@lru_cache(maxsize=1)
def torch_device() -> str:
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def run_model(model, frame: np.ndarray, **options):
    """One ultralytics model's result for a frame, with its tensors already on the CPU.
    Models on different threads take turns on the GPU."""
    with _GPU_LOCK:
        return model(frame, device=torch_device(), verbose=False, **options)[0].cpu()


class CameraWorker(threading.Thread, Generic[Result]):
    MAX_FPS: Optional[float] = None  # None analyses every camera frame

    def __init__(self, name: str, game_state: ThreadSafeGameState, mapper_source: MapperSource):
        super().__init__(name=name, daemon=True)
        self.game_state = game_state
        self.mapper_source = mapper_source
        self.running = True
        self._lock = threading.Lock()
        self._latest: Optional[Result] = None

    def latest(self) -> Optional[Result]:
        """The newest result; the same object until another frame is analysed."""
        with self._lock:
            return self._latest

    def stop(self) -> None:
        self.running = False

    def setup(self) -> None:
        """Loads models; runs on this thread before the first frame."""

    def process(self, frame: np.ndarray, stamp: float, mapper: ScreenMapper) -> Result:
        raise NotImplementedError

    def run(self) -> None:
        self.setup()
        last_stamp, last_start = None, 0.0
        min_interval = 1.0 / self.MAX_FPS if self.MAX_FPS else 0.0
        while self.running and self.game_state.running:
            mapper = self.mapper_source()
            frame, stamp = self.game_state.get_current_frame(timeout=0.1)
            if (mapper is None or frame is None or stamp == last_stamp
                    or time.monotonic() - last_start < min_interval):
                time.sleep(0.003)
                continue
            last_stamp, last_start = stamp, time.monotonic()
            try:
                result = self.process(frame, stamp, mapper)
            except Exception as e:
                print(f"Error in {self.name}: {e}")
                time.sleep(0.1)
                continue
            with self._lock:
                self._latest = result
