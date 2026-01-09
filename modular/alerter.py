"""
Two-Level Alert System Module
Implements progressive alerts based on drowsiness symptoms (state-based)

Level 1: Triggers when drowsiness symptoms are detected
Level 2: Escalates only if Level 1 persists
"""

import sys
import time
import threading
from array import array

try:
    import pygame
    pygame_available = True
except ImportError:
    pygame_available = False

from config import (
    LEVEL1_DURATION_SECONDS,
    YAWN_ALERT_WINDOW_SECONDS,
    YAWN_ALERT_THRESHOLD,
    YAWN_RECENT_WINDOW_SECONDS
)


def _beep(frequency_hz: int, duration_s: float):
    """
    Cross-platform beep:
    - Windows: winsound.Beep (reliable)
    - Else: pygame mixer tone
    """
    if sys.platform.startswith("win"):
        try:
            import winsound
            winsound.Beep(int(frequency_hz), int(duration_s * 1000))
            return
        except Exception:
            pass

    # Fallback: pygame tone (best-effort)
    if pygame_available:
        try:
            sample_rate = 22050
            n_samples = int(duration_s * sample_rate)
            # simple square-ish wave
            buf = array("h")
            period = max(1, int(sample_rate / max(1, frequency_hz)))
            amp = 12000
            for i in range(n_samples):
                buf.append(amp if (i % period) < (period // 2) else -amp)
            sound = pygame.mixer.Sound(buffer=buf.tobytes())
            sound.play()
        except Exception:
            pass


class AlertEngine:
    """
    Manages two-level alert system with audio and visual feedback.
    
    Alert Logic:
    - Level 1: Triggers when driver state indicates drowsiness symptoms
               (SLIGHTLY_DROWSY, DROWSY, VERY_DROWSY, INATTENTIVE)
    - Level 2: Escalates when 3 Level 1 alerts occur within 30-second window
    """
    
    # States that indicate drowsiness symptoms (trigger Level 1)
    DROWSY_STATES = ["SLIGHTLY_DROWSY", "DROWSY", "VERY_DROWSY", "INATTENTIVE"]
    
    def __init__(self):
        """Initialize alert engine."""
        self.level1_start = None
        self.level1_triggered_at = None
        self.level2_triggered = False
        self.level1_active = False
        self.level2_active = False
        
        # Level 1 alert frequency tracking (for Level 2 escalation)
        self.level1_trigger_timestamps = []  # List of timestamps when Level 1 was triggered
        self.level2_escalation_window = 30.0  # 30-second window for counting Level 1 occurrences
        self.level2_trigger_count = 3  # Trigger Level 2 after 3 Level 1 alerts in window
        
        # Yawn-based alert tracking
        self.yawn_timestamps = []  # List of yawn timestamps for alert tracking
        self.yawns_since_level1 = 0  # Count of yawns since Level 1 was triggered
        
        # Initialize pygame mixer for audio alerts
        self.audio_enabled = False
        if pygame_available:
            try:
                pygame.mixer.init()
                self.audio_enabled = True
            except Exception:
                print("Warning: Audio alerts disabled (pygame mixer not available)")
        else:
            print("Warning: pygame not available, audio alerts disabled")
        
        # Alert thread control
        self.alert_thread = None
        self.stop_alert = False
    
    def process(self, state, timestamp, yawn_timestamps=None):
        """
        Process driver state and yawn timestamps, trigger appropriate alerts based on symptoms.
        
        Frequency-based Level 2 escalation:
        - Level 2 triggers when 3 Level 1 alerts occur within 30-second window
        
        Args:
            state: Current driver state string (ALERT, SLIGHTLY_DROWSY, DROWSY, etc.)
            timestamp: Current timestamp in seconds
            yawn_timestamps: List of recent yawn timestamps (optional, for yawn-based alerts)
        """
        # Update yawn timestamps if provided
        if yawn_timestamps is not None:
            # Add new yawns that aren't already tracked
            for ts in yawn_timestamps:
                if ts not in self.yawn_timestamps:
                    self.yawn_timestamps.append(ts)
                    # Track if yawn occurred after Level 1 was triggered
                    if self.level1_triggered_at is not None and ts >= self.level1_triggered_at:
                        self.yawns_since_level1 += 1
        
        # Check if state indicates drowsiness symptoms
        has_drowsiness_symptoms = state in self.DROWSY_STATES
        
        # Check yawn-based trigger (independent of state)
        yawn_trigger = self._check_yawn_trigger(timestamp)
        
        # Level 1 can be triggered by either state-based symptoms OR yawn frequency
        should_trigger_level1 = has_drowsiness_symptoms or yawn_trigger
        
        if should_trigger_level1:
            # Start tracking Level 1 alert duration
            if self.level1_start is None:
                self.level1_start = timestamp
            
            elapsed = timestamp - self.level1_start
            
            # Trigger Level 1 after duration threshold
            if elapsed >= LEVEL1_DURATION_SECONDS and not self.level1_active:
                if yawn_trigger and not has_drowsiness_symptoms:
                    trigger_reason = "yawn frequency"
                elif yawn_trigger and has_drowsiness_symptoms:
                    trigger_reason = "drowsiness symptoms + yawn frequency"
                else:
                    trigger_reason = "drowsiness symptoms"
                self.trigger_level1(timestamp, trigger_reason)
            
            # Check if Level 1 should be reset (state is ALERT and no new yawns)
            # This prevents Level 1 from staying active when only old yawns are in the window
            if self.level1_active and self.level1_triggered_at is not None:
                # If state is ALERT and no new yawns occurred after Level 1, reset immediately
                if not has_drowsiness_symptoms and self.yawns_since_level1 == 0:
                    # Check if enough time has passed since Level 1 (at least 5 seconds)
                    level1_elapsed = timestamp - self.level1_triggered_at
                    if level1_elapsed >= 5.0:  # Give a small buffer before reset
                        # State is ALERT and no new yawns → reset Level 1
                        self.reset()
                        return  # Exit early, don't check for Level 2
            
            # Check for Level 2 escalation: 3 Level 1 alerts within 30-second window
            if self.level1_active and not self.level2_active:
                self._check_and_trigger_level2(timestamp)
        else:
            # Reset if symptoms clear (driver becomes alert) AND no yawn trigger
            # This handles the case where yawn frequency drops below threshold
            if state == "ALERT" or state == "NO_FACE":
                # Reset if yawn frequency also dropped below threshold
                if not yawn_trigger:
                    self.reset()
            elif not yawn_trigger:
                # If yawn frequency dropped but state is still drowsy, 
                # reset Level 1 but keep monitoring state-based symptoms
                if self.level1_active and self.level1_triggered_at is not None:
                    # Check if Level 1 was triggered by yawn frequency only
                    # If so, reset it since yawn frequency dropped
                    if not has_drowsiness_symptoms:
                        self.reset()
    
    def _check_and_trigger_level2(self, timestamp):
        """
        Check if Level 2 should be triggered based on frequency of Level 1 alerts.
        
        Level 2 triggers when 3 Level 1 alerts occur within 30-second window.
        
        Args:
            timestamp: Current timestamp
        """
        # Add current Level 1 trigger to tracking
        if self.level1_triggered_at is not None:
            self.level1_trigger_timestamps.append(self.level1_triggered_at)
        
        # Remove old triggers outside the 30-second window
        window_start = timestamp - self.level2_escalation_window
        self.level1_trigger_timestamps = [
            ts for ts in self.level1_trigger_timestamps if ts >= window_start
        ]
        
        # Count Level 1 triggers in the window
        level1_count = len(self.level1_trigger_timestamps)
        
        print(f"[LEVEL 2 CHECK] {level1_count}/{self.level2_trigger_count} Level 1 alerts in {self.level2_escalation_window}s window")
        
        # Trigger Level 2 if threshold reached
        if level1_count >= self.level2_trigger_count:
            self.trigger_level2(timestamp)
    
    def _check_yawn_trigger(self, timestamp):
        """
        Check if yawn frequency triggers Level 1 alert.
        
        Research-backed thresholds:
        - ≥ 2 yawns/min → Unusual (Moderate risk) → Level 1 Alert
        - ≥ 3 yawns/min → Strong drowsiness indicator (High risk) → Level 1 Alert
        - ≥ 4 yawns/min → Critical/Unsafe → Level 1 Alert
        
        Uses rolling 1-minute window for yawn frequency calculation.
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            True if yawn frequency should trigger Level 1, False otherwise
        """
        # Clean old yawns outside the tracking window (keep 1 minute)
        cutoff_time = timestamp - YAWN_ALERT_WINDOW_SECONDS
        self.yawn_timestamps = [ts for ts in self.yawn_timestamps if ts >= cutoff_time]
        
        # Count yawns in the last 1 minute (rolling window)
        window_start = timestamp - YAWN_ALERT_WINDOW_SECONDS
        yawns_in_window = sum(1 for ts in self.yawn_timestamps if ts >= window_start)
        
        # Calculate yawns per minute
        yawns_per_minute = yawns_in_window  # Since window is 60 seconds
        
        # Trigger Level 1 if ≥ threshold yawns per minute
        if yawns_per_minute >= YAWN_ALERT_THRESHOLD:
            return True
        
        return False
    
    def _check_recent_yawns(self, timestamp):
        """
        Check if there were yawns in the recent window (for Level 2 escalation).
        This prevents escalation based on old yawns that are just lingering in the rolling window.
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            True if yawns occurred in the recent window, False otherwise
        """
        if not self.yawn_timestamps:
            return False
        
        # Check if any yawns occurred in the last YAWN_RECENT_WINDOW_SECONDS
        recent_cutoff = timestamp - YAWN_RECENT_WINDOW_SECONDS
        recent_yawns = [ts for ts in self.yawn_timestamps if ts >= recent_cutoff]
        
        return len(recent_yawns) > 0
    
    def get_yawn_frequency(self, timestamp):
        """
        Get current yawn frequency (yawns per minute) in rolling 1-minute window.
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            Yawns per minute (float)
        """
        # Clean old yawns
        cutoff_time = timestamp - YAWN_ALERT_WINDOW_SECONDS
        self.yawn_timestamps = [ts for ts in self.yawn_timestamps if ts >= cutoff_time]
        
        # Count yawns in last minute
        window_start = timestamp - YAWN_ALERT_WINDOW_SECONDS
        yawns_in_window = sum(1 for ts in self.yawn_timestamps if ts >= window_start)
        
        return float(yawns_in_window)  # yawns per minute (window is 60 seconds)
    
    def trigger_level1(self, timestamp, reason="drowsiness symptoms"):
        """
        Trigger Level 1 alert (drowsiness symptoms or yawn pattern detected).
        
        Args:
            timestamp: Timestamp when alert was triggered
            reason: Reason for trigger ("drowsiness symptoms" or "yawn pattern")
        """
        if self.level1_active:
            return
        
        self.level1_active = True
        self.level1_triggered_at = timestamp
        self.yawns_since_level1 = 0  # Reset counter when Level 1 triggers
        print(f"[LEVEL 1 ALERT] Triggered at {timestamp:.2f}s - Reason: {reason}")
        if reason == "yawn frequency":
            yawn_freq = self.get_yawn_frequency(timestamp)
            risk_level = "High" if yawn_freq >= 4 else ("Moderate" if yawn_freq >= 3 else "Moderate")
            print(f"  → Yawn Frequency: {yawn_freq:.1f} yawns/min ({risk_level} risk)")
            print(f"  → Research threshold: ≥{YAWN_ALERT_THRESHOLD} yawns/min indicates unusual/drowsy behavior")
        else:
            print("  → Symptoms: Eye closure, high PERCLOS, excessive blinking, yawning, or inattention")
        
        # Start audio/visual alerts
        self.start_level1_alerts()
    
    def trigger_level2(self, timestamp):
        """
        Trigger Level 2 alert (emergency escalation - symptoms persist).
        
        Args:
            timestamp: Timestamp when alert was triggered
        """
        if self.level2_active:
            return
        
        self.level2_active = True
        self.level2_triggered = True
        print(f"[LEVEL 2 EMERGENCY] Drowsiness symptoms persist - Emergency alert at {timestamp:.2f}s")
        print("  → Driver unresponsive to Level 1 warnings - Immediate attention required!")
        
        # Start emergency alerts
        self.start_level2_alerts()
    
    def start_level1_alerts(self):
        """Start Level 1 audio and visual alerts."""
        if self.alert_thread and self.alert_thread.is_alive():
            return
        
        self.stop_alert = False
        self.alert_thread = threading.Thread(target=self._level1_alert_loop, daemon=True)
        self.alert_thread.start()
    
    def start_level2_alerts(self):
        """Start Level 2 emergency alerts."""
        self.stop_alert = False
        if self.alert_thread and self.alert_thread.is_alive():
            # Stop Level 1 alerts
            self.stop_alert = True
            time.sleep(0.5)
        
        self.alert_thread = threading.Thread(target=self._level2_alert_loop, daemon=True)
        self.alert_thread.start()
    
    def _level1_alert_loop(self):
        """Level 1 alert loop - beep every 2 seconds (warning tone)."""
        while not self.stop_alert and self.level1_active:
            if self.audio_enabled:
                try:
                    _beep(800, 0.2)  # Warning tone
                except Exception as e:
                    print(f"Audio alert error: {e}")
            
            time.sleep(2)  # Beep every 2 seconds
    
    def _level2_alert_loop(self):
        """Level 2 alert loop - continuous loud alarm (emergency tone)."""
        while not self.stop_alert and self.level2_active:
            if self.audio_enabled:
                try:
                    _beep(1000, 0.3)  # Emergency tone (louder, longer)
                except Exception as e:
                    print(f"Emergency audio error: {e}")
            
            time.sleep(0.5)  # More frequent alerts for emergency
    
    def reset(self):
        """Reset alert state when driver becomes alert again (symptoms clear)."""
        if self.level1_start is not None:
            self.level1_start = None
            self.level1_triggered_at = None
            self.level1_active = False
            self.level2_active = False
            self.stop_alert = True
            # Clear tracking when reset
            self.yawn_timestamps = []
            self.yawns_since_level1 = 0
            self.level1_trigger_timestamps = []  # Clear Level 1 trigger history
            print("[ALERT RESET] Driver alertness restored - symptoms cleared")
    
    def manual_reset(self):
        """Manually reset alerts (for testing or manual intervention)."""
        self.reset()
        self.level2_triggered = False
    
    def get_alert_level(self):
        """
        Get current alert level.
        
        Returns:
            alert_level: 0 (no alert), 1 (Level 1), or 2 (Level 2)
        """
        if self.level2_active:
            return 2
        elif self.level1_active:
            return 1
        return 0
    
    def get_level1_elapsed(self, current_time):
        """
        Get elapsed time since Level 1 was triggered.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Elapsed seconds since Level 1 trigger, or 0 if not active
        """
        if self.level1_triggered_at is not None:
            return max(0.0, current_time - self.level1_triggered_at)
        return 0.0

