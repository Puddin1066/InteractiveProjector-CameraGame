import pygame
import pyautogui
import cv2
import numpy as np
import sys
import math
import os
import random
import time
import logging
from ultralytics import YOLO
from screeninfo import get_monitors
from modules.background import draw_text_with_bg
from modules.calibration import *
from modules.boom_animation import generate_boom_frames
from modules.cloud import Cloud
from modules.pop_score import ScorePopup
from modules.video_source import open_local_capture

# Suppress Ultralytics logging
os.environ["YOLO_VERBOSE"] = "False"
logging.getLogger('ultralytics').setLevel(logging.CRITICAL)

# Suppress OpenCV logging
cv2.setLogLevel(0)

# Constants
SCREEN_WIDTH = 1360
SCREEN_HEIGHT = 768
FPS = 90
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.7
CLICK_COOLDOWN = 0.5
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "best.onnx")
CRACK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "boom1.png")
BACKGROUND_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "background.jpg")
CALIBRATION_FILE = "calibration.json"
CAMERA_INDEX = 0  # Configurable camera index
BALLOON_FILES = ["balloon1.png", "balloon2.png", "balloon3.png"]
POP_SOUND_PATH = "balloon-pop.mp3"

# Initialize Pygame
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
pygame.init()
monitors = get_monitors()
if len(monitors) < 2:
    print("Error: External monitor (projector) not detected")
    sys.exit(1)
external_screen = monitors[1]
os.environ['SDL_VIDEO_WINDOW_POS'] = f"{external_screen.x},{external_screen.y}"
screen = pygame.display.set_mode((external_screen.width, external_screen.height)) # 2040, 1152
pygame.display.set_caption("Balloon Popping Game")
clock = pygame.time.Clock()

actual_width, actual_height = screen.get_size()

# Load assets
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
BALLOON_IMAGES = []

# Load balloon images
for file in BALLOON_FILES:
    path = os.path.join(base_dir, "assets", file)
    if not os.path.exists(path):
        print(f"Warning: Balloon image {path} not found. Skipping.")
        continue
    try:
        img = pygame.image.load(path).convert_alpha()
        img = pygame.transform.scale(img, (420, 480))
        BALLOON_IMAGES.append(img)
    except pygame.error as e:
        print(f"Warning: Failed to load {path}: {e}. Skipping.")

if not BALLOON_IMAGES:
    print("Error: No valid balloon images loaded. Exiting.")
    pygame.quit()
    sys.exit(1)

# Load crack image
try:
    # crack_img = pygame.image.load(CRACK_PATH).convert_alpha()
    # crack_img = pygame.transform.scale(crack_img, (260, 150))
    base_crack = pygame.image.load(CRACK_PATH).convert_alpha()
    base_crack = pygame.transform.scale(base_crack, (200, 120))  # adjust if needed
    boom_frames = generate_boom_frames(base_crack, num_frames=6)

except pygame.error as e:
    print(f"Error loading boom1.png: {e}")
    sys.exit(1)

miss_image = pygame.image.load("assets/miss.png").convert_alpha()
miss_image = pygame.transform.scale(miss_image, (150, 100))
miss_frames = generate_boom_frames(miss_image, num_frames=6)

miss_sound = pygame.mixer.Sound("assets/miss.mp3")

# Load pop sound
def load_sound(filename):
    path = os.path.join(base_dir, "assets", filename)
    if os.path.exists(path):
        try:
            return pygame.mixer.Sound(path)
        except pygame.error as e:
            print(f"Failed to load sound {filename}: {e}")
    return None

pop_sound = load_sound(POP_SOUND_PATH)

# Load background image
try:
    background_image = pygame.image.load(BACKGROUND_IMAGE_PATH).convert()
    background_image = pygame.transform.scale(background_image, (external_screen.width, external_screen.height))
except pygame.error as e:
    print(f"Error loading background image {BACKGROUND_IMAGE_PATH}: {e}")
    pygame.quit()
    sys.exit(1)

# Load animated background elements
cloud_image1 = pygame.image.load(os.path.join(base_dir, "assets", "cloud1.png")).convert_alpha()
cloud_image2 = pygame.image.load(os.path.join(base_dir, "assets", "cloud2.png")).convert_alpha()
cloud_images = [cloud_image1, cloud_image2]

clouds = [Cloud(cloud_images, external_screen.width, external_screen.height) for _ in range(10)]

