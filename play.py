"""
Starts a projector game.

    python3 play.py                      list the games
    python3 play.py spooky-slash         start one (anything after the name goes to the game)
    python3 play.py spooky-slash --camera 1 --projector 1

The camera and projector numbers are remembered in .env (see .env.example), so
they only need to be given once, or again when the hardware changes. The game
runs with the project's .venv Python when there is one.
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / ".env"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

# name: (module, description)
GAMES: Dict[str, Tuple[str, str]] = {
    "spooky-slash": ("games.spooky_slash",
                     "Fruit Ninja on the wall, sliced by up to five kids' hands (Lincoln Lynx Halloween)"),
    "midnight-slash": ("games.midnight_slash",
                       "Spookier Spooky Slash: 3-minute team rounds that speed up, witch-hat Lynx"),
    "pumpkin-slash": ("games.pumpkin_slash", "Two-team pumpkin slicing; the camera faces the players"),
    "pong": ("games.halloween_pong", "Halloween Pong; raise a hand on your half of the wall"),
    "haunted-wall": ("games.haunted_wall_cc0", "Tag the ghosts drifting across the wall"),
    "balloon-pop": ("games.balloon_pop", "The original balloon-popping game"),
}
# play.py option: setting it remembers in .env
HARDWARE_OPTIONS = {"--camera": "CAMERA_INDEX", "--projector": "PROJECTOR_MONITOR_INDEX"}


def read_settings() -> Dict[str, str]:
    if not SETTINGS.exists():
        return {}
    settings = {}
    for line in SETTINGS.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            settings[key.strip()] = value.strip()
    return settings


def remember(changes: Dict[str, str]) -> None:
    """Writes the changed settings into .env, keeping its other lines."""
    lines = SETTINGS.read_text().splitlines() if SETTINGS.exists() else []
    pending = dict(changes)
    for i, line in enumerate(lines):
        key = line.partition("=")[0].strip()
        if key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    lines += [f"{key}={value}" for key, value in pending.items()]
    SETTINGS.write_text("\n".join(lines) + "\n")


def split_hardware_options(args: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """Separates --camera N / --projector N from the options meant for the game."""
    changes, rest = {}, []
    args = list(args)
    while args:
        arg = args.pop(0)
        if arg in HARDWARE_OPTIONS and args:
            changes[HARDWARE_OPTIONS[arg]] = args.pop(0)
        else:
            rest.append(arg)
    return changes, rest


def list_games() -> None:
    print(__doc__.strip().split("\n\n")[1])
    print("\nGames:")
    for name, (_, description) in GAMES.items():
        print(f"  {name:<14} {description}")
    settings = read_settings()
    print(f"\nCamera {settings.get('CAMERA_INDEX', '0')}, projector {settings.get('PROJECTOR_MONITOR_INDEX', '1')} "
          "(change with --camera N --projector N; python3 -m tools.camera_probe lists cameras)")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in GAMES:
        if len(sys.argv) >= 2 and sys.argv[1] not in ("-h", "--help"):
            print(f"Unknown game: {sys.argv[1]}\n")
        list_games()
        return 0 if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help") else 2

    module = GAMES[sys.argv[1]][0]
    changes, game_args = split_hardware_options(sys.argv[2:])
    if changes:
        remember(changes)
    env = {**read_settings(), **os.environ, **changes}
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    try:
        return subprocess.call([python, "-m", module, *game_args], cwd=ROOT, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
