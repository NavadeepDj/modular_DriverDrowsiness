"""
PERCLOS (Percentage of Eye Closure) Calculator Module
Tracks eye closure state and calculates PERCLOS percentage
"""

from collections import deque
from config import PERCLOS_WINDOW_SIZE, EAR_CLOSED_THRESHOLD


class PERCLOSCalculator:
    """
    Calculates PERCLOS (Percentage of Eye Closure) over a time window.
    
    PERCLOS = (time eyes are closed / total time) * 100%
    """
    
    def __init__(self):
        """Initialize PERCLOS calculator."""
        self.closed_state = deque()      # Boolean queue: True if closed, False if open
        self.state_timestamps = deque()  # Timestamps corresponding to each state
    
    def update(self, ear, timestamp):
        """
        Update PERCLOS tracking with new EAR value.
        
        Args:
            ear: Current Eye Aspect Ratio value
            timestamp: Current timestamp
        """
        is_closed = ear < EAR_CLOSED_THRESHOLD
        self.closed_state.append(is_closed)
        self.state_timestamps.append(timestamp)
        
        # Maintain window size - remove old entries outside the window
        while self.state_timestamps and (timestamp - self.state_timestamps[0]) > PERCLOS_WINDOW_SIZE:
            self.state_timestamps.popleft()
            self.closed_state.popleft()
    
    def calculate(self, current_time):
        """
        Calculate PERCLOS percentage for the current time window.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            PERCLOS percentage (0.0 to 100.0)
        """
        if not self.state_timestamps:
            return 0.0
        
        window_start = current_time - PERCLOS_WINDOW_SIZE
        closed = 0
        total = 0
        
        # Count closed vs total states in the window
        for is_closed, ts in zip(self.closed_state, self.state_timestamps):
            if ts >= window_start:
                total += 1
                if is_closed:
                    closed += 1
        
        if total == 0:
            return 0.0
        
        return (closed / total) * 100.0

