"""Address book content hashing and visual fingerprint helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

# 16-color palette (terminal-safe hues) indexed by hex nibble 0-f
NIBBLE_COLORS = [
    "#1e1e2e",
    "#45475a",
    "#585b70",
    "#6c7086",
    "#f38ba8",
    "#fab387",
    "#f9e2af",
    "#a6e3a1",
    "#94e2d5",
    "#89b4fa",
    "#cba6f7",
    "#f5c2e7",
    "#b4befe",
    "#74c7ec",
    "#89dceb",
    "#a6adc8",
]

TERMINAL_NIBBLE_COLORS = [
    "red",
    "orange1",
    "yellow",
    "green",
    "cyan",
    "blue",
    "magenta",
    "white",
    "bright_red",
    "bright_yellow",
    "bright_green",
    "bright_cyan",
    "bright_blue",
    "bright_magenta",
    "grey70",
    "grey30",
]


def canonical_contacts_payload(contacts: list[dict[str, Any]]) -> bytes:
    """Stable JSON bytes for hashing — sorted by id, normalized keys."""
    normalized = sorted(
        (dict(sorted(c.items())) for c in contacts),
        key=lambda c: c.get("id", ""),
    )
    return json.dumps(normalized, separators=(",", ":"), sort_keys=True).encode("utf-8")


def compute_content_hash(contacts: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256(canonical_contacts_payload(contacts)).hexdigest()
    return f"SHA256:{digest}"


def hash_hex(content_hash: str) -> str:
    if content_hash.startswith("SHA256:"):
        return content_hash.removeprefix("SHA256:")
    return content_hash


def hash_nibbles(content_hash: str, *, limit: int = 64) -> list[int]:
    hex_str = hash_hex(content_hash)[:limit]
    return [int(ch, 16) for ch in hex_str]


def hash_block_colors(content_hash: str, *, grid: int = 8) -> list[str]:
    nibbles = hash_nibbles(content_hash, limit=grid * grid)
    return [NIBBLE_COLORS[n] for n in nibbles]


def render_hash_grid_rich(content_hash: str, *, grid: int = 8) -> str:
    """Render an 8×8 colored block grid for Textual/Rich."""
    nibbles = hash_nibbles(content_hash, limit=grid * grid)
    rows: list[str] = []
    for row in range(grid):
        cells = nibbles[row * grid : (row + 1) * grid]
        parts = [f"[{TERMINAL_NIBBLE_COLORS[n]}]█[/]" for n in cells]
        rows.append("".join(parts))
    return "\n".join(rows)


def render_hash_grid_ascii(content_hash: str, *, grid: int = 8) -> str:
    """Compact ASCII fingerprint for logs."""
    hex_str = hash_hex(content_hash)[: grid * grid // 2]
    rows = []
    cols = grid // 2
    for row in range(grid):
        start = row * cols
        rows.append(hex_str[start : start + cols])
    return "\n".join(rows)
