"""Hardware-independent smoke checks for Haunted Wall entry points."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    "haunted_wall.py",
    "haunted_wall_cc0.py",
    "launch_haunted_wall_macos.py",
    "prepare_halloween_assets.py",
    "camera_probe.py",
    "modules/video_source.py",
]


def main() -> int:
    missing = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.exists():
            missing.append(relative)
            continue
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        print(f"syntax ok: {relative}")

    if missing:
        print("missing required files:")
        for item in missing:
            print(f"  - {item}")
        return 1

    print("Haunted Wall smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
