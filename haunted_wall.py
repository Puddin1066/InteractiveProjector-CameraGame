"""Looping Halloween projection game driven by Reolink/RTSP motion sensing.

The projector is treated as the canvas and the camera as a coarse, invisible
touch surface. Motion in the camera view is warped into projector coordinates
using the repo's existing four-corner homography calibration.
"""

from __future__ import annotations

import math
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np
import pygame
from screeninfo import get_monitors

from modules import config
from modules.calibration import (
    get_calibration_points,
    get_perspective_transform,
    load_calibration_points,
    save_calibration_points,
)
from modules.video_source import VideoSource


Color = Tuple[int, int, int]


@dataclass
class Ghost:
    x: float
    y: float
    radius: int
    vx: float
    vy: float
    phase: float
    hue: int = 0
    hit_flash: float = 0.0

    def update(self, width: int, height: int, dt: float) -> None:
        self.phase += dt * 2.0
        self.x += self.vx * dt
        self.y += (self.vy + math.sin(self.phase) * 12.0) * dt

        if self.x < self.radius or self.x > width - self.radius:
            self.vx *= -1
            self.x = max(self.radius, min(width - self.radius, self.x))
        if self.y < self.radius or self.y > height - self.radius:
            self.vy *= -1
            self.y = max(self.radius, min(height - self.radius, self.y))

        self.hit_flash = max(0.0, self.hit_flash - dt)

    @property
    def center(self) -> Tuple[int, int]:
        return int(self.x), int(self.y)


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: float

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 80 * dt
        self.life -= dt


