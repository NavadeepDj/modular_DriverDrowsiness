"""
Head Pose Estimation Module
Uses 2D MediaPipe FaceMesh landmarks + a generic 3D face model with solvePnP
to estimate yaw, pitch, and roll, and derive a simple attentiveness flag.
"""

import cv2
import numpy as np
import math
from collections import deque


def _rotation_matrix_to_euler_angles(R: np.ndarray):
    """
    Convert a 3x3 rotation matrix to yaw, pitch, roll in degrees.

    The implementation mirrors the standalone demo you provided and then
    normalizes angles into [-180, 180] so they behave nicely across wraparound.
    """
    sy = math.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    singular = sy < 1e-6

    if not singular:
        x = math.atan2(R[2, 1], R[2, 2])   # pitch
        y = math.atan2(-R[2, 0], sy)       # yaw
        z = math.atan2(R[1, 0], R[0, 0])   # roll
    else:
        x = math.atan2(-R[1, 2], R[1, 1])
        y = math.atan2(-R[2, 0], sy)
        z = 0.0

    # Convert radians → degrees and mirror pitch like in the demo
    yaw, pitch, roll = map(math.degrees, [y, -x, z])

    # Normalize to [-180, 180]
    yaw = (yaw + 180.0) % 360.0 - 180.0
    pitch = pitch % 360.0 - 180.0
    roll = (roll + 180.0) % 360.0 - 180.0
    return yaw, pitch, roll


class HeadPoseEstimator:
    """
    Lightweight head-pose estimator built around MediaPipe FaceMesh landmarks.

    It does **not** run MediaPipe itself; you pass in the `face_landmarks`
    object that `FaceDetector.detect()` already returns.
    """

    # Stable landmark indices for a 3D face model (MediaPipe FaceMesh indices)
    NOSE_TIP = 1
    CHIN = 152
    LEFT_EYE_OUTER = 33
    RIGHT_EYE_OUTER = 263
    MOUTH_LEFT = 61
    MOUTH_RIGHT = 291

    def __init__(self, smooth_window: int = 5):
        # Short history to smooth head-pose angles frame-to-frame
        self._angle_history = deque(maxlen=smooth_window)

    def estimate(self, face_landmarks, frame_shape):
        """
        Estimate head-pose (yaw, pitch, roll) and attentiveness flag.

        Args:
            face_landmarks: MediaPipe face landmarks object (from FaceDetector)
            frame_shape: shape of BGR frame (H, W, C)

        Returns:
            yaw, pitch, roll, looking
            If estimation fails, returns (None, None, None, False).
        """
        if face_landmarks is None:
            return None, None, None, False

        h, w = frame_shape[:2]

        def lm2xy(i):
            lm = face_landmarks.landmark[i]
            return np.array([lm.x * w, lm.y * h], dtype=np.float64)

        # 2D image points (pixels)
        image_points = np.array(
            [
                lm2xy(self.NOSE_TIP),
                lm2xy(self.CHIN),
                lm2xy(self.LEFT_EYE_OUTER),
                lm2xy(self.RIGHT_EYE_OUTER),
                lm2xy(self.MOUTH_LEFT),
                lm2xy(self.MOUTH_RIGHT),
            ],
            dtype=np.float64,
        )

        # Generic 3D model points (in mm), matching the indices above
        model_points = np.array(
            [
                [0.0, 0.0, 0.0],           # Nose tip
                [0.0, -63.6, -12.5],       # Chin
                [-43.3, 32.7, -26.0],      # Left eye outer
                [43.3, 32.7, -26.0],       # Right eye outer
                [-28.9, -28.9, -24.1],     # Left mouth corner
                [28.9, -28.9, -24.1],      # Right mouth corner
            ],
            dtype=np.float64,
        )

        # Approximate pinhole camera intrinsics
        focal_length = w
        center = (w / 2.0, h / 2.0)
        camera_matrix = np.array(
            [
                [focal_length, 0.0, center[0]],
                [0.0, focal_length, center[1]],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        success_pnp, rvec, _tvec = cv2.solvePnP(
            model_points,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success_pnp:
            return None, None, None, False

        R_mat, _ = cv2.Rodrigues(rvec)
        yaw, pitch, roll = _rotation_matrix_to_euler_angles(R_mat)

        # Smooth angles using a simple moving average
        self._angle_history.append((yaw, pitch, roll))
        yaw_s = float(np.mean([a[0] for a in self._angle_history]))
        pitch_s = float(np.mean([a[1] for a in self._angle_history]))
        roll_s = float(np.mean([a[2] for a in self._angle_history]))

        # Attention heuristic: "looking at road/camera"
        yaw_abs = abs(yaw_s)
        # Normalize pitch cyclically around ±180 like in the demo
        pitch_mod = min(abs(pitch_s), abs(abs(pitch_s) - 180.0))
        # Slightly tighter thresholds so off-axis head pose is flagged sooner.
        looking = yaw_abs < 20.0 and pitch_mod < 15.0

        return yaw_s, pitch_s, roll_s, looking


