"""
Streams what a Chrome page is showing, through the Chrome DevTools screencast.

Shadow detection needs to know how bright the projector made each part of the
wall; for a browser game the page's own frames are exactly that.
"""
import base64
import json
import threading
import time
import urllib.request
from typing import Callable, Optional, Tuple

import cv2
import numpy as np
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

FrameHandler = Callable[[np.ndarray], None]  # grayscale luminance 0..1 at the requested size
CONNECT_TIMEOUT = 20.0


class BrowserScreencast(threading.Thread):
    def __init__(self, devtools_port: Callable[[], Optional[int]], size: Tuple[int, int], on_frame: FrameHandler):
        """`devtools_port` returns Chrome's DevTools port once it is known."""
        super().__init__(name="BrowserScreencast", daemon=True)
        self.devtools_port = devtools_port
        self.size = size
        self.on_frame = on_frame
        self.running = True

    def run(self) -> None:
        url = self._page_socket_url()
        if url is None:
            print("Could not watch the game page; shadows may be found poorly.")
            return
        try:
            with connect(url, max_size=None) as devtools:
                devtools.send(json.dumps({"id": 1, "method": "Page.startScreencast", "params": {
                    "format": "jpeg", "quality": 70, "maxWidth": self.size[0], "maxHeight": self.size[1]}}))
                while self.running:
                    try:
                        event = json.loads(devtools.recv(timeout=0.5))
                    except TimeoutError:
                        continue
                    if event.get("method") != "Page.screencastFrame":
                        continue
                    params = event["params"]
                    devtools.send(json.dumps({"id": 2, "method": "Page.screencastFrameAck",
                                              "params": {"sessionId": params["sessionId"]}}))
                    self.on_frame(self._luminance(params["data"]))
        except (ConnectionClosed, OSError) as closed:
            if self.running:
                print(f"Stopped watching the game page: {closed}")

    def stop(self) -> None:
        self.running = False

    def _page_socket_url(self) -> Optional[str]:
        deadline = time.monotonic() + CONNECT_TIMEOUT
        while self.running and time.monotonic() < deadline:
            port = self.devtools_port()
            if port:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
                        pages = [t for t in json.load(response) if t.get("type") == "page"]
                    if pages:
                        return pages[0]["webSocketDebuggerUrl"]
                except OSError:
                    pass
            time.sleep(0.25)
        return None

    def _luminance(self, jpeg_base64: str) -> np.ndarray:
        image = cv2.imdecode(np.frombuffer(base64.b64decode(jpeg_base64), np.uint8), cv2.IMREAD_GRAYSCALE)
        if image.shape[1::-1] != self.size:
            image = cv2.resize(image, self.size, interpolation=cv2.INTER_AREA)
        return image.astype(np.float32) / 255.0
