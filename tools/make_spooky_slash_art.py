"""
Draws the spooky Lincoln Lynx Halloween art for web/spooky_slash, the reskinned
Fruit Ninja browser game. Run it again after changing any of the art:

    python -m tools.make_spooky_slash_art

Each image keeps the size the game code places it at on the 853x480 stage and is
written at OUTPUT_SCALE times that, so it stays sharp on a 1080p projector. The
backdrop stays bright on purpose: shadows only show up on a well-lit wall.
"""
import math
import random
from pathlib import Path
from typing import Tuple

import numpy as np
import pygame
from PIL import Image

from modules.treat_sprites import (CANDY_COLORS, LYNX_GREEN, SKULL_WHITE, candy_sprite, ghost_sprite,
                                   lynx_coin_sprite, pumpkin_sprite)

IMAGES = Path(__file__).resolve().parent.parent / "web" / "spooky_slash" / "images"
STAGE = (853, 480)
OUTPUT_SCALE = 3
SUPERSAMPLE = 2                 # drawn this much larger again, then smoothed down
PX = OUTPUT_SCALE * SUPERSAMPLE  # drawing pixels per stage unit
FONT_PATH = "/System/Library/Fonts/Supplemental/Impact.ttf"

Color = Tuple[int, ...]
SKY_TOP: Color = (212, 198, 240)
SKY_BOTTOM: Color = (208, 238, 218)
HILLS: Color = (188, 222, 200)
MOON: Color = (255, 251, 232)
MOON_LYNX: Color = (214, 200, 238)
STONE: Color = (230, 228, 240)
STONE_EDGE: Color = (172, 162, 205)
STONE_TEXT: Color = (110, 185, 140)
PALE_PUMPKIN: Color = (255, 196, 130)
PALE_STEM: Color = (140, 196, 150)
WEB: Color = (168, 150, 212)
BAT: Color = (190, 172, 230)
PURPLE: Color = (110, 60, 190)
DEEP_PURPLE: Color = (60, 31, 110)
ORANGE: Color = (255, 140, 20)
MISS_RED: Color = (240, 70, 40)
WHITE: Color = (255, 255, 255)
GOLD: Color = (255, 205, 50)
BOMB: Color = (48, 30, 70)
FUSE: Color = (205, 170, 120)


# --- drawing helpers -------------------------------------------------------

def canvas(w: float, h: float) -> pygame.Surface:
    return pygame.Surface((round(w * PX), round(h * PX)), pygame.SRCALPHA)


def save(surface: pygame.Surface, name: str, size: Tuple[float, float], folder: Path = IMAGES) -> None:
    out = pygame.transform.smoothscale(surface, (round(size[0] * OUTPUT_SCALE), round(size[1] * OUTPUT_SCALE)))
    image = Image.frombytes("RGBA", out.get_size(), pygame.image.tobytes(out, "RGBA"))
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".jpg":
        image.convert("RGB").save(path, quality=90)
    else:
        image.save(path)
    print(f"  {name} {image.width}x{image.height}")


def fit(sprite: pygame.Surface, w: float, h: float) -> pygame.Surface:
    """`sprite` scaled to fill a w x h stage-unit canvas, keeping its shape, centered."""
    target = canvas(w, h)
    k = min(target.get_width() / sprite.get_width(), target.get_height() / sprite.get_height())
    scaled = pygame.transform.smoothscale(sprite, (round(sprite.get_width() * k), round(sprite.get_height() * k)))
    target.blit(scaled, scaled.get_rect(center=target.get_rect().center))
    return target


def text(words: str, height: float, fill: Color, outline: Color = None, outline_width: float = 0.08) -> pygame.Surface:
    """Impact text `height` stage units tall, with an optional outline."""
    font = pygame.font.Font(FONT_PATH, round(height * PX * 1.25))
    face = font.render(words, True, fill)
    if outline is None:
        return face
    border = max(1, round(height * PX * outline_width))
    shape = font.render(words, True, outline)
    out = pygame.Surface((face.get_width() + 2 * border, face.get_height() + 2 * border), pygame.SRCALPHA)
    for step in range(16):
        a = 2 * math.pi * step / 16
        out.blit(shape, (border + border * math.cos(a), border + border * math.sin(a)))
    out.blit(face, (border, border))
    return out


