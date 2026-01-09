"""
Supabase Cloud Integration Module
Logs driver drowsiness metrics and events to Supabase database

Tables:
- driver_snapshots: Periodic snapshots of driver state (every N seconds)
- alert_events: Alert triggers (Level 1, Level 2)
- driving_sessions: Session summaries
"""

import time
from datetime import datetime
from typing import Optional, Dict, Any
import os

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("Warning: supabase-py not installed. Install with: pip install supabase")


class SupabaseLogger:
    """
    Logs driver drowsiness data to Supabase.
    
    Efficient logging strategy:
    - Periodic snapshots (every N seconds) with key metrics
    - Alert events (immediate logging when alerts trigger)
    - State changes (when driver state changes)
    - Session summaries (on session end)
    """
    
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        """
        Initialize Supabase logger.
        
        Args:
            supabase_url: Supabase project URL (or from SUPABASE_URL env var)
            supabase_key: Supabase anon key (or from SUPABASE_KEY env var)
        """
        self.initialized = False
        self.client: Optional[Client] = None
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[float] = None
        
        # Get credentials from args, .env file, or environment variables
        url = supabase_url or os.getenv("SUPABASE_URL")
        key = supabase_key or os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            print("Warning: Supabase credentials not provided. Logging disabled.")
            print("Set SUPABASE_URL and SUPABASE_KEY in .env file, environment variables, or pass as arguments.")
            if not DOTENV_AVAILABLE:
                print("Tip: Install python-dotenv to use .env file: pip install python-dotenv")
            return
        
        if not SUPABASE_AVAILABLE:
            print("Warning: supabase-py package not installed. Logging disabled.")
            print("Install with: pip install supabase")
            return
        
        try:
            self.client = create_client(url, key)
            self.initialized = True
            print("✅ Supabase logger initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize Supabase logger: {e}")
            self.initialized = False
    
    def start_session(self) -> Optional[str]:
        """
        Start a new driving session.
        
        Returns:
            Session ID (str) or None if not initialized
        """
        if not self.initialized or not self.client:
            return None
        
        try:
            self.session_start_time = time.time()
            session_id = f"session_{int(self.session_start_time * 1000)}"
            self.current_session_id = session_id
            
            # Create session record
            session_data = {
                "session_id": session_id,
                "started_at": datetime.utcnow().isoformat(),
                "status": "active"
            }
            
            result = self.client.table("driving_sessions").insert(session_data).execute()
            print(f"📊 Started driving session: {session_id}")
            return session_id
        except Exception as e:
            print(f"Error starting session: {e}")
            return None
    
    def log_snapshot(
        self,
        state: str,
        score: float,
        ear: Optional[float],
        perclos: float,
        blink_rate: float,
        yawn_count: int,
        alert_level: int,
        yaw: Optional[float] = None,
        pitch: Optional[float] = None,
        roll: Optional[float] = None,
        looking: bool = False,
        yawn_frequency: float = 0.0
    ):
        """
        Log periodic snapshot of driver state.
        
        Only logs essential metrics to avoid excessive data.
        
        Args:
            state: Driver state (ALERT, SLIGHTLY_DROWSY, DROWSY, etc.)
            score: Drowsiness score (0-100)
            ear: Eye Aspect Ratio
            perclos: PERCLOS percentage
            blink_rate: Blink rate (blinks/min)
            yawn_count: Number of yawns in window
            alert_level: Current alert level (0, 1, 2)
            yaw: Head yaw angle (optional)
            pitch: Head pitch angle (optional)
            roll: Head roll angle (optional)
            looking: Whether looking at road (optional)
            yawn_frequency: Yawns per minute (optional)
        """
        if not self.initialized or not self.client:
            return
        
        try:
            snapshot_data = {
                "session_id": self.current_session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "driver_state": state,
                "drowsiness_score": round(score, 2),
                "perclos": round(perclos, 2),
                "blink_rate": round(blink_rate, 2),
                "yawn_count": yawn_count,
                "yawn_frequency": round(yawn_frequency, 2),
                "alert_level": alert_level,
                "ear": round(ear, 3) if ear is not None else None,
                "head_yaw": round(yaw, 2) if yaw is not None else None,
                "head_pitch": round(pitch, 2) if pitch is not None else None,
                "head_roll": round(roll, 2) if roll is not None else None,
                "looking_at_road": looking
            }
            
            self.client.table("driver_snapshots").insert(snapshot_data).execute()
        except Exception as e:
            print(f"Error logging snapshot: {e}")
    
    def log_alert(
        self,
        alert_type: str,
        alert_level: int,
        driver_state: str,
        score: float,
        perclos: float,
        trigger_reason: Optional[str] = None
    ):
        """
        Log alert event (Level 1 or Level 2 trigger).
        
        Args:
            alert_type: "LEVEL1" or "LEVEL2"
            alert_level: Alert level (1 or 2)
            driver_state: Current driver state
            score: Drowsiness score at alert time
            perclos: PERCLOS at alert time
            trigger_reason: Reason for alert (optional)
        """
        if not self.initialized or not self.client:
            return
        
        try:
            alert_data = {
                "session_id": self.current_session_id,
                "alert_type": alert_type,
                "alert_level": alert_level,
                "timestamp": datetime.utcnow().isoformat(),
                "driver_state": driver_state,
                "drowsiness_score": round(score, 2),
                "perclos": round(perclos, 2),
                "trigger_reason": trigger_reason or "drowsiness symptoms detected"
            }
            
            self.client.table("alert_events").insert(alert_data).execute()
            print(f"📢 Alert logged to Supabase: {alert_type}")
        except Exception as e:
            print(f"Error logging alert: {e}")
    
    def log_state_change(
        self,
        old_state: str,
        new_state: str,
        score: float,
        perclos: float
    ):
        """
        Log driver state change.
        
        Args:
            old_state: Previous driver state
            new_state: New driver state
            score: Drowsiness score
            perclos: PERCLOS percentage
        """
        if not self.initialized or not self.client:
            return
        
        # Only log significant state changes (not every minor fluctuation)
        significant_states = ["ALERT", "SLIGHTLY_DROWSY", "DROWSY", "VERY_DROWSY", "INATTENTIVE"]
        if old_state not in significant_states or new_state not in significant_states:
            return
        
        if old_state == new_state:
            return  # No change
        
        try:
            change_data = {
                "session_id": self.current_session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "old_state": old_state,
                "new_state": new_state,
                "drowsiness_score": round(score, 2),
                "perclos": round(perclos, 2)
            }
            
            self.client.table("state_changes").insert(change_data).execute()
        except Exception as e:
            print(f"Error logging state change: {e}")
    
    def end_session(
        self,
        avg_score: float,
        max_score: float,
        alert_count: int,
        level1_count: int = 0,
        level2_count: int = 0
    ):
        """
        End current session and log summary.
        
        Args:
            avg_score: Average drowsiness score
            max_score: Maximum drowsiness score
            alert_count: Total alert count
            level1_count: Number of Level 1 alerts
            level2_count: Number of Level 2 alerts
        """
        if not self.initialized or not self.client or not self.current_session_id:
            return
        
        try:
            duration = time.time() - self.session_start_time if self.session_start_time else 0
            
            session_data = {
                "session_id": self.current_session_id,
                "ended_at": datetime.utcnow().isoformat(),
                "status": "completed",
                "duration_seconds": round(duration, 2),
                "avg_drowsiness_score": round(avg_score, 2),
                "max_drowsiness_score": round(max_score, 2),
                "total_alerts": alert_count,
                "level1_alerts": level1_count,
                "level2_alerts": level2_count
            }
            
            # Update session record
            self.client.table("driving_sessions").update(session_data).eq(
                "session_id", self.current_session_id
            ).execute()
            
            print(f"📊 Session ended: {self.current_session_id} (Duration: {duration:.1f}s)")
            self.current_session_id = None
            self.session_start_time = None
        except Exception as e:
            print(f"Error ending session: {e}")
    
    def is_initialized(self) -> bool:
        """Check if logger is initialized and ready."""
        return self.initialized

