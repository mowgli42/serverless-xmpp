"""Text UI entrypoint."""

from __future__ import annotations

import argparse

from xmpp_p2p_chat.common.config import load_config
from xmpp_p2p_chat.text_ui.app import ChatApp


def main() -> None:
    parser = argparse.ArgumentParser(description="XMPP P2P Chat Text UI")
    parser.add_argument("--url", help="WebSocket API URL")
    args = parser.parse_args()
    config = load_config()
    app = ChatApp(api_url=args.url or config.api_ws_url, token=config.api_token)
    app.run()


if __name__ == "__main__":
    main()