def blit_center(target: pygame.Surface, image: pygame.Surface, x: float, y: float) -> None:
    """Center `image` at stage-unit point (x, y) of `target`."""
    target.blit(image, image.get_rect(center=(x * PX, y * PX)))


def fit_width(image: pygame.Surface, w: float) -> pygame.Surface:
    """Shrink `image` to at most w stage units wide."""
    if image.get_width() <= w * PX:
        return image
    k = w * PX / image.get_width()
    return pygame.transform.smoothscale(image, (round(image.get_width() * k), round(image.get_height() * k)))


def p(*points: float) -> list:
    """Stage-unit coordinates to drawing pixels."""
    return [(x * PX, y * PX) for x, y in zip(points[::2], points[1::2])]


# --- treats -----------------------------------------------------------------

def candy_corn_sprite(size: float) -> pygame.Surface:
    surface = canvas(size, size)
    s = size * PX
    top, left, right = (s * 0.5, s * 0.06), (s * 0.1, s * 0.92), (s * 0.9, s * 0.92)

    def at(f):  # the triangle's edges at height fraction f from the tip
        return (top[0] + (left[0] - top[0]) * f, top[1] + (left[1] - top[1]) * f), \
               (top[0] + (right[0] - top[0]) * f, top[1] + (right[1] - top[1]) * f)

    pygame.draw.polygon(surface, DEEP_PURPLE, [top, left, right])
    for f0, f1, color in ((0.05, 0.36, WHITE), (0.36, 0.68, ORANGE), (0.68, 0.95, GOLD)):
        (a, b), (c, d) = at(f0), at(f1)
        pygame.draw.polygon(surface, color, [a, b, d, c])
    for dx in (-0.1, 0.1):
        pygame.draw.circle(surface, DEEP_PURPLE, (s * (0.5 + dx), s * 0.55), s * 0.035)
    pygame.draw.arc(surface, DEEP_PURPLE, pygame.Rect(s * 0.42, s * 0.55, s * 0.16, s * 0.1), math.pi, 2 * math.pi,
                    max(2, round(s * 0.02)))
    return surface


def skull_bomb_sprite(size: float) -> pygame.Surface:
    """Round bomb with a skull; its fuse ends at the top-left, where the game lights a flame."""
    surface = canvas(size, size)
    s = size * PX
    c, r = (s * 0.56, s * 0.58), s * 0.38
    fuse = [(s * 0.08, s * 0.09), (s * 0.12, s * 0.2), (s * 0.24, s * 0.22), (s * 0.3, s * 0.3)]
    pygame.draw.lines(surface, FUSE, False, fuse, max(3, round(s * 0.06)))
    pygame.draw.circle(surface, (*BOMB, 255), c, r)
    cap = pygame.Rect(0, 0, s * 0.16, s * 0.12)
    cap.center = (c[0] - r * 0.62, c[1] - r * 0.62)
    pygame.draw.rect(surface, (120, 110, 140), cap, border_radius=round(s * 0.02))
    pygame.draw.circle(surface, (90, 70, 120), (c[0] - r * 0.4, c[1] - r * 0.4), r * 0.18)
    skull = r * 0.55
    pygame.draw.circle(surface, SKULL_WHITE, (c[0], c[1] - skull * 0.15), skull * 0.8)
    jaw = pygame.Rect(0, 0, skull * 0.9, skull * 0.5)
    jaw.midtop = (c[0], c[1] + skull * 0.3)
    pygame.draw.rect(surface, SKULL_WHITE, jaw, border_radius=round(skull * 0.15))
    for dx in (-0.32, 0.32):
        pygame.draw.circle(surface, BOMB, (c[0] + dx * skull, c[1] - skull * 0.15), skull * 0.22)
    pygame.draw.polygon(surface, BOMB, [(c[0], c[1] + skull * 0.05), (c[0] - skull * 0.1, c[1] + skull * 0.25),
                                        (c[0] + skull * 0.1, c[1] + skull * 0.25)])
    return surface


