"""
Lynx Spooky Slash: Fruit Ninja sliced with children's hands in front of the
projection, in Lincoln Lynx Halloween colors, for up to five children at once.

The game itself is the Baidu JS team's Fruit Ninja HTML5 game
(https://github.com/ChineseDron/fruit-ninja) reskinned in web/spooky_slash and
shown full screen in Chrome on the projector. This script finds every child's
hands with the camera and sends them to the game as blades. The mouse slices
too, for testing.

    python play.py spooky-slash [--layout wall] [--blades shadows] [--debug]

Layouts:
- players (default): the camera sits at the wall facing the children, who play
  from a few steps back, out of the projector's beam. The game shows them, cut
  out of the camera image and mirrored, inside the scene. No calibration.
- wall: the camera watches the wall from behind the children, who stand in the
  projection. The game projects markers so the camera can find the picture;
  press C in the game to calibrate again. Only this layout can use
  --blades shadows (moving hand shadows instead of hands).

--debug shows the camera view with the blades on the laptop. Ctrl+C quits.
"""
import argparse
import tempfile
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence

import cv2
import numpy as np

from modules import config
from modules.blade_sources import BladeSource, PoseBlades, ShadowBlades
from modules.calibration import Calibration, get_calibration, load_calibration, save_calibration
from modules.camera_capture_thread import CameraCaptureThread
from modules.displays import projector_monitor
from modules.kiosk_browser import devtools_port, open_kiosk
from modules.marker_calibration import MarkerCalibrator
from modules.player_cutout import PlayerCutout
from modules.screen_mapper import (FACING_PLAYERS, FACING_WALL, CameraToScreenMapper, PlayerFacingMapper,
                                   ScreenMapper)
from modules.threaded_game_state import ThreadSafeGameState
from modules.web_game_server import WebGameServer

WEB_ROOT = Path(__file__).resolve().parent.parent / "web" / "spooky_slash"
POLL_SECONDS = 0.005
PAGE_TIMEOUT = 20.0
MARKER_SETTLE_SECONDS = 1.0  # projector and camera exposure catch up with the marker screen
MARKER_SECONDS = 3.0         # longest time spent looking for markers
MARKER_FRAMES = 8            # frames with markers that are enough
DEBUG_VIEW_INTERVAL = 0.1
DEBUG_VIEW_SCALE = 0.25  # of the screen size
DEBUG_FRAMES_KEPT = 300
DEBUG_FOLDER = Path(tempfile.gettempdir()) / "spooky_slash_debug"
STATUS_INTERVAL = 5.0
CALIBRATION_VIEW = Path(tempfile.gettempdir()) / "spooky_slash_calibration_view.jpg"


class CameraFrames:
    """The running camera's frames with a cv2.VideoCapture-style read(), for the corner-click tool."""

    def __init__(self, game_state: ThreadSafeGameState):
        self.game_state = game_state

    def read(self):
        frame, _ = self.game_state.get_current_frame(timeout=0.1)
        return frame is not None, frame


