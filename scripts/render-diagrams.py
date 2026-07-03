#!/usr/bin/env python3
"""Render PlantUML sources under docs/diagrams/src/ to PNG in docs/diagrams/."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import plantuml
except ImportError as exc:  # pragma: no cover
    print("Missing dependency: pip install plantuml six", file=sys.stderr)
    raise SystemExit(1) from exc

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "docs" / "diagrams" / "src"
OUT_DIR = ROOT / "docs" / "diagrams"


def main() -> int:
    if not SRC_DIR.is_dir():
        print(f"Source directory not found: {SRC_DIR}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    renderer = plantuml.PlantUML(url="https://www.plantuml.com/plantuml/png/")

    sources = sorted(SRC_DIR.glob("*.puml"))
    if not sources:
        print(f"No .puml files in {SRC_DIR}", file=sys.stderr)
        return 1

    for src in sources:
        out = OUT_DIR / f"{src.stem}.png"
        print(f"Rendering {src.relative_to(ROOT)} → {out.relative_to(ROOT)}")
        renderer.processes_file(str(src), outfile=str(out))
        if not out.exists() or out.stat().st_size < 100:
            print(f"Render failed or empty output: {out}", file=sys.stderr)
            return 1

    print(f"Done — {len(sources)} diagram(s) written to {OUT_DIR.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
