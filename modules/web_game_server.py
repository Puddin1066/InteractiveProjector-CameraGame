"""
Serves a browser game to the projector and exchanges JSON messages with it
(plus binary messages, such as images, to the page).

The game's JavaScript lives as one file per module under <root>/scripts and is
bundled into scripts/all.js on every request, so edits show up on reload.
Messages go both ways over a WebSocket on its own port.

A game can be served from several roots, e.g. a theme folder over a base game:
each file, script modules included, comes from the first root that has it.
"""
import json
import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, Sequence, Set

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import ServerConnection, serve

BUNDLE_PATH = "/scripts/all.js"
ENTRY_MODULE = "scripts/main"

# The tiny module loader the game was originally compiled with (jsbuild)
_LOADER = """void function(global){
\tvar mapping = {}, cache = {};
\tglobal.startModule = function(m){ require(m).start(); };
\tglobal.define = function(id, func){ mapping[id] = func; };
\tglobal.require = function(id){
\t\tif(!/\\.js$/.test(id)) id += '.js';
\t\treturn cache[id] || (cache[id] = mapping[id]({}));
\t};
}(this);
"""


def bundle_scripts(roots: Sequence[Path]) -> str:
    """Every scripts/**/*.js module wrapped for the loader, then the entry module started."""
    modules: Dict[str, Path] = {}
    for root in reversed(roots):  # earlier roots override later ones
        for path in (root / "scripts").rglob("*.js"):
            modules[path.relative_to(root).as_posix()] = path
    modules.pop(BUNDLE_PATH.lstrip("/"), None)
    parts = [_LOADER]
    for module_id, path in sorted(modules.items()):
        parts.append(f'define("{module_id}", function(exports){{\n{path.read_text(encoding="utf-8")}\n'
                     f'return exports;\n}});\n')
    parts.append(f'startModule("{ENTRY_MODULE}");\n')
    return "\n".join(parts)


class _GameRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, roots: Sequence[Path], **kwargs):
        self.roots = roots
        super().__init__(*args, directory=str(roots[0]), **kwargs)

    def translate_path(self, path):
        for root in self.roots:
            self.directory = str(root)
            candidate = super().translate_path(path)
            if os.path.isfile(candidate) or os.path.isfile(os.path.join(candidate, "index.html")):
                return candidate
        self.directory = str(self.roots[0])
        return super().translate_path(path)

    def do_GET(self):
        if self.path.split("?")[0] != BUNDLE_PATH:
            return super().do_GET()
        body = bundle_scripts(self.roots).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        pass


class WebGameServer:
    def __init__(self, roots: Sequence[Path], on_message: Callable[[dict], None],
                 host: str = "127.0.0.1", http_port: int = 0, ws_port: int = 0):
        """`roots` in lookup order; port 0 picks a free port."""
        self.roots = list(roots)
        self.on_message = on_message
        self.host = host
        self._clients: Set[ServerConnection] = set()
        self._clients_lock = threading.Lock()
        self._connected = threading.Event()
        self._http = ThreadingHTTPServer((host, http_port), partial(_GameRequestHandler, roots=self.roots))
        self._ws = serve(self._serve_client, host, ws_port)
        self.http_port = self._http.server_address[1]
        self.ws_port = self._ws.socket.getsockname()[1]

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.http_port}/?ws={self.ws_port}"

    def start(self) -> None:
        threading.Thread(target=self._http.serve_forever, name="GameHTTP", daemon=True).start()
        threading.Thread(target=self._ws.serve_forever, name="GameWebSocket", daemon=True).start()
        print(f"Game served at {self.url}")

    def wait_for_page(self, timeout: float) -> bool:
        """True once a game page has connected."""
        return self._connected.wait(timeout)

    def broadcast(self, message: dict) -> None:
        self._send(json.dumps(message, separators=(",", ":")))

    def broadcast_binary(self, data: bytes) -> None:
        """Arrives in the page as a Blob, e.g. an image."""
        self._send(data)

    def _send(self, data) -> None:
        with self._clients_lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.send(data)
            except ConnectionClosed:
                pass

    def stop(self) -> None:
        self._ws.shutdown()
        self._http.shutdown()

    def _serve_client(self, connection: ServerConnection) -> None:
        with self._clients_lock:
            self._clients.add(connection)
        self._connected.set()
        try:
            for raw in connection:
                try:
                    self.on_message(json.loads(raw))
                except (ValueError, KeyError, TypeError) as bad_message:
                    print(f"Ignoring bad message from the game: {bad_message}")
        except ConnectionClosed:
            pass
        finally:
            with self._clients_lock:
                self._clients.discard(connection)
