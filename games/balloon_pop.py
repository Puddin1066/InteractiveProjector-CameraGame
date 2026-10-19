"""
Threaded Interactive Projector Camera Game
Multi-threaded implementation for improved performance and responsiveness.

Threading Architecture:
- Main Thread: Game logic, rendering, UI events
- Camera Thread: Continuous frame capture
- Pointer Tracking Thread: Hand (or ball) detection mapped onto the projector
- Audio Thread: Sound effects processing
"""
import pygame
import cv2
import sys
import os
import time
import logging

# Local imports
from modules import config
from modules.background import draw_text_with_bg
from modules.boom_animation import generate_boom_frames
from modules.cloud import Cloud
from modules.pop_score import ScorePopup
from modules.balloon import Balloon
from modules.effects import CrackEffect, MissEffect

# Threading modules
from modules.projector_app import ProjectorApp
from modules.audio_manager_thread import AudioManager

# Suppress logging
os.environ["YOLO_VERBOSE"] = "False"
logging.getLogger('ultralytics').setLevel(logging.CRITICAL)
_cv_logging = getattr(getattr(cv2, "utils", None), "logging", None)
if _cv_logging is not None and hasattr(_cv_logging, "setLogLevel"):
    _cv_logging.setLogLevel(getattr(_cv_logging, "LOG_LEVEL_SILENT", 0))
elif hasattr(cv2, "setLogLevel"):
    cv2.setLogLevel(0)

# Constants (config-driven)
SCREEN_WIDTH = config.SCREEN_WIDTH
SCREEN_HEIGHT = config.SCREEN_HEIGHT
FPS = config.FPS
CLICK_COOLDOWN = config.CLICK_COOLDOWN
BALLOON_FILES = config.BALLOON_FILES
GAME_DURATION = config.GAME_DURATION
POINTER_HOLD_TO_START = config.POINTER_HOLD_TO_START
CRACK_PATH = config.CRACK_PATH
MISS_PATH = config.MISS_PATH
BACKGROUND_IMAGE_PATH = config.BACKGROUND_IMAGE_PATH
CALIBRATION_FILE = config.CALIBRATION_FILE
ASSETS_DIR = config.ASSETS_DIR
BASE_DIR = config.BASE_DIR


