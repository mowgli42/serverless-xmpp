"""Structured logging for SigNoz (JSON) and EBK status lines for AI terminals."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xmpp_p2p_chat.common.config import AppConfig

_RESERVED = {
    "name",
    "msg",
    "args",
    "created",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "exc_info",
    "exc_text",
    "thread",
    "threadName",
    "taskName",
}


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def _record_attributes(record: logging.LogRecord) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in _RESERVED or key.startswith("_"):
            continue
        if value is not None:
            attrs[key] = value
    return attrs


class SigNozJsonFormatter(logging.Formatter):
    """OpenTelemetry-friendly JSON log records for SigNoz / OTLP collectors."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_iso(),
            "severity_text": record.levelname,
            "severity_number": record.levelno,
            "body": record.getMessage(),
            "logger": record.name,
            "attributes": _record_attributes(record),
        }
        if record.exc_info:
            payload["attributes"]["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class EbkStatusFormatter(logging.Formatter):
    """Compact @ebk status lines for Chaterm-style AI terminals and OpenClaw agents."""

    def format(self, record: logging.LogRecord) -> str:
        attrs = _record_attributes(record)
        parts = [
            f"ts={_utc_iso()}",
            f"level={record.levelname.lower()}",
            f"logger={record.name}",
        ]
        event = attrs.pop("event", None)
        if event:
            parts.append(f"event={event}")
        for key in sorted(attrs):
            value = attrs[key]
            if isinstance(value, str) and (" " in value or "=" in value):
                parts.append(f'{key}="{value}"')
            else:
                parts.append(f"{key}={value}")
        if record.getMessage() and record.getMessage() != str(event or ""):
            msg = record.getMessage().replace("\n", " ")
            if " " in msg:
                parts.append(f'msg="{msg}"')
            else:
                parts.append(f"msg={msg}")
        return "@ebk " + " ".join(parts)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str = "",
    **fields: Any,
) -> None:
    """Emit a structured log with a stable event name."""
    logger.log(level, message or event, extra={"event": event, **fields})


def setup_logging(config: AppConfig) -> None:
    """Configure root logging: human text, SigNoz JSON file, and EBK stderr lines."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    text_fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(text_fmt)
    root.addHandler(console)

    if config.log_file:
        path = Path(config.log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(text_fmt)
        root.addHandler(file_handler)

    if config.log_json_file:
        json_path = Path(config.log_json_file).expanduser()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_handler = logging.FileHandler(json_path, encoding="utf-8")
        json_handler.setFormatter(SigNozJsonFormatter())
        root.addHandler(json_handler)

    if config.log_ebk_stderr:
        ebk = logging.StreamHandler(sys.stderr)
        ebk.setFormatter(EbkStatusFormatter())
        ebk.addFilter(lambda record: bool(getattr(record, "event", None)))
        root.addHandler(ebk)
