# Haunted Wall: Reolink + projector

This fork adds an experimental looping Halloween installation that uses a
Reolink RTSP camera as the sensor and an HDMI projector (tested conceptually for
XGIMI MoGo-class projectors) as the interactive canvas.

## What it does

1. Reads a Reolink RTSP stream through OpenCV.
2. Uses the existing four-corner calibration to map camera coordinates into
   projector coordinates.
3. Builds a motion/silhouette mask using OpenCV background subtraction.
4. Warps that mask into projector space.
5. Treats overlap between participant motion and a projected ghost as a hit.
6. Runs continuously with an attract state when nobody is moving.

This first version intentionally uses broad movement instead of fingertip
tracking. That is more tolerant of IP-camera latency, works with multiple
children, and avoids adding another ML dependency before the Reolink stream is
proven responsive enough.

## Hardware

- MacBook or other computer running the game
- Reolink camera on the same LAN
- XGIMI MoGo (or another projector) connected as an external HDMI display

The camera does **not** connect to the projector. The computer is the bridge:

`Reolink -> RTSP -> Mac/OpenCV -> Haunted Wall -> HDMI -> projector`

## Reolink setup

Enable RTSP for the camera in Reolink's settings if the model supports it. Start
with the lower-resolution/sub stream to minimize buffering:

`rtsp://USERNAME:PASSWORD@CAMERA_IP/Preview_01_sub`

If the camera is a battery model, RTSP availability can depend on the exact
model and whether it is routed through a Reolink Home Hub/NVR.

Do not put camera credentials in Git.

## Run

Install the existing requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Export configuration (or use a local launcher that loads `.env`):

```bash
export REOLINK_RTSP_URL='rtsp://USERNAME:PASSWORD@CAMERA_IP/Preview_01_sub'
export PROJECTOR_MONITOR_INDEX=1
export HAUNTED_WALL_DEBUG=1
python haunted_wall.py
```

On first launch the projector displays a bright calibration field. A camera
window opens on the computer. Click the four corners of the projected area in
the camera view and confirm the calibration. The repository stores that
homography in its existing `calibration.json` format.

After calibration, do not move the camera or projector. If either moves, press
`R` to recalibrate.

Controls:

- `ESC`: quit
- `R`: recalibrate

## Why the game uses motion first

The goal of the first hardware test is to answer one question: **is the Reolink
RTSP path responsive enough to feel interactive?**

Broad silhouette/motion collisions tolerate substantially more latency than
precision fingertip tracking. If this feels good, MediaPipe hand/body tracking
can be added as a second input provider without changing the projector or
calibration architecture.

If it feels delayed, use the Reolink sub stream, wire the camera with Ethernet
if possible, and minimize Wi-Fi hops. If latency remains poor, a USB camera can
replace the RTSP source without changing the game architecture.

## Tuning

Environment variables:

- `MOTION_THRESHOLD` — binary threshold after background subtraction.
- `MINIMUM_MOTION_PIXELS` — overlap required to trigger a ghost.
- `HIT_COOLDOWN_SECONDS` — minimum time between hits.
- `PROJECTOR_MONITOR_INDEX` — which detected display receives the game.
- `HAUNTED_WALL_DEBUG=1` — shows input/debug information.

The intended first field test is a 10–15 minute session with one and then
multiple children, watching for false triggers, perceived lag, dead zones, and
whether the camera can see the complete projected rectangle.
