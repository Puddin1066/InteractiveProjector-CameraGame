"""Confetti bursts and floating text popups."""
import math
import random
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import pygame

from .halloween_ui import draw_text

Color = Tuple[int, int, int]


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: Color
    size: float
    life: float
    spin: float = 0.0
    angle: float = 0.0


@dataclass
class Popup:
    text: str
    color: Color
    x: float
    y: float
    life: float


class Effects:
    def __init__(self, screen_height: int):
        self.height = screen_height
        self.particles: List[Particle] = []
        self.popups: List[Popup] = []

    def confetti(self, x: float, y: float, count: int, colors: Sequence[Color]) -> None:
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.15, 0.55) * self.height
            self.particles.append(Particle(
                x, y, math.cos(angle) * speed, math.sin(angle) * speed - 0.2 * self.height,
                random.choice(colors), random.uniform(0.008, 0.016) * self.height,
                random.uniform(0.8, 1.6), random.uniform(-8, 8)))

    def popup(self, text: str, color: Color, x: float, y: float) -> None:
        self.popups.append(Popup(text, color, x, y, 1.0))

    def update(self, dt: float) -> None:
        gravity = 0.6 * self.height
        for p in self.particles:
            p.vy += gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.angle += p.spin * dt
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0]
        for popup in self.popups:
            popup.y -= 0.1 * self.height * dt
            popup.life -= dt
        self.popups = [p for p in self.popups if p.life > 0]

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        for p in self.particles:
            rect = pygame.Rect(0, 0, p.size * 2, p.size)
            rect.center = (p.x, p.y)
            pygame.draw.ellipse(screen, p.color, rect.inflate(0, abs(math.sin(p.angle)) * p.size))
        for popup in self.popups:
            draw_text(screen, popup.text, font, popup.color, (popup.x, popup.y), int(255 * min(1.0, popup.life * 2)))
