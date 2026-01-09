"""
Optimized Single-File Driver Drowsiness & Attentiveness Detector

Features:
  - MediaPipe Face Mesh for robust face + eye landmarks
  - EAR (Eye Aspect Ratio), PERCLOS, blink rate & durations
  - Head pose estimation (yaw, pitch, roll) for attentiveness
  - Simple drowsiness state: ALERT / SLIGHTLY_DROWSY / DROWSY / VERY_DROWSY / INATTENTIVE
  - Lightweight console logging and on-screen overlay

This script is self-contained so you can run:
    python driver_drowsy.py
"""

import cv2
import math
import time
from collections import deque

import mediapipe as mp
import numpy as np

# ===========================
# CONFIG
# ===========================

# Eye Aspect Ratio (EAR) thresholds  (mirrors config.py)
EAR_CLOSED_THRESHOLD = 0.16
EAR_DROWSY_THRESHOLD = 0.16

# Lip Aspect Ratio (LAR) thresholds for yawn detection
LAR_THRESHOLD = 0.65                  # LAR > threshold => mouth open (yawning) - increased for accuracy
YAWN_DURATION_SECONDS = 1.5           # Mouth open for >= 1.5s => yawn event - increased for accuracy
LAR_SMOOTHING_WINDOW = 5              # Number of frames to average LAR for smoothing (reduces noise)
LAR_CONSECUTIVE_FRAMES = 3            # Require LAR > threshold for N consecutive frames before detecting yawn

# Continuous closure durations (seconds)
EYE_CLOSED_DROWSY_SECONDS = 0.6       # EAR < threshold for >= 0.6s => drowsy
MICROSLEEP_SECONDS = 0.45             # closure >= 0.45s => microsleep event

# PERCLOS configuration
PERCLOS_WINDOW_SIZE = 10              # seconds
PERCLOS_ALERT_MAX = 10.0
PERCLOS_DROWSY_MIN = 30.0
PERCLOS_HIGH_DROWSY_MIN = 40.0

# Blink thresholds
BLINK_RATE_WINDOW = 60                # seconds
BLINK_RATE_ALERT_MAX = 18.0
BLINK_RATE_DROWSY_MIN = 28.0

# Blink duration thresholds (seconds)
BLINK_DURATION_ALERT_MAX = 0.18       # 100–180ms alert range
BLINK_DURATION_DROWSY_MIN = 0.28      # 280–500ms drowsy range
BLINK_DURATION_MICROSLEEP_MIN = 0.48  # >480ms microsleep

# Blink detection debounce
BLINK_MIN_SECONDS = 0.08
BLINK_MAX_SECONDS = 0.80
BLINK_MIN_INTERVAL_SECONDS = 0.10

# Drowsiness score thresholds
SCORE_ALERT = 25
SCORE_SLIGHTLY_DROWSY = 55
SCORE_DROWSY = 80
SCORE_VERY_DROWSY = 100

# Camera settings
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 30

# Camera backend (mainly for Windows reliability)
# Options: "AUTO", "DSHOW", "MSMF"
CAMERA_BACKEND = "AUTO"

# How many camera indices to probe if CAMERA_INDEX fails (0..N-1)
CAMERA_PROBE_COUNT = 4

# Visualization settings
DRAW_FACE_MESH = True  # Set to True to draw full face mesh, False for eye contours only


# ===========================
# HELPER FUNCTIONS
# ===========================

def calculate_ear(eye_landmarks):
    """Calculate EAR for a single eye given 6 (x, y) points."""
    if len(eye_landmarks) != 6:
        return None
    pts = np.array(eye_landmarks, dtype=np.float32)
    # vertical
    v1 = np.linalg.norm(pts[1] - pts[5])
    v2 = np.linalg.norm(pts[2] - pts[4])
    # horizontal
    h = np.linalg.norm(pts[0] - pts[3])
    if h == 0:
        return None
    return (v1 + v2) / (2.0 * h)


