"""
Pointer tracking thread.
Runs a PointerDetector on each new camera frame, maps the results onto the
projector, and publishes them to the game state for any game to consume.
"""
import threading
import time

from . import config
from .pointer_detectors import RegionTiledDetector
from .screen_mapper import CameraToScreenMapper
from .threaded_game_state import ThreadSafeGameState


class PointerTrackingThread(threading.Thread):
    SCREEN_MARGIN = 50  # px outside the projection still accepted

    def __init__(self, detector: RegionTiledDetector, mapper: CameraToScreenMapper,
                 game_state: ThreadSafeGameState):
        super().__init__(name="PointerTracking")
        self.daemon = True

        self.detector = detector
        self.game_state = game_state
        self.set_mapper(mapper)
        self.running = True

        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0

    def set_mapper(self, mapper: CameraToScreenMapper) -> None:
        self.mapper = mapper
        self.detector.set_region(mapper.camera_region(config.DETECTION_REGION_MARGIN))

    def run(self):
        print(f"Pointer tracking thread started ({self.detector.label})")
        last_frame_timestamp = None

        while self.running and self.game_state.running:
            try:
                frame, frame_timestamp = self.game_state.get_current_frame(timeout=0.1)
                if frame is None or frame_timestamp == last_frame_timestamp:
                    time.sleep(0.005)
                    continue
                last_frame_timestamp = frame_timestamp

                mapper = self.mapper
                screen_pointers = []
                for pointer in self.detector.detect(frame):
                    sx, sy = mapper.to_screen(pointer.x, pointer.y)
                    if mapper.contains(sx, sy, self.SCREEN_MARGIN):
                        screen_pointers.append((sx, sy, pointer.confidence))
                self.game_state.update_pointers(screen_pointers)

                self._update_fps()
            except Exception as e:
                print(f"Error in pointer tracking thread: {e}")
                time.sleep(0.1)

        self.detector.close()
        print("Pointer tracking thread stopped")

    def _update_fps(self):
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.fps_start_time >= 1.0:
            self.current_fps = self.frame_count / (current_time - self.fps_start_time)
            self.game_state.update_fps(inference_fps=self.current_fps)
            self.frame_count = 0
            self.fps_start_time = current_time

    def stop(self):
        self.running = False
