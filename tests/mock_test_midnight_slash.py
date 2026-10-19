"""
MOCK end-to-end test of Midnight Slash's browser game: NO camera, NO pose
model and NO projector. The real game server serves the real page to headless
Chrome, and this script sends it scripted blade sweeps the way the hand
tracker does. The page's game clock (Date.now) runs SPEEDUP times faster, so a
three-minute round takes about 18 seconds.

    python tests/mock_test_midnight_slash.py

It slices the start pumpkin, sweeps through one round, saves screenshots of
the menu, the round, a Witching Hour, the countdown, the results and the menu
coming back to MOCK_FOLDER, and fails on any JavaScript error.
"""
import base64
import itertools
import json
import random
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from games.midnight_slash import THEME_ROOT  # noqa: E402
from games.spooky_slash import WEB_ROOT  # noqa: E402
from modules.kiosk_browser import CHROME  # noqa: E402
from modules.web_game_server import WebGameServer  # noqa: E402

SPEEDUP = 10
STAGE = (853, 480)
DEVTOOLS_PORT = 9339
MOCK_FOLDER = Path(tempfile.gettempdir()) / "midnight_slash_mock"
START_PUMPKIN = (447.5 / STAGE[0], 328 / STAGE[1])  # as a fraction of the window, see scripts/sence.js
SWEEP_STEPS, STEP_SECONDS = 10, 0.03
FAST_CLOCK = f"""(function(){{
    var real = Date.now.bind( Date ), start = real();
    Date.now = function(){{ return start + ( real() - start ) * {SPEEDUP}; }};
}})();"""
VISIBLE_TEXT = """Array.from( document.querySelectorAll( "text" ) )
    .filter( function( t ){ return t.style.display != "none" && t.textContent.trim(); } )
    .map( function( t ){ return t.textContent; } ).join( " | " )"""
# real seconds after the round starts: screenshot name
SHOTS = {2.0: "round-early", 5.2: "witching-hour", 13.0: "round-late", 17.6: "countdown", 19.5: "results"}
ROUND_SECONDS = 20.0
MENU_BACK_SECONDS = 11.0


class DevTools:
    """Just enough of the Chrome DevTools Protocol: commands, plus the page's errors."""

    def __init__(self, ws_url: str):
        self.socket = connect(ws_url, max_size=None)
        self.ids = itertools.count(1)
        self.errors = []

    def call(self, method: str, **params) -> dict:
        call_id = next(self.ids)
        self.socket.send(json.dumps({"id": call_id, "method": method, "params": params}))
        while True:
            reply = json.loads(self.socket.recv())
            if reply.get("id") == call_id:
                return reply.get("result", {})
            self._note(reply)

    def _note(self, event: dict) -> None:
        if event.get("method") == "Runtime.exceptionThrown":
            self.errors.append(event["params"]["exceptionDetails"].get("exception", {}).get("description"))
        elif event.get("method") == "Runtime.consoleAPICalled" and event["params"]["type"] == "error":
            self.errors.append(" ".join(str(a.get("value")) for a in event["params"]["args"]))

    def text(self) -> str:
        return self.call("Runtime.evaluate", expression=VISIBLE_TEXT)["result"].get("value", "")

    def screenshot(self, name: str) -> None:
        data = self.call("Page.captureScreenshot", format="png")["data"]
        path = MOCK_FOLDER / f"{name}.png"
        path.write_bytes(base64.b64decode(data))
        print(f"  {path.name}: {self.text()}")


def page_socket_url() -> str:
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{DEVTOOLS_PORT}/json") as response:
                pages = [t for t in json.load(response) if t["type"] == "page"]
            if pages:
                return pages[0]["webSocketDebuggerUrl"]
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError("headless Chrome did not start")


def sweep(server: WebGameServer, start, end, blade_id: int = 0) -> None:
    """One MOCK hand swipe from start to end (window fractions)."""
    for i in range(SWEEP_STEPS + 1):
        f = i / SWEEP_STEPS
        x, y = start[0] + (end[0] - start[0]) * f, start[1] + (end[1] - start[1]) * f
        server.broadcast({"type": "blades", "blades": [{"id": blade_id, "x": x, "y": y}]})
        time.sleep(STEP_SECONDS)
    server.broadcast({"type": "blades", "blades": []})


def main() -> int:
    MOCK_FOLDER.mkdir(exist_ok=True)
    print("MOCK test: scripted blades, headless Chrome, game clock sped up "
          f"{SPEEDUP}x; no camera or projector")
    server = WebGameServer((THEME_ROOT, WEB_ROOT), lambda message: None)
    server.start()
    chrome = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={DEVTOOLS_PORT}",
                               f"--window-size={STAGE[0]},{STAGE[1]}", "--autoplay-policy=no-user-gesture-required",
                               "--mute-audio", f"--user-data-dir={tempfile.mkdtemp()}", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tools = DevTools(page_socket_url())
        for domain in ("Page", "Runtime"):
            tools.call(f"{domain}.enable")
        tools.call("Page.addScriptToEvaluateOnNewDocument", source=FAST_CLOCK)
        tools.call("Page.navigate", url=server.url)
        if not server.wait_for_page(10):
            print("FAIL: the page never connected to the game server")
            return 1
        time.sleep(6.5)  # boot messages, then the menu slides in
        tools.screenshot("menu")

        sweep(server, (START_PUMPKIN[0] - 0.12, START_PUMPKIN[1]), (START_PUMPKIN[0] + 0.12, START_PUMPKIN[1]))
        time.sleep(2.5)  # the menu leaves, the round starts
        rng, started, shots = random.Random(7), time.time(), dict(SHOTS)
        while time.time() - started < ROUND_SECONDS:
            y0, y1 = rng.uniform(0.15, 0.85), rng.uniform(0.15, 0.85)
            sweep(server, (0.05, y0), (0.95, y1), rng.randrange(5))
            for at in [t for t in shots if time.time() - started >= t]:
                tools.screenshot(shots.pop(at))
        time.sleep(MENU_BACK_SECONDS)
        tools.screenshot("menu-again")

        tools.call("Runtime.evaluate", expression="0")  # collect any last events
        if tools.errors:
            print("FAIL: JavaScript errors:\n  " + "\n  ".join(map(str, tools.errors)))
            return 1
        print(f"PASS (MOCK). Screenshots in {MOCK_FOLDER}")
        return 0
    finally:
        chrome.terminate()
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