def calculate_average_ear(left_eye, right_eye):
    le = calculate_ear(left_eye)
    re = calculate_ear(right_eye)
    if le is None or re is None:
        return None
    return (le + re) / 2.0


def calculate_lar(mouth_landmarks):
    """Calculate LAR (Lip Aspect Ratio) for yawn detection.
    
    Uses MediaPipe landmarks:
    - 13: upper lip
    - 14: lower lip
    - 61: left mouth corner
    - 291: right mouth corner
    
    LAR = (vertical distance between upper and lower lip) / (horizontal distance between corners)
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


def rotation_matrix_to_euler_angles(R: np.ndarray):
    """Convert 3x3 rotation matrix to yaw, pitch, roll in degrees."""
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

    yaw, pitch, roll = map(math.degrees, [y, -x, z])
    yaw = (yaw + 180.0) % 360.0 - 180.0
    pitch = pitch % 360.0 - 180.0
    roll = (roll + 180.0) % 360.0 - 180.0
    return yaw, pitch, roll


# ===========================
# METRICS
# ===========================

class DrowsinessMetrics:
    """Tracks EAR history, blink behaviour, closure durations, PERCLOS, LAR, yawns."""

    def __init__(self):
        # EAR history
        self.ear_history = deque()
        self.ear_timestamps = deque()

        # Blink / microsleep tracking
        self.blink_timestamps = deque()
        self.blink_durations = deque()
        self.microsleep_timestamps = deque()
        self.microsleep_durations = deque()

        self.last_ear = None
        self.eyes_closed = False
        self.closed_start_ts = None
        self.last_blink_ts = None

        # Closed/open state for PERCLOS
        self.closed_state = deque()
        self.state_timestamps = deque()

        # LAR / Yawn tracking
        self.lar_history = deque(maxlen=LAR_SMOOTHING_WINDOW)  # Limited size for smoothing
        self.lar_timestamps = deque()
        self.yawn_timestamps = deque()
        self.yawn_durations = deque()
        self.last_lar = None
        self.mouth_open = False
        self.mouth_open_start_ts = None
        self.lar_above_threshold_count = 0  # Count consecutive frames with LAR > threshold

    def update(self, ear, timestamp, lar=None):
        if ear is None:
            return

        self.ear_history.append(ear)
        self.ear_timestamps.append(timestamp)

        is_closed = ear < EAR_CLOSED_THRESHOLD
        self.closed_state.append(is_closed)
        self.state_timestamps.append(timestamp)

        # Maintain window size for PERCLOS history
        while self.state_timestamps and (timestamp - self.state_timestamps[0]) > PERCLOS_WINDOW_SIZE:
            self.state_timestamps.popleft()
            self.closed_state.popleft()

        # Blink / closure logic
        if self.last_ear is not None:
            if not self.eyes_closed and is_closed:
                self.eyes_closed = True
                self.closed_start_ts = timestamp
            elif self.eyes_closed and not is_closed:
                self.eyes_closed = False
                if self.closed_start_ts is not None:
                    duration = max(0.0, timestamp - self.closed_start_ts)
                    if self.last_blink_ts is None or (timestamp - self.last_blink_ts) >= BLINK_MIN_INTERVAL_SECONDS:
                        if duration >= BLINK_DURATION_MICROSLEEP_MIN:
                            self.microsleep_timestamps.append(timestamp)
                            self.microsleep_durations.append(duration)
                        elif BLINK_MIN_SECONDS <= duration <= BLINK_MAX_SECONDS:
                            self.blink_timestamps.append(timestamp)
                            self.blink_durations.append(duration)
                            self.last_blink_ts = timestamp
                self.closed_start_ts = None

        self.last_ear = ear

        # LAR / Yawn tracking with improved accuracy
        if lar is not None:
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
                if not self.mouth_open and validated_open:
                    self.mouth_open = True
                    self.mouth_open_start_ts = timestamp
                elif self.mouth_open and not validated_open:
                    self.mouth_open = False
                    if self.mouth_open_start_ts is not None:
                        duration = max(0.0, timestamp - self.mouth_open_start_ts)
                        if duration >= YAWN_DURATION_SECONDS:
                            self.yawn_timestamps.append(timestamp)
                            self.yawn_durations.append(duration)
                    self.mouth_open_start_ts = None

            self.last_lar = smoothed_lar  # Use smoothed LAR for tracking

    def calculate_perclos(self, current_time):
        if not self.state_timestamps:
            return 0.0
        window_start = current_time - PERCLOS_WINDOW_SIZE
        closed = 0
        total = 0
        for is_closed, ts in zip(self.closed_state, self.state_timestamps):
            if ts >= window_start:
                total += 1
                if is_closed:
                    closed += 1
        if total == 0:
            return 0.0
        return (closed / total) * 100.0

    def calculate_blink_rate(self, current_time):
        if not self.blink_timestamps:
            return 0.0
        window_start = current_time - BLINK_RATE_WINDOW
        recent = [ts for ts in self.blink_timestamps if ts >= window_start]
        if not recent:
            return 0.0
        return (len(recent) / BLINK_RATE_WINDOW) * 60.0

    def get_avg_blink_duration(self, current_time):
        window_start = current_time - BLINK_RATE_WINDOW
        durations = [d for d, ts in zip(self.blink_durations, self.blink_timestamps) if ts >= window_start]
        if not durations:
            return 0.0
        return float(sum(durations) / len(durations))

    def get_current_closed_duration(self, current_time):
        if self.eyes_closed and self.closed_start_ts is not None:
            return float(max(0.0, current_time - self.closed_start_ts))
        return 0.0

    def get_microsleep_count(self, current_time):
        window_start = current_time - BLINK_RATE_WINDOW
        return sum(1 for ts in self.microsleep_timestamps if ts >= window_start)

    def get_current_lar(self):
        """Get the most recent smoothed LAR value."""
        if not self.lar_history:
            return None
        # Return smoothed LAR (average of recent frames)
        return float(np.mean(self.lar_history))

    def get_yawn_count(self, current_time):
        """Get yawn count in the last window."""
        window_start = current_time - BLINK_RATE_WINDOW
        return sum(1 for ts in self.yawn_timestamps if ts >= window_start)

    def get_current_yawn_duration(self, current_time):
        """Get current yawn duration if mouth is currently open."""
        if self.mouth_open and self.mouth_open_start_ts is not None:
            return float(max(0.0, current_time - self.mouth_open_start_ts))
        return 0.0
    
    def is_yawning(self, current_time, current_lar=None):
        """Check if currently yawning (LAR > threshold AND duration >= threshold).
        
        Matches the reference code logic:
        - yawning_detected = True when lar > LAR_THRESHOLD AND duration > YAWN_TIME_THRESHOLD
        - Stays True as long as lar > LAR_THRESHOLD continues
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


