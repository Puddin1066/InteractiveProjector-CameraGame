"""
Pumpkin Slash: a Halloween slicing game for the projector wall.

The laptop camera faces the players, who stand a few steps back and swipe their
hands through the air; each hand is a glowing blade on the wall. Slice pumpkins,
candy and ghosts for points, chain quick slices for combos, and avoid skulls.
Two players share the wall: blades that start on the left score for team
Pumpkin, on the right for team Slime. Swipe the big pumpkin to start a round.

Keys: Q/Esc quit, R back to the start screen, Space start a round.
Dragging with the mouse button held also slices (for testing).
"""
import math
import random
import time
from typing import List, Tuple

import pygame

from tools import prepare_halloween_assets
from modules import config
from modules.halloween_theme import HalloweenArt, assets_present
from modules.halloween_ui import GHOST_WHITE, SIDES, draw_text, start_audio
from modules.particles import Effects
from modules.projector_app import ProjectorApp
from modules.screen_mapper import FACING_PLAYERS
from modules.slash import CANDY, GHOST, PUMPKIN, SKULL, START, BladeTracker, Phase, SlashRound
from modules.slice_effects import SliceBursts
from modules.teams import LEFT, RIGHT
from modules.treat_sprites import (CANDY_COLORS, DANGER_RED, PUMPKIN_ORANGE, candy_sprite, pumpkin_sprite,
                                   skull_sprite)

JUICE = {"pumpkin": PUMPKIN_ORANGE, "start": PUMPKIN_ORANGE, "candy": (240, 90, 170),
         "ghost": (220, 235, 255), "skull": DANGER_RED}
BLADE_TRAIL_SECONDS = 0.18
MOON_AT = (0.78, 0.17)  # clear of the title, the timer and the right-hand score


