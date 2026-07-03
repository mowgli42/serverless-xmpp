"""Connection service entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from xmpp_p2p_chat.common.config import load_config, save_default_config
from xmpp_p2p_chat.connection_service.service import ConnectionService


def main() -> None:
    parser = argparse.ArgumentParser(description="XMPP P2P Chat Connection Service")
    parser.add_argument("--config", type=Path, help="Path to config.toml")
    parser.add_argument("--init-config", action="store_true", help="Write default config and exit")
    args = parser.parse_args()

    if args.init_config:
        path = save_default_config(args.config)
        print(f"Default config written to {path}")
        sys.exit(0)

    config = load_config(args.config)
    service = ConnectionService(config)
    try:
        asyncio.run(service.run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