sparkle_img = pygame.image.load(os.path.join(base_dir, "assets", "sparkle.png")).convert_alpha()
sparkle_img = pygame.transform.scale(sparkle_img, (external_screen.width, external_screen.height))  # Adjust as needed

def get_day_night_overlay(elapsed_time, total_time):
    overlay = pygame.Surface((actual_width, actual_height), pygame.SRCALPHA)
    progress = elapsed_time / total_time
    alpha = int(min(180, 255 * progress))  # Max darkness
    overlay.fill((0, 0, 64, alpha))  # Night bluish tint
    return overlay

# Initialize YOLO model with suppressed output
try:
    original_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    model = YOLO(MODEL_PATH, task="detect", verbose=False)
    sys.stdout = original_stdout
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    sys.exit(1)

# Initialize camera
cap = open_local_capture(CAMERA_INDEX)
if not cap.isOpened():
    print("Error: Could not open camera")
    pygame.quit()
    sys.exit(1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 720)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

cap.set(cv2.CAP_PROP_FPS, 30)  # Set to 30 FPS

# Load or perform calibration
calibration_points, offset_x, offset_y, debug_offset_x, debug_offset_y = load_calibration_points()
transform_matrix = None
if calibration_points and len(calibration_points) == 4:
    print(f"Loading existing calibration with homography offset ({offset_x}, {offset_y}) and debug offset ({debug_offset_x}, {debug_offset_y})...")
    transform_matrix = get_perspective_transform(calibration_points, external_screen.width, external_screen.height, 0, 0)
else:
    print("Performing camera calibration...")
    calibration_points = get_calibration_points(cap)
    offset_x, offset_y = 0, 0  # Set homography offset to 0,0
    debug_offset_x, debug_offset_y = 0, 0  
    if calibration_points and len(calibration_points) == 4:
        save_calibration_points(calibration_points, offset_x, offset_y, debug_offset_x, debug_offset_y)
        transform_matrix = get_perspective_transform(calibration_points, external_screen.width, external_screen.height, 0, 0)
    else:
        print("Error: Calibration failed")
        cap.release()
        pygame.quit()
        sys.exit()

# Colors and fonts
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
FONT = pygame.font.SysFont("Impact", 32)
BIG_FONT = pygame.font.SysFont("Impact", 48)

# Balloon movement variables
ZONE_COUNT = 5
zone_width = actual_width // ZONE_COUNT
occupied_zones = set()

# Balloon class
class Balloon:
    def __init__(self):
        self.image = random.choice(BALLOON_IMAGES)
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        self.radius = min(self.width, self.height) // 2
        self.popped = False
        self.movement_type = random.choice(['zigzag', 'sway', 'spiral'])
        self.wind_offset = 0  # used for wind gusts
        self.birth_time = time.time()
        self.reset()

    def reset(self):
        global occupied_zones
        if len(occupied_zones) >= ZONE_COUNT:
            occupied_zones.clear()
        
        zone = random.choice([i for i in range(ZONE_COUNT) if i not in occupied_zones])
        max_x_offset = max(0, zone_width - self.width)
        self.x = zone * zone_width + random.randint(0, max_x_offset)
        occupied_zones.add(zone)

        # self.y = actual_height + random.randint(0, 50)
        self.y = actual_height - 10  # Almost just off-screen
        self.speed = random.uniform(28.0, 30.0)  # higher speed
        self.popped = False
        self.style = random.choice(['zigzag', 'spiral', 'sway'])  # re-randomize style
        self.wind_amplitude = random.uniform(0.8, 2.0)

    def update(self, slow_factor=1.0):
        if not self.popped:
            # Vertical movement
            self.y -= self.speed * slow_factor
            
            # Horizontal personality movement
            t = time.time() - self.birth_time

            if self.movement_type == 'zigzag':
                self.x += math.sin(t * 5) * 8  # fast side-to-side
            elif self.movement_type == 'sway':
                self.x += math.sin(self.y * 0.01) * 6  # smooth slow sway
            elif self.movement_type == 'spiral':
                self.x += math.sin(t * 3) * (self.y * 0.008)  # spiral outward

            # Occasional wind gust
            if random.random() < 0.002:  # ~0.2% chance per frame
                self.wind_offset = random.uniform(-10, 10)
            else:
                self.wind_offset *= 0.9  # fade out wind

            self.x += self.wind_offset

            # Reset if out of screen
            if self.y + self.height < 0:
                self.reset()

    def draw(self, win):
        if not self.popped:
            win.blit(self.image, (self.x, self.y))

    def is_clicked(self, pos):
        cx = self.x + self.width // 2
        cy = self.y + self.height // 2
        dx = pos[0] - cx
        dy = pos[1] - cy
        return dx * dx + dy * dy <= self.radius * self.radius

