"""
Builds the Midnight Slash art in web/midnight_slash/images from the painted
source pictures in art/midnight_slash, plus a few pieces drawn with Spooky
Slash's art helpers in the midnight colors. Run it again after changing any of
the source art:

    python -m tools.make_midnight_slash_art

The source pictures are painted on a flat magenta background, which is keyed
out here. Every image keeps the size the game places it at (see
tools/make_spooky_slash_art.py); Spooky Slash supplies anything not made here.
"""
from pathlib import Path
from typing import Tuple

import numpy as np
import pygame
from PIL import Image

from tools import make_spooky_slash_art as art

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "art" / "midnight_slash"
IMAGES = ROOT / "web" / "midnight_slash" / "images"

KEY_NEAR, KEY_FAR = 40.0, 100.0  # color distance from the background: fully clear, fully solid
MIN_ALPHA = 0.05                 # fainter pixels are cropped away

GOLD: art.Color = (255, 210, 63)
NIGHT_GREEN: art.Color = (6, 46, 24)
SLIME: art.Color = (125, 255, 58)

TREATS = {
    # game name: (source picture, stage size, color of the cut face)
    "pumpkin": ("pumpkin", 96, (255, 200, 90)),
    "ghost": ("ghost", 88, (235, 255, 240)),
    "candy": ("candy", 84, (120, 230, 140)),
    "candycorn": ("potion", 84, (150, 255, 90)),
    "coin": ("medallion", 80, (255, 230, 120)),
}


def keyed(name: str) -> pygame.Surface:
    """Source picture `name` with its flat background made transparent, cropped to what is left."""
    rgb = np.asarray(Image.open(SOURCE / f"{name}.jpg").convert("RGB"), np.float32)
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    key = np.median(border, axis=0)
    alpha = np.clip((np.linalg.norm(rgb - key, axis=2) - KEY_NEAR) / (KEY_FAR - KEY_NEAR), 0, 1)
    # edge pixels are a blend of picture and background; take the background back out
    a = np.maximum(alpha, 1e-3)[..., None]
    color = np.clip((rgb - (1 - a) * key) / a, 0, 255)
    rgba = np.dstack([color, alpha * 255]).astype(np.uint8)
    ys, xs = np.nonzero(alpha > MIN_ALPHA)
    rgba = np.ascontiguousarray(rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    return pygame.image.frombytes(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA")


def save(surface: pygame.Surface, name: str, size: Tuple[float, float]) -> None:
    art.save(surface, name, size, IMAGES)


def make_treats() -> None:
    for name, (source, size, cut_color) in TREATS.items():
        whole = art.fit(keyed(source), size, size)
        left, right = art.halves(whole, cut_color)
        for suffix, image in (("", whole), ("-1", left), ("-2", right)):
            save(image, f"fruit/{name}{suffix}.png", (size, size))
    save(art.fit(keyed("skull"), 68, 68), "fruit/boom.png", (68, 68))
    save(art.fit(keyed("pumpkin"), 29, 31), "score.png", (29, 31))


def make_background() -> None:
    w, h = art.STAGE
    size = (w * art.OUTPUT_SCALE, h * art.OUTPUT_SCALE)
    backdrop = Image.open(SOURCE / "backdrop.jpg").convert("RGB").resize(size, Image.LANCZOS)
    backdrop.save(IMAGES / "background.jpg", quality=90)
    print(f"  background.jpg {size[0]}x{size[1]}")


def make_logo() -> None:
    w, h = 480, 170
    surface = art.canvas(w, h)
    art.blit_center(surface, art.text("LINCOLN LYNX", 26, GOLD, NIGHT_GREEN, 0.12), w / 2, 20)
    art.blit_center(surface, art.fit(keyed("title"), w, h - 40), w / 2, 40 + (h - 40) / 2)
    save(surface, "logo.png", (w, h))


def make_banners() -> None:
    for source, name, size in (("mascot", "mascot.png", (170, 227)), ("times-up", "game-over.png", (490, 85)),
                               ("witching-hour", "witching-hour.png", (560, 150))):
        save(art.fit(keyed(source), *size), name, size)


def make_menu() -> None:
    art.make_home_mask((*NIGHT_GREEN, 215), GOLD, IMAGES)
    art.make_home_desc((10, 56, 30), GOLD, GOLD, IMAGES)
    art.make_start_ring(GOLD, NIGHT_GREEN, IMAGES)


def main() -> None:
    pygame.font.init()
    print(f"Writing art to {IMAGES}")
    make_treats()
    make_background()
    make_logo()
    make_banners()
    make_menu()


if __name__ == "__main__":
    main()