# ===========================
# SCORER
# ===========================

class DrowsinessScorer:
    """Calculates drowsiness score and classifies driver state."""

    def __init__(self):
        self.current_score = 0.0
        self.current_state = "ALERT"
        self._last_perclos = 0.0
        self._rule_drowsy = False

    def calculate_score(
        self,
        perclos,
        blink_rate,
        ear,
        closed_duration=0.0,
        avg_blink_duration=0.0,
        microsleep_count=0,
        yawn_count=0,
        current_yawn_duration=0.0,
    ):
        score = 0.0

        # 1) PERCLOS (primary)
        if perclos <= PERCLOS_ALERT_MAX:
            score += perclos * 1.0  # 0..10
        elif perclos < PERCLOS_DROWSY_MIN:
            score += 10 + (perclos - PERCLOS_ALERT_MAX) * 1.5  # 10..40
        elif perclos < PERCLOS_HIGH_DROWSY_MIN:
            score += 40 + (perclos - PERCLOS_DROWSY_MIN) * 2.0  # 40..60
        else:
            score += 60 + min((perclos - PERCLOS_HIGH_DROWSY_MIN) * 1.0, 25)  # 60..85

        # 2) Blink rate (supporting)
        if blink_rate > BLINK_RATE_ALERT_MAX:
            score += min((blink_rate - BLINK_RATE_ALERT_MAX) * 1.2, 20)
        if blink_rate > BLINK_RATE_DROWSY_MIN:
            score += min((blink_rate - BLINK_RATE_DROWSY_MIN) * 0.8, 10)

        # 3) Blink duration
        if avg_blink_duration >= BLINK_DURATION_DROWSY_MIN:
            score += min((avg_blink_duration - BLINK_DURATION_DROWSY_MIN) * 120, 20)

        # 4) Continuous closure / microsleep
        if closed_duration >= EYE_CLOSED_DROWSY_SECONDS:
            score += 25
        if closed_duration >= BLINK_DURATION_MICROSLEEP_MIN:
            score += 25
        if microsleep_count > 0:
            score += 20

        # 5) Instantaneous EAR
        if ear is not None and ear < EAR_CLOSED_THRESHOLD:
            score += min((EAR_CLOSED_THRESHOLD - ear) * 200, 10)

        # 6) Yawning (strong drowsiness indicator)
        if yawn_count > 0:
            score += min(yawn_count * 15, 30)  # Up to 30 points for multiple yawns
        if current_yawn_duration >= YAWN_DURATION_SECONDS:
            score += 20  # Active yawn adds significant score

        # Rule-based override (simple academic rule)
        rule_drowsy = False
        if perclos is not None and perclos >= PERCLOS_DROWSY_MIN:
            rule_drowsy = True
        if closed_duration >= EYE_CLOSED_DROWSY_SECONDS:
            rule_drowsy = True
        if avg_blink_duration >= BLINK_DURATION_MICROSLEEP_MIN:
            rule_drowsy = True

        if rule_drowsy and score < SCORE_DROWSY:
            score = float(SCORE_DROWSY)

        # Clamp
        score = float(max(0.0, min(score, 100.0)))

        self.current_score = score
        self._last_perclos = perclos
        self._rule_drowsy = rule_drowsy
        return score

    def classify_state(self, score):
        perclos = self._last_perclos
        rule_drowsy = self._rule_drowsy

        # Hard drowsy rule
        if rule_drowsy:
            state = "DROWSY" if score < SCORE_VERY_DROWSY else "VERY_DROWSY"
        # PERCLOS bands
        elif perclos is not None:
            if perclos < PERCLOS_ALERT_MAX:
                state = "ALERT"
            elif perclos <= PERCLOS_DROWSY_MIN:
                state = "SLIGHTLY_DROWSY"
            else:
                state = "DROWSY"
        # Fallback on score thresholds
        else:
            if score <= SCORE_ALERT:
                state = "ALERT"
            elif score <= SCORE_SLIGHTLY_DROWSY:
                state = "SLIGHTLY_DROWSY"
            elif score <= SCORE_DROWSY:
                state = "DROWSY"
            else:
                state = "VERY_DROWSY"

        self.current_state = state
        return state


