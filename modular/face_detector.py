"""
Face Detection Module
MediaPipe Face Mesh detection and landmark extraction
"""

import cv2
import numpy as np
import mediapipe as mp
from config import DRAW_FACE_MESH

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


class FaceDetector:
    """
    MediaPipe Face Mesh detector for face, eye, and mouth landmarks.
    """
    
    # MediaPipe Face Mesh landmark indices
    LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
    
    # Lip landmarks for LAR (Lip Aspect Ratio) yawn detection:
    # 13: upper lip
    # 14: lower lip
    # 61: left mouth corner
    # 291: right mouth corner
    MOUTH_INDICES = [13, 14, 61, 291]  # Order: upper, lower, left, right
    
    def __init__(self, draw_face_mesh=False):
        """
        Initialize face detector.
        
        Args:
            draw_face_mesh: If True, draw full face mesh overlay
        """
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.draw_face_mesh = draw_face_mesh
    
    def detect(self, frame):
        """
        Detect face landmarks from frame.
        
        Args:
            frame: BGR image frame
            
        Returns:
            MediaPipe face landmarks object or None if no face detected
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)
        
        if not results.multi_face_landmarks:
            return None
        
        return results.multi_face_landmarks[0]
    
    def get_eye_landmarks(self, face_landmarks, frame_shape):
        """
        Extract eye landmark coordinates.
        
        Args:
            face_landmarks: MediaPipe face landmarks object
            frame_shape: Shape of frame (H, W, C)
            
        Returns:
            Tuple of (left_eye, right_eye) where each is a list of 6 (x, y) tuples
        """
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
        """
        Extract mouth landmark coordinates for LAR calculation.
        
        Args:
            face_landmarks: MediaPipe face landmarks object
            frame_shape: Shape of frame (H, W, C)
            
        Returns:
            List of 4 (x, y) tuples: [upper_lip, lower_lip, left_corner, right_corner]
        """
        h, w = frame_shape[:2]
        mouth = []
        
        if face_landmarks:
            # Order: upper, lower, left, right
            for idx in self.MOUTH_INDICES:
                lm = face_landmarks.landmark[idx]
                mouth.append((int(lm.x * w), int(lm.y * h)))
        
        return mouth
    
    def draw_face_mesh_landmarks(self, frame, face_landmarks):
        """
        Draw the full MediaPipe face mesh (net/tesselation) on the frame.
        
        Args:
            frame: BGR image frame
            face_landmarks: MediaPipe face landmarks object
            
        Returns:
            Frame with mesh drawn (if enabled)
        """
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
    
    def draw_eye_contours(self, frame, left_eye, right_eye, color=(0, 255, 255), thickness=2):
        """
        Draw eye contours on frame.
        
        Args:
            frame: BGR image frame
            left_eye: List of 6 (x, y) tuples for left eye
            right_eye: List of 6 (x, y) tuples for right eye
            color: BGR color tuple
            thickness: Line thickness
        """
        for eye in (left_eye, right_eye):
            if len(eye) == 6:
                pts = np.array(eye, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=thickness)

