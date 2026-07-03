#!/usr/bin/env python3
"""Capture Web UI screenshot using Playwright (no-sandbox for CI)."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8767/"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/screenshots/web-ui.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        # Wait for contacts to load from WebSocket API
        page.wait_for_selector("text=Bob", timeout=20000)
        page.wait_for_selector("text=You:", timeout=20000)
        page.wait_for_selector("text=Book", timeout=20000)
        page.locator("button", has_text="Bob").first.click()
        page.wait_for_selector("text=Hey Alice", timeout=10000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(out), full_page=False)
        browser.close()
    print(f"Web UI screenshot: {out}")


if __name__ == "__main__":
    main()