class SpookySlash:
    def __init__(self, layout: str, blades: str, debug: bool, web_roots: Sequence[Path] = (WEB_ROOT,)):
        """`web_roots`: the browser game's folders, a theme first, e.g. (theme, WEB_ROOT)."""
        monitor = projector_monitor()
        self.monitor = monitor
        self.screen_size = (monitor.width, monitor.height)
        self.layout = layout
        self.mapper: Optional[ScreenMapper] = (
            PlayerFacingMapper(self.screen_size, config.PLAYER_REACH_ZONE) if layout == FACING_PLAYERS else None)
        self.game_state = ThreadSafeGameState()
        self.cutout = (PlayerCutout(self.game_state, self._current_mapper, self.screen_size)
                       if layout == FACING_PLAYERS else None)
        self.blades: BladeSource = (
            PoseBlades(self.game_state, self._current_mapper) if blades == "hands"
            else ShadowBlades(self.game_state, self._current_mapper, self.screen_size, devtools_port))
        self.debug_view = _DebugView(self.game_state, self._current_mapper, self.screen_size) if debug else None
        self.server = WebGameServer(web_roots, self._on_game_message)
        self.camera: Optional[CameraCaptureThread] = None
        self._recalibrate = threading.Event()

    def run(self) -> None:
        self.server.start()
        browser = open_kiosk(self.server.url, self.monitor)
        try:
            if not self.server.wait_for_page(PAGE_TIMEOUT):
                print("The game page did not open in Chrome.")
                return
            self.camera = CameraCaptureThread(config.CAMERA_INDEX, self.game_state)
            self.camera.start()
            self.blades.start()
            if self.cutout:
                self.cutout.start()
            if self.layout == FACING_WALL:
                self._recalibrate.set()
                print("Slice with your hands! Press C in the game to recalibrate. Ctrl+C quits.")
            else:
                print("Slice with your hands from a few steps back! Ctrl+C quits.")
            self._play(browser)
        except KeyboardInterrupt:
            pass
        finally:
            self.game_state.shutdown()
            self.blades.stop()
            if self.cutout:
                self.cutout.stop()
            if self.camera:
                self.camera.stop()
                self.camera.join(timeout=2.0)
            self.server.stop()
            browser.terminate()
            cv2.destroyAllWindows()

    def _current_mapper(self) -> Optional[ScreenMapper]:
        return self.mapper

    def _on_game_message(self, message: dict) -> None:
        if message.get("type") != "recalibrate":
            return
        if self.layout == FACING_WALL:
            self._recalibrate.set()
        else:
            print("The camera faces the players, so there is nothing to calibrate.")

    def _play(self, browser) -> None:
        """Until the game window closes: calibrate when asked, and send the game the blades and the
        cut-out players from each analysed camera frame."""
        last_reading = last_cutout = None
        status = _Status()
        while browser.poll() is None:
            if self._recalibrate.is_set():
                self._recalibrate.clear()
                self._calibrate()
                last_reading = self.blades.latest()  # made from the calibration screen
            reading = self.blades.latest()
            cutout = self.cutout.latest() if self.cutout else None
            if reading is last_reading and cutout is last_cutout:
                time.sleep(POLL_SECONDS)
                continue
            if reading is not last_reading:
                last_reading = reading
                _, blades = reading
                self.server.broadcast({"type": "blades", "blades": [asdict(blade) for blade in blades]})
                status.add(blades)
                if self.debug_view:
                    self.debug_view.add(blades)
            if cutout is not last_cutout:
                last_cutout = cutout
                self.server.broadcast_binary(cutout)

    # Calibration
    def _calibrate(self) -> None:
        """Find the projection with the camera; fall back to the saved calibration, then to clicking the corners."""
        self.server.broadcast({"type": "blades", "blades": [], "reset": True})
        calibration = self._find_markers()
        if calibration is None:
            calibration = load_calibration()
            if calibration is not None:
                print("Using the saved calibration. Press C in the game to try again.")
            else:
                calibration = self._click_corners()
        else:
            save_calibration(calibration)
        self.server.broadcast({"type": "calibration-done"})
        if calibration is None:
            print("No calibration, so shadows cannot be found. Use the mouse to play, or press C to try again.")
            return
        self.mapper = CameraToScreenMapper(calibration, self.screen_size)

    def _find_markers(self) -> Optional[Calibration]:
        print("Calibrating: finding the projected markers with the camera...")
        calibrator = MarkerCalibrator(self.screen_size)
        self.server.broadcast(calibrator.page_message())
        time.sleep(MARKER_SETTLE_SECONDS)
        frames_with_markers, last_stamp = 0, None
        deadline = time.monotonic() + MARKER_SECONDS
        while time.monotonic() < deadline and frames_with_markers < MARKER_FRAMES:
            frame, stamp = self.game_state.get_current_frame(timeout=0.2)
            if frame is None or stamp == last_stamp:
                continue
            last_stamp = stamp
            frames_with_markers += calibrator.add_frame(frame) > 0
        calibration = calibrator.result()
        calibrator.save_last_view(str(CALIBRATION_VIEW))
        print(f"What the camera saw: {CALIBRATION_VIEW}")
        if calibration is None:
            print(f"Automatic calibration failed: {calibrator.problem}.")
        else:
            print(f"Calibrated from {calibrator.markers_seen} of {len(calibrator.markers)} markers.")
        return calibration

    def _click_corners(self) -> Optional[Calibration]:
        print("Click the four corners of the white projection in the camera window.")
        self.server.broadcast({"type": "calibration", "markers": []})
        calibration = get_calibration(CameraFrames(self.game_state))
        if calibration is not None:
            save_calibration(calibration)
        return calibration


