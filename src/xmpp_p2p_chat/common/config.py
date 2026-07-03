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
    password_ref: str = ""
    server: str = ""
    port: int = 5222


@dataclass
class P2PConfig:
    local_jid: str = ""
    listen_host: str = "0.0.0.0"
    listen_port: int = 5223
    mdns_enabled: bool = True
    mdns_service_type: str = "_xmpp-p2p._tcp.local."


@dataclass
class UIConfig:
    serve_web: bool = True
    web_host: str = "127.0.0.1"
    web_port: int = 8767
    web_root: str = ""


@dataclass
class AppConfig:
    data_directory: Path = field(default_factory=default_data_dir)
    bundled_addressbook: str = ""
    import_bundled_if_empty: bool = True
    default_transport: str = "direct-p2p"
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_token: str = ""
    log_level: str = "INFO"
    log_file: str = ""
    enforce_tls: bool = True
    allow_self_signed_direct: bool = True
    xmpp: XMPPConfig = field(default_factory=XMPPConfig)
    p2p: P2PConfig = field(default_factory=P2PConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    @property
    def web_ui_url(self) -> str:
        return f"http://{self.ui.web_host}:{self.ui.web_port}/"

    @property
    def p2p_cert_dir(self) -> Path:
        return self.data_directory / "p2p"

    @property
    def effective_local_jid(self) -> str:
        return self.p2p.local_jid or self.xmpp.jid or "user@p2p.local"

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
        data_section = data.get("data", {})
        cfg.bundled_addressbook = data_section.get("bundled_addressbook", cfg.bundled_addressbook)
        cfg.import_bundled_if_empty = bool(
            data_section.get("import_bundled_if_empty", cfg.import_bundled_if_empty)
        )

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
            password_ref=xmpp.get("password_ref", cfg.xmpp.password_ref),
            server=xmpp.get("server", cfg.xmpp.server),
            port=int(xmpp.get("port", cfg.xmpp.port)),
        )

        p2p = data.get("p2p", {})
        cfg.p2p = P2PConfig(
            local_jid=p2p.get("local_jid", cfg.p2p.local_jid),
            listen_host=p2p.get("listen_host", cfg.p2p.listen_host),
            listen_port=int(p2p.get("listen_port", cfg.p2p.listen_port)),
            mdns_enabled=bool(p2p.get("mdns_enabled", cfg.p2p.mdns_enabled)),
            mdns_service_type=p2p.get("mdns_service_type", cfg.p2p.mdns_service_type),
        )

        ui = data.get("ui", {})
        cfg.ui = UIConfig(
            serve_web=bool(ui.get("serve_web", cfg.ui.serve_web)),
            web_host=ui.get("web_host", cfg.ui.web_host),
            web_port=int(ui.get("web_port", cfg.ui.web_port)),
            web_root=ui.get("web_root", cfg.ui.web_root),
        )

    cfg.data_directory.mkdir(parents=True, exist_ok=True)
    cfg.addressbooks_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def save_default_config(path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "data": {
            "directory": str(default_data_dir()),
            "bundled_addressbook": "",
            "import_bundled_if_empty": True,
        },
        "connection": {
            "default_transport": "direct-p2p",
            "api_host": "127.0.0.1",
            "api_port": 8765,
            "api_token": "",
        },
        "logging": {"level": "INFO", "file": ""},
        "security": {"enforce_tls": True, "allow_self_signed_direct": True},
        "xmpp": {"jid": "", "password": "", "server": "", "port": 5222},
        "p2p": {
            "local_jid": "",
            "listen_host": "0.0.0.0",
            "listen_port": 5223,
            "mdns_enabled": True,
            "mdns_service_type": "_xmpp-p2p._tcp.local.",
        },
        "ui": {"serve_web": True, "web_host": "127.0.0.1", "web_port": 8767, "web_root": ""},
    }
    with config_path.open("wb") as fh:
        tomli_w.dump(data, fh)
    return config_path
