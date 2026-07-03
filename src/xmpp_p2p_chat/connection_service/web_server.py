"""Threaded static HTTP server for the built web UI."""

from __future__ import annotations

import functools
import http.server
import logging
import socketserver
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def find_web_ui_dist() -> Path | None:
    """Locate web_ui/dist from a dev checkout or explicit install layout."""
    module_root = Path(__file__).resolve()
    for parent in module_root.parents:
        candidate = parent / "web_ui" / "dist"
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


class WebUIServer:
    def __init__(self, host: str, port: int, root: Path) -> None:
        self.host = host
        self.port = port
        self.root = root
        self._httpd: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        if not self.root.is_dir() or not (self.root / "index.html").is_file():
            logger.warning(
                "Web UI not found at %s — build with: cd web_ui && npm install && npm run build",
                self.root,
            )
            return False

        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler,
            directory=str(self.root),
        )
        self._httpd = socketserver.TCPServer((self.host, self.port), handler)
        self._httpd.allow_reuse_address = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        logger.info("Web UI available at http://%s:%d/ (API: ws://127.0.0.1:8765/rpc)", self.host, self.port)
        return True

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
