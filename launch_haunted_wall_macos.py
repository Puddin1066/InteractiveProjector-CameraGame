"""One-command macOS launcher for Haunted Wall.

Targets the preferred hardware topology:
    iPhone 14 -> USB/Continuity Camera -> Mac -> HDMI -> XGIMI MoGo 4

The launcher probes local camera indices, chooses the first usable local camera
unless CAMERA_INDEX is already set, verifies that an external display exists,
sets the relevant environment variables, and then launches Haunted Wall.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Optional

import cv2
from screeninfo import get_monitors


MAX_CAMERA_INDEX = int(os.getenv("CAMERA_PROBE_MAX_INDEX", "8"))


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

    candidates = []
    for idx in range(MAX_CAMERA_INDEX + 1):
        if probe_camera(idx):
            candidates.append(idx)

    if not candidates:
        return None

    # Prefer a non-zero camera when possible. On many Macs camera 0 is the
    # built-in FaceTime camera while Continuity Camera appears at a later index.
    if len(candidates) > 1:
        return candidates[-1]
    return candidates[0]


def choose_projector() -> Optional[int]:
    monitors = get_monitors()
    explicit = os.getenv("PROJECTOR_MONITOR_INDEX", "").strip()
    if explicit:
        idx = int(explicit)
        return idx if 0 <= idx < len(monitors) else None

    if len(monitors) < 2:
        return None

    # Prefer the first external display. The built-in Mac display is usually 0.
    return 1


def main() -> int:
    if platform.system() != "Darwin":
        print("WARNING: this launcher is optimized for macOS.")

    camera_index = choose_camera()
    if camera_index is None:
        print("No usable local camera found.")
        print("Connect/unlock the iPhone, enable Continuity Camera, then run camera_probe.py.")
        return 2

    projector_index = choose_projector()
    if projector_index is None:
        print("No external display detected.")
        print("Connect the MoGo 4 by HDMI and make sure macOS sees it as a second display.")
        return 3

    env = os.environ.copy()
    env["SENSOR_MODE"] = "local"
    env["CAMERA_INDEX"] = str(camera_index)
    env["PROJECTOR_MONITOR_INDEX"] = str(projector_index)
    env.setdefault("CAMERA_WIDTH", "1280")
    env.setdefault("CAMERA_HEIGHT", "720")
    env.setdefault("CAMERA_FPS", "30")

    print("Haunted Wall hardware selection")
    print(f"  Camera index:    {camera_index}")
    print(f"  Projector index: {projector_index}")
    print("  Sensor mode:     local")
    print("Launching haunted_wall.py ...")

    return subprocess.call([sys.executable, "haunted_wall.py"], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