# ===========================
# MEDIA PIPE FACE + HEAD POSE
# ===========================

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


class FaceAndHeadEstimator:
    """Wrapper around MediaPipe FaceMesh for eyes + head pose."""

    LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
    # Lip landmarks for LAR (Lip Aspect Ratio) yawn detection:
    # 13: upper lip
    # 14: lower lip
    # 61: left mouth corner
    # 291: right mouth corner
    UPPER_LIP = 13
    LOWER_LIP = 14
    MOUTH_LEFT = 61
    MOUTH_RIGHT = 291
    MOUTH_INDICES = [13, 14, 61, 291]  # Order: upper, lower, left, right

    NOSE_TIP = 1
    CHIN = 152
    LEFT_EYE_OUTER = 33
    RIGHT_EYE_OUTER = 263
    MOUTH_LEFT = 61
    MOUTH_RIGHT = 291

    def __init__(self, draw_face_mesh=False):
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._angle_history = deque(maxlen=5)
        self.draw_face_mesh = draw_face_mesh

    def detect(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            return None
        return results.multi_face_landmarks[0]
    
    def draw_face_mesh_landmarks(self, frame, face_landmarks):
        """Draw the full MediaPipe face mesh (net/tesselation) on the frame using a single uniform color."""
        if face_landmarks and self.draw_face_mesh:
            # Single uniform color for entire face mesh (white/light color)
            uniform_style = mp_drawing.DrawingSpec(
                color=(255, 255, 255),  # White in BGR - same color for all parts
                thickness=1,
                circle_radius=0
            )
            
            # Draw tesselation mesh (triangular grid that wraps the entire face)
            mp_drawing.draw_landmarks(
                image=frame,
                landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=uniform_style
            )
            
            # Draw face contours (jawline, lips, eyebrows) with same color
            mp_drawing.draw_landmarks(
                image=frame,
                landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=uniform_style
            )
            
            # Draw iris connections (if refine_landmarks=True) with same color
            try:
                mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=mp_face_mesh.FACEMESH_IRISES,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=uniform_style
                )
            except (AttributeError, KeyError):
                # Iris connections may not be available in all versions
                pass
        return frame

    def get_eye_landmarks(self, face_landmarks, frame_shape):
        h, w = frame_shape[:2]
        left_eye = []
        right_eye = []
        if face_landmarks:
            for idx in self.LEFT_EYE_INDICES:
                lm = face_landmarks.landmark[idx]
                left_eye.append((int(lm.x * w), int(lm.y * h)))
            for idx in self.RIGHT_EYE_INDICES:
                lm = face_landmarks.landmark[idx]
                right_eye.append((int(lm.x * w), int(lm.y * h)))
        return left_eye, right_eye

    def get_mouth_landmarks(self, face_landmarks, frame_shape):
        """Extract mouth landmark coordinates for LAR calculation.
        
        Returns: [upper_lip, lower_lip, left_corner, right_corner]
        """
        h, w = frame_shape[:2]
        mouth = []
        if face_landmarks:
            # Order: upper, lower, left, right
            for idx in self.MOUTH_INDICES:
                lm = face_landmarks.landmark[idx]
                mouth.append((int(lm.x * w), int(lm.y * h)))
        return mouth

    def draw_eye_contours(self, frame, left_eye, right_eye, color=(0, 255, 255), thickness=2):
        for eye in (left_eye, right_eye):
            if len(eye) == 6:
                pts = np.array(eye, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=thickness)

    def estimate_head_pose(self, face_landmarks, frame_shape):
        if face_landmarks is None:
            return None, None, None, False

        h, w = frame_shape[:2]

        def lm2xy(i):
            lm = face_landmarks.landmark[i]
            return np.array([lm.x * w, lm.y * h], dtype=np.float64)

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

        model_points = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.0, -63.6, -12.5],
                [-43.3, 32.7, -26.0],
                [43.3, 32.7, -26.0],
                [-28.9, -28.9, -24.1],
                [28.9, -28.9, -24.1],
            ],
            dtype=np.float64,
        )

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

        success, rvec, _ = cv2.solvePnP(
            model_points,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not success:
            return None, None, None, False

        R_mat, _ = cv2.Rodrigues(rvec)
        yaw, pitch, roll = rotation_matrix_to_euler_angles(R_mat)

        self._angle_history.append((yaw, pitch, roll))
        yaw_s = float(np.mean([a[0] for a in self._angle_history]))
        pitch_s = float(np.mean([a[1] for a in self._angle_history]))
        roll_s = float(np.mean([a[2] for a in self._angle_history]))

        yaw_abs = abs(yaw_s)
        pitch_mod = min(abs(pitch_s), abs(abs(pitch_s) - 180.0))
        looking = yaw_abs < 20.0 and pitch_mod < 15.0

        return yaw_s, pitch_s, roll_s, looking


# ===========================
# MAIN LOOP
# ===========================

def _backend_candidates():
    """Get list of camera backends to try (Windows compatibility)."""
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
        f"- Try changing CAMERA_INDEX in the script.\n"
        f"- On Windows, set CAMERA_BACKEND to 'DSHOW' or 'MSMF'.\n"
    )
    if last_error:
        msg += f"Last error: {last_error}\n"
    raise RuntimeError(msg)


