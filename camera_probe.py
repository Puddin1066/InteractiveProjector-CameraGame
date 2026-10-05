"""Probe local camera indices so macOS users can identify iPhone/USB cameras.

OpenCV does not reliably expose friendly AVFoundation device names across builds,
so this utility tries a short range of local indices and lets the user see which
source is the desired camera.
"""

import time

import cv2


MAX_INDEX = 8
PREVIEW_SECONDS = 2.5


def main() -> int:
    found = []
    print("Probing local camera indices 0 through", MAX_INDEX)
    print("If macOS asks for Camera permission, allow it and rerun this script.\n")

    for index in range(MAX_INDEX + 1):
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            continue

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            continue

        found.append(index)
        h, w = frame.shape[:2]
        print(f"Camera index {index}: opened at approximately {w}x{h}")

        started = time.time()
        window = f"Camera index {index} - Q skips"
        while time.time() - started < PREVIEW_SECONDS:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            cv2.putText(
                frame,
                f"CAMERA_INDEX={index}",
                (24, 44),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window, frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

        cap.release()
        cv2.destroyWindow(window)

    cv2.destroyAllWindows()

    if not found:
        print("No local cameras opened through OpenCV.")
        print("Check macOS Camera privacy permissions and Continuity Camera setup.")
        return 2

    print("\nAvailable OpenCV camera indices:", ", ".join(map(str, found)))
    print("Choose the index whose preview showed the iPhone, then run:")
    print("  export SENSOR_MODE=local")
    print("  export CAMERA_INDEX=<that number>")
    print("  python haunted_wall.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
