# Agent instructions: InteractiveProjector-CameraGame

## Mission
Make the existing **Haunted Wall** Halloween installation dependable on a MacBook with an XGIMI MoGo 4 connected by HDMI and an iPhone 14 serving as a camera when available. Preserve the existing balloon-pop game and existing Halloween art. Do not substitute a web app, mobile app, or a new engine without evidence that the current Python implementation cannot meet requirements.

## Existing source of truth
Read `README.md`, `HAUNTED_WALL.md`, `IPHONE_SENSOR.md`, `HALLOWEEN_ASSETS.md`, `requirements.txt`, `launch_haunted_wall_macos.py`, `haunted_wall.py`, `camera_probe.py`, `reolink_diagnostic.py`, and the calibration/display modules before changing behavior. Verify paths in the checked-out repository.

## System architecture
iPhone camera (preferred; USB/Continuity Camera) or built-in/USB camera (fallback) -> Mac OpenCV and person detector -> four-corner camera/projector mapping -> looping Haunted Wall game -> HDMI -> MoGo 4. A Reolink RTSP camera remains a secondary optional fallback. No Wi-Fi should be required for the core Mac-to-projector output.

## Definition of done (all required)
1. An explicit, repeatable macOS setup and launch procedure works from a fresh checkout, with dependency versions documented and clear actionable failures.
2. The launcher detects and selects a working camera, supports `CAMERA_INDEX` override, and clearly identifies a missing iPhone camera without silently claiming it is selected.
3. Projector/external monitor selection is deterministic, supports `PROJECTOR_MONITOR_INDEX`, and gives a useful error or safe local preview if HDMI is absent.
4. A first-run calibration clearly displays the projected quadrilateral and persists a validated four-corner transform. Recalibration is available when camera/projector moves.
5. Attract-mode visuals run without a detected person. Person interactions dismiss ghosts and give clear feedback; detections of projected artwork alone do not count.
6. Camera stream interruption, model load failure, absent assets, or display mismatch fail gracefully, recover where feasible, and never trap the user in an unclosable fullscreen window.
7. A hardware-free automated test suite covers coordinate mapping, hit testing/cooldowns, camera fallback selection, monitor selection, and asset fallback. Where dependencies are unavailable, provide deterministic mocks.
8. A concise operator guide documents required cables, macOS camera permissions, commands, troubleshooting, and known limitations. Include a hardware acceptance checklist for iPhone + Mac + MoGo 4 that cannot be claimed as passed in CI.
9. Existing balloon-pop functionality is not inadvertently broken. No secrets, RTSP credentials, proprietary models, or downloaded binary assets are committed.
10. Verification evidence: commands run, exit status, test results, and separate **verified in CI/local environment** from **requires physical hardware test**. Never call the project complete while required automated checks fail or hardware acceptance is unverified.

## Working method for coding agents (including OmO)
- Start with a read-only repository inventory and execute the existing tests, if dependencies permit.
- Write a small task plan and address the highest-risk blocker first (camera/display discovery, then calibration, then event mapping).
- Implement one bounded change at a time, add or update tests, and run the relevant test suite.
- Avoid broad unrelated refactors, unnecessary dependency upgrades, paid assets, or rewrites of otherwise functional code.
- Iterate diagnosis -> fix -> test until automated acceptance criteria pass or a real blocker is documented.
- Do not fabricate FPS/latency figures or claim connected hardware was tested without access to it.
- Work on a feature branch and submit a reviewable PR with summary, tests, failures, and exact hardware field-test steps.

## Hardware acceptance checklist (human-run, not CI)
- Mac detects MoGo 4 as external display over HDMI; full-screen graphics appear on projector.
- macOS exposes intended iPhone camera, or program visibly falls back to a selected Mac/USB camera.
- Four corners of projected area can be selected in the camera preview and saved.
- Adult and child walking into ghosts register hits; empty scene does not cause hits.
- Disconnect/reconnect camera produces a recoverable state; Escape exits.
- Re-run after restart and verify same configuration loads predictably.

## Initial task for an autonomous loop
Audit the current main branch against the definition of done, implement the missing pieces in priority order, and open a PR with reproducible tests. Put unresolved real-hardware checks under a separate heading; never mark them complete by inference.
