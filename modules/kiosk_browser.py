"""Opens a web page full screen on the projector in its own Chrome window."""
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = Path(tempfile.gettempdir()) / "projector-game-chrome"  # separate from the user's own Chrome
DEVTOOLS_PORT_FILE = PROFILE_DIR / "DevToolsActivePort"
LEFTOVER_EXIT_SECONDS = 1.0


def open_kiosk(url: str, monitor) -> subprocess.Popen:
    """`monitor` is a screeninfo monitor; terminate the returned process to close the window.
    DevTools listens on a free local port, see `devtools_port`."""
    if not Path(CHROME).exists():
        raise FileNotFoundError(f"Google Chrome is needed to show the game: {CHROME}")
    _close_leftover_window()
    DEVTOOLS_PORT_FILE.unlink(missing_ok=True)
    return subprocess.Popen([
        CHROME,
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--autoplay-policy=no-user-gesture-required",
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=0",
        f"--window-position={monitor.x},{monitor.y}",
        f"--window-size={monitor.width},{monitor.height}",
        "--kiosk",
        f"--app={url}",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _close_leftover_window() -> None:
    """A game window left open by a crash would take over the new launch, which then exits at once."""
    if subprocess.run(["pkill", "-f", str(PROFILE_DIR)]).returncode == 0:
        time.sleep(LEFTOVER_EXIT_SECONDS)


def devtools_port() -> Optional[int]:
    """The kiosk Chrome's DevTools port, once it has started."""
    try:
        return int(DEVTOOLS_PORT_FILE.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None
