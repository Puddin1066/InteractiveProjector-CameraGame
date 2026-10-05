"""Polished Haunted Wall visual theme using CC0 OpenGameArt assets.

This subclasses the interaction engine in haunted_wall.py, so camera sensing,
calibration, collision logic, scoring, and projector behavior stay unchanged.
Only the visual rendering layer is replaced. If the CC0 files are absent, the
base procedural visuals are used automatically.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import pygame

from haunted_wall import HauntedWall


class CC0HauntedWall(HauntedWall):
    def __init__(self) -> None:
        super().__init__()
        self.asset_dir = Path(__file__).resolve().parent / "assets" / "halloween_cc0"
        self.graveyard1 = self._load_image("graveyard1.png")
        self.graveyard2 = self._load_image("graveyard2.png")
        self.ghost_sheet = self._load_image("ghost_sheet.png")
        self.ghost_frames = self._slice_ghosts(self.ghost_sheet)
        self.theme_ready = bool(self.graveyard2 and self.ghost_frames)
        if self.theme_ready:
            print("Visual theme: CC0 graveyard + animated ghost sprites")
        else:
            print("Visual theme assets missing; using procedural fallback.")
            print("Run: python prepare_halloween_assets.py")

    def _load_image(self, name: str):
        path = self.asset_dir / name
        if not path.exists():
            return None
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except pygame.error:
            return None

    @staticmethod
    def _slice_ghosts(sheet):
        if sheet is None:
            return []
        frames = []
        cols, rows = 3, 5
        fw = sheet.get_width() // cols
        fh = sheet.get_height() // rows
        for row in range(rows):
            for col in range(cols):
                rect = pygame.Rect(col * fw, row * fh, fw, fh)
                frame = sheet.subsurface(rect).copy()
                frames.append(frame)
        return frames

    def _draw_background(self, t: float) -> None:
        if not self.theme_ready:
            return super()._draw_background(t)

        # Deep blue-black field with a soft moon; the CC0 graveyard layer is
        # placed over it and drifts slowly to make the projection feel alive.
        self.screen.fill((4, 7, 16))
        moon_x = int(self.width * 0.80)
        moon_y = int(self.height * 0.18)
        moon_r = max(70, int(min(self.width, self.height) * 0.10))
        pygame.draw.circle(self.screen, (232, 228, 188), (moon_x, moon_y), moon_r)
        pygame.draw.circle(
            self.screen,
            (4, 7, 16),
            (moon_x + moon_r // 3, moon_y - moon_r // 5),
            int(moon_r * 0.88),
        )

        # Graveyard2 contains transparent spooky tree/ground layers. Use the
        # lower half as a large foreground silhouette and drift it slightly.
        src = self.graveyard2
        lower = src.subsurface(
            pygame.Rect(0, src.get_height() // 2, src.get_width(), src.get_height() // 2)
        ).copy()
        scaled_h = int(self.height * 0.58)
        scaled_w = int(lower.get_width() * scaled_h / max(1, lower.get_height()))
        layer = pygame.transform.smoothscale(lower, (scaled_w, scaled_h))
        drift = int(math.sin(t * 0.08) * 35)
        y = self.height - scaled_h
        for x in range(-scaled_w + drift, self.width + scaled_w, scaled_w):
            self.screen.blit(layer, (x, y))

        # Dim parallax horizon using the upper part of Graveyard1.
        if self.graveyard1 is not None:
            src2 = self.graveyard1
            strip_h = max(1, int(src2.get_height() * 0.48))
            upper = src2.subsurface(pygame.Rect(0, 0, src2.get_width(), strip_h)).copy()
            far_h = int(self.height * 0.34)
            far_w = int(upper.get_width() * far_h / max(1, upper.get_height()))
            far = pygame.transform.smoothscale(upper, (far_w, far_h))
            far.set_alpha(145)
            far_y = int(self.height * 0.38)
            drift2 = int(math.sin(t * 0.045) * 18)
            for x in range(-far_w + drift2, self.width + far_w, far_w):
                self.screen.blit(far, (x, far_y))

        # Procedural fog remains because it works well under projection and
        # adds movement without depending on more external assets.
        fog = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for i in range(5):
            y = int(self.height * (0.62 + i * 0.07))
            wobble = int(math.sin(t * 0.45 + i) * 60)
            pygame.draw.ellipse(
                fog,
                (130, 145, 165, 18 + i * 5),
                pygame.Rect(-150 + wobble, y, self.width + 300, 70),
            )
        self.screen.blit(fog, (0, 0))

    def _draw_ghost(self, ghost) -> None:
        if not self.theme_ready:
            return super()._draw_ghost(ghost)

        # Animate through the CC0 sprite sheet at about 9 fps, offset per ghost
        # so the targets do not all flap in sync.
        frame_index = int((pygame.time.get_ticks() / 110.0) + ghost.phase * 2) % len(self.ghost_frames)
        frame = self.ghost_frames[frame_index]
        size = max(96, int(ghost.radius * 2.7))
        sprite = pygame.transform.smoothscale(frame, (size, size))
        if ghost.hit_flash > 0:
            sprite = sprite.copy()
            sprite.fill((255, 150, 55, 70), special_flags=pygame.BLEND_RGBA_ADD)
        rect = sprite.get_rect(center=ghost.center)
        self.screen.blit(sprite, rect)


if __name__ == "__main__":
    # Running this file directly uses the polished theme when assets exist and
    # automatically falls back to the original procedural renderer otherwise.
    CC0HauntedWall().run()
