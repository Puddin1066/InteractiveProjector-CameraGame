"""
Downloads the Midnight Slash music and voices (all CC0) and writes them to
web/midnight_slash/sound as the .ogg/.mp3 pairs the game loads, at matching
loudness. Needs ffmpeg. Run it again after changing the list:

    python -m tools.make_midnight_slash_sounds

Spooky Slash supplies the sounds not made here (throw, slice, skull).
"""
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SOUND = ROOT / "web" / "midnight_slash" / "sound"
OPENGAMEART = "https://opengameart.org/sites/default/files/"
LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11"

# game name: (source URL, (start, end) seconds to keep or None for all); credited in web/midnight_slash/index.html
SOURCES: Dict[str, Tuple[str, Optional[Tuple[float, float]]]] = {
    "music-play": (OPENGAMEART + "HarpsiChordFlurry.ogg", None),
    "music-menu": (OPENGAMEART + "Spook.mp3", (3.962, 19.700)),  # the part that loops seamlessly
    "start": (OPENGAMEART + "witch_cackle-1.ogg", None),
    "cackle": (OPENGAMEART + "ghostly_cackle_laugh_1.ogg", None),
    "cheer": ("https://bigsoundbank.com/UPLOAD/mp3/0236.mp3", None),
}
# the countdown tick, made rather than downloaded
TICK = "sine=frequency=1100:duration=0.09,afade=t=out:st=0.02:d=0.07"
ENCODINGS = {"ogg": ["-c:a", "libvorbis", "-q:a", "5"], "mp3": ["-c:a", "libmp3lame", "-q:a", "3"]}


def download(url: str, folder: Path) -> Path:
    path = folder / url.rsplit("/", 1)[1]
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response, path.open("wb") as out:
        shutil.copyfileobj(response, out)
    return path


def encode(inputs: list, name: str, audio_filter: str) -> None:
    for extension, codec in ENCODINGS.items():
        out = SOUND / f"{name}.{extension}"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-af", audio_filter, "-ar", "44100", *codec,
                        str(out)], check=True)
        print(f"  {out.name}")


def main() -> None:
    SOUND.mkdir(parents=True, exist_ok=True)
    print(f"Writing sounds to {SOUND}")
    with tempfile.TemporaryDirectory() as folder:
        for name, (url, keep) in SOURCES.items():
            trim = ["-ss", str(keep[0]), "-to", str(keep[1])] if keep else []
            encode([*trim, "-i", str(download(url, Path(folder)))], name, LOUDNESS)
    encode(["-f", "lavfi", "-i", TICK], "tick", "volume=0.6")


if __name__ == "__main__":
    main()
