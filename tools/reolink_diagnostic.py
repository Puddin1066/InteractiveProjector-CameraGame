"""Quick hardware diagnostic for the Haunted Wall installation."""

import os
import time

import cv2
from screeninfo import get_monitors

from modules import config
from modules.video_source import VideoSource


def main() -> int:
    monitors = get_monitors()
    print(f"Detected {len(monitors)} display(s):")
    for i, monitor in enumerate(monitors):
        print(
            f"  [{i}] {monitor.width}x{monitor.height} "
            f"at ({monitor.x},{monitor.y})"
        )

    source = VideoSource.from_environment(
        fallback_camera_index=config.CAMERA_INDEX,
        width=config.CAMERA_WIDTH,
        height=config.CAMERA_HEIGHT,
        fps=config.CAMERA_FPS,
    )
    if not source.isOpened():
        print("ERROR: camera stream could not be opened.")
        return 2

    print(f"Camera source: {source.describe()}")
    print("Sampling frames for 8 seconds. Press Q in the preview window to stop early.")

    started = time.time()
    frames = 0
    failures = 0
    first_shape = None

    while time.time() - started < 8.0:
        ok, frame = source.read()
        if not ok or frame is None:
            failures += 1
            time.sleep(0.01)
            continue

        frames += 1
        first_shape = first_shape or frame.shape
        cv2.imshow("Reolink diagnostic - press Q to stop", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    elapsed = max(time.time() - started, 0.001)
    fps = frames / elapsed
    source.release()
    cv2.destroyAllWindows()

    print("\nDiagnostic summary")
    print(f"  Frames received: {frames}")
    print(f"  Read failures:   {failures}")
    print(f"  Capture rate:    {fps:.1f} fps")
    if first_shape:
        print(f"  Frame size:      {first_shape[1]}x{first_shape[0]}")

    projector_index = int(os.getenv("PROJECTOR_MONITOR_INDEX", "1"))
    projector_ok = projector_index < len(monitors)
    print(
        f"  Projector index: {projector_index} "
        f"({'available' if projector_ok else 'NOT FOUND'})"
    )

    if frames == 0:
        return 3
    if fps < 10:
        print("WARNING: capture rate is low for interactive play; try the Reolink sub stream.")
    if not projector_ok:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