class _Status:
    """Prints how fast the camera is analysed and how many blade points it makes, every few seconds."""

    def __init__(self):
        self._reset()

    def _reset(self) -> None:
        self._since = time.monotonic()
        self._frames = self._blade_points = 0

    def add(self, blades) -> None:
        self._frames += 1
        self._blade_points += len(blades)
        if time.monotonic() - self._since >= STATUS_INTERVAL:
            print(f"Camera: {self._frames / STATUS_INTERVAL:.0f} frames/s analysed, {self._blade_points} blade points")
            self._reset()


class _DebugView:
    """Shows, and saves to DEBUG_FOLDER, the camera image warped onto the screen with the blades on it."""

    def __init__(self, game_state: ThreadSafeGameState, mapper_source, screen_size):
        self.game_state = game_state
        self.mapper_source = mapper_source
        self.size = (int(screen_size[0] * DEBUG_VIEW_SCALE), int(screen_size[1] * DEBUG_VIEW_SCALE))
        self._last = 0.0
        self._count = 0
        DEBUG_FOLDER.mkdir(exist_ok=True)

    def add(self, blades) -> None:
        mapper = self.mapper_source()
        frame, _ = self.game_state.get_current_frame(timeout=0)
        if time.monotonic() - self._last < DEBUG_VIEW_INTERVAL or mapper is None or frame is None:
            return
        self._last = time.monotonic()
        to_view = np.diag([DEBUG_VIEW_SCALE, DEBUG_VIEW_SCALE, 1.0]) @ mapper.matrix_for_frame(frame.shape[1], frame.shape[0])
        view = cv2.warpPerspective(frame, to_view, self.size)
        width, height = self.size
        for blade in blades:
            center = (int(blade.x * width), int(blade.y * height))
            cv2.circle(view, center, 6, (0, 140, 255), -1)
            cv2.putText(view, str(blade.id + 1), (center[0] + 8, center[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.imwrite(str(DEBUG_FOLDER / f"{self._count % DEBUG_FRAMES_KEPT:04d}.jpg"), view)
        self._count += 1
        cv2.imshow("Spooky Slash debug", view)
        cv2.waitKey(1)


def main(web_roots: Sequence[Path] = (WEB_ROOT,), description: str = __doc__) -> None:
    parser = argparse.ArgumentParser(description=description.split("\n\n")[0])
    parser.add_argument("--layout", choices=(FACING_PLAYERS, FACING_WALL), default=config.CAMERA_FACING or FACING_PLAYERS,
                        help="where the camera looks: at the players (default) or at the wall")
    parser.add_argument("--blades", choices=("hands", "shadows"), default="hands",
                        help="find the children's hands with a pose model (default), or their moving shadows")
    parser.add_argument("--debug", action="store_true", help="show and save the camera view with the blades")
    args = parser.parse_args()
    missing = [str(root) for root in web_roots if not root.is_dir()]
    if missing:
        parser.error(f"the browser game is not in this checkout: {', '.join(missing)} "
                     "(it is kept out of the public repository, see README)")
    if args.blades == "shadows" and args.layout != FACING_WALL:
        parser.error("--blades shadows needs --layout wall: the camera must see the shadows on the wall")
    SpookySlash(args.layout, args.blades, args.debug, web_roots).run()


if __name__ == "__main__":
    main()
