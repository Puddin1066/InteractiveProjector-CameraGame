"""One-command macOS launcher for Haunted Wall.

The sensor is the Mac's built-in camera. It is OpenCV index 0 on a Mac and
avoids the extra delay of a phone link.

The launcher uses that camera unless CAMERA_INDEX is already set, verifies
that an external display exists, prepares the optional CC0 Halloween art pack,
and launches the polished Haunted Wall.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

import cv2
from screeninfo import get_monitors


MAX_CAMERA_INDEX = int(os.getenv("CAMERA_PROBE_MAX_INDEX", "8"))
ROOT = Path(__file__).resolve().parent


def probe_camera(index: int) -> bool:
    cap = cv2.VideoCapture(index)
    try:
        if not cap.isOpened():
            return False
        for _ in range(6):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size:
                return True
        return False
    finally:
        cap.release()


def prefer_builtin_camera(candidates: list[int]) -> Optional[int]:
    """Pick the Mac built-in camera.

    OpenCV lists the FaceTime camera first. A later index is usually an
    iPhone or another attached camera.
    """
    if not candidates:
        return None
    return candidates[0]


def choose_camera() -> Optional[int]:
    explicit = os.getenv("CAMERA_INDEX", "").strip()
    if explicit:
        try:
            idx = int(explicit)
        except ValueError:
            raise SystemExit("CAMERA_INDEX must be an integer")
        if probe_camera(idx):
            return idx
        raise SystemExit(f"CAMERA_INDEX={idx} could not be opened")

    candidates = [idx for idx in range(MAX_CAMERA_INDEX + 1) if probe_camera(idx)]
    return prefer_builtin_camera(candidates)


def choose_projector() -> Optional[int]:
    monitors = get_monitors()
    explicit = os.getenv("PROJECTOR_MONITOR_INDEX", "").strip()
    if explicit:
        idx = int(explicit)
        return idx if 0 <= idx < len(monitors) else None
    return 1 if len(monitors) >= 2 else None


def ensure_visual_assets() -> None:
    required = [
        ROOT / "assets" / "halloween_cc0" / "graveyard2.png",
        ROOT / "assets" / "halloween_cc0" / "ghost_sheet.png",
    ]
    if all(path.exists() and path.stat().st_size > 0 for path in required):
        return

    print("Preparing optional CC0 Halloween visuals ...")
    try:
        result = subprocess.call([sys.executable, str(ROOT / "prepare_halloween_assets.py")])
        if result != 0:
            print("Asset preparation failed; the game will use its procedural fallback.")
    except Exception as exc:
        print(f"Could not prepare visual assets ({exc}); using procedural fallback.")


def main() -> int:
    if platform.system() != "Darwin":
        print("WARNING: this launcher is optimized for macOS.")

    camera_index = choose_camera()
    if camera_index is None:
        print("No usable local camera found.")
        print("Allow Camera access for Terminal, then run camera_probe.py.")
        print("The Mac built-in camera is index 0.")
        return 2

    projector_index = choose_projector()
    if projector_index is None:
        print("No external display detected.")
        print("Connect the MoGo 4 by HDMI and make sure macOS sees it as a second display.")
        return 3

    ensure_visual_assets()

    env = os.environ.copy()
    env["SENSOR_MODE"] = "local"
    env["CAMERA_INDEX"] = str(camera_index)
    env["PROJECTOR_MONITOR_INDEX"] = str(projector_index)
    env.setdefault("CAMERA_WIDTH", "1280")
    env.setdefault("CAMERA_HEIGHT", "720")
    env.setdefault("CAMERA_FPS", "30")

    sensor_name = "Mac built-in camera" if camera_index == 0 else "selected local camera"
    print("Haunted Wall hardware selection")
    print(f"  Sensor:          {sensor_name}, index {camera_index}")
    print(f"  Projector index: {projector_index}")
    print("  Sensor mode:     local")
    print("  Visual theme:    CC0 graveyard/ghost theme (with fallback)")
    print("Launching haunted_wall_cc0.py ...")

    return subprocess.call([sys.executable, str(ROOT / "haunted_wall_cc0.py")], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
