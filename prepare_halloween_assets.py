"""Download the small CC0 art set used by the polished Haunted Wall theme.

Sources are pinned to OpenGameArt-hosted files whose asset pages explicitly
list the works under CC0/public-domain terms. The game still runs without these
files; this script simply upgrades the visual presentation.
"""

from __future__ import annotations

import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DEST = ROOT / "assets" / "halloween_cc0"

ASSETS = {
    "graveyard1.png": "https://opengameart.org/sites/default/files/Graveyard1.png",
    "graveyard2.png": "https://opengameart.org/sites/default/files/Graveyard2.png",
    "ghost_sheet.png": "https://opengameart.org/sites/default/files/enemy-sheet0_1.png",
}


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, url in ASSETS.items():
        target = DEST / name
        if target.exists() and target.stat().st_size > 0:
            print(f"exists: {target.relative_to(ROOT)}")
            continue
        print(f"downloading {name} ...")
        request = urllib.request.Request(url, headers={"User-Agent": "HauntedWall/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            target.write_bytes(response.read())
        print(f"saved:  {target.relative_to(ROOT)}")

    print("CC0 Halloween assets ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
