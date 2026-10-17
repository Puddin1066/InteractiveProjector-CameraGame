"""
Threaded Interactive Projector Camera Game
Multi-threaded implementation for improved performance and responsiveness.

Threading Architecture:
- Main Thread: Game logic, rendering, UI events
- Camera Thread: Continuous frame capture
- YOLO Thread: Object detection inference  
- Audio Thread: Sound effects processing
"""
import pygame
import pyautogui
import cv2
import numpy as np
import sys
import os
import time
import logging
import threading
from screeninfo import get_monitors

# Local imports
from modules import config
from modules.background import draw_text_with_bg
from modules.calibration import (
    get_calibration_points,
    get_perspective_transform,
    load_calibration_points,
    save_calibration_points,
)
from modules.boom_animation import generate_boom_frames
from modules.cloud import Cloud
from modules.pop_score import ScorePopup
from modules.balloon import Balloon
from modules.effects import CrackEffect, MissEffect

# Threading modules
from modules.threaded_game_state import ThreadSafeGameState
from modules.camera_capture_thread import CameraCaptureThread
from modules.yolo_inference_thread import YOLOInferenceThread
from modules.audio_manager_thread import AudioManager
from modules.video_source import open_local_capture

# Suppress logging
os.environ["YOLO_VERBOSE"] = "False"
logging.getLogger('ultralytics').setLevel(logging.CRITICAL)
cv2.setLogLevel(0)

