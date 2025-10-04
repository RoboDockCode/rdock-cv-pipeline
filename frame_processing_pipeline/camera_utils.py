"""Utilities for camera capture and frame processing"""
import cv2 as cv
import time


def open_camera(camera_indices=[0, 1, 2]):
    """
    Try to open a camera from a list of indices
    
    Args:
        camera_indices: List of camera indices to try
        
    Returns:
        OpenCV VideoCapture object if successful, None otherwise
    """
    for idx in camera_indices:
        print(f"Trying camera index {idx}...")
        cap = cv.VideoCapture(idx)
        if cap.isOpened():
            print(f"✅ Camera {idx} opened successfully!")
            return cap
        else:
            cap.release()
    
    print("❌ Could not open any camera")
    return None


class FrameCaptureSession:
    """Manages a frame capture session with timing and statistics"""
    
    def __init__(self, cap, process_interval=10):
        """
        Initialize capture session
        
        Args:
            cap: OpenCV VideoCapture object
            process_interval: Process every Nth frame (default: 10)
        """
        self.cap = cap
        self.process_interval = process_interval
        self.frame_count = 0
        self.prev_frame = None
        self.start_time = time.time()
        
    def read_frame(self):
        """Read next frame from camera"""
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        self.frame_count += 1
        return frame
    
    def should_process(self):
        """Check if current frame should be processed based on interval"""
        return self.prev_frame is not None and self.frame_count % self.process_interval == 0
    
    def update_prev_frame(self, frame):
        """Store current frame for next pair processing"""
        self.prev_frame = frame.copy()
    
    def get_elapsed_time(self):
        """Get elapsed time since session started"""
        return time.time() - self.start_time
    
    def get_stats(self):
        """Get session statistics"""
        elapsed = self.get_elapsed_time()
        fps = self.frame_count / elapsed if elapsed > 0 else 0
        return {
            'frames': self.frame_count,
            'elapsed': elapsed,
            'fps': fps
        }
    
    def release(self):
        """Release camera and destroy windows"""
        self.cap.release()
        cv.destroyAllWindows()

