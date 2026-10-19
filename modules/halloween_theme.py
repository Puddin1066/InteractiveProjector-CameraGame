"""
Halloween art shared by the wall games: a graveyard backdrop and the animated
ghost, built from the CC0 files in assets/halloween_cc0 (see HALLOWEEN_ASSETS.md,
fetched by prepare_halloween_assets.py).
"""
import math
import os
from typing import List, Optional, Tuple

import pygame

from . import config

ASSET_DIR = os.path.join(config.ASSETS_DIR, "halloween_cc0")
ASSET_FILES = ("graveyard1.png", "graveyard2.png", "ghost_sheet.png")

# ghost_sheet.png is a 3x5 grid of 302x201 cells in its top-left 906x1005 area.
GHOST_GRID = (3, 5)
GHOST_CELL = (302, 201)
# Regions (left, top, right, bottom) of the sprite sheets holding one seamless
# layer each, without the sheets' transparent margins.
TREE_REGION = (31, 522, 1899, 1067)   # graveyard2: lower tree line, crosses and ground
HILL_REGION = (31, 193, 1899, 542)    # graveyard1: mountain horizon

Color = Tuple[int, int, int]
NIGHT_SKY: Tuple[Color, Color] = ((4, 7, 16), (4, 7, 16))
# Projected light is what lets the camera see players' hands, so game modes
# use a bright twilight instead of a black night.
TWILIGHT_SKY: Tuple[Color, Color] = ((70, 30, 110), (235, 120, 45))
MOON_COLOR = (240, 232, 190)


def assets_present() -> bool:
    return all(os.path.exists(os.path.join(ASSET_DIR, name)) for name in ASSET_FILES)


def slice_ghost_frames(sheet: Optional[pygame.Surface]) -> List[pygame.Surface]:
    if sheet is None:
        return []
    cols, rows = GHOST_GRID
    cell_w, cell_h = GHOST_CELL
    return [
        sheet.subsurface(pygame.Rect(col * cell_w, row * cell_h, cell_w, cell_h)).copy()
        for row in range(rows) for col in range(cols)
    ]


class HalloweenArt:
    """Loads the art once at a fixed screen size and draws it each frame."""

    GHOST_FPS = 9

    def __init__(self, size: Tuple[int, int], sky: Tuple[Color, Color] = TWILIGHT_SKY,
                 moon_at: Tuple[float, float] = (0.80, 0.18)):
        self.width, self.height = size
        self.moon_at = moon_at
        trees = _load("graveyard2.png")
        hills = _load("graveyard1.png")
        self.ghost_frames = slice_ghost_frames(_load("ghost_sheet.png"))
        self.ready = bool(trees and self.ghost_frames)

        self._sky = self._build_sky(*sky)
        self._trees = self._build_trees(trees)
        self._hills = self._build_hills(hills)
        self._fog = self._build_fog()

    def draw_backdrop(self, surface: pygame.Surface, t: float) -> None:
        surface.blit(self._sky, (0, 0))
        self._draw_moon(surface)
        if self._hills is not None:
            self._blit_tiled(surface, self._hills, int(self.height * 0.49), math.sin(t * 0.045) * 18)
        if self._trees is not None:
            self._blit_tiled(surface, self._trees, self.height - self._trees.get_height(),
                             math.sin(t * 0.08) * 35)
        surface.blit(self._fog, (int(math.sin(t * 0.45) * 60) - 150, 0))

    def ghost_frame(self, t: float, phase: float = 0.0) -> Optional[pygame.Surface]:
        if not self.ghost_frames:
            return None
        index = int(t * self.GHOST_FPS + phase * 2) % len(self.ghost_frames)
        return self.ghost_frames[index]

    def _draw_moon(self, surface: pygame.Surface) -> None:
        radius = max(70, int(min(self.width, self.height) * 0.10))
        center = (int(self.width * self.moon_at[0]), int(self.height * self.moon_at[1]))
        pygame.draw.circle(surface, MOON_COLOR, center, radius)

    def _blit_tiled(self, surface, layer, y, drift) -> None:
        layer_w = layer.get_width()
        for x in range(-layer_w + int(drift), self.width + layer_w, layer_w):
            surface.blit(layer, (x, y))

    def _build_sky(self, top: Color, bottom: Color) -> pygame.Surface:
        sky = pygame.Surface((self.width, self.height))
        for y in range(self.height):
            f = y / max(1, self.height - 1)
            color = tuple(int(a + (b - a) * f) for a, b in zip(top, bottom))
            pygame.draw.line(sky, color, (0, y), (self.width, y))
        return sky

    def _build_trees(self, sheet) -> Optional[pygame.Surface]:
        if sheet is None:
            return None
        return _scale_to_height(_region(sheet, TREE_REGION), int(self.height * 0.45))

    def _build_hills(self, sheet) -> Optional[pygame.Surface]:
        """Sits low enough that the tree layer's ground hides its flat bottom."""
        if sheet is None:
            return None
        hills = _scale_to_height(_region(sheet, HILL_REGION), int(self.height * 0.36))
        hills.set_alpha(145)
        return hills

    def _build_fog(self) -> pygame.Surface:
        fog = pygame.Surface((self.width + 300, self.height), pygame.SRCALPHA)
        for i in range(5):
            y = int(self.height * (0.62 + i * 0.07))
            pygame.draw.ellipse(fog, (130, 145, 165, 18 + i * 5),
                                pygame.Rect(0, y, self.width + 300, 70))
        return fog


def _load(name: str) -> Optional[pygame.Surface]:
    path = os.path.join(ASSET_DIR, name)
    if not os.path.exists(path):
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except pygame.error:
        return None


def _region(sheet: pygame.Surface, region: Tuple[int, int, int, int]) -> pygame.Surface:
    left, top, right, bottom = region
    return sheet.subsurface(pygame.Rect(left, top, right - left, bottom - top))


def _scale_to_height(image: pygame.Surface, height: int) -> pygame.Surface:
    width = int(image.get_width() * height / max(1, image.get_height()))
    return pygame.transform.smoothscale(image, (width, height))
