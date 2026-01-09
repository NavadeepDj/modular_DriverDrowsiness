"""
Camera Utilities Module
Handles camera initialization and robust frame reading with retry logic
"""

import cv2
import time
from config import (
    CAMERA_INDEX,
    CAMERA_BACKEND,
    CAMERA_PROBE_COUNT,
    FRAME_WIDTH,
    FRAME_HEIGHT,
    TARGET_FPS
)


def _backend_candidates():
    """
    Get list of camera backends to try (Windows compatibility).
    
    Returns:
        List of backend constants or None for default
    """
    backend = str(CAMERA_BACKEND).upper()
    if backend == "DSHOW" and hasattr(cv2, "CAP_DSHOW"):
        return [cv2.CAP_DSHOW]
    if backend == "MSMF" and hasattr(cv2, "CAP_MSMF"):
        return [cv2.CAP_MSMF]
    
    # AUTO: try common Windows backends first, then default
    candidates = []
    if hasattr(cv2, "CAP_DSHOW"):
        candidates.append(cv2.CAP_DSHOW)
    if hasattr(cv2, "CAP_MSMF"):
        candidates.append(cv2.CAP_MSMF)
    candidates.append(None)  # default backend
    return candidates


def open_camera():
    """
    Open a working camera capture device.
    Tries multiple backends and indices to avoid 'Failed to capture frame' on Windows.
    
    Returns:
        cv2.VideoCapture object
        
    Raises:
        RuntimeError: If no camera can be opened
    """
    indices = [CAMERA_INDEX] + [i for i in range(CAMERA_PROBE_COUNT) if i != CAMERA_INDEX]
    
    last_error = None
    for backend in _backend_candidates():
        for idx in indices:
            try:
                cap = cv2.VideoCapture(idx, backend) if backend is not None else cv2.VideoCapture(idx)
                if not cap.isOpened():
                    cap.release()
                    continue
                
                # Apply desired properties (some drivers ignore these; that's okay)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
                
                # Warm up a few frames
                ok = False
                for _ in range(10):
                    ret, _frame = cap.read()
                    if ret:
                        ok = True
                        break
                    time.sleep(0.05)
                
                if ok:
                    backend_name = "DEFAULT" if backend is None else str(backend)
                    print(f"Camera opened: index={idx}, backend={backend_name}")
                    return cap
                
                cap.release()
            except Exception as e:
                last_error = e
    
    msg = (
        f"Error: Could not read frames from any camera.\n"
        f"Tried indices: {indices}\n"
        f"Tried backends: {['DEFAULT' if b is None else b for b in _backend_candidates()]}\n"
        f"Tips:\n"
        f"- Close other apps using the camera (Teams/Zoom/Browser).\n"
        f"- Try changing CAMERA_INDEX in config.py.\n"
        f"- On Windows, set CAMERA_BACKEND to 'DSHOW' or 'MSMF'.\n"
    )
    if last_error:
        msg += f"Last error: {last_error}\n"
    raise RuntimeError(msg)