def halves(whole: pygame.Surface, cut_color: Color) -> Tuple[pygame.Surface, pygame.Surface]:
    """Left and right halves, each on the full canvas, with the cut face showing."""
    w = whole.get_width()
    band = max(2, round(w * 0.05))
    result = []
    for keep_left in (True, False):
        half = whole.copy()
        lo, hi = (w // 2, w) if keep_left else (0, w // 2)
        half.fill((0, 0, 0, 0), pygame.Rect(lo, 0, hi - lo, whole.get_height()))
        face = slice(w // 2 - band, w // 2) if keep_left else slice(w // 2, w // 2 + band)
        rgb, alpha = pygame.surfarray.pixels3d(half), pygame.surfarray.pixels_alpha(half)
        inside = alpha[face] > 0
        rgb[face][inside] = cut_color
        del rgb, alpha
        result.append(half)
    return result[0], result[1]


TREATS = {
    # name: (drawing at a large radius, stage size, color of the cut face)
    "pumpkin": (lambda: pumpkin_sprite(200), 96, (255, 214, 120)),
    "ghost": (lambda: ghost_sprite(200), 88, (250, 246, 255)),
    "candy": (lambda: candy_sprite(150, CANDY_COLORS[0]), 84, (255, 190, 220)),
    "candycorn": (lambda: candy_corn_sprite(84), 84, (255, 236, 170)),
    "coin": (lambda: lynx_coin_sprite(200), 80, (255, 236, 150)),
}


def make_treats() -> None:
    for name, (draw, size, cut_color) in TREATS.items():
        whole = fit(draw(), size, size)
        left, right = halves(whole, cut_color)
        for suffix, image in (("", whole), ("-1", left), ("-2", right)):
            save(image, f"fruit/{name}{suffix}.png", (size, size))
    save(skull_bomb_sprite(68), "fruit/boom.png", (68, 68))
    save(fit(pumpkin_sprite(200), 29, 31), "score.png", (29, 31))


# --- backdrop -----------------------------------------------------------------

def lerp_color(a: Color, b: Color, f: float) -> Color:
    return tuple(round(x + (y - x) * f) for x, y in zip(a, b))


def draw_lynx_head(surface: pygame.Surface, cx: float, cy: float, r: float, color: Color) -> None:
    """Lynx head silhouette: pointed ears with tufts and cheek ruffs."""
    for side in (-1, 1):
        ear = p(cx + side * r * 0.2, cy - r * 0.6, cx + side * r * 0.75, cy - r * 0.42, cx + side * r * 0.55, cy - r * 1.15)
        pygame.draw.polygon(surface, color, ear)
        tip = ear[2]
        pygame.draw.line(surface, color, tip, (tip[0], tip[1] - r * 0.22 * PX), max(2, round(r * 0.07 * PX)))
        ruff = p(cx + side * r * 0.55, cy + r * 0.1, cx + side * r * 0.98, cy + r * 0.5, cx + side * r * 0.4, cy + r * 0.72)
        pygame.draw.polygon(surface, color, ruff)
    head = pygame.Rect(0, 0, r * 1.6 * PX, r * 1.45 * PX)
    head.center = (cx * PX, cy * PX)
    pygame.draw.ellipse(surface, color, head)


def draw_bat(surface: pygame.Surface, x: float, y: float, size: float) -> None:
    wing = [(x, y), (x - size * 2.2, y - size * 0.8), (x - size * 1.6, y + size * 0.1), (x - size * 1.1, y - size * 0.1),
            (x - size * 0.6, y + size * 0.4)]
    pygame.draw.polygon(surface, BAT, p(*[v for pt in wing for v in pt]))
    pygame.draw.polygon(surface, BAT, p(*[v for px, py in wing for v in (2 * x - px, py)]))
    pygame.draw.circle(surface, BAT, (x * PX, y * PX), size * 0.45 * PX)


def draw_tombstone(surface: pygame.Surface, x: float, base: float, w: float, h: float, label: str) -> None:
    edge = max(2, round(1.2 * PX))
    body = pygame.Rect(0, 0, w * PX, (h - w / 2) * PX)
    body.midbottom = (x * PX, base * PX)
    for color, width in ((STONE, 0), (STONE_EDGE, edge)):
        pygame.draw.circle(surface, color, (x * PX, body.top), w / 2 * PX, width, draw_top_left=True, draw_top_right=True)
        pygame.draw.rect(surface, color, body, width)
    pygame.draw.rect(surface, STONE, body.inflate(-2 * edge, 0).move(0, -edge))
    blit_center(surface, fit_width(text(label, w * 0.26, STONE_TEXT), w * 0.85), x, base - h * 0.55)


def draw_cobweb(surface: pygame.Surface, corner: Tuple[float, float], reach: float) -> None:
    cx, cy = corner
    sx = 1 if cx == 0 else -1
    spokes = [math.radians(a) for a in (5, 25, 45, 65, 85)]
    width = max(1, round(0.6 * PX))
    for a in spokes:
        pygame.draw.line(surface, WEB, (cx * PX, cy * PX),
                         ((cx + sx * reach * math.cos(a)) * PX, (cy + reach * math.sin(a)) * PX), width)
    for ring in (0.3, 0.55, 0.8):
        pts = [((cx + sx * reach * ring * math.cos(a)) * PX, (cy + reach * ring * math.sin(a)) * PX) for a in spokes]
        pygame.draw.lines(surface, WEB, False, pts, width)


def draw_fog(surface: pygame.Surface, rng: random.Random) -> None:
    w, h = STAGE
    fog = canvas(w, h)
    for _ in range(26):
        rect = pygame.Rect(0, 0, rng.uniform(120, 260) * PX, rng.uniform(25, 50) * PX)
        rect.center = (rng.uniform(-40, w + 40) * PX, rng.uniform(h * 0.83, h * 1.02) * PX)
        pygame.draw.ellipse(fog, (*WHITE, 70), rect)
    surface.blit(fog, (0, 0))


def make_background() -> None:
    w, h = STAGE
    surface = canvas(w, h)
    for y in range(surface.get_height()):
        pygame.draw.line(surface, lerp_color(SKY_TOP, SKY_BOTTOM, y / surface.get_height()), (0, y), (surface.get_width(), y))
    rng = random.Random(31)
    for _ in range(60):
        pygame.draw.circle(surface, WHITE, (rng.uniform(0, w) * PX, rng.uniform(0, h * 0.55) * PX), rng.uniform(0.6, 1.4) * PX)

    moon_x, moon_y, moon_r = w * 0.78, h * 0.28, h * 0.15
    glow = canvas(w, h)
    for k in (1.6, 1.35, 1.15):
        pygame.draw.circle(glow, (*MOON, 60), (moon_x * PX, moon_y * PX), moon_r * k * PX)
    surface.blit(glow, (0, 0))
    pygame.draw.circle(surface, MOON, (moon_x * PX, moon_y * PX), moon_r * PX)
    draw_lynx_head(surface, moon_x, moon_y + moon_r * 0.18, moon_r * 0.55, MOON_LYNX)

    hills = p(0, h * 0.82, w * 0.2, h * 0.76, w * 0.45, h * 0.8, w * 0.7, h * 0.75, w, h * 0.8, w, h, 0, h)
    pygame.draw.polygon(surface, HILLS, hills)
    for x, base, tw, th, label in ((w * 0.07, h * 0.95, 46, 74, "RIP"), (w * 0.22, h * 0.9, 40, 62, "BOO"),
                                   (w * 0.4, h * 0.97, 52, 80, "LYNX"), (w * 0.62, h * 0.92, 42, 64, "EEK"),
                                   (w * 0.8, h * 0.96, 50, 78, "GO LYNX"), (w * 0.95, h * 0.9, 38, 58, "RIP")):
        draw_tombstone(surface, x, base, tw, th, label)
    for x, y, r in ((w * 0.3, h * 0.95, 13), (w * 0.52, h * 0.93, 10), (w * 0.71, h * 0.97, 12)):
        pumpkin = pygame.Rect(0, 0, r * 2.2 * PX, r * 1.8 * PX)
        pumpkin.center = (x * PX, y * PX)
        pygame.draw.ellipse(surface, PALE_PUMPKIN, pumpkin)
        pygame.draw.rect(surface, PALE_STEM, pygame.Rect(x * PX - r * 0.15 * PX, pumpkin.top - r * 0.35 * PX, r * 0.3 * PX, r * 0.45 * PX))
    draw_fog(surface, rng)
    draw_cobweb(surface, (0, 0), 70)
    draw_cobweb(surface, (w, 0), 70)
    for x, y, size in ((0.18, 0.42, 7), (0.33, 0.3, 5), (0.55, 0.22, 6), (0.62, 0.45, 4), (0.9, 0.55, 5)):
        draw_bat(surface, w * x, h * y, size)
    save(surface, "background.jpg", STAGE)


# --- menu, HUD and effects --------------------------------------------------------

def make_home_mask(band_color: Color = (*LYNX_GREEN, 225), trim: Color = GOLD, folder: Path = IMAGES) -> None:
    w, h = STAGE[0], 183
    surface = canvas(w, h)
    band = p(0, 0, w, 0, w, 130, 0, 175)
    pygame.draw.polygon(surface, band_color, band)
    pygame.draw.line(surface, trim, band[3], band[2], round(3 * PX))
    save(surface, "home-mask.png", (w, h), folder)


def make_logo() -> None:
    surface = canvas(288, 135)
    blit_center(surface, text("LINCOLN", 24, WHITE, LYNX_GREEN), 144, 22)
    blit_center(surface, fit_width(text("LYNX", 82, GOLD, DEEP_PURPLE), 280), 144, 88)
    save(surface, "logo.png", (288, 135))


def make_title() -> None:
    surface = canvas(244, 81)
    blit_center(surface, fit_width(text("SPOOKY SLASH!", 44, ORANGE, DEEP_PURPLE), 240), 122, 40)
    save(surface, "ninja.png", (244, 81))


def make_home_desc(stone_color: Color = STONE, edge: Color = STONE_EDGE, ink: Color = DEEP_PURPLE,
                   folder: Path = IMAGES) -> None:
    w, h = 161, 91
    surface = canvas(w, h)
    stone = pygame.Rect(4 * PX, 14 * PX, (w - 8) * PX, (h - 18) * PX)
    pygame.draw.rect(surface, stone_color, stone, border_radius=round(30 * PX))
    pygame.draw.rect(surface, edge, stone, round(2 * PX), border_radius=round(30 * PX))
    for i, line in enumerate(("SWIPE YOUR HANDS", "THROUGH THE AIR", "TO SLASH!")):
        blit_center(surface, fit_width(text(line, 15, ink), w - 30), w / 2, 34 + i * 19)
    save(surface, "home-desc.png", (w, h), folder)


def make_start_ring(fill: Color = ORANGE, edge: Color = DEEP_PURPLE, folder: Path = IMAGES) -> None:
    size = 195
    surface = canvas(size, size)
    c = size / 2
    pygame.draw.circle(surface, edge, (c * PX, c * PX), 97 * PX)
    pygame.draw.circle(surface, fill, (c * PX, c * PX), 94 * PX)
    pygame.draw.circle(surface, edge, (c * PX, c * PX), 63 * PX)
    pygame.draw.circle(surface, (0, 0, 0, 0), (c * PX, c * PX), 60 * PX)
    words, radius, gap = "SLASH TO PLAY", 78, 1.5
    glyphs = [text(ch, 20, WHITE, edge, 0.12) for ch in words]
    arcs = [math.degrees((g.get_width() / PX + gap) / radius) for g in glyphs]
    for start in (-90, 90):  # once along the top, once along the bottom
        angle = start - sum(arcs) / 2
        for glyph, arc in zip(glyphs, arcs):
            middle = angle + arc / 2
            a = math.radians(middle)
            blit_center(surface, pygame.transform.rotozoom(glyph, -middle - 90, 1),
                        c + radius * math.cos(a), c + radius * math.sin(a))
            angle += arc
    save(surface, "new-game.png", (size, size), folder)


def make_game_over() -> None:
    surface = canvas(490, 85)
    blit_center(surface, fit_width(text("GAME OVER", 70, ORANGE, DEEP_PURPLE), 480), 245, 42)
    save(surface, "game-over.png", (490, 85))


def x_mark(w: float, h: float, fill: Color, edge: Color) -> pygame.Surface:
    surface = canvas(w, h)
    m = min(w, h)
    for color, thick in ((edge, 0.36), (fill, 0.22)):
        for a, b in (((0.18, 0.18), (0.82, 0.82)), ((0.82, 0.18), (0.18, 0.82))):
            start, end = (a[0] * w * PX, a[1] * h * PX), (b[0] * w * PX, b[1] * h * PX)
            width = round(m * thick * PX)
            pygame.draw.line(surface, color, start, end, width)
            for point in (start, end):
                pygame.draw.circle(surface, color, point, width / 2)
    return surface


def make_misses() -> None:
    save(x_mark(54, 50, MISS_RED, DEEP_PURPLE), "lose.png", (54, 50))
    for name, size in (("x", (22, 19)), ("xx", (27, 26)), ("xxx", (32, 32))):
        save(x_mark(*size, WHITE, PURPLE), f"{name}.png", size)
        save(x_mark(*size, MISS_RED, DEEP_PURPLE), f"{name}f.png", size)


def soft_ellipse(w: float, h: float, color: Color, peak_alpha: int, steps: int = 12) -> pygame.Surface:
    surface = canvas(w, h)
    for i in range(steps):
        f = 1 - i / steps
        rect = pygame.Rect(0, 0, w * PX * f, h * PX * f)
        rect.center = surface.get_rect().center
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.ellipse(layer, (*color, round(peak_alpha / steps)), rect)
        surface.blit(layer, (0, 0))
    return surface


def make_effects() -> None:
    save(soft_ellipse(106, 77, PURPLE, 0), "shadow.png", (106, 77))  # no fake shadow under treats: real shadows only
    save(soft_ellipse(43, 43, (225, 220, 240), 230), "smoke.png", (43, 43))
    flash = soft_ellipse(358, 20, GOLD, 160)
    flash.blit(soft_ellipse(358, 8, WHITE, 255), (0, 6 * PX))
    save(flash, "flash.png", (358, 20))


def check_brightness() -> None:
    """Shadow detection needs a bright wall; report the backdrop's darkest areas."""
    lum = np.asarray(Image.open(IMAGES / "background.jpg").convert("L"), np.float32) / 255
    print(f"Backdrop brightness: mean {lum.mean():.2f}, darkest 1% {np.percentile(lum, 1):.2f}")


def main() -> None:
    pygame.font.init()
    print(f"Writing art to {IMAGES}")
    make_treats()
    make_background()
    make_home_mask()
    make_logo()
    make_title()
    make_home_desc()
    make_start_ring()
    make_game_over()
    make_misses()
    make_effects()
    check_brightness()


if __name__ == "__main__":
    main()