class CrackEffect:
    def __init__(self, x, y, duration=1):
        self.x = x
        self.y = y
        self.start_time = time.time()
        self.duration = duration
        self.frame_duration = duration / len(boom_frames)

    def draw(self, win):
        elapsed = time.time() - self.start_time
        if elapsed < self.duration:
            frame_index = int(elapsed / self.frame_duration)
            if frame_index < len(boom_frames):
                frame = boom_frames[frame_index]
                # Adjust position to keep effect centered
                fx = self.x - frame.get_width() // 2
                fy = self.y - frame.get_height() // 2
                win.blit(frame, (fx, fy))
            return True
        return False

class MissEffect:
    def __init__(self, x, y, duration=1):
        self.x = x
        self.y = y
        self.start_time = time.time()
        self.duration = duration
        self.frame_duration = duration / len(miss_frames)

    def draw(self, win):
        elapsed = time.time() - self.start_time
        if elapsed < self.duration:
            frame_index = int(elapsed / self.frame_duration)
            if frame_index < len(miss_frames):
                frame = miss_frames[frame_index]
                # Adjust position to keep effect centered
                fx = self.x - frame.get_width() // 2
                fy = self.y - frame.get_height() // 2
                win.blit(frame, (fx, fy))
            return True
        return False

# Main loop variables
balloons = [Balloon() for _ in range(1)]
cracks = []
misses = []
last_click_time = 0
running = True
show_debug_overlay = False
font = pygame.font.SysFont(None, 36)
score = 0
GAME_DURATION = 120
start_time = pygame.time.get_ticks()
game_over = False
score_popups = []

# Compute inverse transform for manual clicks
inv_transform_matrix = np.linalg.inv(transform_matrix)

