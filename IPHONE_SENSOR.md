# iPhone sensor setup (preferred)

For the Halloween Haunted Wall, a local camera is preferred over the Reolink RTSP path because it avoids network buffering and gives the vision stack a cleaner, lower-latency feed.

## Physical topology

`iPhone 14 -> USB cable -> Mac -> HDMI -> XGIMI MoGo 4`

The Mac runs OpenCV/YOLO, calibration, collision logic, and Pygame. The projector is only the display.

## Fast path

1. Connect the iPhone 14 to the Mac with a USB data cable.
2. Unlock the iPhone and trust the Mac if prompted.
3. Connect the MoGo 4 to the Mac over HDMI and confirm macOS shows a second display.
4. Run:

```bash
python launch_haunted_wall_macos.py
```

The launcher probes local OpenCV camera indices, chooses a usable local camera, verifies an external display, sets `SENSOR_MODE=local`, and launches Haunted Wall.

If the Mac's built-in camera is selected instead of the iPhone, run `python camera_probe.py`, note the iPhone index, then launch with:

```bash
CAMERA_INDEX=<IPHONE_INDEX> python launch_haunted_wall_macos.py
```

## macOS / Continuity Camera

Make sure Continuity Camera is enabled and that macOS allows camera access for Terminal/Python (or the terminal app you use). Continuity Camera availability is controlled by macOS/iOS, not this repository.

A wired iPhone may still need Apple's Continuity Camera prerequisites to be satisfied before macOS exposes it as a camera device. If OpenCV does not see it, first verify that another Mac camera app can select the iPhone, then rerun:

```bash
python camera_probe.py
```

## Manual setup

The script previews every local OpenCV camera index it can open. Note the index whose preview is the iPhone.

Then configure the game:

```bash
export SENSOR_MODE=local
export CAMERA_INDEX=<IPHONE_INDEX>
export CAMERA_WIDTH=1280
export CAMERA_HEIGHT=720
export CAMERA_FPS=30
export PROJECTOR_MONITOR_INDEX=1
python reolink_diagnostic.py
```

Despite its historical filename, `reolink_diagnostic.py` uses the generic `VideoSource` adapter and therefore also validates the selected iPhone/local camera.

If the diagnostic looks good, run:

```bash
python haunted_wall.py
```

Complete the four-corner calibration, then leave both the iPhone and projector fixed in position.

## Fallbacks

- Dedicated USB webcam: set `SENSOR_MODE=local` and choose its `CAMERA_INDEX`.
- Reolink E1: set `SENSOR_MODE=rtsp` and `REOLINK_RTSP_URL=...`.

The game/calibration code does not change between these sensors.
