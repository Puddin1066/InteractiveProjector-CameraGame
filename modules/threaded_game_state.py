"""
Thread-safe game state management for the Interactive Projector Camera Game.
Handles shared data between multiple threads with proper synchronization.
"""
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple
from queue import Queue, Empty


@dataclass
class DetectionResult:
    """Container for YOLO detection results"""
    x: float
    y: float
    confidence: float
    timestamp: float


class ThreadSafeGameState:
    """
    Thread-safe game state manager that coordinates between:
    - Camera capture thread
    - YOLO inference thread  
    - Main game loop thread
    - Audio processing thread
    """
    
    def __init__(self):
        # Thread synchronization
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._detection_lock = threading.Lock()

        # Frame data
        self.current_frame = None
        self.frame_timestamp = 0
        self.frame_ready = threading.Event()

        # Detection results
        self._detection_queue = Queue(maxsize=5)  # Buffer recent detections
        self.latest_detection: Optional[DetectionResult] = None
        self._pointers: List[DetectionResult] = []

        # Click cooldown state
        self.last_click_time = 0
        self.click_cooldown = 0.5
        
        # Game state
        self._score = 0
        self._game_over = False
        self._game_started = False
        self._start_screen_active = True
        self._start_time = 0
        
        # Performance metrics
        self.fps_camera = 0
        self.fps_inference = 0
        self.fps_game = 0
        
        # Thread control
        self.running = True
        
    # Frame management
    def update_frame(self, frame, timestamp=None):
        """Update current frame (called by camera thread)"""
        with self._lock:
            self.current_frame = frame.copy()
            self.frame_timestamp = timestamp or time.time()
            self.frame_ready.set()
    
    def get_current_frame(self, timeout=0.1):
        """Get latest frame (called by inference thread)"""
        if self.frame_ready.wait(timeout):
            with self._lock:
                if self.current_frame is not None:
                    return self.current_frame.copy(), self.frame_timestamp
        return None, 0
    
    # Detection management
    def add_detection(self, x: float, y: float, confidence: float):
        """Add new detection result (called by inference thread)"""
        detection = DetectionResult(x, y, confidence, time.time())
        
        with self._detection_lock:
            # Add to queue, remove old if full
            if self._detection_queue.full():
                try:
                    self._detection_queue.get_nowait()
                except Empty:
                    pass
            
            try:
                self._detection_queue.put_nowait(detection)
                self.latest_detection = detection
            except:
                pass  # Queue operations can fail in edge cases
    
    def get_latest_detections(self, max_count=5) -> List[DetectionResult]:
        """Get recent detections (called by main thread)"""
        detections = []
        with self._detection_lock:
            # Get all available detections
            while not self._detection_queue.empty() and len(detections) < max_count:
                try:
                    detections.append(self._detection_queue.get_nowait())
                except Empty:
                    break
        return detections
    
    def update_pointers(self, pointers: List[Tuple[float, float, float]]):
        """Replace the tracked pointers with this frame's (x, y, confidence) list."""
        now = time.time()
        snapshot = [DetectionResult(x, y, confidence, now) for x, y, confidence in pointers]
        with self._detection_lock:
            self._pointers = snapshot
            if snapshot:
                self.latest_detection = snapshot[0]

    def get_pointers(self, max_age=0.2) -> List[DetectionResult]:
        """Screen-space pointers from the latest tracked frame, if recent enough."""
        now = time.time()
        with self._detection_lock:
            return [p for p in self._pointers if now - p.timestamp < max_age]

    def has_recent_detection(self, max_age=0.1) -> bool:
        """Check if we have a recent detection"""
        with self._detection_lock:
            if self.latest_detection:
                return (time.time() - self.latest_detection.timestamp) < max_age
        return False

    # Game state properties
    @property
    def score(self):
        with self._lock:
            return self._score
    
    @score.setter 
    def score(self, value):
        with self._lock:
            self._score = value
    
    @property
    def game_over(self):
        with self._lock:
            return self._game_over
    
    @game_over.setter
    def game_over(self, value):
        with self._lock:
            self._game_over = value
    
    @property
    def game_started(self):
        with self._lock:
            return self._game_started
    
    @game_started.setter
    def game_started(self, value):
        with self._lock:
            self._game_started = value
    
    @property
    def start_screen_active(self):
        with self._lock:
            return self._start_screen_active
    
    @start_screen_active.setter
    def start_screen_active(self, value):
        with self._lock:
            self._start_screen_active = value
    
    @property
    def start_time(self):
        with self._lock:
            return self._start_time
    
    @start_time.setter
    def start_time(self, value):
        with self._lock:
            self._start_time = value
    
    # Thread control
    def shutdown(self):
        """Signal all threads to stop"""
        with self._lock:
            self.running = False
            self.frame_ready.set()  # Wake up any waiting threads
    
    def reset_game(self):
        """Reset game state for new game"""
        with self._lock:
            self._score = 0
            self._game_over = False
            self._game_started = False
            self._start_screen_active = True
            self._start_time = 0
            self.last_click_time = 0

        with self._detection_lock:
            self._pointers = []
            # Clear detection queue
            while not self._detection_queue.empty():
                try:
                    self._detection_queue.get_nowait()
                except Empty:
                    break
    
    # Performance monitoring
    def update_fps(self, camera_fps=None, inference_fps=None, game_fps=None):
        """Update FPS counters for monitoring"""
        with self._lock:
            if camera_fps is not None:
                self.fps_camera = camera_fps
            if inference_fps is not None:
                self.fps_inference = inference_fps  
            if game_fps is not None:
                self.fps_game = game_fps
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        with self._lock:
            return {
                'camera_fps': self.fps_camera,
                'inference_fps': self.fps_inference,
                'game_fps': self.fps_game,
                'detection_queue_size': self._detection_queue.qsize(),
                'frame_ready': self.frame_ready.is_set()
            }