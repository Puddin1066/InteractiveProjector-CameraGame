"""Polished Haunted Wall visual theme using CC0 OpenGameArt assets.

This subclasses the interaction engine in games/haunted_wall.py, so camera sensing,
calibration, collision logic, scoring, and projector behavior stay unchanged.
Only the visual rendering layer is replaced. If the CC0 files are absent, the
base procedural visuals are used automatically.
"""

from __future__ import annotations

import pygame

from games.haunted_wall import HauntedWall
from modules.halloween_theme import NIGHT_SKY, HalloweenArt


class CC0HauntedWall(HauntedWall):
    def __init__(self) -> None:
        super().__init__()
        self.art = HalloweenArt((self.width, self.height), sky=NIGHT_SKY)
        self.theme_ready = self.art.ready
        if self.theme_ready:
            print("Visual theme: CC0 graveyard + animated ghost sprites")
        else:
            print("Visual theme assets missing; using procedural fallback.")
            print("Run: python -m tools.prepare_halloween_assets")

    def _draw_background(self, t: float) -> None:
        if not self.theme_ready:
            return super()._draw_background(t)
        self.art.draw_backdrop(self.screen, t)

    def _draw_ghost(self, ghost) -> None:
        if not self.theme_ready:
            return super()._draw_ghost(ghost)

        frame = self.art.ghost_frame(pygame.time.get_ticks() / 1000.0, ghost.phase)
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
