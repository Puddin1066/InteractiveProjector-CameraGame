"""
Halloween Pong for the projector wall.

Each half of the wall belongs to one player: raise a hand on that side and a
glowing ghost hand follows it anywhere on that half; touch the ghost ball to send
it back. A side with no hand is played by the computer, so one person can play
alone and the game runs as a demo when nobody is playing.

Keys: Q/Esc quit, R restart the match, C recalibrate the camera.
Holding the mouse button on a side also steers that hand (for testing).
"""
import math
import time
from collections import deque

import pygame

from tools import prepare_halloween_assets
from modules import config
from modules.halloween_theme import HalloweenArt, assets_present
from modules.halloween_ui import GHOST_WHITE, SIDES, draw_text, start_audio
from modules.pong import Phase, PongMatch
from modules.projector_app import ProjectorApp
from modules.teams import LEFT, RIGHT, side_of

CENTER_LINE = (255, 200, 120)
TRAIL_LENGTH = 8
MOON_AT = (0.5, 0.20)  # behind the center line, clear of the scores
PLAYER_HOLD_SECONDS = 1.5  # a side stays with its player through brief tracking dropouts
HAND_GLOW = 8  # px of player color around each ghost hand


class HalloweenPong:
    def __init__(self):
        if not assets_present():
            prepare_halloween_assets.main()

        self.app = ProjectorApp("Halloween Pong")
        self.screen = self.app.screen
        self.width, self.height = self.app.width, self.app.height
        self.art = HalloweenArt((self.width, self.height), moon_at=MOON_AT)
        self.match = PongMatch(self.width, self.height)
        self.clock = pygame.time.Clock()
        self.score_font = pygame.font.SysFont("Impact", int(self.height * 0.12))
        self.message_font = pygame.font.SysFont("Impact", int(self.height * 0.06))
        self.label_font = pygame.font.SysFont("Impact", int(self.height * 0.035))
        self.ghost_sprites = self._scale_ghosts()
        self.hand_sprites = {side: self._make_hand_sprite(side) for side in SIDES}
        self.trail = deque(maxlen=TRAIL_LENGTH)
        self._last_seen = {LEFT: None, RIGHT: None}  # side -> (time, (x, y))
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
                targets = self._hand_targets()
                for event in self.match.update(dt, targets):
                    self._play_sound(event)
                self._render(time.time() - start, targets)
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
                    self.match.reset()
                elif event.key == pygame.K_c:
                    self.app.recalibrate()
        return True

    def _hand_targets(self) -> dict:
        """Player hand position per side, or None where the computer plays.
        A side keeps its last position for PLAYER_HOLD_SECONDS after the hand is lost."""
        now = time.monotonic()
        for side, position in self._hands_by_side().items():
            self._last_seen[side] = (now, position)

        targets = {}
        for side, last in self._last_seen.items():
            recent = last is not None and now - last[0] <= PLAYER_HOLD_SECONDS
            targets[side] = last[1] if recent else None
        return targets

    def _hands_by_side(self) -> dict:
        """The tracked hand on each half nearest that side's ghost hand."""
        positions = [(p.x, p.y) for p in self.app.pointers()]
        if pygame.mouse.get_focused() and pygame.mouse.get_pressed()[0]:
            positions.append(pygame.mouse.get_pos())

        nearest = {}
        for position in positions:
            side = side_of(position[0], self.width)
            hand = self.match.hands[side]
            current = nearest.get(side)
            if current is None or math.dist(position, (hand.x, hand.y)) < math.dist(current, (hand.x, hand.y)):
                nearest[side] = position
        return nearest

    # Sound
    def _play_sound(self, event: str) -> None:
        if not self.audio:
            return
        if event == "hit":
            self.audio.play_sound("pop_wav", volume=0.6, priority="high")
        elif event == "score":
            self.audio.play_miss_sound()
        elif event == "win":
            self.audio.play_pop_sound()

    # Drawing
    def _render(self, t: float, targets: dict) -> None:
        self.art.draw_backdrop(self.screen, t)
        self._draw_center_line()
        for side, hand in self.match.hands.items():
            sprite = self.hand_sprites[side]
            self.screen.blit(sprite, sprite.get_rect(center=(hand.x, hand.y)))
        self._draw_ball(t)
        self._draw_scores()
        self._draw_labels(targets)
        self._draw_message(targets)
        pygame.display.flip()

    def _draw_center_line(self) -> None:
        dash, gap, x = int(self.height * 0.03), int(self.height * 0.025), self.width // 2
        for y in range(0, self.height, dash + gap):
            pygame.draw.rect(self.screen, CENTER_LINE, (x - 3, y, 6, dash), border_radius=3)

    def _make_hand_sprite(self, side: str) -> pygame.Surface:
        """Open ghost hand, fingers up, glowing in the side's color, sized to the hit radius.
        The thumb points toward the center line."""
        r = self.match.hands[side].radius
        size = int(2 * (r + HAND_GLOW))
        sprite = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = cy = size / 2
        thumb_side = 1 if side == LEFT else -1
        fingers = [(-0.42, 0.62), (-0.14, 0.74), (0.14, 0.70), (0.42, 0.56)]  # (x offset, length)

        for color, grow in ((SIDES[side]["color"], HAND_GLOW), (GHOST_WHITE, 0)):
            palm = pygame.Rect(0, 0, 1.12 * r + 2 * grow, 0.95 * r + 2 * grow)
            palm.center = (cx, cy + 0.28 * r)
            pygame.draw.ellipse(sprite, color, palm)
            width = 0.26 * r + 2 * grow
            for dx, length in fingers:
                finger = pygame.Rect(0, 0, width, length * r + 2 * grow)
                finger.midbottom = (cx + dx * r * thumb_side, cy + 0.15 * r)
                pygame.draw.rect(sprite, color, finger, border_radius=int(width / 2))
            thumb_base = (cx + 0.40 * r * thumb_side, cy + 0.42 * r)
            thumb_tip = (cx + 0.85 * r * thumb_side, cy + 0.02 * r)
            pygame.draw.line(sprite, color, thumb_base, thumb_tip, int(width))
            pygame.draw.circle(sprite, color, thumb_tip, width / 2)
        return sprite

    def _draw_ball(self, t: float) -> None:
        ball = self.match.ball
        self.trail.append((ball.x, ball.y))
        for i, (x, y) in enumerate(self.trail):
            alpha = int(90 * (i + 1) / len(self.trail))
            radius = int(ball.radius * (0.4 + 0.5 * (i + 1) / len(self.trail)))
            mist = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(mist, (235, 245, 255, alpha), (radius, radius), radius)
            self.screen.blit(mist, (x - radius, y - radius))

        if not self.ghost_sprites:
            pygame.draw.circle(self.screen, SIDES[LEFT]["color"], (ball.x, ball.y), ball.radius)
            return
        frames = self.ghost_sprites["right" if ball.vx > 0 else "left"]
        frame = frames[int(t * self.art.GHOST_FPS) % len(frames)]
        self.screen.blit(frame, frame.get_rect(center=(ball.x, ball.y)))

    def _draw_scores(self) -> None:
        for side, fraction in ((LEFT, 0.25), (RIGHT, 0.75)):
            self._draw_text(str(self.match.scores[side]), self.score_font,
                            SIDES[side]["color"], (self.width * fraction, self.height * 0.10))

    def _draw_labels(self, targets: dict) -> None:
        for side, fraction in ((LEFT, 0.25), (RIGHT, 0.75)):
            who = "player" if targets[side] is not None else "computer"
            self._draw_text(f"{SIDES[side]['name']}: {who}", self.label_font,
                            SIDES[side]["color"], (self.width * fraction, self.height * 0.19))

    def _draw_message(self, targets: dict) -> None:
        center = (self.width / 2, self.height * 0.32)
        if self.match.phase is Phase.WON:
            side = SIDES[self.match.winner]
            self._draw_text(f"{side['name']} side wins!", self.score_font, side["color"], center)
        elif targets[LEFT] is None and targets[RIGHT] is None:
            self._draw_text("Raise a hand on either side to play", self.message_font, GHOST_WHITE, center)

    def _draw_text(self, text, font, color, center) -> None:
        draw_text(self.screen, text, font, color, center)

    def _scale_ghosts(self) -> dict:
        """Ghost frames sized to the ball, facing each direction (the art faces left)."""
        if not self.art.ghost_frames:
            return {}
        width = int(self.match.ball.radius * 3.2)
        frame_w, frame_h = self.art.ghost_frames[0].get_size()
        size = (width, int(width * frame_h / frame_w))
        left = [pygame.transform.smoothscale(f, size) for f in self.art.ghost_frames]
        return {"left": left, "right": [pygame.transform.flip(f, True, False) for f in left]}


if __name__ == "__main__":
    print("Starting Halloween Pong...")
    HalloweenPong().run()