# Constants (config-driven)
SCREEN_WIDTH = config.SCREEN_WIDTH
SCREEN_HEIGHT = config.SCREEN_HEIGHT
FPS = config.FPS
CONF_THRESHOLD = config.CONF_THRESHOLD
IOU_THRESHOLD = config.IOU_THRESHOLD
CLICK_COOLDOWN = config.CLICK_COOLDOWN
CAMERA_INDEX = config.CAMERA_INDEX
BALLOON_FILES = config.BALLOON_FILES
GAME_DURATION = config.GAME_DURATION
MODEL_PATH = config.MODEL_PATH
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
        self.game_state = ThreadSafeGameState()
        
        # Thread references
        self.camera_thread = None
        self.yolo_thread = None
        self.audio_thread = None
        
        # Pygame setup
        self._init_pygame()
        self._load_assets()
        self._init_calibration()
        self._init_game_objects()
        
        # Performance monitoring
        self.fps_counter = 0
        self.fps_start_time = time.time()
        
    def _init_pygame(self):
        """Initialize Pygame and display"""
        os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
        pygame.init()
        
        # Setup external monitor (projector)
        monitors = get_monitors()
        if len(monitors) < 2:
            print("Error: External monitor (projector) not detected")
            sys.exit(1)
        
        self.external_screen = monitors[1]
        os.environ['SDL_VIDEO_WINDOW_POS'] = f"{self.external_screen.x},{self.external_screen.y}"
        
        self.screen = pygame.display.set_mode(
            (self.external_screen.width, self.external_screen.height)
        )
        pygame.display.set_caption("Threaded Balloon Popping Game")
        self.clock = pygame.time.Clock()
        
        self.actual_width, self.actual_height = self.screen.get_size()
        print(f"Display: {self.actual_width}x{self.actual_height}")
    
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
    
    def _init_calibration(self):
        """Initialize camera calibration"""
        # Load existing calibration or perform new one
        calibration_points, offset_x, offset_y, debug_offset_x, debug_offset_y = load_calibration_points()
        
        if calibration_points and len(calibration_points) == 4:
            print(f"Loading existing calibration...")
            self.transform_matrix = get_perspective_transform(
                calibration_points, self.external_screen.width, self.external_screen.height, 0, 0
            )
            self.inv_transform_matrix = np.linalg.inv(self.transform_matrix)  # For manual clicks
            self.offset_x, self.offset_y = offset_x, offset_y
            self.debug_offset_x, self.debug_offset_y = debug_offset_x, debug_offset_y
        else:
            print("Performing camera calibration...")
            # Temporary camera for calibration
            temp_cap = open_local_capture(CAMERA_INDEX)
            if not temp_cap.isOpened():
                print("Error: Could not open camera for calibration")
                sys.exit(1)
                
            calibration_points = get_calibration_points(temp_cap)
            temp_cap.release()
            
            if calibration_points and len(calibration_points) == 4:
                self.offset_x, self.offset_y = 0, 0
                self.debug_offset_x, self.debug_offset_y = 0, 0
                save_calibration_points(calibration_points, self.offset_x, self.offset_y, 
                                      self.debug_offset_x, self.debug_offset_y)
                self.transform_matrix = get_perspective_transform(
                    calibration_points, self.external_screen.width, self.external_screen.height, 0, 0
                )
                self.inv_transform_matrix = np.linalg.inv(self.transform_matrix)  # For manual clicks
            else:
                print("Error: Calibration failed")
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
            # Start camera thread
            self.camera_thread = CameraCaptureThread(CAMERA_INDEX, self.game_state)
            self.camera_thread.start()
            print("Camera thread started")
            
            # Start YOLO inference thread
            self.yolo_thread = YOLOInferenceThread(
                MODEL_PATH, self.game_state, CONF_THRESHOLD, IOU_THRESHOLD,
                self.transform_matrix, self.debug_offset_x, self.debug_offset_y
            )
            self.yolo_thread.start()
            print("YOLO inference thread started")
            
            # Start audio manager thread
            self.audio_thread = AudioManager(self.game_state, BASE_DIR)
            self.audio_thread.start()
            print("Audio manager thread started")
            
            return True
            
        except Exception as e:
            print(f"Error starting threads: {e}")
            self.stop_threads()
            return False
    
    def stop_threads(self):
        """Stop all worker threads"""
        print("Stopping threads...")
        
        # Signal shutdown
        self.game_state.shutdown()
        
        # Stop threads
        if self.camera_thread:
            self.camera_thread.stop()
        if self.yolo_thread:
            self.yolo_thread.stop()
        if self.audio_thread:
            self.audio_thread.stop()
        
        # Wait for threads to finish (with timeout)
        threads = [self.camera_thread, self.yolo_thread, self.audio_thread]
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
        
        print("All threads stopped")
    
    def handle_detections(self):
        """Process detections from YOLO thread"""
        detections = self.game_state.get_latest_detections(max_count=5)
        
        for detection in detections:
            if (time.time() - detection.timestamp < 0.1 and  # Recent detection
                time.time() - self.game_state.last_click_time >= CLICK_COOLDOWN):
                
                screen_x = int(detection.x + self.external_screen.x)
                screen_y = int(detection.y + self.external_screen.y)
                
                # Move mouse and click
                pyautogui.moveTo(screen_x, screen_y)
                pyautogui.click(button='left')
                
                # Check balloon collisions
                self._process_click(screen_x - self.external_screen.x, 
                                  screen_y - self.external_screen.y, 'detection')
    
    def _process_click(self, x, y, source='manual'):
        """Process a click event (from detection or manual input)"""
        clicked = False
        
        # Check balloon collisions
        for balloon in self.balloons[:]:
            if balloon.is_clicked((x, y)):
                balloon.popped = True
                self.audio_thread.play_pop_sound()
                
                self.cracks.append(CrackEffect(x, y, self.boom_frames))
                self.balloons.remove(balloon)
                
                self.game_state.score += 1
                self.score_popups.append(ScorePopup(x, y))
                clicked = True
                break
        
        if not clicked:
            self.misses.append(MissEffect(x, y, self.miss_frames))
            self.audio_thread.play_miss_sound()
    
    def handle_events(self):
        """Handle Pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
                
            elif event.type == pygame.KEYDOWN:
                if self.game_state.start_screen_active:
                    # Start game on any keypress (like original)
                    self.game_state.start_screen_active = False
                    self.game_state.game_started = True
                    self.game_state.start_time = time.time()
                elif event.key == pygame.K_q:
                    return False
                elif event.key == pygame.K_c:
                    self._recalibrate()
                elif event.key == pygame.K_d:
                    self.show_debug_overlay = not self.show_debug_overlay
                elif self.game_state.game_over:
                    if event.key == pygame.K_r:
                        self._restart_game()
                    elif event.key == pygame.K_ESCAPE:
                        return False
                        
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.game_state.start_screen_active:
                    # Start game on mouse click (like original)
                    self.game_state.start_screen_active = False
                    self.game_state.game_started = True
                    self.game_state.start_time = time.time()
                elif not self.game_state.game_over:
                    # Manual click with inverse perspective transform (like original)
                    current_time = time.time()
                    
                    # Check cooldown directly (consistent with detection handling)
                    if current_time - self.game_state.last_click_time >= CLICK_COOLDOWN:
                        mx, my = event.pos
                        
                        # Apply inverse perspective transform to convert to warped coordinates
                        point = np.float32([[[mx, my]]])
                        warped_point = cv2.perspectiveTransform(point, self.inv_transform_matrix)[0][0]
                        cx, cy = warped_point
                        
                        # Check if click is within valid game area
                        if 0 <= cx <= self.external_screen.width and 0 <= cy <= self.external_screen.height:
                            # Process click directly (consistent with detection handling)
                            self._process_click(mx, my, 'manual')
                            self.game_state.last_click_time = current_time
                            print(f"Manual click processed: ({mx}, {my}) -> warped ({cx:.1f}, {cy:.1f})")
                        else:
                            print(f"Click outside game area: ({mx}, {my}) -> warped ({cx:.1f}, {cy:.1f})")
                    else:
                        print(f"Click ignored due to cooldown ({current_time - self.game_state.last_click_time:.2f}s < {CLICK_COOLDOWN}s)")

        return True
    
    def _recalibrate(self):
        """Perform camera recalibration"""
        print("Starting recalibration...")
        # Temporarily stop threads that use camera
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.join(timeout=2.0)
        
        # Perform calibration
        temp_cap = open_local_capture(CAMERA_INDEX)
        calibration_points = get_calibration_points(temp_cap)
        temp_cap.release()
        
        if calibration_points and len(calibration_points) == 4:
            save_calibration_points(calibration_points, 0, 0, 0, 0)
            self.transform_matrix = get_perspective_transform(
                calibration_points, self.external_screen.width, self.external_screen.height, 0, 0
            )
            self.inv_transform_matrix = np.linalg.inv(self.transform_matrix)  # Update inverse matrix
            print("Recalibration completed")
            
            # Restart camera thread
            self.camera_thread = CameraCaptureThread(CAMERA_INDEX, self.game_state)
            self.camera_thread.start()
        else:
            print("Recalibration failed")
    
    def _restart_game(self):
        """Restart the game"""
        self.game_state.reset_game()
        self.fade_alpha = 0
        self.game_over_y = -100
        self.game_over_start_time = None
        
        # Reset balloons
        for balloon in self.balloons:
            balloon.reset()
    
    def update_game_logic(self):
        """Update game objects and logic"""
        # Handle start screen
        if self.game_state.start_screen_active:
            # Check for detection to start game
            if self.game_state.has_recent_detection(max_age=0.2):
                self.game_state.start_screen_active = False
                self.game_state.game_started = True
                self.game_state.start_time = time.time()
            return
        
        if self.game_state.game_over:
            return
        
        # Process detections from YOLO thread
        self.handle_detections()
        
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
        title_text = self.big_font.render("Tap to Start", True, self.WHITE)
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
                ("Press R to restart", self.font, self.GREEN),
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
    
    def render_debug_window(self):
        """Render debug window showing camera feed with detections (like original)"""
        # Get latest frame from camera thread
        frame_data = self.game_state.get_current_frame()
        if frame_data is None:
            return
        
        frame, timestamp = frame_data
        
        # Apply perspective transform like original
        warped_frame = cv2.warpPerspective(frame, self.transform_matrix, 
                                         (self.external_screen.width, self.external_screen.height))
        
        # Resize for debug display
        debug_view = cv2.resize(warped_frame, (SCREEN_WIDTH, SCREEN_HEIGHT))
        
        # Draw ROI boundary like original
        roi_points = np.float32([[0, 0], [self.external_screen.width-1, 0], 
                                [self.external_screen.width-1, self.external_screen.height-1], 
                                [0, self.external_screen.height-1]])
        roi_points = roi_points.astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(debug_view, [roi_points], True, (255, 0, 0), 2)
        
        # Draw detection boxes from YOLO thread
        detections = self.game_state.get_latest_detections()
        for detection in detections:
            cx, cy = detection.x, detection.y
            confidence = detection.confidence
            
            # Scale coordinates for debug display
            scale_x = SCREEN_WIDTH / self.external_screen.width
            scale_y = SCREEN_HEIGHT / self.external_screen.height
            
            cx_scaled = int(cx * scale_x)
            cy_scaled = int(cy * scale_y)
            
            # Create a virtual bounding box around the center point (since we only store center)
            box_size = 40  # Virtual box size
            x1_scaled = cx_scaled - box_size // 2
            y1_scaled = cy_scaled - box_size // 2
            x2_scaled = cx_scaled + box_size // 2
            y2_scaled = cy_scaled + box_size // 2
            
            # Draw detection box and center point like original
            cv2.rectangle(debug_view, (x1_scaled, y1_scaled), (x2_scaled, y2_scaled), (0, 255, 0), 2)
            cv2.circle(debug_view, (cx_scaled, cy_scaled), 5, (0, 0, 255), -1)
            cv2.putText(debug_view, f"Green Ball: {confidence:.2f}", (x1_scaled, y1_scaled - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Show debug window like original
        cv2.imshow("Camera Feed", debug_view)

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
                
                # Render debug window (like original)
                self.render_debug_window()
                
                # Check for cv2 window quit (like original)
                if cv2.waitKey(1) & 0xFF == ord('q'):
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
            cv2.destroyAllWindows()


# Main execution
if __name__ == "__main__":
    print("Starting Threaded Interactive Projector Camera Game...")
    game = ThreadedBalloonGame()
    game.run()