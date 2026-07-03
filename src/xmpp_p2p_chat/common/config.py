"""Configuration loading for xmpp-p2p-chat."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def default_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return _expand(f"{xdg}/xmpp-p2p-chat/config.toml")
    return _expand("~/.config/xmpp-p2p-chat/config.toml")


def default_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return _expand(f"{xdg}/xmpp-p2p-chat")
    return _expand("~/.local/share/xmpp-p2p-chat")


@dataclass
class XMPPConfig:
    jid: str = ""
    password: str = ""
    server: str = ""
    port: int = 5222


@dataclass
class AppConfig:
    data_directory: Path = field(default_factory=default_data_dir)
    default_transport: str = "xmpp-server"
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_token: str = ""
    log_level: str = "INFO"
    log_file: str = ""
    enforce_tls: bool = True
    allow_self_signed_direct: bool = False
    xmpp: XMPPConfig = field(default_factory=XMPPConfig)

    @property
    def addressbook_path(self) -> Path:
        return self.data_directory / "addressbook.json"

    @property
    def addressbooks_dir(self) -> Path:
        return self.data_directory / "addressbooks.d"

    @property
    def db_path(self) -> Path:
        return self.data_directory / "messages.db"

    @property
    def api_ws_url(self) -> str:
        return f"ws://{self.api_host}:{self.api_port}/rpc"


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or default_config_path()
    cfg = AppConfig()

    if config_path.exists():
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)

        if data_dir := data.get("data", {}).get("directory"):
            cfg.data_directory = _expand(data_dir)

        conn = data.get("connection", {})
        cfg.default_transport = conn.get("default_transport", cfg.default_transport)
        cfg.api_host = conn.get("api_host", cfg.api_host)
        cfg.api_port = int(conn.get("api_port", cfg.api_port))
        cfg.api_token = conn.get("api_token", cfg.api_token)

        logging_cfg = data.get("logging", {})
        cfg.log_level = logging_cfg.get("level", cfg.log_level)
        cfg.log_file = logging_cfg.get("file", cfg.log_file)

        security = data.get("security", {})
        cfg.enforce_tls = bool(security.get("enforce_tls", cfg.enforce_tls))
        cfg.allow_self_signed_direct = bool(
            security.get("allow_self_signed_direct", cfg.allow_self_signed_direct)
        )

        xmpp = data.get("xmpp", {})
        cfg.xmpp = XMPPConfig(
            jid=xmpp.get("jid", cfg.xmpp.jid),
            password=xmpp.get("password", cfg.xmpp.password),
            server=xmpp.get("server", cfg.xmpp.server),
            port=int(xmpp.get("port", cfg.xmpp.port)),
        )

    cfg.data_directory.mkdir(parents=True, exist_ok=True)
    cfg.addressbooks_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def save_default_config(path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "data": {"directory": str(default_data_dir())},
        "connection": {
            "default_transport": "xmpp-server",
            "api_host": "127.0.0.1",
            "api_port": 8765,
            "api_token": "",
        },
        "logging": {"level": "INFO", "file": ""},
        "security": {"enforce_tls": True, "allow_self_signed_direct": False},
        "xmpp": {"jid": "", "password": "", "server": "", "port": 5222},
    }
    with config_path.open("wb") as fh:
        tomli_w.dump(data, fh)
    return config_path
