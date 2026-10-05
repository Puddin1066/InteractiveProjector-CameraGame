"""Looping Halloween projection game driven by a Reolink RTSP camera.

The projector is the canvas; a person detector running on the camera feed is
the sensor. Camera detections are mapped into projector coordinates with the
repository's existing four-corner homography calibration.
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
from ultralytics import YOLO

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
    """Self-resetting spooky wall with broad body/silhouette interaction."""

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

        self.font = pygame.font.SysFont("Arial Rounded MT Bold", 34, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 20)
        self.big_font = pygame.font.SysFont("Arial Rounded MT Bold", 64, bold=True)

        self.camera = VideoSource.from_environment(
            fallback_camera_index=config.CAMERA_INDEX,
            width=config.CAMERA_WIDTH,
            height=config.CAMERA_HEIGHT,
            fps=config.CAMERA_FPS,
        )
        if not self.camera.isOpened():
            print(
                "Could not open camera source. Set REOLINK_RTSP_URL and verify "
                "that RTSP is enabled for this Reolink camera."
            )
            sys.exit(2)

        self.calibration_file = os.path.join(
            config.BASE_DIR, "haunted_wall_calibration.json"
        )
        self.transform_matrix = self._load_or_calibrate()

        model_name = os.getenv("HAUNTED_WALL_MODEL", "yolov8n.pt")
        self.detector = YOLO(model_name)
        self.person_confidence = float(os.getenv("PERSON_CONFIDENCE", "0.35"))
        self.detect_every_n_frames = max(
            1, int(os.getenv("DETECT_EVERY_N_FRAMES", "2"))
        )
        self.frame_number = 0
        self.person_polygons: List[np.ndarray] = []

        self.hit_cooldown = float(os.getenv("HIT_COOLDOWN_SECONDS", "0.35"))
        self.last_hit = 0.0
        self.ghosts: List[Ghost] = [self._spawn_ghost() for _ in range(8)]
        self.sparks: List[Spark] = []
        self.score = 0
        self.last_presence = 0.0
        self.start_time = time.time()
        self.running = True

    def _load_or_calibrate(self) -> np.ndarray:
        points, *_ = load_calibration_points(filename=self.calibration_file)
        if points and len(points) == 4:
            return get_perspective_transform(points, self.width, self.height)

        self._draw_calibration_field()
        print("Calibration: click the four projected corners in the camera window.")
        points = get_calibration_points(self.camera)
        if not points:
            print("Calibration cancelled.")
            sys.exit(3)

        save_calibration_points(points, filename=self.calibration_file)
        return get_perspective_transform(points, self.width, self.height)

    def _draw_calibration_field(self) -> None:
        self.screen.fill((8, 8, 16))
        border = max(14, min(self.width, self.height) // 45)
        pygame.draw.rect(
            self.screen,
            (255, 120, 20),
            (border, border, self.width - border * 2, self.height - border * 2),
            width=border,
        )
        for x, y in (
            (border * 2, border * 2),
            (self.width - border * 2, border * 2),
            (self.width - border * 2, self.height - border * 2),
            (border * 2, self.height - border * 2),
        ):
            pygame.draw.circle(self.screen, (255, 255, 255), (x, y), border)
        label = self.font.render("CALIBRATION", True, (255, 255, 255))
        self.screen.blit(label, (self.width // 2 - label.get_width() // 2, 50))
        pygame.display.flip()
        time.sleep(0.6)

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

    def _detect_people(self, frame: np.ndarray) -> List[np.ndarray]:
        """Return person bounding polygons transformed into projector space."""
        results = self.detector.predict(
            frame,
            imgsz=640,
            conf=self.person_confidence,
            classes=[0],
            device="cpu",
            verbose=False,
        )
        polygons: List[np.ndarray] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
                corners = np.float32([[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]])
                projected = cv2.perspectiveTransform(corners, self.transform_matrix)[0]
                polygons.append(projected.astype(np.int32))
        return polygons

    @staticmethod
    def _ghost_hits_person(ghost: Ghost, polygons: List[np.ndarray]) -> bool:
        point = (float(ghost.x), float(ghost.y))
        margin = float(ghost.radius * 0.55)
        for polygon in polygons:
            if cv2.pointPolygonTest(polygon, point, True) >= -margin:
                return True
        return False

    def _draw_background(self, t: float) -> None:
        self.screen.fill((5, 8, 18))
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
        for i in range(5):
            y = int(self.height * (0.70 + i * 0.045))
            wobble = int(math.sin(t * 0.55 + i) * 30)
            rect = pygame.Rect(-80 + wobble, y, self.width + 160, 35)
            pygame.draw.ellipse(
                self.screen,
                (18 + i * 2, 23 + i * 3, 34 + i * 3),
                rect,
            )
        for i in range(7):
            x = int((i + 0.5) * self.width / 7)
            y = self.height - 55
            r = 25 + (i % 3) * 4
            pygame.draw.circle(self.screen, (215, 75, 12), (x, y), r)
            pygame.draw.rect(
                self.screen,
                (55, 90, 30),
                (x - 4, y - r - 9, 8, 12),
            )
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
        ghost.hue = replacement.hue
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

    def _draw_debug_people(self) -> None:
        if os.getenv("HAUNTED_WALL_DEBUG", "0") != "1":
            return
        for polygon in self.person_polygons:
            pts = [(int(x), int(y)) for x, y in polygon]
            if len(pts) >= 3:
                pygame.draw.polygon(self.screen, (80, 220, 120), pts, width=3)

    def _draw_ui(self, active: bool) -> None:
        title = self.big_font.render("HAUNTED WALL", True, (245, 240, 215))
        self.screen.blit(title, (38, 24))
        prompt = "Move through the ghosts!" if active else "Come closer... the wall is watching."
        prompt_surface = self.font.render(prompt, True, (255, 150, 45))
        self.screen.blit(prompt_surface, (42, 98))
        score_surface = self.font.render(
            f"Ghosts scared away: {self.score}", True, (225, 245, 255)
        )
        self.screen.blit(score_surface, (42, 142))
        if os.getenv("HAUNTED_WALL_DEBUG", "0") == "1":
            source = self.small_font.render(
                f"Sensor: {self.camera.describe()} | people: {len(self.person_polygons)} | "
                "ESC quits | R recalibrates",
                True,
                (170, 180, 195),
            )
            self.screen.blit(source, (42, self.height - 34))

    def _recalibrate(self) -> None:
        self._draw_calibration_field()
        points = get_calibration_points(self.camera)
        if points:
            save_calibration_points(points, filename=self.calibration_file)
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
            if ok and frame is not None:
                self.frame_number += 1
                if self.frame_number % self.detect_every_n_frames == 0:
                    self.person_polygons = self._detect_people(frame)
                    if self.person_polygons:
                        self.last_presence = now

            active = now - self.last_presence < 4.0
            self._draw_background(now - self.start_time)
            for ghost in self.ghosts:
                ghost.update(self.width, self.height, dt)
                if (
                    self.person_polygons
                    and now - self.last_hit >= self.hit_cooldown
                    and self._ghost_hits_person(ghost, self.person_polygons)
                ):
                    self._burst(ghost)
                    self.last_hit = now
                self._draw_ghost(ghost)

            for spark in self.sparks:
                spark.update(dt)
            self.sparks = [s for s in self.sparks if s.life > 0]
            self._draw_sparks()
            self._draw_debug_people()
            self._draw_ui(active)
            pygame.display.flip()

        self.camera.release()
        pygame.quit()


if __name__ == "__main__":
    HauntedWall().run()