class PumpkinSlash:
    def __init__(self):
        if not assets_present():
            prepare_halloween_assets.main()

        self.app = ProjectorApp("Pumpkin Slash", default_facing=FACING_PLAYERS)
        self.screen = self.app.screen
        self.width, self.height = self.app.width, self.app.height
        self.art = HalloweenArt((self.width, self.height), moon_at=MOON_AT)
        self.round = SlashRound(self.width, self.height)
        self.blades = BladeTracker(self.width, self.height)
        self.clock = pygame.time.Clock()
        self.big_font = pygame.font.SysFont("Impact", int(self.height * 0.13))
        self.score_font = pygame.font.SysFont("Impact", int(self.height * 0.09))
        self.message_font = pygame.font.SysFont("Impact", int(self.height * 0.06))
        self.small_font = pygame.font.SysFont("Impact", int(self.height * 0.035))
        self.sprites = self._build_sprites()
        self.bursts = SliceBursts(self.height)
        self.effects = Effects(self.height)
        self.audio = None

        self.app.calibrate()

    def run(self):
        self.app.start_tracking()
        self.audio = start_audio(self.app.game_state)
        start = time.time()
        try:
            running = True
            while running:
                dt = min(self.clock.tick(config.FPS) / 1000.0, 0.05)
                running = self._handle_events()
                segments = self.blades.update(self._hand_samples(), time.time())
                for event in self.round.update(dt, segments):
                    self._on_event(event)
                self.bursts.update(dt)
                self.effects.update(dt)
                self._render(time.time() - start)
                running = self.app.show_camera_debug() and running
        except KeyboardInterrupt:
            pass
        finally:
            if self.audio:
                self.audio.stop()
            self.app.shutdown()
            pygame.quit()

    # Input
    def _handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    return False
                if event.key == pygame.K_r:
                    self.round.reset()
                elif event.key == pygame.K_SPACE and self.round.phase is not Phase.PLAYING:
                    self.round.start()
        return True

    def _hand_samples(self) -> List[Tuple[float, float, float]]:
        samples = [(p.x, p.y, p.timestamp) for p in self.app.pointers()]
        if pygame.mouse.get_focused() and pygame.mouse.get_pressed()[0]:
            samples.append((*pygame.mouse.get_pos(), time.time()))
        return samples

    # Game events: sound and effects
    def _on_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "slice":
            self._burst(event[1])
        elif kind == "combo":
            _, side, count = event
            self.effects.popup(f"COMBO x{count}!", SIDES[side]["color"], *self._side_anchor(side))
            self._play("pop")
        elif kind == "end":
            self.bursts.clear()
            self._play("pop")

    def _burst(self, hit) -> None:
        treat = hit.treat
        self._play("miss" if treat.kind is SKULL else "pop_wav")
        self.bursts.burst(treat, self._treat_image(treat, 0.0), hit.blade_angle, JUICE[treat.kind.name])
        if hit.points:
            text = f"+{hit.points}" if hit.points > 0 else f"{hit.points}"
            color = SIDES[hit.side]["color"] if hit.points > 0 else DANGER_RED
            self.effects.popup(text, color, treat.x, treat.y - treat.radius)

    def _side_anchor(self, side: str) -> Tuple[float, float]:
        for blade in self.blades.blades:
            if blade.side == side:
                return blade.tip
        return (self.width * (0.25 if side == LEFT else 0.75), self.height * 0.4)

    def _play(self, sound: str) -> None:
        if self.audio:
            self.audio.play_sound(sound, volume=0.6, priority="high")

    # Drawing
    def _render(self, t: float) -> None:
        self.art.draw_backdrop(self.screen, t)
        for treat in self.round.treats:
            image = self._treat_image(treat, t)
            self.screen.blit(image, image.get_rect(center=(treat.x, treat.y)))
        self.bursts.draw(self.screen)
        self._draw_blades()
        self.effects.draw(self.screen, self.message_font)
        self._draw_hud()
        pygame.display.flip()

    def _treat_image(self, treat, t: float) -> pygame.Surface:
        if treat.kind is GHOST and self.sprites["ghost"]:
            frames = self.sprites["ghost"]
            return frames[int(t * self.art.GHOST_FPS) % len(frames)]
        image = self.sprites[treat.kind.name]
        return pygame.transform.rotate(image, math.degrees(treat.angle)) if treat.angle else image

    def _draw_blades(self) -> None:
        now = time.time()
        for blade in self.blades.blades:
            color = SIDES[blade.side]["color"]
            trail = [(x, y) for x, y, ts in blade.points if now - ts <= BLADE_TRAIL_SECONDS]
            for i in range(1, len(trail)):
                width = max(3, int(self.height * 0.022 * i / len(trail)))
                pygame.draw.line(self.screen, color, trail[i - 1], trail[i], width)
            tip = blade.tip
            pygame.draw.circle(self.screen, color, tip, int(self.height * 0.025))
            pygame.draw.circle(self.screen, GHOST_WHITE, tip, int(self.height * 0.012))

    def _draw_hud(self) -> None:
        phase = self.round.phase
        if phase is Phase.READY:
            draw_text(self.screen, "SWIPE THE PUMPKIN TO START!", self.message_font, GHOST_WHITE,
                      (self.width / 2, self.height * 0.18))
            draw_text(self.screen, "Stand back, face the camera, and swipe your hand fast",
                      self.small_font, GHOST_WHITE, (self.width / 2, self.height * 0.80))
            return

        for side, fraction in ((LEFT, 0.12), (RIGHT, 0.88)):
            color = SIDES[side]["color"]
            draw_text(self.screen, str(self.round.scores[side]), self.score_font, color,
                      (self.width * fraction, self.height * 0.09))
            draw_text(self.screen, SIDES[side]["name"], self.small_font, color,
                      (self.width * fraction, self.height * 0.17))

        if phase is Phase.PLAYING:
            seconds = math.ceil(self.round.time_left)
            color = DANGER_RED if seconds <= 10 else GHOST_WHITE
            draw_text(self.screen, f"{seconds // 60}:{seconds % 60:02d}", self.score_font, color,
                      (self.width / 2, self.height * 0.09))
        else:
            winner = self.round.winner
            if winner is None:
                draw_text(self.screen, "It's a tie!", self.big_font, GHOST_WHITE,
                          (self.width / 2, self.height * 0.40))
            else:
                draw_text(self.screen, f"{SIDES[winner]['name']} team wins!", self.big_font,
                          SIDES[winner]["color"], (self.width / 2, self.height * 0.40))
            draw_text(self.screen, f"{self.round.scores[LEFT]}  -  {self.round.scores[RIGHT]}",
                      self.score_font, GHOST_WHITE, (self.width / 2, self.height * 0.56))

    # Sprites, drawn once at the size each treat is hit at
    def _build_sprites(self) -> dict:
        size = lambda kind: kind.radius * self.height
        return {
            "start": pumpkin_sprite(size(START)),
            "pumpkin": pumpkin_sprite(size(PUMPKIN)),
            "candy": candy_sprite(size(CANDY), random.choice(CANDY_COLORS)),
            "skull": skull_sprite(size(SKULL)),
            "ghost": self._ghost_frames(size(GHOST)),
        }

    def _ghost_frames(self, radius: float) -> List[pygame.Surface]:
        if not self.art.ghost_frames:
            return []
        frame_w, frame_h = self.art.ghost_frames[0].get_size()
        width = int(radius * 2.6)
        size = (width, int(width * frame_h / frame_w))
        return [pygame.transform.smoothscale(f, size) for f in self.art.ghost_frames]


if __name__ == "__main__":
    print("Starting Pumpkin Slash...")
    PumpkinSlash().run()
