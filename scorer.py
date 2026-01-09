"""
Drowsiness Scoring Engine
Calculates drowsiness score and classifies driver state
"""

from config import (
    SCORE_ALERT,
    SCORE_SLIGHTLY_DROWSY,
    SCORE_DROWSY,
    SCORE_VERY_DROWSY,
    EAR_CLOSED_THRESHOLD,
    EYE_CLOSED_DROWSY_SECONDS,
    PERCLOS_ALERT_MAX,
    PERCLOS_DROWSY_MIN,
    PERCLOS_HIGH_DROWSY_MIN,
    BLINK_RATE_ALERT_MAX,
    BLINK_RATE_DROWSY_MIN,
    BLINK_DURATION_DROWSY_MIN,
    BLINK_DURATION_MICROSLEEP_MIN,
)


class DrowsinessScorer:
    """Calculates drowsiness score and determines driver state"""
    
    def __init__(self):
        """Initialize scorer"""
        self.current_score = 0
        self.current_state = "ALERT"
    
    def calculate_score(
        self,
        perclos,
        blink_rate,
        ear,
        closed_duration=0.0,
        avg_blink_duration=0.0,
        microsleep_count=0,
    ):
        """
        Calculate drowsiness score from metrics
        
        Score ranges from 0 (alert) to 100 (very drowsy)
        
        Args:
            perclos: PERCLOS percentage (0-100)
            blink_rate: Blink rate (blinks per minute)
            ear: Current Eye Aspect Ratio
            
        Returns:
            score: Drowsiness score (0-100)
        """
        score = 0.0

        # 1) PERCLOS (industry standard)
        # Alert: <10%, Highly drowsy: >30–40%
        if perclos <= PERCLOS_ALERT_MAX:
            score += perclos * 1.0  # 0..10
        elif perclos < PERCLOS_DROWSY_MIN:
            score += 10 + (perclos - PERCLOS_ALERT_MAX) * 1.5  # 10..40
        elif perclos < PERCLOS_HIGH_DROWSY_MIN:
            score += 40 + (perclos - PERCLOS_DROWSY_MIN) * 2.0  # 40..60
        else:
            score += 60 + min((perclos - PERCLOS_HIGH_DROWSY_MIN) * 1.0, 25)  # 60..85

        # 2) Blink rate (supporting)
        # Alert: 10–20, Severe: >30
        if blink_rate > BLINK_RATE_ALERT_MAX:
            score += min((blink_rate - BLINK_RATE_ALERT_MAX) * 1.2, 20)
        if blink_rate > BLINK_RATE_DROWSY_MIN:
            score += min((blink_rate - BLINK_RATE_DROWSY_MIN) * 0.8, 10)

        # 3) Blink duration (stronger than rate)
        if avg_blink_duration >= BLINK_DURATION_DROWSY_MIN:
            score += min((avg_blink_duration - BLINK_DURATION_DROWSY_MIN) * 120, 20)

        # 4) Continuous closure / microsleep (strongest)
        if closed_duration >= EYE_CLOSED_DROWSY_SECONDS:
            score += 25
        if closed_duration >= BLINK_DURATION_MICROSLEEP_MIN:
            score += 25
        if microsleep_count > 0:
            score += 20

        # 5) Instantaneous EAR (minor contribution)
        if ear is not None and ear < EAR_CLOSED_THRESHOLD:
            score += min((EAR_CLOSED_THRESHOLD - ear) * 200, 10)

        # --- Rule-based override (matches the description you pasted) ---
        # If (PERCLOS > 30%) OR
        #    (EAR < threshold for > EYE_CLOSED_DROWSY_SECONDS) OR
        #    (Blink duration > BLINK_DURATION_MICROSLEEP_MIN)
        # → Driver is at least DROWSY.
        rule_drowsy = False
        if perclos is not None and perclos >= PERCLOS_DROWSY_MIN:
            rule_drowsy = True
        if closed_duration >= EYE_CLOSED_DROWSY_SECONDS:
            rule_drowsy = True
        if avg_blink_duration >= BLINK_DURATION_MICROSLEEP_MIN:
            rule_drowsy = True

        if rule_drowsy and score < SCORE_DROWSY:
            score = float(SCORE_DROWSY)

        # Ensure score is between 0 and 100
        score = float(max(0.0, min(score, 100.0)))

        # Cache latest values so classify_state can respect PERCLOS bands
        self.current_score = score
        self._last_perclos = perclos
        self._rule_drowsy = rule_drowsy
        return score
    
    def classify_state(self, score):
        """
        Classify driver state based on score
        
        Args:
            score: Drowsiness score (0-100)
            
        Returns:
            state: Driver state string
        """
        perclos = getattr(self, "_last_perclos", None)
        rule_drowsy = getattr(self, "_rule_drowsy", False)

        # 1) If the hard drowsy rule fired, force at least DROWSY
        if rule_drowsy:
            if score >= SCORE_DROWSY:
                state = "VERY_DROWSY"
            else:
                state = "DROWSY"
        # 2) Otherwise, map state primarily from PERCLOS bands
        elif perclos is not None:
            if perclos < PERCLOS_ALERT_MAX:
                state = "ALERT"
            elif perclos <= PERCLOS_DROWSY_MIN:
                state = "SLIGHTLY_DROWSY"
            else:
                state = "DROWSY"
        # 3) Fallback: purely score-based if PERCLOS unavailable
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
    
    def get_score(self):
        """Get current drowsiness score"""
        return self.current_score
    
    def get_state(self):
        """Get current driver state"""
        return self.current_state

