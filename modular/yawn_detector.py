"""
Yawn Detection Module
Detects yawning using LAR (Lip Aspect Ratio) with smoothing and validation
"""

import numpy as np
from collections import deque
from config import (
    LAR_THRESHOLD,
    YAWN_DURATION_SECONDS,
    LAR_SMOOTHING_WINDOW,
    LAR_CONSECUTIVE_FRAMES,
    BLINK_RATE_WINDOW
)


def calculate_lar(mouth_landmarks):
    """
    Calculate LAR (Lip Aspect Ratio) for yawn detection.
    
    Uses MediaPipe landmarks:
    - 13: upper lip
    - 14: lower lip
    - 61: left mouth corner
    - 291: right mouth corner
    
    LAR = (vertical distance between upper and lower lip) / (horizontal distance between corners)
    
    Args:
        mouth_landmarks: List of 4 (x, y) tuples [upper, lower, left, right]
        
    Returns:
        LAR value (float) or None if invalid
    """
    if len(mouth_landmarks) != 4:
        return None
    
    upper = np.array(mouth_landmarks[0], dtype=np.float32)
    lower = np.array(mouth_landmarks[1], dtype=np.float32)
    left = np.array(mouth_landmarks[2], dtype=np.float32)
    right = np.array(mouth_landmarks[3], dtype=np.float32)
    
    # Vertical distance between upper and lower lip
    vertical_dist = np.linalg.norm(upper - lower)
    
    # Horizontal distance between mouth corners
    horizontal_dist = np.linalg.norm(left - right)
    
    if horizontal_dist == 0:
        return None
    
    return vertical_dist / horizontal_dist


class YawnDetector:
    """
    Detects yawning using LAR (Lip Aspect Ratio) with improved accuracy.
    
    Features:
    - LAR smoothing over multiple frames (reduces noise)
    - Frame validation (requires consecutive frames above threshold)
    - Yawn duration tracking
    - Yawn count in time window
    """
    
    def __init__(self):
        """Initialize yawn detector."""
        self.lar_history = deque(maxlen=LAR_SMOOTHING_WINDOW)  # Limited size for smoothing
        self.lar_timestamps = deque()
        self.yawn_timestamps = deque()
        self.yawn_durations = deque()
        self.last_lar = None
        self.mouth_open = False
        self.mouth_open_start_ts = None
        self.lar_above_threshold_count = 0  # Count consecutive frames with LAR > threshold
    
    def update(self, lar, timestamp):
        """
        Update yawn tracking with new LAR value.
        
        Args:
            lar: Current Lip Aspect Ratio value
            timestamp: Current timestamp
        """
        if lar is None:
            return
        
        self.lar_history.append(lar)
        self.lar_timestamps.append(timestamp)
        
        # Calculate smoothed LAR (average of recent frames) for noise reduction
        smoothed_lar = float(np.mean(self.lar_history)) if len(self.lar_history) > 0 else lar
        
        # Check if smoothed LAR is above threshold
        is_open = smoothed_lar > LAR_THRESHOLD
        
        # Frame validation: require consecutive frames above threshold
        if is_open:
            self.lar_above_threshold_count += 1
        else:
            self.lar_above_threshold_count = 0
        
        # Only consider mouth open if LAR has been above threshold for consecutive frames
        validated_open = self.lar_above_threshold_count >= LAR_CONSECUTIVE_FRAMES
        
        if self.last_lar is not None:
            # Detect mouth opening
            if not self.mouth_open and validated_open:
                self.mouth_open = True
                self.mouth_open_start_ts = timestamp
            
            # Detect mouth closing
            elif self.mouth_open and not validated_open:
                self.mouth_open = False
                if self.mouth_open_start_ts is not None:
                    duration = max(0.0, timestamp - self.mouth_open_start_ts)
                    # Record yawn if duration meets threshold
                    if duration >= YAWN_DURATION_SECONDS:
                        self.yawn_timestamps.append(timestamp)
                        self.yawn_durations.append(duration)
                self.mouth_open_start_ts = None
        
        self.last_lar = smoothed_lar  # Use smoothed LAR for tracking
    
    def get_current_lar(self):
        """
        Get the most recent smoothed LAR value.
        
        Returns:
            Smoothed LAR value (float) or None if no history
        """
        if not self.lar_history:
            return None
        # Return smoothed LAR (average of recent frames)
        return float(np.mean(self.lar_history))
    
    def get_yawn_count(self, current_time):
        """
        Get yawn count in the last time window.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Number of yawns in the window
        """
        window_start = current_time - BLINK_RATE_WINDOW
        return sum(1 for ts in self.yawn_timestamps if ts >= window_start)
    
    def get_recent_yawn_timestamps(self, current_time, window_seconds):
        """
        Get yawn timestamps within a specific time window.
        
        Args:
            current_time: Current timestamp
            window_seconds: Time window in seconds
            
        Returns:
            List of yawn timestamps within the window
        """
        window_start = current_time - window_seconds
        return [ts for ts in self.yawn_timestamps if ts >= window_start]
    
    def get_current_yawn_duration(self, current_time):
        """
        Get current yawn duration if mouth is currently open.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Duration in seconds (0.0 if mouth is closed)
        """
        if self.mouth_open and self.mouth_open_start_ts is not None:
            return float(max(0.0, current_time - self.mouth_open_start_ts))
        return 0.0
    
    def is_yawning(self, current_time, current_lar=None):
        """
        Check if currently yawning (LAR > threshold AND duration >= threshold).
        
        Matches the reference code logic:
        - yawning_detected = True when lar > LAR_THRESHOLD AND duration > YAWN_TIME_THRESHOLD
        - Stays True as long as lar > LAR_THRESHOLD continues
        
        Args:
            current_time: Current timestamp
            current_lar: Current LAR value (if None, uses smoothed LAR from history)
            
        Returns:
            True if currently yawning, False otherwise
        """
        if current_lar is None:
            current_lar = self.get_current_lar()
        
        if current_lar is None:
            return False
        
        # Must have LAR > threshold
        if current_lar <= LAR_THRESHOLD:
            return False
        
        # Must have mouth open for >= threshold duration
        if self.mouth_open and self.mouth_open_start_ts is not None:
            duration = current_time - self.mouth_open_start_ts
            return duration >= YAWN_DURATION_SECONDS
        
        return False

