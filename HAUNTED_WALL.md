# Haunted Wall: Reolink + projector

This fork adds an experimental looping Halloween installation that uses a
Reolink RTSP camera as the sensor and an HDMI projector (for example an XGIMI
MoGo) as the interactive canvas.

## What it does

1. Reads a Reolink RTSP stream through OpenCV.
2. Uses the existing four-corner calibration to map camera coordinates into
   projector coordinates.
3. Runs the existing Ultralytics/YOLO stack with the stock person class.
4. Maps each detected person's camera bounding polygon into projector space.
5. Treats overlap between a person and a projected ghost as a hit.
6. Runs continuously with an attract state when nobody is detected.

The first version intentionally uses broad person/body interaction rather than
fingertip tracking. That is more tolerant of IP-camera latency, works with more
than one child, and—critically—does not mistake the projector's own moving
artwork for participant motion.

## Hardware

- MacBook or other computer running the game
- Reolink camera on the same LAN
- XGIMI MoGo (or another projector) connected as an external HDMI display

The camera does **not** connect to the projector. The computer is the bridge:

`Reolink -> RTSP -> Mac/OpenCV/YOLO -> Haunted Wall -> HDMI -> projector`

## Reolink setup

Enable RTSP for the camera in Reolink's settings if the model supports it. Start
with the lower-resolution/sub stream to minimize buffering:

`rtsp://USERNAME:PASSWORD@CAMERA_IP/Preview_01_sub`

If the camera is a battery model, RTSP availability can depend on the exact
model and whether it is routed through a Reolink Home Hub/NVR.

Do not put camera credentials in Git.

## First test: camera + projector diagnostic

Install the existing requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then export the camera URL and run the diagnostic before starting the game:

```bash
export REOLINK_RTSP_URL='rtsp://USERNAME:PASSWORD@CAMERA_IP/Preview_01_sub'
export PROJECTOR_MONITOR_INDEX=1
python reolink_diagnostic.py
```

The diagnostic previews the camera, reports delivered frame rate, and lists the
displays detected by `screeninfo`. If the stream is slow, try the Reolink sub
stream and Ethernet before changing game code.

## Run Haunted Wall

```bash
export REOLINK_RTSP_URL='rtsp://USERNAME:PASSWORD@CAMERA_IP/Preview_01_sub'
export PROJECTOR_MONITOR_INDEX=1
export HAUNTED_WALL_DEBUG=1
python haunted_wall.py
```

`yolov8n.pt` is the default person detector. Ultralytics may download it the
first time it is used if it is not already cached locally. You can override the
model with `HAUNTED_WALL_MODEL`.

On first launch the projector displays a bright calibration field. A camera
window opens on the computer. Click the four corners of the projected area in
the camera view and confirm the calibration. Haunted Wall keeps its own
`haunted_wall_calibration.json`, separate from the original balloon game's
calibration.

After calibration, do not move the camera or projector. If either moves, press
`R` to recalibrate.

Controls:

- `ESC`: quit
- `R`: recalibrate

## Why person detection instead of raw motion

A naive motion detector sees the animated ghosts, fog and pumpkins projected
onto the wall as movement. That can make the game trigger itself. A person
classifier gives the first hardware version a much cleaner sensor signal: the
projection can animate continuously while interactions are driven by detected
people.

This is intentionally coarse. A ghost disappears when its projected position
overlaps a detected participant region. If Reolink latency proves acceptable,
a later input provider can add MediaPipe hands/pose for swatting, pointing and
more precise gestures without changing the calibration or projector layers.

## Tuning

Environment variables:

- `HAUNTED_WALL_MODEL` — Ultralytics model; default `yolov8n.pt`.
- `PERSON_CONFIDENCE` — person detection threshold; default `0.35`.
- `DETECT_EVERY_N_FRAMES` — reduce/increase CPU inference frequency; default `2`.
- `HIT_COOLDOWN_SECONDS` — minimum time between ghost hits; default `0.35`.
- `PROJECTOR_MONITOR_INDEX` — display receiving the game; usually `1` on a laptop.
- `HAUNTED_WALL_DEBUG=1` — draws detected participant polygons and sensor status.

The intended first field test is one adult, then one child, then multiple
children. Watch for perceived lag, missed detections, false person detections,
dead zones, and whether the camera can see the complete projected rectangle.
