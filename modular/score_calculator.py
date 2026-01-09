"""
Drowsiness Score Calculator Module
Calculates drowsiness score and classifies driver state based on all metrics
"""

from config import (
    SCORE_ALERT,
    SCORE_SLIGHTLY_DROWSY,
    SCORE_DROWSY,
    SCORE_VERY_DROWSY,
    PERCLOS_ALERT_MAX,
    PERCLOS_DROWSY_MIN,
    PERCLOS_HIGH_DROWSY_MIN,
    BLINK_RATE_ALERT_MAX,
    BLINK_RATE_DROWSY_MIN,
    BLINK_DURATION_DROWSY_MIN,
    BLINK_DURATION_MICROSLEEP_MIN,
    EYE_CLOSED_DROWSY_SECONDS,
    EAR_CLOSED_THRESHOLD,
    YAWN_DURATION_SECONDS
)


class ScoreCalculator:
    """
    Calculates drowsiness score (0-100) and classifies driver state.
    
    Score Weightage:
    - PERCLOS: up to 85 points (primary metric)
    - Continuous closure/microsleep: up to 70 points
    - Yawning: up to 50 points
    - Blink rate: up to 30 points
    - Blink duration: up to 20 points
    - Instantaneous EAR: up to 10 points
    """
    
    def __init__(self):
        """Initialize score calculator."""
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
        """
        Calculate drowsiness score from all metrics.
        
        Args:
            perclos: PERCLOS percentage (0-100)
            blink_rate: Blink rate (blinks per minute)
            ear: Current Eye Aspect Ratio
            closed_duration: Current eye closure duration (seconds)
            avg_blink_duration: Average blink duration (seconds)
            microsleep_count: Number of microsleep events in window
            yawn_count: Number of yawns in window
            current_yawn_duration: Current yawn duration (seconds)
            
        Returns:
            Drowsiness score (0.0 to 100.0)
        """
        score = 0.0
        
        # 1) PERCLOS (primary) - up to 85 points
        if perclos <= PERCLOS_ALERT_MAX:
            score += perclos * 1.0  # 0..10
        elif perclos < PERCLOS_DROWSY_MIN:
            score += 10 + (perclos - PERCLOS_ALERT_MAX) * 1.5  # 10..40
        elif perclos < PERCLOS_HIGH_DROWSY_MIN:
            score += 40 + (perclos - PERCLOS_DROWSY_MIN) * 2.0  # 40..60
        else:
            score += 60 + min((perclos - PERCLOS_HIGH_DROWSY_MIN) * 1.0, 25)  # 60..85
        
        # 2) Blink rate (supporting) - up to 30 points
        if blink_rate > BLINK_RATE_ALERT_MAX:
            score += min((blink_rate - BLINK_RATE_ALERT_MAX) * 1.2, 20)
        if blink_rate > BLINK_RATE_DROWSY_MIN:
            score += min((blink_rate - BLINK_RATE_DROWSY_MIN) * 0.8, 10)
        
        # 3) Blink duration - up to 20 points
        if avg_blink_duration >= BLINK_DURATION_DROWSY_MIN:
            score += min((avg_blink_duration - BLINK_DURATION_DROWSY_MIN) * 120, 20)
        
        # 4) Continuous closure / microsleep - up to 70 points
        if closed_duration >= EYE_CLOSED_DROWSY_SECONDS:
            score += 25
        if closed_duration >= BLINK_DURATION_MICROSLEEP_MIN:
            score += 25
        if microsleep_count > 0:
            score += 20
        
        # 5) Instantaneous EAR - up to 10 points
        if ear is not None and ear < EAR_CLOSED_THRESHOLD:
            score += min((EAR_CLOSED_THRESHOLD - ear) * 200, 10)
        
        # 6) Yawning (strong drowsiness indicator) - up to 50 points
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
        
        # Force minimum score if rule-based drowsy detected
        if rule_drowsy and score < SCORE_DROWSY:
            score = float(SCORE_DROWSY)
        
        # Clamp to 0-100
        score = float(max(0.0, min(score, 100.0)))
        
        self.current_score = score
        self._last_perclos = perclos
        self._rule_drowsy = rule_drowsy
        return score
    
    def classify_state(self, score):
        """
        Classify driver state from score and metrics.
        
        Priority:
        1. Hard drowsy rule (PERCLOS >= 30% OR closed >= 0.6s OR blink duration >= 0.48s)
        2. PERCLOS bands
        3. Score thresholds
        
        Args:
            score: Current drowsiness score
            
        Returns:
            State string: "ALERT", "SLIGHTLY_DROWSY", "DROWSY", "VERY_DROWSY"
        """
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

