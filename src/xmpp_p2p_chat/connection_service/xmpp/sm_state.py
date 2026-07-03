"""Persist XEP-0198 stream management state between reconnects."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SM_STATE_FILENAME = ".xmpp-sm-state.json"


@dataclass
class StreamManagementState:
    jid: str
    sm_id: str | None
    handled: int = 0
    last_ack: int = 0
    saved_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> StreamManagementState:
        return cls(
            jid=str(data.get("jid", "")),
            sm_id=data.get("sm_id"),
            handled=int(data.get("handled", 0)),
            last_ack=int(data.get("last_ack", 0)),
            saved_at=str(data.get("saved_at", "")),
        )

    def to_dict(self) -> dict:
        return {
            "jid": self.jid,
            "sm_id": self.sm_id,
            "handled": self.handled,
            "last_ack": self.last_ack,
            "saved_at": self.saved_at or datetime.now(UTC).isoformat(),
        }


def sm_state_path(data_dir: Path) -> Path:
    return data_dir / SM_STATE_FILENAME


def load_sm_state(data_dir: Path, jid: str) -> StreamManagementState | None:
    path = sm_state_path(data_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = StreamManagementState.from_dict(data)
    except (json.JSONDecodeError, OSError, ValueError, TypeError) as exc:
        logger.warning("Could not load SM state from %s: %s", path, exc)
        return None
    if state.jid.lower() != jid.lower():
        logger.info("Ignoring SM state for different JID (%s != %s)", state.jid, jid)
        return None
    return state


def save_sm_state(data_dir: Path, state: StreamManagementState) -> None:
    path = sm_state_path(data_dir)
    state.saved_at = datetime.now(UTC).isoformat()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(path)


def clear_sm_state(data_dir: Path) -> None:
    path = sm_state_path(data_dir)
    if path.exists():
        path.unlink()
