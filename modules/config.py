"""
Central configuration for the Interactive Projector Camera Game.
All tunable constants live here so behavior can be adjusted without
touching game, threading, or vision code.
"""
import os

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# Target screen size used for calibration and coordinate mapping
SCREEN_WIDTH = 1360
SCREEN_HEIGHT = 768

# Game loop
FPS = 90
GAME_DURATION = 120  # seconds
CLICK_COOLDOWN = 0.5  # seconds between clicks

# Input. "hand" tracks palm centers with MediaPipe; "ball" uses the YOLO
# green-ball model in MODEL_PATH.
INPUT_MODE = os.getenv("INPUT_MODE", "hand").strip().lower()
MAX_HANDS = int(os.getenv("MAX_HANDS", "2"))
HAND_CONFIDENCE = float(os.getenv("HAND_CONFIDENCE", "0.3"))
# Detection runs only on the calibrated projection (plus a margin, as a fraction
# of its size), split into side-by-side tiles, so hands at the wall look larger
# to the model than they do in the full camera frame.
DETECTION_REGION_MARGIN = 0.2
DETECTION_TILES = int(os.getenv("DETECTION_TILES", "2"))

# Where the camera points. "wall": it sees the projection, players touch the wall,
# and a four-corner calibration is needed. "players": it faces the players, who
# play from a few steps back (no shadows on the game, no calibration). Unset means
# each game's own default.
CAMERA_FACING = os.getenv("CAMERA_FACING", "").strip().lower() or None
# Part of the player-facing camera image that maps onto the whole projection
# (x0, y0, x1, y1): roughly where standing players' raised hands move.
PLAYER_REACH_ZONE = (0.12, 0.05, 0.88, 0.75)

# Person segmentation (silhouettes) with MediaPipe's selfie segmenter
SEGMENTER_MODEL_PATH = os.path.join(MODELS_DIR, "selfie_segmenter.tflite")
SEGMENTER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
    "selfie_segmenter/float16/latest/selfie_segmenter.tflite"
)
HAND_MODEL_PATH = os.path.join(MODELS_DIR, "hand_landmarker.task")
HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
POINTER_MAX_AGE = 0.2  # seconds a tracked pointer stays valid after last seen
POINTER_HOLD_TO_START = 0.5  # seconds a pointer must stay up to start/restart
POINTER_RESTART_DELAY = 3.0  # seconds after game over before a pointer can restart

# YOLO detection thresholds
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.7

# Camera. Index 0 is the Mac built-in FaceTime camera. Set CAMERA_INDEX to
# choose a different local device. Calibration and tracking must use the same
# capture size, because some cameras crop their field of view at 4:3 sizes.
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "720"))
CAMERA_FPS = 30

# Assets
MODEL_PATH = os.path.join(MODELS_DIR, "best.onnx")
CALIBRATION_FILE = os.path.join(BASE_DIR, "calibration.json")
BALLOON_FILES = ["balloon1.png", "balloon2.png", "balloon3.png"]
CRACK_PATH = os.path.join(ASSETS_DIR, "boom1.png")
MISS_PATH = os.path.join(ASSETS_DIR, "miss.png")
BACKGROUND_IMAGE_PATH = os.path.join(ASSETS_DIR, "background.jpg")
POP_SOUND_PATH = os.path.join(ASSETS_DIR, "balloon-pop.mp3")
MISS_SOUND_PATH = os.path.join(ASSETS_DIR, "miss.mp3")