"""Structured logging tests (SigNoz JSON + EBK status lines)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from xmpp_p2p_chat.common.config import AppConfig
from xmpp_p2p_chat.common.structured_logging import (
    EbkStatusFormatter,
    SigNozJsonFormatter,
    log_event,
    setup_logging,
)


def test_signoz_json_formatter_includes_event_attributes():
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Service started",
        args=(),
        exc_info=None,
    )
    record.event = "service.start"
    record.contact_count = 2
    line = SigNozJsonFormatter().format(record)
    data = json.loads(line)
    assert data["severity_text"] == "INFO"
    assert data["body"] == "Service started"
    assert data["attributes"]["event"] == "service.start"
    assert data["attributes"]["contact_count"] == 2


def test_ebk_formatter_compact_line():
    record = logging.LogRecord(
        name="xmpp_p2p_chat.connection_service.api",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="dispatch failed",
        args=(),
        exc_info=None,
    )
    record.event = "rpc.error"
    record.method = "chat.send_message"
    line = EbkStatusFormatter().format(record)
    assert line.startswith("@ebk ")
    assert "event=rpc.error" in line
    assert "method=chat.send_message" in line


def test_setup_logging_writes_json_file(tmp_path: Path):
    json_path = tmp_path / "logs.json"
    cfg = AppConfig()
    cfg.log_level = "INFO"
    cfg.log_json_file = str(json_path)
    cfg.log_ebk_stderr = False
    setup_logging(cfg)
    log_event(logging.getLogger("test.service"), logging.INFO, "test.event", sample=1)
    logging.shutdown()
    assert json_path.exists()
    lines = json_path.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[-1])
    assert payload["attributes"]["event"] == "test.event"


@pytest.mark.asyncio
async def test_service_emits_structured_start_log(service, tmp_path: Path):
    log_path = service._test_log_json  # noqa: SLF001
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line)["attributes"].get("event") for line in lines]
    assert "service.start" in events
