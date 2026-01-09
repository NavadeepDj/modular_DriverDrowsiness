"""
EAR (Eye Aspect Ratio) Detection Module
Calculates EAR for single eye and average EAR for both eyes
"""

import numpy as np


def calculate_ear(eye_landmarks):
    """
    Calculate EAR for a single eye given 6 (x, y) points.
    
    Args:
        eye_landmarks: List of 6 (x, y) tuples representing eye landmarks
        
    Returns:
        EAR value (float) or None if invalid
    """
    if len(eye_landmarks) != 6:
        return None
    
    pts = np.array(eye_landmarks, dtype=np.float32)
    # vertical distances
    v1 = np.linalg.norm(pts[1] - pts[5])
    v2 = np.linalg.norm(pts[2] - pts[4])
    # horizontal distance
    h = np.linalg.norm(pts[0] - pts[3])
    
    if h == 0:
        return None
    
    return (v1 + v2) / (2.0 * h)


def calculate_average_ear(left_eye, right_eye):
    """
    Calculate average EAR from both eyes.
    
    Args:
        left_eye: List of 6 (x, y) tuples for left eye
        right_eye: List of 6 (x, y) tuples for right eye
        
    Returns:
        Average EAR value (float) or None if invalid
    """
    le = calculate_ear(left_eye)
    re = calculate_ear(right_eye)
    
    if le is None or re is None:
        return None
    
    return (le + re) / 2.0

