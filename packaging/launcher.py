#!/usr/bin/env python3
"""Unified launcher for packaged serverless-xmpp builds."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Serverless XMPP Chat")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["service", "tui", "both"],
        default="both",
        help="Run connection service, TUI, or both (default: both)",
    )
    args = parser.parse_args()

    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
        os.environ.setdefault("XMPP_P2P_BUNDLED_ADDRESSBOOK", os.path.join(base, "xmpp_p2p_chat", "share", "addressbook.json"))
        os.environ.setdefault("XMPP_P2P_WEB_ROOT", os.path.join(base, "web_ui", "dist"))

    if args.mode == "service":
        from xmpp_p2p_chat.connection_service.__main__ import main as service_main

        service_main()
    elif args.mode == "tui":
        from xmpp_p2p_chat.text_ui.__main__ import main as tui_main

        tui_main()
    else:
        service_proc = subprocess.Popen([sys.executable, "-m", "xmpp_p2p_chat.connection_service"])
        try:
            from xmpp_p2p_chat.text_ui.__main__ import main as tui_main

            tui_main()
        finally:
            service_proc.terminate()
            service_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
