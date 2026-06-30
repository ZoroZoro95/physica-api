#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "frontend" / "public" / "landing-simulation.mp4"
MAX_BYTES = 8 * 1024 * 1024


def main() -> int:
    if not VIDEO.exists():
        print("PASS landing media: no local MP4 asset")
        return 0
    size = VIDEO.stat().st_size
    if size > MAX_BYTES:
        print(
            f"FAIL landing media too large: {VIDEO} is {size / (1024 * 1024):.1f} MB; "
            f"limit is {MAX_BYTES / (1024 * 1024):.1f} MB"
        )
        return 1
    print(f"PASS landing media: {size / (1024 * 1024):.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