class ThreadedBalloonGame:
    """Main game class with multi-threading support"""
    
    def __init__(self):
        # Initialize game state manager
        self.app = ProjectorApp("Threaded Balloon Popping Game")
        self.game_state = self.app.game_state
        self.screen = self.app.screen
        self.external_screen = self.app.monitor
        self.actual_width, self.actual_height = self.app.width, self.app.height
        self.clock = pygame.time.Clock()

        self.audio_thread = None
        self.pointer_held_since = None
        
        self._load_assets()
        self.app.calibrate()
        self._init_game_objects()
        
        # Performance monitoring
        self.fps_counter = 0
        self.fps_start_time = time.time()
        
    def _load_assets(self):
        """Load game assets (images, sounds, etc.)"""
        # Load balloon images
        self.balloon_images = []
        for file in BALLOON_FILES:
            path = os.path.join(ASSETS_DIR, file)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    img = pygame.transform.scale(img, (420, 480))
                    self.balloon_images.append(img)
                except pygame.error as e:
                    print(f"Warning: Failed to load {path}: {e}")
        
        if not self.balloon_images:
            print("Error: No valid balloon images loaded")
            sys.exit(1)
        
        # Load effect images
        try:
            base_crack = pygame.image.load(CRACK_PATH).convert_alpha()
            base_crack = pygame.transform.scale(base_crack, (200, 120))
            self.boom_frames = generate_boom_frames(base_crack, num_frames=6)
            
            miss_image = pygame.image.load(MISS_PATH).convert_alpha()
            miss_image = pygame.transform.scale(miss_image, (150, 100))
            self.miss_frames = generate_boom_frames(miss_image, num_frames=6)
            
        except Exception as e:
            print(f"Error loading effect images: {e}")
            sys.exit(1)
        
        # Load background and UI elements
        try:
            self.background_image = pygame.image.load(BACKGROUND_IMAGE_PATH).convert()
            self.background_image = pygame.transform.scale(
                self.background_image, 
                (self.external_screen.width, self.external_screen.height)
            )
            
            # Load cloud images
            cloud_image1 = pygame.image.load(os.path.join(ASSETS_DIR, "cloud1.png")).convert_alpha()
            cloud_image2 = pygame.image.load(os.path.join(ASSETS_DIR, "cloud2.png")).convert_alpha()
            cloud_images = [cloud_image1, cloud_image2]
            
            self.clouds = [
                Cloud(cloud_images, self.external_screen.width, self.external_screen.height) 
                for _ in range(10)
            ]
            
            # Load sparkle effect
            self.sparkle_img = pygame.image.load(os.path.join(ASSETS_DIR, "sparkle.png")).convert_alpha()
            self.sparkle_img = pygame.transform.scale(
                self.sparkle_img, 
                (self.external_screen.width, self.external_screen.height)
            )
            
        except Exception as e:
            print(f"Error loading background assets: {e}")
            sys.exit(1)
    
    def _init_game_objects(self):
        """Initialize game objects and UI elements"""
        # Fonts
        self.font = pygame.font.SysFont("Impact", 32)
        self.big_font = pygame.font.SysFont("Impact", 48)
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (200, 0, 0)
        self.YELLOW = (255, 255, 0)
        self.GREEN = (0, 255, 0)
        
        # Zone management for balloon spawning (must be before creating balloons)
        self.ZONE_COUNT = 5
        self.zone_width = self.actual_width // self.ZONE_COUNT
        self.occupied_zones = set()
        
        # Game objects (now that zone variables are defined)
        self.balloons = [self.create_balloon() for _ in range(1)]
        self.cracks = []
        self.misses = []
        self.score_popups = []
        self.start_balloons = [self.create_balloon() for _ in range(4)]
        
        # Game state
        self.show_debug_overlay = False
        self.fade_alpha = 0
        self.game_over_y = -100
        self.game_over_target_y = SCREEN_HEIGHT // 2 - 80
        self.game_over_start_time = None
    
    def create_balloon(self):
        """Create a new balloon instance"""
        return Balloon(self.balloon_images, self.actual_width, self.actual_height,
                      self.ZONE_COUNT, self.zone_width, self.occupied_zones)
    
    def start_threads(self):
        """Start all worker threads"""
        try:
            self.app.start_tracking()

            try:
                self.audio_thread = AudioManager(self.game_state, BASE_DIR)
                self.audio_thread.start()
                print("Audio manager thread started")
            except Exception as audio_error:
                self.audio_thread = None
                print(f"Audio unavailable: {audio_error}")

            return True
            
        except Exception as e:
            print(f"Error starting threads: {e}")
            self.stop_threads()
            return False
    
    def stop_threads(self):
        """Stop all worker threads"""
        print("Stopping threads...")
        if self.audio_thread:
            self.audio_thread.stop()
        self.app.shutdown()
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2.0)
        print("All threads stopped")
    
    def handle_pointers(self, pointers):
        """Pop any balloon a tracked pointer is over"""
        for pointer in pointers:
            self._pop_balloon_at(pointer.x, pointer.y)

    def _pop_balloon_at(self, x, y):
        """Pop the first balloon under (x, y); return True if one popped"""
        for balloon in self.balloons:
            if balloon.is_clicked((x, y)):
                balloon.popped = True
                if self.audio_thread:
                    self.audio_thread.play_pop_sound()
                self.cracks.append(CrackEffect(x, y, self.boom_frames))
                self.balloons.remove(balloon)
                self.game_state.score += 1
                self.score_popups.append(ScorePopup(x, y))
                return True
        return False

    def _process_click(self, x, y):
        """Mouse click: pop a balloon, or show a miss"""
        if not self._pop_balloon_at(x, y):
            self.misses.append(MissEffect(x, y, self.miss_frames))
            if self.audio_thread:
                self.audio_thread.play_miss_sound()

    def _pointer_held(self, pointers, seconds):
        """True once some pointer has stayed visible for `seconds`"""
        if not pointers:
            self.pointer_held_since = None
            return False
        now = time.time()
        if self.pointer_held_since is None:
            self.pointer_held_since = now
        return now - self.pointer_held_since >= seconds

    def _start_game(self):
        self.game_state.start_screen_active = False
        self.game_state.game_started = True
        self.game_state.start_time = time.time()
        self.pointer_held_since = None
    
    def handle_events(self):
        """Handle Pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
                
            elif event.type == pygame.KEYDOWN:
                if self.game_state.start_screen_active:
                    self._start_game()
                elif event.key == pygame.K_q:
                    return False
                elif event.key == pygame.K_c:
                    self.app.recalibrate()
                elif event.key == pygame.K_d:
                    self.show_debug_overlay = not self.show_debug_overlay
                elif self.game_state.game_over:
                    if event.key == pygame.K_r:
                        self._restart_game()
                    elif event.key == pygame.K_ESCAPE:
                        return False
                        
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.game_state.start_screen_active:
                    self._start_game()
                elif not self.game_state.game_over:
                    current_time = time.time()
                    if current_time - self.game_state.last_click_time >= CLICK_COOLDOWN:
                        self._process_click(*event.pos)
                        self.game_state.last_click_time = current_time

        return True
    
    def _restart_game(self):
        """Restart the game"""
        self.game_state.reset_game()
        self.fade_alpha = 0
        self.game_over_y = -100
        self.game_over_start_time = None
        self.pointer_held_since = None
        
        # Reset balloons
        for balloon in self.balloons:
            balloon.reset()
    
    def update_game_logic(self):
        """Update game objects and logic"""
        pointers = self.app.pointers()

        if self.game_state.start_screen_active:
            if self._pointer_held(pointers, POINTER_HOLD_TO_START):
                self._start_game()
            return
        
        if self.game_state.game_over:
            restart_allowed = (time.time() - self.game_over_start_time
                               >= config.POINTER_RESTART_DELAY)
            if restart_allowed and self._pointer_held(pointers, POINTER_HOLD_TO_START):
                self._restart_game()
            return
        
        self.handle_pointers(pointers)
        
        # Update balloons
        for balloon in self.balloons:
            balloon.update()
        
        # Add new balloons if needed
        if len(self.balloons) == 0:
            self.balloons.append(self.create_balloon())
        
        # Check game over condition
        elapsed_time = time.time() - self.game_state.start_time
        if elapsed_time >= GAME_DURATION and not self.game_state.game_over:
            self.game_state.game_over = True
            self.game_over_start_time = time.time()
        
        # Update effects
        self.cracks = [c for c in self.cracks if c.update()]
        self.misses = [m for m in self.misses if m.update()]
        self.score_popups = [s for s in self.score_popups if s.update()]
    
    def render_frame(self):
        """Render the current frame"""
        # Clear screen with background
        self.screen.blit(self.background_image, (0, 0))
        
        # Draw clouds
        for cloud in self.clouds:
            cloud.update()
            cloud.draw(self.screen)
        
        if self.game_state.start_screen_active:
            self._render_start_screen()
        elif self.game_state.game_over:
            self._render_game_over()
        else:
            self._render_gameplay()
        
        self.app.draw_pointers()

        # Debug overlay
        if self.show_debug_overlay:
            self._render_debug_overlay()
        
        pygame.display.flip()
    
    def _render_start_screen(self):
        """Render start screen"""
        # Draw floating balloons
        for balloon in self.start_balloons:
            balloon.update()
            balloon.draw(self.screen)
        
        # Semi-transparent overlay
        overlay = pygame.Surface((self.external_screen.width, self.external_screen.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        # Title text
        title_text = self.big_font.render("Hold your hand up to start", True, self.WHITE)
        title_rect = title_text.get_rect(center=(self.actual_width//2, self.actual_height//2))
        self.screen.blit(title_text, title_rect)
    
    def _render_gameplay(self):
        """Render gameplay elements"""
        # Day/night overlay
        elapsed_time = time.time() - self.game_state.start_time
        overlay = self._get_day_night_overlay(elapsed_time, GAME_DURATION)
        self.screen.blit(overlay, (0, 0))
        
        # Sparkle effect in late game
        if elapsed_time > GAME_DURATION * 0.5:
            fade_duration = GAME_DURATION * 0.5
            fade_elapsed = elapsed_time - (GAME_DURATION * 0.5)
            fade_alpha = int(min(255, (fade_elapsed / fade_duration) * 255))
            
            sparkle_fade = self.sparkle_img.copy()
            sparkle_fade.set_alpha(fade_alpha)
            self.screen.blit(sparkle_fade, (0, 0))
        
        # Draw game objects
        for balloon in self.balloons:
            balloon.draw(self.screen)
        
        for crack in self.cracks:
            crack.draw(self.screen)
            
        for miss in self.misses:
            miss.draw(self.screen)
            
        for score_popup in self.score_popups:
            score_popup.draw(self.screen)
        
        # UI elements
        time_left = max(0, GAME_DURATION - int(elapsed_time))
        timer_text = self.font.render(f"Time Left: {time_left}s", True, self.BLACK)
        score_text = self.font.render(f"Score: {self.game_state.score}", True, self.BLACK)
        
        draw_text_with_bg(self.screen, timer_text, 20, 20)
        draw_text_with_bg(self.screen, score_text, 20, 100)
    
    def _render_game_over(self):
        """Render game over screen"""
        # Draw floating balloons
        for balloon in self.start_balloons:
            balloon.update()
            balloon.draw(self.screen)
        
        # Semi-transparent overlay
        overlay = pygame.Surface((self.external_screen.width, self.external_screen.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        # Animate game over text
        if self.game_over_start_time:
            elapsed = time.time() - self.game_over_start_time
            t = min(1, elapsed / 2)  # 2 second animation
            eased_y = int(self._ease_out_bounce(t) * (self.game_over_target_y + 80))
            
            # Game over text
            lines = [
                ("Oops!!! The time is up.", self.font, self.YELLOW),
                ("Game Over!", self.big_font, self.RED),
                (f"Your Final Score: {self.game_state.score}", self.font, self.WHITE),
                ("Hold your hand up or press R to restart", self.font, self.GREEN),
                ("TRY AGAIN!!!", self.font, self.WHITE)
            ]
            
            y_offset = eased_y - self.game_over_target_y
            current_y = self.actual_height // 2 - 100 + y_offset
            
            for text, font, color in lines:
                rendered = font.render(text, True, color)
                text_rect = rendered.get_rect(center=(self.actual_width//2, current_y))
                self.screen.blit(rendered, text_rect)
                current_y += 60
    
    def _render_debug_overlay(self):
        """Render debug information"""
        stats = self.game_state.get_performance_stats()
        y = 10
        
        debug_lines = [
            f"Camera FPS: {stats['camera_fps']:.1f}",
            f"Inference FPS: {stats['inference_fps']:.1f}",
            f"Game FPS: {stats['game_fps']:.1f}",
            f"Detection Queue: {stats['detection_queue_size']}",
            f"Frame Ready: {stats['frame_ready']}"
        ]
        
        for line in debug_lines:
            text = self.font.render(line, True, self.WHITE)
            self.screen.blit(text, (self.actual_width - 300, y))
            y += 25
    
    def _get_day_night_overlay(self, elapsed_time, total_time):
        """Create day/night transition overlay"""
        overlay = pygame.Surface((self.actual_width, self.actual_height), pygame.SRCALPHA)
        progress = elapsed_time / total_time
        alpha = int(min(180, 255 * progress))
        overlay.fill((0, 0, 64, alpha))
        return overlay
    
    def _ease_out_bounce(self, t):
        """Easing function for game over animation"""
        n1 = 7.5625
        d1 = 2.75
        if t < 1 / d1:
            return n1 * t * t
        elif t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        elif t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        else:
            t -= 2.625 / d1
            return n1 * t * t + 0.984375
    
    def update_fps_counter(self):
        """Update FPS counter"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.fps_start_time >= 1.0:
            fps = self.fps_counter / (current_time - self.fps_start_time)
            self.game_state.update_fps(game_fps=fps)
            self.fps_counter = 0
            self.fps_start_time = current_time
    
    def run(self):
        """Main game loop"""
        if not self.start_threads():
            return
        
        print("🎮 Starting main game loop...")
        
        try:
            running = True
            while running:
                # Handle events
                running = self.handle_events()
                
                # Update game logic
                self.update_game_logic()
                
                # Render frame
                self.render_frame()
                
                if not self.app.show_camera_debug():
                    running = False
                
                # Update FPS
                self.update_fps_counter()
                
                # Control frame rate
                self.clock.tick(FPS)
                
        except KeyboardInterrupt:
            print("\nGame interrupted by user")
        except Exception as e:
            print(f"Error in main game loop: {e}")
        finally:
            self.stop_threads()
            pygame.quit()


# Main execution
if __name__ == "__main__":
    print("Starting Threaded Interactive Projector Camera Game...")
    game = ThreadedBalloonGame()
    game.run()