#start screen
def draw_start_screen(surface, alpha=255):
    surface.blit(background_image, (0, 0))
    
    for cloud in clouds:
        cloud.update()
        cloud.draw(surface)

    # Optional: draw floating balloons
    for balloon in start_balloons:
        balloon.update()
        balloon.draw(surface)

    overlay = pygame.Surface((external_screen.width, external_screen.height), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))  # semi-transparent dark
    surface.blit(overlay, (0, 0))

    font = pygame.font.SysFont("Impact", 72)
    text = font.render("Tap to Start", True, (255, 255, 255))
    text_rect = text.get_rect(center=(external_screen.width//2, external_screen.height//2))
    surface.blit(text, text_rect)

start_screen_active = True
fade_out_timer = None
fade_duration = 1.0  # seconds for the fade out effect
fade_alpha = 100  # Fully opaque to begin with
game_started = False

start_balloons = [Balloon() for _ in range(4)]

# Game Over screen
fade_overlay = pygame.Surface((external_screen.width, external_screen.height))
fade_overlay.fill((0, 0, 0))
fade_alpha = 0
game_over_y = -100  # Start off-screen
game_over_target_y = SCREEN_HEIGHT // 2 - 80
# Fade overlay
dim_overlay = pygame.Surface((external_screen.width, external_screen.height))
dim_overlay.fill((0, 0, 0))
dim_overlay.set_alpha(fade_alpha)  # Range from 0 to ~180
screen.blit(background_image, (0, 0))  # Draw game background
screen.blit(dim_overlay, (0, 0))       # Apply fade

def ease_out_bounce(t):
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
    
game_over_start_time = None

def draw_glow_text(surface, text, font, x, y, color):
    base = font.render(text, True, color)
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        glow = font.render(text, True, (100, 100, 100))
        glow.set_alpha(120)
        surface.blit(glow, (x + dx, y + dy))
    surface.blit(base, (x, y))

# Main loop
while running:
    clock.tick(FPS)
     # Read camera frame
    ret, frame = cap.read()
    if not ret:
        print("Warning: Could not read frame")
        continue
        
    # Apply perspective transform
    warped_frame = cv2.warpPerspective(frame, transform_matrix, (external_screen.width, external_screen.height))
    
    results = model.predict(warped_frame, imgsz=640, conf=CONF_THRESHOLD, iou=IOU_THRESHOLD, device="cpu", verbose=False)

    # Check for tap to begin game
    if start_screen_active:
        draw_start_screen(screen)
        pygame.display.flip()

        # Process events JUST to check for tap
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                start_screen_active = False
                game_started = True
                start_time = pygame.time.get_ticks()
        for result in results:
            if result.boxes:
                start_screen_active = False
                game_started = True
                start_time = pygame.time.get_ticks()
                break  # Exit loop once started

        continue

    if not game_over:
        # Process detections
        current_time = time.time()
        for result in results:
            if result.boxes:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2

                    # Apply inverse perspective transform to convert to screen coordinates
                    point = np.float32([[[cx, cy]]])
                    warped_point = cv2.perspectiveTransform(point, inv_transform_matrix)[0][0]
                    screen_x, screen_y = warped_point
            
                    if (0 <= cx <= external_screen.width and 0 <= cy <= external_screen.height and 
                        current_time - last_click_time >= CLICK_COOLDOWN):
                        screen_x = int(cx + debug_offset_x + external_screen.x)
                        screen_y = int(cy + debug_offset_y + external_screen.y)

                        # Move the mouse and click
                        pyautogui.moveTo(screen_x, screen_y)
                        pyautogui.click(button='left')
                        
                        clicked = False
                        for balloon in balloons[:]:
                            if balloon.is_clicked((screen_x, screen_y)):
                                balloon.popped = True
                                if pop_sound:
                                    pop_sound.play()
                                crack_x = int(screen_x - base_crack.get_width() / 2)
                                crack_y = int(screen_y - base_crack.get_height() / 2)
                                cracks.append(CrackEffect(crack_x, crack_y))
                                balloons.remove(balloon)
                                score += 1
                                score_popups.append(ScorePopup(screen_x, screen_y))
                                last_click_time = current_time
                                clicked = True
                                break
                        if not clicked:
                            misses.append(MissEffect(screen_x, screen_y))
                            miss_sound.play()

        # Add new balloons if needed
        if len(balloons) == 0:
            balloons.append(Balloon())
    
    # Update and draw balloons
    for balloon in balloons:
        balloon.update()    
    elapsed_time = (pygame.time.get_ticks() - start_time) / 1000
    time_left = max(0, GAME_DURATION - int(elapsed_time))
    if elapsed_time >= GAME_DURATION and not game_over:
        game_over = True

    # Debug view
    debug_view = warped_frame.copy()
    debug_view = cv2.resize(warped_frame, (SCREEN_WIDTH, SCREEN_HEIGHT))

    # Draw ROI boundary
    roi_points = np.float32([[0, 0], [external_screen.width-1, 0], [external_screen.width-1, external_screen.height-1], [0, external_screen.height-1]])
    roi_points = roi_points.astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(debug_view, [roi_points], True, (255, 0, 0), 2)
    for result in results:
        if result.boxes:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2 
                confidence = float(box.conf[0])
                cv2.rectangle(debug_view, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(debug_view, (int(cx), int(cy)), 5, (0, 0, 255), -1)
                cv2.putText(debug_view, f"Green Ball: {confidence:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    cv2.imshow("Camera Feed", debug_view)
    
    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                running = False
            elif event.key == pygame.K_c:
                print("Starting recalibration...")
                calibration_points = get_calibration_points(cap)
                if calibration_points and len(calibration_points) == 4:
                    offset_x, offset_y = 0, 0
                    debug_offset_x, debug_offset_y = 0, 0
                    save_calibration_points(calibration_points, offset_x, offset_y, debug_offset_x, debug_offset_y)
                    transform_matrix = get_perspective_transform(calibration_points, external_screen.width, external_screen.height, offset_x, offset_y)
                    test_calibration_accuracy(transform_matrix, calibration_points)
            elif game_over:
                if event.key == pygame.K_r:
                    score = 0
                    start_time = pygame.time.get_ticks()
                    game_over = False
                    start_screen_active = True
                    fade_alpha = 0
                    game_over_y = -100
                    game_over_start_time = None
                    for b in balloons:
                        b.reset()
                elif event.key == pygame.K_ESCAPE:
                    running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
            current_time = time.time()
            if current_time - last_click_time >= CLICK_COOLDOWN:
                mx, my = event.pos
                point = np.float32([[[mx, my]]])
                warped_point = cv2.perspectiveTransform(point, inv_transform_matrix)[0][0]
                cx, cy = warped_point
                if 0 <= cx <= external_screen.width and 0 <= cy <= external_screen.height:
                    clicked = False
                    for balloon in balloons[:]:
                        if balloon.is_clicked((mx, my)):
                            balloon.popped = True
                            if pop_sound:
                                pop_sound.play()
                            cracks.append(CrackEffect(mx, my))
                            balloons.remove(balloon)
                            score += 1
                            score_popups.append(ScorePopup(mx, my))
                            clicked = True
                            break
                    last_click_time = current_time
                if not clicked:
                    misses.append(MissEffect(mx, my))
                    miss_sound.play()
    # Render screen
    screen.blit(background_image, (0, 0))

    # Clouds
    for cloud in clouds:
        cloud.update()
        cloud.draw(screen)

    if not game_over:
        overlay = get_day_night_overlay(elapsed_time, GAME_DURATION)
        screen.blit(overlay, (0, 0))
        
        # Draw sparkles
        if elapsed_time > GAME_DURATION * 0.5:
            # Calculate how much time has passed since fade-in started
            fade_duration = GAME_DURATION * 0.5  # Remaining time after 60%
            fade_elapsed = elapsed_time - (GAME_DURATION * 0.5)

            # Compute alpha (0 to 255) based on progress
            fade_alpha = int(min(255, (fade_elapsed / fade_duration) * 255))

            # Apply the alpha to a copy of the sparkle image
            sparkle_fade = sparkle_img.copy()
            sparkle_fade.set_alpha(fade_alpha)

            # Blit with fading
            screen.blit(sparkle_fade, (0, 0))

        for balloon in balloons:
            balloon.draw(screen)
        cracks = [c for c in cracks if c.draw(screen)]
        score_popups = [s for s in score_popups if s.draw(screen)]
        misses = [m for m in misses if m.draw(screen)]
        timer_text = FONT.render(f"Time Left: {time_left}s", True, (0,0,0))
        score_text = FONT.render(f"Score: {score}", True, (0,0,0))
        draw_text_with_bg(screen, timer_text, 20, 20)
        draw_text_with_bg(screen, score_text, 20, 100)

    # Game over handling
    else:
        if game_over_start_time is None:
            game_over_start_time = pygame.time.get_ticks()

        # Draw background consistent with start screen
        screen.blit(background_image, (0, 0))
        
        # Draw clouds
        for cloud in clouds:
            cloud.update()
            cloud.draw(screen)

        # Draw floating balloons (same as start screen)
        for balloon in start_balloons:
            balloon.update()  # Use normal update, not slow-motion
            balloon.draw(screen)

        # Apply semi-transparent overlay (same as start screen)
        overlay = pygame.Surface((external_screen.width, external_screen.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # Match start screen's overlay
        screen.blit(overlay, (0, 0))

        # Animate "Game Over" drop
        elapsed_drop = (pygame.time.get_ticks() - game_over_start_time) / 1000
        drop_duration = 2  # seconds
        t = min(1, elapsed_drop / drop_duration)
        eased_y = int(ease_out_bounce(t) * (game_over_target_y + 80))

        # Define fonts for hierarchy
        title_font = pygame.font.SysFont("Impact", 80)  # Larger for "Game Over!"
        score_font = pygame.font.SysFont("Impact", 60)  # Slightly smaller for score
        message_font = pygame.font.SysFont("Impact", 48)  # Smaller for messages

        # Calculate total text block height
        text_lines = [
            ("Oops!!! The time is up.", message_font, YELLOW),
            ("Game Over!", title_font, RED),
            (f"Your Final Score: {score}", score_font, WHITE),
            ("Press R to restart", message_font, GREEN),
            ("TRY AGAIN!!!", message_font, WHITE)
        ]
        line_spacing = 50  # Consistent spacing between lines
        total_height = sum(font.size(text)[1] for text, font, _ in text_lines) + line_spacing * (len(text_lines) - 1)
        start_y = external_screen.height // 2 - total_height // 2 + eased_y - game_over_target_y  # Center the block around eased_y

        # Optional: Draw semi-transparent background box
        max_width = max(font.size(text)[0] for text, font, _ in text_lines)
        box_padding = 20
        box_rect = pygame.Rect(
            external_screen.width // 2 - max_width // 2 - box_padding,
            external_screen.height // 2 - total_height // 2 - box_padding,
            max_width + 2 * box_padding,
            total_height + 2 * box_padding
        )
        pygame.draw.rect(screen, (0, 0, 0, 20), box_rect, border_radius=10)

        # Draw text lines
        current_y = start_y
        for text, font, color in text_lines:
            draw_glow_text(screen, text, font,
                        external_screen.width // 2 - font.size(text)[0] // 2,
                        current_y - 80, color)
            current_y += font.size(text)[1] + line_spacing

    pygame.display.flip()
    
    # Check for exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        running = False

# Cleanup
cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()