# iPhone sensor setup (preferred)

For the Halloween Haunted Wall, a local camera is preferred over the Reolink RTSP path because it avoids network buffering and gives the vision stack a cleaner, lower-latency feed.

## Physical topology

`iPhone -> USB cable -> Mac -> HDMI -> MoGo projector`

The Mac runs OpenCV/YOLO, calibration, collision logic, and Pygame. The projector is only the display.

## macOS / Continuity Camera

1. Connect the iPhone to the Mac with its normal USB data/charging cable.
2. Unlock the iPhone and trust the Mac if prompted.
3. Make sure Continuity Camera is enabled in iPhone settings and that macOS allows camera access for Terminal/Python (or the terminal app you use).
4. Run:

```bash
python camera_probe.py
```

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

## Important caveat

Continuity Camera availability is controlled by macOS/iOS, not this repository. A wired iPhone can still require the Apple Continuity Camera prerequisites to be satisfied before macOS exposes it as a camera device. If OpenCV does not see it, first verify that another Mac camera app can select the iPhone, then rerun `camera_probe.py`.

## Fallbacks

- Dedicated USB webcam: set `SENSOR_MODE=local` and choose its `CAMERA_INDEX`.
- Reolink E1: set `SENSOR_MODE=rtsp` and `REOLINK_RTSP_URL=...`.

The game/calibration code does not change between these sensors.