def draw_overlay(
    frame,
    state,
    score,
    ear,
    perclos,
    blink_rate,
    yaw,
    pitch,
    roll,
    looking,
    lar=None,
    yawn_count=0,
    is_yawning=False,
    current_yawn_duration=0.0,
):
    color_map = {
        "ALERT": (0, 255, 0),
        "SLIGHTLY_DROWSY": (0, 255, 255),
        "DROWSY": (0, 165, 255),
        "VERY_DROWSY": (0, 0, 255),
        "INATTENTIVE": (0, 0, 255),
    }
    color = color_map.get(state, (255, 255, 255))

    cv2.putText(frame, f"State: {state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(frame, f"Score: {score:.1f}/100", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # Draw numeric metrics in black for better visibility on light backgrounds
    if ear is not None:
        cv2.putText(frame, f"EAR: {ear:.3f}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.putText(frame, f"PERCLOS: {perclos:.1f}%", (10, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.putText(frame, f"Blink Rate: {blink_rate:.1f}/min", (10, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    # Show "YAWNING DETECTED" when LAR > threshold AND duration >= threshold (matching reference code)
    if is_yawning:
        cv2.putText(frame, "YAWNING DETECTED", (30, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)

    if yaw is not None and pitch is not None and roll is not None:
        y_offset = 190
        attn_text = "ATTENTIVE" if looking else "NOT ATTENTIVE"
        attn_color = (0, 255, 0) if looking else (0, 0, 255)
        cv2.putText(
            frame,
            f"Attention: {attn_text}",
            (10, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            attn_color,
            2,
        )
        cv2.putText(
            frame,
            f"Yaw: {yaw:.1f}  Pitch: {pitch:.1f}  Roll: {roll:.1f}",
            (10, y_offset + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
        )
        
        # Show LAR below the attention text
        if lar is not None:
            cv2.putText(
                frame,
                f"LAR: {lar:.2f}",
                (10, y_offset + 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
            )
        
        # Show yawn count below LAR
        cv2.putText(
            frame,
            f"Yawns: {yawn_count}",
            (10, y_offset + 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255) if yawn_count > 0 else (0, 0, 0),
            1,
        )


def main():
    print("Starting Driver Drowsiness & Attentiveness Detector...")
    cap = open_camera()
    face_head = FaceAndHeadEstimator(draw_face_mesh=DRAW_FACE_MESH)
    metrics = DrowsinessMetrics()
    scorer = DrowsinessScorer()

    frame_count = 0
    start_time = time.time()

    consecutive_failures = 0
    last_warning_time = 0
    
    try:
        while True:
            t0 = time.time()
            ret, frame = cap.read()
            
            # Validate frame
            if not ret or frame is None or frame.size == 0:
                consecutive_failures += 1
                
                # Few transient failures: silently retry (common camera glitches)
                if consecutive_failures <= 5:
                    time.sleep(0.01)  # Very short delay for transient glitches
                    continue
                
                # Moderate failures: warn occasionally (not every time)
                if consecutive_failures <= 20:
                    current_time = time.time()
                    # Only warn once every 5 seconds to avoid spam
                    if current_time - last_warning_time > 5.0:
                        print(f"Warning: Camera glitch detected ({consecutive_failures} failures), retrying...")
                        last_warning_time = current_time
                    time.sleep(0.05)
                    continue

                # Many consecutive failures: try to re-open the camera once
                print("Error: Camera appears stuck, attempting to re-open...")
                try:
                    cap.release()
                except Exception:
                    pass

                try:
                    time.sleep(0.5)  # Brief pause before re-opening
                    cap = open_camera()
                    consecutive_failures = 0
                    last_warning_time = 0
                    print("Camera successfully re-opened, resuming...")
                    continue
                except Exception as e:
                    print(f"Failed to re-open camera: {e}")
                    break

            # Successful read: reset failure counter
            if consecutive_failures > 0:
                consecutive_failures = 0
                last_warning_time = 0

            face_landmarks = face_head.detect(frame)

            state = "NO_FACE"
            score = 0.0
            ear = None
            perclos = 0.0
            blink_rate = 0.0
            yaw = pitch = roll = None
            looking = False

            now = time.time()  # Get current time once per frame
            
            if face_landmarks:
                # Draw face mesh if enabled
                face_head.draw_face_mesh_landmarks(frame, face_landmarks)
                
                left_eye, right_eye = face_head.get_eye_landmarks(face_landmarks, frame.shape)
                mouth_landmarks = face_head.get_mouth_landmarks(face_landmarks, frame.shape)
                
                if left_eye and right_eye:
                    # Draw eye contours (only if face mesh is not drawn, or as overlay)
                    if not DRAW_FACE_MESH:
                        face_head.draw_eye_contours(frame, left_eye, right_eye)
                    ear = calculate_average_ear(left_eye, right_eye)

                lar = None
                if mouth_landmarks and len(mouth_landmarks) == 4:
                    lar = calculate_lar(mouth_landmarks)

                if ear is not None:
                    metrics.update(ear, now, lar=lar)

                    yaw, pitch, roll, looking = face_head.estimate_head_pose(face_landmarks, frame.shape)

                    perclos = metrics.calculate_perclos(now)
                    blink_rate = metrics.calculate_blink_rate(now)
                    avg_blink = metrics.get_avg_blink_duration(now)
                    closed_dur = metrics.get_current_closed_duration(now)
                    micro_count = metrics.get_microsleep_count(now)
                    yawn_count = metrics.get_yawn_count(now)
                    current_yawn_dur = metrics.get_current_yawn_duration(now)

                    score = scorer.calculate_score(
                        perclos,
                        blink_rate,
                        ear,
                        closed_duration=closed_dur,
                        avg_blink_duration=avg_blink,
                        microsleep_count=micro_count,
                        yawn_count=yawn_count,
                        current_yawn_duration=current_yawn_dur,
                    )
                    state = scorer.classify_state(score)

                    # Attentiveness override
                    if yaw is not None and not looking:
                        state = "INATTENTIVE"

            # Get yawn status for display
            lar_display = lar if face_landmarks and lar is not None else (metrics.get_current_lar() if face_landmarks else None)
            yawn_count_display = metrics.get_yawn_count(now) if face_landmarks else 0
            is_yawning_now = metrics.is_yawning(now, current_lar=lar_display) if face_landmarks else False
            current_yawn_dur_display = metrics.get_current_yawn_duration(now) if face_landmarks else 0.0
            draw_overlay(frame, state, score, ear, perclos, blink_rate, yaw, pitch, roll, looking, 
                        lar_display, yawn_count_display, is_yawning_now, current_yawn_dur_display)

            cv2.imshow("Driver Drowsiness", frame)

            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                if ear is not None:
                    print(
                        f"FPS: {fps:.1f} | State: {state} | Score: {score:.1f} | "
                        f"EAR: {ear:.3f} | PERCLOS: {perclos:.1f}% | "
                        f"Blink Rate: {blink_rate:.1f}/min"
                    )
                else:
                    print(f"FPS: {fps:.1f} | No face detected")

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Shutdown complete.")


if __name__ == "__main__":
    main()


