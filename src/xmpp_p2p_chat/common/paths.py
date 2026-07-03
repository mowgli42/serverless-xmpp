"""Resolve paths to bundled resources (dev tree or PyInstaller)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def package_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def bundled_addressbook_path() -> Path | None:
    env = os.environ.get("XMPP_P2P_BUNDLED_ADDRESSBOOK")
    if env:
        path = Path(env).expanduser()
        if path.exists():
            return path.resolve()

    candidates = [
        package_root() / "share" / "addressbook.json",
        Path(__file__).resolve().parents[3] / "examples" / "addressbook.sample.json",
    ]
    for path in candidates:
        if path.exists():
            return path.resolve()
    return None


def bundled_web_ui_path() -> Path | None:
    env = os.environ.get("XMPP_P2P_WEB_ROOT")
    if env:
        path = Path(env).expanduser()
        if path.is_dir():
            return path.resolve()
    candidates = [
        package_root() / "web_ui" / "dist",
        Path(__file__).resolve().parents[3] / "web_ui" / "dist",
    ]
    for path in candidates:
        if path.is_dir() and (path / "index.html").exists():
            return path.resolve()
    return None
