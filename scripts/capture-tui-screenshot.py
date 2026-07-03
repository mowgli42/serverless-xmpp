#!/usr/bin/env python3
"""Capture Textual TUI screenshot (SVG + PNG) against a running service."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from textual.widgets import Label, ListItem, Static

from xmpp_p2p_chat.text_ui.app import ChatApp


class ScreenshotApp(ChatApp):
    """Run headless, populate UI, save screenshot, exit."""

    def __init__(self, out_dir: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._out_dir = out_dir

    async def on_ready(self) -> None:
        await asyncio.sleep(2.5)
        self._load_contacts()
        for _ in range(30):
            await asyncio.sleep(0.5)
            if self.contacts and self.addressbook_status.get("content_hash"):
                break

        if self.contacts:
            contact = self.contacts[0]
            self.current_chat_id = contact["id"]
            self.current_contact_name = contact["name"]
            self.query_one("#chat-title", Label).update(f"Chat with {contact['name']}")
            try:
                await self._open_chat(contact["id"])
            except Exception:
                pass

        if not self.messages:
            self.messages = [
                {
                    "direction": "in",
                    "body": "Hey Alice — P2P is working!",
                    "timestamp": "2026-07-02T12:00:00+00:00",
                    "status": "delivered",
                },
                {
                    "direction": "out",
                    "body": "Hi Bob! Serverless mode confirmed.",
                    "timestamp": "2026-07-02T12:01:00+00:00",
                    "status": "delivered",
                },
                {
                    "direction": "in",
                    "body": "No central server needed",
                    "timestamp": "2026-07-02T12:02:00+00:00",
                    "status": "delivered",
                },
            ]
            await self._render_messages()

        if not self.query("#contact-list ListItem"):
            list_view = self.query_one("#contact-list")
            await list_view.clear()
            for contact in self.contacts or [
                {"id": "bob", "name": "Bob"},
                {"id": "carol", "name": "Carol"},
            ]:
                show = self.presence.get(contact["id"], {}).get("show", "offline")
                label = f"[{'green' if show == 'available' else 'dim'}]●[/] {contact['name']}"
                await list_view.append(ListItem(Label(label), id=f"contact-{contact['id']}"))

        self.query_one("#status-bar", Static).update("direct-p2p:connected · 2 contacts")
        await asyncio.sleep(0.5)

        svg_name = self.save_screenshot(filename="text-ui.svg", path=str(self._out_dir))
        svg_path = self._out_dir / svg_name
        png_path = self._out_dir / "text-ui.png"
        try:
            import cairosvg

            cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=1482)
        except ImportError:
            subprocess.run(
                ["convert", "-density", "300", "-background", "#0a0a0a", str(svg_path), str(png_path)],
                check=True,
            )
        print(f"TUI screenshot: {png_path}")
        await self.client.disconnect()
        self.exit()


def main() -> None:
    out_dir = Path(os.environ.get("SCREENSHOT_DIR", "docs/screenshots"))
    out_dir.mkdir(parents=True, exist_ok=True)
    api_url = os.environ.get("API_WS_URL", "ws://127.0.0.1:8765/rpc")
    ScreenshotApp(out_dir, api_url=api_url).run(headless=True, size=(120, 38))


if __name__ == "__main__":
    main()
