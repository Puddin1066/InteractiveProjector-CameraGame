# Security Policy

## Supported versions

This project has no releases; only the latest `main` is supported.

## Reporting a vulnerability

Do not report security problems in public issues.

Report them privately through GitHub: open the repository's **Security** tab
and choose **Report a vulnerability**
(<https://github.com/Puddin1066/InteractiveProjector-CameraGame/security/advisories/new>).
Please include:

- the affected commit
- what an attacker could do
- steps to reproduce
- a proof of concept, if it is safe to share
- a suggested fix, if you have one

This is a volunteer hobby project: expect an acknowledgement within a week.

## What to keep in mind

- The games run a local web server and WebSocket bound to `127.0.0.1` for the
  projector's browser window. They are not meant to be exposed to a network.
- Camera credentials (for example a Reolink RTSP URL) belong in your local,
  git-ignored `.env`. Never commit them; `.env.example` holds placeholders only.
- The camera sees children. Debug frames are written only to the system's
  temporary folder; do not commit or share camera captures.
