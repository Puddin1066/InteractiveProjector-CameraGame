"""
Enhanced camera capture thread that integrates with ThreadSafeGameState.
Provides continuous frame capture with performance monitoring.
"""
import cv2
import threading
import queue
import time
from typing import Optional
from . import config
from .threaded_game_state import ThreadSafeGameState
from .video_source import open_local_capture


class CameraCaptureThread(threading.Thread):
    """
    Enhanced camera capture thread with game state integration.
    Continuously captures frames and updates the shared game state.
    """
    
    def __init__(self, camera_index: int, game_state: ThreadSafeGameState,
                 width: int = config.CAMERA_WIDTH, height: int = config.CAMERA_HEIGHT,
                 target_fps: int = config.CAMERA_FPS):
        super().__init__(name="CameraCapture")
        self.daemon = True  # Dies when main thread dies
        
        self.camera_index = camera_index
        self.game_state = game_state
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        
        # Performance tracking
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0
        self.dropped_frames = 0
        
        # Legacy queue for backward compatibility (if needed)
        self.frame_queue = queue.Queue(maxsize=1)
        self.running = True
        
        # Initialize camera
        self.cap = open_local_capture(self.camera_index, width, height, target_fps)
        if not self.cap.isOpened():
            raise RuntimeError(f"Error: Could not open camera {self.camera_index}")
        
        # Verify settings
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        print(f"📷 Camera initialized: {actual_width}x{actual_height} @ {actual_fps}FPS")
    
    def run(self):
        """Main capture loop with fps control and error handling"""
        print("Camera capture thread started")
        last_frame_time = time.time()
        
        while self.running and self.game_state.running:
            try:
                ret, frame = self.cap.read()
                current_time = time.time()
                
                if ret and frame is not None:
                    # Update game state with new frame
                    self.game_state.update_frame(frame, current_time)
                    
                    # Maintain backward compatibility with queue
                    try:
                        if self.frame_queue.full():
                            self.frame_queue.get_nowait()
                        self.frame_queue.put(frame, block=False)
                    except queue.Full:
                        self.dropped_frames += 1
                    
                    # Update performance metrics
                    self._update_fps()
                    
                    # Frame rate control
                    elapsed = current_time - last_frame_time
                    if elapsed < self.frame_interval:
                        time.sleep(self.frame_interval - elapsed)
                    
                    last_frame_time = current_time
                    
                else:
                    print("Warning: Failed to capture frame")
                    self.dropped_frames += 1
                    time.sleep(0.1)  # Wait longer on failure
                    
            except Exception as e:
                print(f"Error in camera capture thread: {e}")
                time.sleep(0.1)  # Prevent tight error loop
        
        # Cleanup
        self.cap.release()
        print("Camera capture thread stopped")
    
    def _update_fps(self):
        """Update FPS calculation and report to game state"""
        self.frame_count += 1
        current_time = time.time()
        
        if current_time - self.fps_start_time >= 1.0:  # Update every second
            self.current_fps = self.frame_count / (current_time - self.fps_start_time)
            self.game_state.update_fps(camera_fps=self.current_fps)
            
            # Reset counters
            self.frame_count = 0
            self.fps_start_time = current_time
    
    def stop(self):
        """Stop the capture thread"""
        self.running = False
    
    def get_debug_info(self) -> dict:
        """Get debug information for monitoring"""
        return {
            'fps': self.current_fps,
            'dropped_frames': self.dropped_frames,
            'running': self.running,
            'camera_opened': self.cap.isOpened() if hasattr(self, 'cap') else False,
            'target_fps': self.target_fps
        }
    
    def get_frame(self, timeout: float = 0.1) -> Optional[object]:
        """
        Legacy method for backward compatibility.
        Gets frame from queue (non-blocking).
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None