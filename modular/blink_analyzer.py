"""
Blink Analysis Module
Tracks blink rate, blink duration, and microsleep events
"""

from collections import deque
from config import (
    BLINK_RATE_WINDOW,
    BLINK_MIN_SECONDS,
    BLINK_MAX_SECONDS,
    BLINK_MIN_INTERVAL_SECONDS,
    BLINK_DURATION_MICROSLEEP_MIN,
    EAR_CLOSED_THRESHOLD
)


class BlinkAnalyzer:
    """
    Analyzes blink rate, blink duration, and detects microsleep events.
    
    Tracks:
    - Blink rate (blinks per minute)
    - Average blink duration
    - Current eye closure duration
    - Microsleep count
    """
    
    def __init__(self):
        """Initialize blink analyzer."""
        # Blink tracking
        self.blink_timestamps = deque()
        self.blink_durations = deque()
        
        # Microsleep tracking
        self.microsleep_timestamps = deque()
        self.microsleep_durations = deque()
        
        # State tracking
        self.last_ear = None
        self.eyes_closed = False
        self.closed_start_ts = None
        self.last_blink_ts = None
    
    def update(self, ear, timestamp):
        """
        Update blink tracking with new EAR value.
        
        Args:
            ear: Current Eye Aspect Ratio value
            timestamp: Current timestamp
        """
        is_closed = ear < EAR_CLOSED_THRESHOLD
        
        if self.last_ear is not None:
            # Detect eye closure start
            if not self.eyes_closed and is_closed:
                self.eyes_closed = True
                self.closed_start_ts = timestamp
            
            # Detect eye opening (end of closure)
            elif self.eyes_closed and not is_closed:
                self.eyes_closed = False
                
                if self.closed_start_ts is not None:
                    duration = max(0.0, timestamp - self.closed_start_ts)
                    
                    # Check if enough time has passed since last blink (debounce)
                    if self.last_blink_ts is None or (timestamp - self.last_blink_ts) >= BLINK_MIN_INTERVAL_SECONDS:
                        # Classify as microsleep or normal blink
                        if duration >= BLINK_DURATION_MICROSLEEP_MIN:
                            # Microsleep event
                            self.microsleep_timestamps.append(timestamp)
                            self.microsleep_durations.append(duration)
                        elif BLINK_MIN_SECONDS <= duration <= BLINK_MAX_SECONDS:
                            # Normal blink
                            self.blink_timestamps.append(timestamp)
                            self.blink_durations.append(duration)
                            self.last_blink_ts = timestamp
                
                self.closed_start_ts = None
        
        self.last_ear = ear
    
    def calculate_blink_rate(self, current_time):
        """
        Calculate blink rate (blinks per minute) in the time window.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Blink rate (blinks per minute)
        """
        if not self.blink_timestamps:
            return 0.0
        
        window_start = current_time - BLINK_RATE_WINDOW
        recent = [ts for ts in self.blink_timestamps if ts >= window_start]
        
        if not recent:
            return 0.0
        
        return (len(recent) / BLINK_RATE_WINDOW) * 60.0
    
    def get_avg_blink_duration(self, current_time):
        """
        Get average blink duration in the time window.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Average blink duration in seconds
        """
        window_start = current_time - BLINK_RATE_WINDOW
        durations = [
            d for d, ts in zip(self.blink_durations, self.blink_timestamps)
            if ts >= window_start
        ]
        
        if not durations:
            return 0.0
        
        return float(sum(durations) / len(durations))
    
    def get_current_closed_duration(self, current_time):
        """
        Get current eye closure duration if eyes are currently closed.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Duration in seconds (0.0 if eyes are open)
        """
        if self.eyes_closed and self.closed_start_ts is not None:
            return float(max(0.0, current_time - self.closed_start_ts))
        return 0.0
    
    def get_microsleep_count(self, current_time):
        """
        Get microsleep count in the time window.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Number of microsleep events
        """
        window_start = current_time - BLINK_RATE_WINDOW
        return sum(1 for ts in self.microsleep_timestamps if ts >= window_start)

