# Contributing

Thanks for helping. This is a small hobby project of camera-and-projector
games for kids, so changes that keep the games easy to set up and fun at a
party are the most welcome.

## Local setup

```bash
git clone https://github.com/Puddin1066/InteractiveProjector-CameraGame.git
cd InteractiveProjector-CameraGame
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python3 play.py   # lists the games
```

The browser games (Spooky Slash, Midnight Slash) also need Google Chrome.

## Checks

Run these before opening a pull request:

```bash
python3 -m compileall -q play.py games modules tools tests datapreprocessing
python3 tests/smoke_test_haunted_wall.py
.venv/bin/python tests/test_threading.py
.venv/bin/python tests/mock_test_midnight_slash.py   # mock: scripted swipes, headless Chrome
```

CI runs the first two on every pull request. If your change touches what the
camera sees, also try it with a real camera and projector and say so in the
pull request.

## Workflow

- Open an issue first for anything large, such as a new game.
- Keep each pull request focused on one change.
- New games go in `games/` and get an entry in `play.py`; shared code goes in
  `modules/`, one-off scripts in `tools/`.
- A themed version of a browser game goes in its own `web/<theme>` folder
  that holds only what differs, the way `web/midnight_slash` sits over
  `web/spooky_slash`.
- Update the README when commands or behavior change.

## Art, sounds and models

- Only add media you may share: your own work, CC0, or a license that allows
  it. Credit it in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- Do not commit model weights (`models/` is git-ignored; they download on
  first run) or camera captures of people.

## Security

Do not report vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).
