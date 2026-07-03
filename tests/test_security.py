"""Security-related configuration and behavior tests."""

from xmpp_p2p_chat.common.config import AppConfig, load_config


def test_default_api_host_is_localhost():
    cfg = AppConfig()
    assert cfg.api_host == "127.0.0.1"


def test_config_rejects_non_localhost_in_sample(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[connection]
api_host = "127.0.0.1"
api_port = 8765
""",
        encoding="utf-8",
    )
    cfg = load_config(config_file)
    assert cfg.api_host == "127.0.0.1"