class HauntedWall:
    """Self-resetting spooky wall with broad motion-based interactions."""

    def __init__(self) -> None:
        os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
        pygame.init()
        pygame.display.set_caption("Haunted Wall")

        monitors = get_monitors()
        display_index = int(os.getenv("PROJECTOR_MONITOR_INDEX", "1"))
        if len(monitors) <= display_index:
            print(
                f"Projector monitor index {display_index} not found. "
                f"Detected {len(monitors)} monitor(s). Connect the MoGo over HDMI."
            )
            sys.exit(1)

        projector = monitors[display_index]
        os.environ["SDL_VIDEO_WINDOW_POS"] = f"{projector.x},{projector.y}"
        self.width = projector.width
        self.height = projector.height
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.NOFRAME)
        self.clock = pygame.time.Clock()

        self.camera = VideoSource.from_environment(
            fallback_camera_index=config.CAMERA_INDEX,
            width=config.CAMERA_WIDTH,
            height=config.CAMERA_HEIGHT,
            fps=config.CAMERA_FPS,
        )
        if not self.camera.isOpened():
            print(
                "Could not open camera source. Set REOLINK_RTSP_URL in your shell "
                "or .env-compatible launcher and verify RTSP is enabled."
            )
            sys.exit(2)

        self.transform_matrix = self._load_or_calibrate()

        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=250, varThreshold=32, detectShadows=False
        )
        self.motion_threshold = int(os.getenv("MOTION_THRESHOLD", "45"))
        self.minimum_motion_pixels = int(os.getenv("MINIMUM_MOTION_PIXELS", "900"))
        self.hit_cooldown = float(os.getenv("HIT_COOLDOWN_SECONDS", "0.28"))
        self.last_hit = 0.0

        self.ghosts: List[Ghost] = [self._spawn_ghost() for _ in range(8)]
        self.sparks: List[Spark] = []
        self.score = 0
        self.last_presence = time.time()
        self.start_time = time.time()
        self.running = True

        self.font = pygame.font.SysFont("Arial Rounded MT Bold", 34, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 20)
        self.big_font = pygame.font.SysFont("Arial Rounded MT Bold", 64, bold=True)

    def _load_or_calibrate(self) -> np.ndarray:
        points, *_ = load_calibration_points()
        if points and len(points) == 4:
            return get_perspective_transform(points, self.width, self.height)

        # Bright calibration field so the projected rectangle is easy to see
        # inside the camera feed.
        self.screen.fill((8, 8, 16))
        border = max(14, min(self.width, self.height) // 45)
        pygame.draw.rect(
            self.screen,
            (255, 120, 20),
            (border, border, self.width - border * 2, self.height - border * 2),
            width=border,
        )
        label = self.font.render("CALIBRATION", True, (255, 255, 255))
        self.screen.blit(label, (self.width // 2 - label.get_width() // 2, 50))
        pygame.display.flip()
        time.sleep(0.6)

        print("Calibration: click the four projected corners in the camera window.")
        points = get_calibration_points(self.camera)
        if not points:
            print("Calibration cancelled.")
            sys.exit(3)

        save_calibration_points(points)
        return get_perspective_transform(points, self.width, self.height)

    def _spawn_ghost(self) -> Ghost:
        margin = 90
        return Ghost(
            x=random.uniform(margin, max(margin + 1, self.width - margin)),
            y=random.uniform(margin, max(margin + 1, self.height - margin)),
            radius=random.randint(46, 78),
            vx=random.choice([-1, 1]) * random.uniform(35, 85),
            vy=random.uniform(-18, 18),
            phase=random.uniform(0, math.tau),
            hue=random.randint(0, 2),
        )

    def _draw_background(self, t: float) -> None:
        self.screen.fill((5, 8, 18))

        # Moon
        moon_x = int(self.width * 0.82)
        moon_y = int(self.height * 0.17)
        moon_r = max(48, int(min(self.width, self.height) * 0.07))
        pygame.draw.circle(self.screen, (245, 240, 190), (moon_x, moon_y), moon_r)
        pygame.draw.circle(
            self.screen,
            (5, 8, 18),
            (moon_x + moon_r // 3, moon_y - moon_r // 5),
            int(moon_r * 0.9),
        )

        # Simple pulsing fog bands.
        for i in range(5):
            y = int(self.height * (0.70 + i * 0.045))
            wobble = int(math.sin(t * 0.55 + i) * 30)
            rect = pygame.Rect(-80 + wobble, y, self.width + 160, 35)
            pygame.draw.ellipse(self.screen, (18 + i * 2, 23 + i * 3, 34 + i * 3), rect)

        # Decorative pumpkins along the bottom.
        for i in range(7):
            x = int((i + 0.5) * self.width / 7)
            y = self.height - 55
            r = 25 + (i % 3) * 4
            pygame.draw.circle(self.screen, (215, 75, 12), (x, y), r)
            pygame.draw.rect(self.screen, (55, 90, 30), (x - 4, y - r - 9, 8, 12))
            eye_y = y - 5
            pygame.draw.polygon(
                self.screen,
                (255, 210, 60),
                [(x - 13, eye_y), (x - 5, eye_y - 8), (x - 4, eye_y + 3)],
            )
            pygame.draw.polygon(
                self.screen,
                (255, 210, 60),
                [(x + 13, eye_y), (x + 5, eye_y - 8), (x + 4, eye_y + 3)],
            )

    def _draw_ghost(self, ghost: Ghost) -> None:
        x, y = ghost.center
        r = ghost.radius
        palette: List[Color] = [
            (225, 245, 255),
            (210, 255, 220),
            (245, 220, 255),
        ]
        body = (255, 150, 40) if ghost.hit_flash > 0 else palette[ghost.hue]

        pygame.draw.circle(self.screen, body, (x, y - r // 4), r)
        pygame.draw.rect(self.screen, body, (x - r, y - r // 4, r * 2, r))
        for dx in (-r * 2 // 3, 0, r * 2 // 3):
            pygame.draw.circle(self.screen, body, (x + dx, y + r * 3 // 4), r // 3)

        eye_r = max(5, r // 10)
        pygame.draw.circle(self.screen, (20, 20, 35), (x - r // 3, y - r // 4), eye_r)
        pygame.draw.circle(self.screen, (20, 20, 35), (x + r // 3, y - r // 4), eye_r)
        mouth = pygame.Rect(x - r // 6, y + r // 8, r // 3, r // 3)
        pygame.draw.ellipse(self.screen, (20, 20, 35), mouth)

    def _motion_mask_in_projector_space(self, frame: np.ndarray) -> np.ndarray:
        raw = self.bg_subtractor.apply(frame)
        raw = cv2.medianBlur(raw, 7)
        _, raw = cv2.threshold(raw, self.motion_threshold, 255, cv2.THRESH_BINARY)
        kernel = np.ones((7, 7), np.uint8)
        raw = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, kernel, iterations=2)

        return cv2.warpPerspective(
            raw,
            self.transform_matrix,
            (self.width, self.height),
            flags=cv2.INTER_NEAREST,
        )

    def _ghost_hit(self, mask: np.ndarray, ghost: Ghost) -> bool:
        x, y = ghost.center
        r = int(ghost.radius * 0.85)
        x0, x1 = max(0, x - r), min(self.width, x + r)
        y0, y1 = max(0, y - r), min(self.height, y + r)
        if x1 <= x0 or y1 <= y0:
            return False

        roi = mask[y0:y1, x0:x1]
        if roi.size == 0:
            return False
        return cv2.countNonZero(roi) >= self.minimum_motion_pixels

    def _burst(self, ghost: Ghost) -> None:
        ghost.hit_flash = 0.18
        for _ in range(18):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(80, 260)
            self.sparks.append(
                Spark(
                    ghost.x,
                    ghost.y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    random.uniform(0.35, 0.8),
                )
            )

        replacement = self._spawn_ghost()
        ghost.x, ghost.y = replacement.x, replacement.y
        ghost.vx, ghost.vy = replacement.vx, replacement.vy
        ghost.radius = replacement.radius
        self.score += 1

    def _draw_sparks(self) -> None:
        for spark in self.sparks:
            if spark.life > 0:
                pygame.draw.circle(
                    self.screen,
                    (255, 185, 55),
                    (int(spark.x), int(spark.y)),
                    max(2, int(6 * spark.life)),
                )

    def _draw_ui(self, active: bool) -> None:
        title = self.big_font.render("HAUNTED WALL", True, (245, 240, 215))
        self.screen.blit(title, (38, 24))

        if active:
            prompt = "Wave, jump and swat the ghosts!"
        else:
            prompt = "Come closer... the wall is watching."
        prompt_surface = self.font.render(prompt, True, (255, 150, 45))
        self.screen.blit(prompt_surface, (42, 98))

        score_surface = self.font.render(
            f"Ghosts scared away: {self.score}", True, (225, 245, 255)
        )
        self.screen.blit(score_surface, (42, 142))

        if os.getenv("HAUNTED_WALL_DEBUG", "0") == "1":
            source = self.small_font.render(
                f"Sensor: {self.camera.describe()} | ESC quits | R recalibrates",
                True,
                (170, 180, 195),
            )
            self.screen.blit(source, (42, self.height - 34))

    def _recalibrate(self) -> None:
        self.screen.fill((8, 8, 16))
        pygame.display.flip()
        points = get_calibration_points(self.camera)
        if points:
            save_calibration_points(points)
            self.transform_matrix = get_perspective_transform(points, self.width, self.height)

    def run(self) -> None:
        print(f"Sensor: {self.camera.describe()}")
        print("Haunted Wall started. ESC quits; R recalibrates.")

        while self.running:
            dt = self.clock.tick(60) / 1000.0
            now = time.time()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_r:
                        self._recalibrate()

            ok, frame = self.camera.read()
            mask = None
            if ok and frame is not None:
                mask = self._motion_mask_in_projector_space(frame)
                if cv2.countNonZero(mask) > self.minimum_motion_pixels * 2:
                    self.last_presence = now

            active = now - self.last_presence < 4.0
            self._draw_background(now - self.start_time)

            for ghost in self.ghosts:
                ghost.update(self.width, self.height, dt)
                if (
                    mask is not None
                    and now - self.last_hit >= self.hit_cooldown
                    and self._ghost_hit(mask, ghost)
                ):
                    self._burst(ghost)
                    self.last_hit = now
                self._draw_ghost(ghost)

            for spark in self.sparks:
                spark.update(dt)
            self.sparks = [s for s in self.sparks if s.life > 0]
            self._draw_sparks()
            self._draw_ui(active)

            pygame.display.flip()

        self.camera.release()
        pygame.quit()


if __name__ == "__main__":
    HauntedWall().run()
