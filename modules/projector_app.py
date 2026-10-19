"""
Shared runtime for projector wall games.
Owns the projector window, the camera-to-screen mapping (four-corner calibration
when the camera faces the wall, none when it faces the players), and the threaded
camera + pointer tracking. Games read screen-space pointers and draw on `screen`.
"""
import os
import time

import cv2
import pygame

from . import config
from .calibration import calibrate_camera, load_calibration, save_calibration
from .camera_capture_thread import CameraCaptureThread
from .displays import projector_monitor
from .pointer_detectors import create_pointer_detector
from .pointer_tracking_thread import PointerTrackingThread
from .screen_mapper import FACING_PLAYERS, FACING_WALL, CameraToScreenMapper, PlayerFacingMapper
from .threaded_game_state import ThreadSafeGameState

DEBUG_VIEW_SIZE = (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
DEBUG_VIEW_INTERVAL = 0.1  # seconds; the laptop preview window is slow to draw and only for setup
POINTER_COLOR = (255, 255, 255)


class ProjectorApp:
    def __init__(self, caption: str, default_facing: str = FACING_WALL):
        """`default_facing` is the game's preferred camera direction; the
        CAMERA_FACING environment variable overrides it."""
        self.camera_facing = config.CAMERA_FACING or default_facing
        if self.camera_facing not in (FACING_WALL, FACING_PLAYERS):
            raise ValueError(f"CAMERA_FACING must be '{FACING_WALL}' or '{FACING_PLAYERS}'")
        os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
        pygame.init()

        self.monitor = projector_monitor()
        # Borderless rather than FULLSCREEN: macOS blanks a full-screen window
        # whenever the OpenCV calibration/camera windows take focus.
        os.environ["SDL_VIDEO_WINDOW_POS"] = f"{self.monitor.x},{self.monitor.y}"
        self.screen = pygame.display.set_mode(
            (self.monitor.width, self.monitor.height), pygame.NOFRAME
        )
        pygame.display.set_caption(caption)
        self.width, self.height = self.screen.get_size()
        print(f"Display: {self.width}x{self.height}")

        self.game_state = ThreadSafeGameState()
        self.mapper = None
        self.camera_thread = None
        self.tracking_thread = None
        self.pointer_label = "Pointer"
        self._last_debug_view = 0.0

    # Calibration
    def calibrate(self):
        """Set up the camera-to-screen mapping: the saved or a new four-corner
        calibration for a wall-facing camera, the reach zone for a player-facing one."""
        if self.camera_facing == FACING_PLAYERS:
            print("Camera faces the players: no calibration needed.")
            self._use_mapper(PlayerFacingMapper((self.width, self.height), config.PLAYER_REACH_ZONE))
            return

        calibration = load_calibration()
        if calibration is not None:
            print("Loading existing calibration...")
        else:
            print("Performing camera calibration...")
            calibration = self._run_calibration()
            if calibration is None:
                print("No camera calibration. Starting without camera tracking.")
                return
            save_calibration(calibration)
        self._apply_calibration(calibration)

    def recalibrate(self):
        if self.camera_facing == FACING_PLAYERS:
            print("Camera faces the players: there is nothing to recalibrate.")
            return
        print("Starting recalibration...")
        # The calibration window needs the camera to itself
        self._stop_camera()

        calibration = self._run_calibration()
        if calibration is None:
            print("Recalibration failed")
        else:
            save_calibration(calibration)
            self._apply_calibration(calibration)
            print("Recalibration completed")

        if self.tracking_thread:
            self.start_tracking()
        else:
            self.start_camera()

    def _run_calibration(self):
        """Interactive four-corner calibration at the tracking capture size"""
        # A bright projection makes the corners visible to the camera
        self.screen.fill((255, 255, 255))
        pygame.display.flip()
        pygame.event.pump()
        return calibrate_camera(config.CAMERA_INDEX, config.CAMERA_WIDTH, config.CAMERA_HEIGHT)

    def _apply_calibration(self, calibration):
        self._use_mapper(CameraToScreenMapper(calibration, (self.width, self.height)))

    def _use_mapper(self, mapper):
        self.mapper = mapper
        if self.tracking_thread:
            self.tracking_thread.set_mapper(mapper)

    # Tracking
    def start_camera(self) -> bool:
        """Start camera capture into the game state. Returns False if the camera failed."""
        try:
            self.camera_thread = CameraCaptureThread(config.CAMERA_INDEX, self.game_state)
            self.camera_thread.start()
            print("Camera thread started")
            return True
        except Exception as camera_error:
            print(f"Camera unavailable: {camera_error}")
            return False

    def start_tracking(self):
        """Start camera capture, plus pointer tracking if it is not running yet"""
        if self.mapper is None or not self.start_camera():
            return
        try:
            if self.tracking_thread is None:
                # Hands near a player-facing camera are already large; one tile keeps it fast
                tiles = 1 if self.camera_facing == FACING_PLAYERS else config.DETECTION_TILES
                detector = create_pointer_detector(tiles=tiles)
                self.pointer_label = detector.label
                self.tracking_thread = PointerTrackingThread(detector, self.mapper, self.game_state)
                self.tracking_thread.start()
        except Exception as tracking_error:
            print(f"Pointer tracking unavailable: {tracking_error}")

    def pointers(self):
        return self.game_state.get_pointers(config.POINTER_MAX_AGE)

    def shutdown(self):
        self.game_state.shutdown()
        self._stop_camera()
        if self.tracking_thread:
            self.tracking_thread.stop()
            self.tracking_thread.join(timeout=2.0)
        cv2.destroyAllWindows()

    def _stop_camera(self):
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.join(timeout=2.0)
            self.camera_thread = None

    # Drawing
    def draw_pointers(self):
        """Ring under each tracked pointer so players see where they are aiming"""
        for pointer in self.pointers():
            center = (int(pointer.x), int(pointer.y))
            pygame.draw.circle(self.screen, POINTER_COLOR, center, 28, 5)
            pygame.draw.circle(self.screen, POINTER_COLOR, center, 6)

    def show_camera_debug(self) -> bool:
        """Camera feed warped to projector space, with tracked pointers marked.
        Returns False when Q is pressed in the camera window."""
        now = time.monotonic()
        if self.mapper is None or now - self._last_debug_view < DEBUG_VIEW_INTERVAL:
            return True
        self._last_debug_view = now
        frame, _ = self.game_state.get_current_frame()
        if frame is None or frame.size == 0:
            return True

        frame_height, frame_width = frame.shape[:2]
        warped = cv2.warpPerspective(
            frame, self.mapper.matrix_for_frame(frame_width, frame_height),
            (self.width, self.height)
        )
        debug_view = cv2.resize(warped, DEBUG_VIEW_SIZE)
        scale_x = DEBUG_VIEW_SIZE[0] / self.width
        scale_y = DEBUG_VIEW_SIZE[1] / self.height

        for pointer in self.pointers():
            center = (int(pointer.x * scale_x), int(pointer.y * scale_y))
            cv2.circle(debug_view, center, 20, (0, 255, 0), 2)
            cv2.circle(debug_view, center, 5, (0, 0, 255), -1)
            cv2.putText(debug_view, f"{self.pointer_label}: {pointer.confidence:.2f}",
                        (center[0] - 20, center[1] - 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.imshow("Camera Feed", debug_view)
        return cv2.waitKey(1) & 0xFF != ord('q')
