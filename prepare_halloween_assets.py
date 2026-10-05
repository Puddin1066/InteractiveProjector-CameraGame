"""Download and validate the CC0 art set used by the polished Haunted Wall theme."""

from __future__ import annotations

import pathlib
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DEST = ROOT / "assets" / "halloween_cc0"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

ASSETS = {
    "graveyard1.png": "https://opengameart.org/sites/default/files/Graveyard1.png",
    "graveyard2.png": "https://opengameart.org/sites/default/files/Graveyard2.png",
    "ghost_sheet.png": "https://opengameart.org/sites/default/files/enemy-sheet0_1.png",
}


def is_valid_png(path: pathlib.Path) -> bool:
    try:
        return path.stat().st_size > 64 and path.read_bytes()[:8] == PNG_SIGNATURE
    except OSError:
        return False


def download_png(name: str, url: str, target: pathlib.Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "HauntedWall/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        data = response.read()

    if not data.startswith(PNG_SIGNATURE):
        raise RuntimeError(
            f"{name} did not return PNG data (Content-Type={content_type or 'unknown'})"
        )

    with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".tmp", delete=False) as tmp:
        tmp.write(data)
        tmp_path = pathlib.Path(tmp.name)

    if not is_valid_png(tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded {name} failed PNG validation")

    tmp_path.replace(target)


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    failures = []

    for name, url in ASSETS.items():
        target = DEST / name
        if is_valid_png(target):
            print(f"exists: {target.relative_to(ROOT)}")
            continue
        if target.exists():
            target.unlink()

        print(f"downloading {name} ...")
        try:
            download_png(name, url, target)
            print(f"saved:  {target.relative_to(ROOT)}")
        except Exception as exc:
            failures.append((name, str(exc)))
            print(f"failed: {name}: {exc}")

    if failures:
        print("Some optional CC0 assets could not be prepared; procedural fallback remains available.")
        return 1

    print("CC0 Halloween assets ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
