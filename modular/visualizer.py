"""
Visualization Module
Draws all metrics and state information on the video frame
"""

import cv2


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
    alert_level=0,
    level1_elapsed=0.0,
    yawn_frequency=0.0,
):
    """
    Draw all metrics and state information on the frame.
    
    Args:
        frame: BGR image frame
        state: Driver state string
        score: Drowsiness score (0-100)
        ear: Eye Aspect Ratio
        perclos: PERCLOS percentage
        blink_rate: Blink rate (blinks per minute)
        yaw: Head yaw angle (degrees)
        pitch: Head pitch angle (degrees)
        roll: Head roll angle (degrees)
        looking: Boolean indicating if driver is looking at road
        lar: Lip Aspect Ratio
        yawn_count: Number of yawns detected
        is_yawning: Boolean indicating if currently yawning
        current_yawn_duration: Current yawn duration (seconds)
        alert_level: Current alert level (0, 1, or 2)
        level1_elapsed: Elapsed time since Level 1 alert (seconds)
        yawn_frequency: Yawns per minute (rolling 1-minute window)
    """
    # State color mapping
    color_map = {
        "ALERT": (0, 255, 0),           # Green
        "SLIGHTLY_DROWSY": (0, 255, 255), # Yellow
        "DROWSY": (0, 165, 255),         # Orange
        "VERY_DROWSY": (0, 0, 255),      # Red
        "INATTENTIVE": (0, 0, 255),      # Red
    }
    color = color_map.get(state, (255, 255, 255))
    
    # Draw state and score
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
    
    # Show "YAWNING DETECTED" when LAR > threshold AND duration >= threshold
    if is_yawning:
        cv2.putText(frame, "YAWNING DETECTED", (30, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
    
    # Draw head pose and attention information
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
        
        # Show yawn count and frequency below LAR
        yawn_color = (0, 0, 255) if yawn_count > 0 else (0, 0, 0)
        cv2.putText(
            frame,
            f"Yawns: {yawn_count}",
            (10, y_offset + 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            yawn_color,
            1,
        )
        
        # Show yawn frequency (yawns per minute) with risk indicator
        if yawn_frequency > 0:
            if yawn_frequency >= 4:
                freq_color = (0, 0, 255)  # Red - Critical
                risk_text = "CRITICAL"
            elif yawn_frequency >= 3:
                freq_color = (0, 100, 255)  # Orange-Red - High risk
                risk_text = "HIGH"
            elif yawn_frequency >= 2:
                freq_color = (0, 165, 255)  # Orange - Moderate risk
                risk_text = "MODERATE"
            else:
                freq_color = (0, 0, 0)  # Black - Normal
                risk_text = "NORMAL"
            
            freq_text = f"Yawn Freq: {yawn_frequency:.1f}/min ({risk_text})"
            cv2.putText(
                frame,
                freq_text,
                (10, y_offset + 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                freq_color,
                1,
            )
    
    # Draw alert level indicator
    if alert_level > 0:
        alert_y = frame.shape[0] - 30
        if alert_level == 2:
            alert_text = "🚨 LEVEL 2 EMERGENCY"
            alert_color = (0, 0, 255)  # Red
            alert_bg = (0, 0, 0)  # Black background
            thickness = 3
        else:
            alert_text = f"⚠️  LEVEL 1 ALERT ({level1_elapsed:.1f}s)"
            alert_color = (0, 165, 255)  # Orange
            alert_bg = (0, 0, 0)  # Black background
            thickness = 2
        
        # Draw background rectangle for better visibility
        text_size = cv2.getTextSize(alert_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, thickness)[0]
        cv2.rectangle(
            frame,
            (10, alert_y - text_size[1] - 5),
            (10 + text_size[0] + 10, alert_y + 5),
            alert_bg,
            -1
        )
        
        cv2.putText(
            frame,
            alert_text,
            (15, alert_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            alert_color,
            thickness,
        )

