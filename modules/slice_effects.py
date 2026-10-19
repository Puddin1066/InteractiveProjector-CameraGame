"""Sliced treats: two halves fly apart across the cut, with a splash of juice."""
import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

Color = Tuple[int, int, int]


@dataclass
class Piece:
    """Half of a sliced treat, or a juice drop (image is None), flying off."""
    image: Optional[pygame.Surface]
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    spin: float
    life: float
    color: Color = (0, 0, 0)
    radius: float = 0.0


class SliceBursts:
    PIECE_LIFE = 1.2
    DROP_LIFE = 0.6
    DROPS = 14

    def __init__(self, screen_height: int):
        self.height = screen_height
        self.pieces: List[Piece] = []

    def burst(self, treat, image: pygame.Surface, cut_angle: float, juice: Color) -> None:
        width, height = image.get_size()
        push = 0.35 * self.height
        normal = (-math.sin(cut_angle), math.cos(cut_angle))
        for half, sign in ((pygame.Rect(0, 0, width // 2, height), -1),
                           (pygame.Rect(width // 2, 0, width - width // 2, height), 1)):
            self.pieces.append(Piece(
                image.subsurface(half).copy(), treat.x + sign * width / 4, treat.y,
                treat.vx * 0.5 + sign * normal[0] * push, treat.vy * 0.3 + sign * normal[1] * push - 0.2 * self.height,
                treat.angle, sign * random.uniform(90, 200), self.PIECE_LIFE,
            ))
        for _ in range(self.DROPS):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.2, 0.6) * self.height
            self.pieces.append(Piece(None, treat.x, treat.y, math.cos(angle) * speed, math.sin(angle) * speed,
                                     0, 0, self.DROP_LIFE, juice, random.uniform(0.006, 0.014) * self.height))

    def clear(self) -> None:
        self.pieces.clear()

    def update(self, dt: float) -> None:
        gravity = 1.5 * self.height
        for piece in self.pieces:
            piece.vy += gravity * dt
            piece.x += piece.vx * dt
            piece.y += piece.vy * dt
            piece.angle += piece.spin * dt
            piece.life -= dt
        self.pieces = [p for p in self.pieces if p.life > 0]

    def draw(self, screen: pygame.Surface) -> None:
        for piece in self.pieces:
            fade = max(0.0, piece.life / self.PIECE_LIFE)
            if piece.image is None:
                pygame.draw.circle(screen, piece.color, (piece.x, piece.y), max(1, piece.radius * fade * 1.6))
                continue
            image = pygame.transform.rotate(piece.image, piece.angle)
            image.set_alpha(int(255 * min(1.0, fade * 2)))
            screen.blit(image, image.get_rect(center=(piece.x, piece.y)))
