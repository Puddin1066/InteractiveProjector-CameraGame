"""Treats for the slicing games, drawn in code at the size they are hit at."""
from typing import Tuple

import pygame

Color = Tuple[int, int, int]
PUMPKIN_ORANGE: Color = (245, 120, 20)
PUMPKIN_DARK: Color = (190, 75, 10)
STEM_GREEN: Color = (70, 120, 40)
FACE_GLOW: Color = (255, 220, 90)
CANDY_COLORS = ((235, 60, 140), (130, 70, 220), (60, 200, 220))
CANDY_STRIPE: Color = (240, 232, 210)
SKULL_WHITE: Color = (235, 235, 225)
DANGER_RED: Color = (230, 30, 40)
DARK: Color = (25, 10, 20)
GHOST_BODY: Color = (238, 232, 255)
GHOST_EDGE: Color = (120, 85, 190)
BLUSH: Color = (255, 170, 200)
COIN_GOLD: Color = (255, 205, 50)
COIN_EDGE: Color = (200, 140, 20)
LYNX_GREEN: Color = (0, 122, 61)


def _canvas(radius: float, pad: float = 1.25) -> Tuple[pygame.Surface, float]:
    size = int(radius * 2 * pad)
    return pygame.Surface((size, size), pygame.SRCALPHA), size / 2


def pumpkin_sprite(radius: float) -> pygame.Surface:
    """Jack-o'-lantern: ribbed orange body, stem, glowing face."""
    surface, c = _canvas(radius)
    body = pygame.Rect(0, 0, radius * 2.1, radius * 1.8)
    body.center = (c, c + radius * 0.1)
    pygame.draw.ellipse(surface, PUMPKIN_DARK, body)
    for inset in (0.0, 0.32, 0.62):
        rib = body.inflate(-body.width * inset, -radius * 0.08)
        pygame.draw.ellipse(surface, PUMPKIN_ORANGE, rib)
        pygame.draw.ellipse(surface, PUMPKIN_DARK, rib, max(2, int(radius * 0.05)))
    stem = pygame.Rect(0, 0, radius * 0.28, radius * 0.45)
    stem.midbottom = (c, body.top + radius * 0.12)
    pygame.draw.rect(surface, STEM_GREEN, stem, border_radius=int(radius * 0.08))

    eye = radius * 0.28
    for dx in (-0.42, 0.42):
        ex, ey = c + dx * radius, c - radius * 0.12
        pygame.draw.polygon(surface, FACE_GLOW, [(ex - eye, ey + eye * 0.7), (ex + eye, ey + eye * 0.7), (ex, ey - eye * 0.8)])
    pygame.draw.polygon(surface, FACE_GLOW, [(c - radius * 0.12, c + radius * 0.18), (c + radius * 0.12, c + radius * 0.18), (c, c)])
    mouth_y = c + radius * 0.42
    teeth = [(c + radius * (x / 10), mouth_y + (radius * 0.14 if i % 2 else 0))
             for i, x in enumerate(range(-6, 7, 2))]
    pygame.draw.polygon(surface, FACE_GLOW, [(c - radius * 0.65, mouth_y - radius * 0.1)] + teeth
                        + [(c + radius * 0.65, mouth_y - radius * 0.1), (c, mouth_y + radius * 0.35)])
    return surface


def candy_sprite(radius: float, color: Color) -> pygame.Surface:
    """Wrapped sweet with twisted ends."""
    surface, c = _canvas(radius, pad=1.6)
    for side in (-1, 1):
        tip = c + side * radius * 1.55
        pygame.draw.polygon(surface, color, [(c + side * radius * 0.6, c), (tip, c - radius * 0.65), (tip, c + radius * 0.65)])
    body = pygame.Rect(0, 0, radius * 1.6, radius * 1.2)
    body.center = (c, c)
    pygame.draw.ellipse(surface, color, body)
    for dx in (-0.35, 0.0, 0.35):
        x = c + dx * radius
        pygame.draw.line(surface, CANDY_STRIPE, (x - radius * 0.15, c - radius * 0.5), (x + radius * 0.15, c + radius * 0.5),
                         max(2, int(radius * 0.12)))
    return surface


def skull_sprite(radius: float) -> pygame.Surface:
    """Skull with a red warning glow: slicing it costs points."""
    surface, c = _canvas(radius, pad=1.35)
    pygame.draw.circle(surface, (*DANGER_RED, 120), (c, c), radius * 1.3)
    pygame.draw.circle(surface, SKULL_WHITE, (c, c - radius * 0.12), radius * 0.9)
    jaw = pygame.Rect(0, 0, radius * 1.0, radius * 0.6)
    jaw.midtop = (c, c + radius * 0.35)
    pygame.draw.rect(surface, SKULL_WHITE, jaw, border_radius=int(radius * 0.15))
    for dx in (-0.35, 0.35):
        pygame.draw.circle(surface, DARK, (c + dx * radius, c - radius * 0.1), radius * 0.24)
    pygame.draw.polygon(surface, DARK, [(c, c + radius * 0.12), (c - radius * 0.1, c + radius * 0.32), (c + radius * 0.1, c + radius * 0.32)])
    for dx in (-0.25, 0.0, 0.25):
        pygame.draw.line(surface, DARK, (c + dx * radius, c + radius * 0.6), (c + dx * radius, c + radius * 0.9),
                         max(2, int(radius * 0.06)))
    return surface


def ghost_sprite(radius: float) -> pygame.Surface:
    """Friendly sheet ghost with a purple edge, so it shows on a bright wall."""
    surface, c = _canvas(radius, pad=1.3)
    edge = max(3, int(radius * 0.08))
    top, bottom, half = c - radius, c + radius, radius * 0.85
    scallops = 4
    hem = [(c - half + 2 * half * (i + 0.5) / scallops, bottom - radius * 0.12) for i in range(scallops)]
    for color, grow in ((GHOST_EDGE, edge), (GHOST_BODY, 0)):
        pygame.draw.circle(surface, color, (c, top + half), half + grow)
        pygame.draw.rect(surface, color, pygame.Rect(c - half - grow, top + half, 2 * (half + grow), radius * 1.0))
        for x, y in hem:
            pygame.draw.circle(surface, color, (x, y), half / scallops + grow)
    for dx in (-0.32, 0.32):
        eye = pygame.Rect(0, 0, radius * 0.24, radius * 0.34)
        eye.center = (c + dx * radius, c - radius * 0.22)
        pygame.draw.ellipse(surface, DARK, eye)
        pygame.draw.circle(surface, GHOST_BODY, (eye.centerx - radius * 0.04, eye.top + radius * 0.09), radius * 0.05)
        pygame.draw.circle(surface, BLUSH, (c + dx * radius * 1.45, c + radius * 0.05), radius * 0.1)
    mouth = pygame.Rect(0, 0, radius * 0.26, radius * 0.3)
    mouth.center = (c, c + radius * 0.12)
    pygame.draw.ellipse(surface, DARK, mouth)
    return surface


def lynx_coin_sprite(radius: float) -> pygame.Surface:
    """Golden coin with a Lincoln-green lynx face: the rare bonus treat."""
    surface, c = _canvas(radius, pad=1.3)
    pygame.draw.circle(surface, (*COIN_GOLD, 90), (c, c), radius * 1.25)
    pygame.draw.circle(surface, COIN_EDGE, (c, c), radius)
    pygame.draw.circle(surface, COIN_GOLD, (c, c), radius * 0.88)
    face = radius * 0.55
    for side in (-1, 1):
        base = c + side * face * 0.55
        ear = [(base - face * 0.32, c - face * 0.45), (base + face * 0.32, c - face * 0.45),
               (base + side * face * 0.2, c - face * 1.25)]
        pygame.draw.polygon(surface, LYNX_GREEN, ear)
        tip = ear[2]
        pygame.draw.line(surface, DARK, tip, (tip[0] + side * face * 0.08, tip[1] - face * 0.35), max(2, int(radius * 0.06)))
    pygame.draw.circle(surface, LYNX_GREEN, (c, c + face * 0.1), face * 0.85)
    for side in (-1, 1):
        eye = pygame.Rect(0, 0, face * 0.38, face * 0.26)
        eye.center = (c + side * face * 0.36, c - face * 0.05)
        pygame.draw.ellipse(surface, COIN_GOLD, eye)
        pygame.draw.ellipse(surface, DARK, eye.inflate(-eye.width * 0.7, 0))
    nose = face * 0.14
    pygame.draw.polygon(surface, BLUSH, [(c - nose, c + face * 0.28), (c + nose, c + face * 0.28), (c, c + face * 0.28 + nose)])
    return surface
