# Modular Driver Drowsiness Detection System

This is a modular version of the driver drowsiness detection system, organized into separate modules for better understanding and maintainability.

## Module Structure

### Core Modules

1. **config.py** - All configuration constants
   - EAR thresholds
   - LAR thresholds
   - PERCLOS settings
   - Blink thresholds
   - Score thresholds
   - Camera settings

2. **ear_detector.py** - Eye Aspect Ratio calculations
   - `calculate_ear()` - Calculate EAR for single eye
   - `calculate_average_ear()` - Calculate average EAR from both eyes

3. **perclos_calculator.py** - PERCLOS (Percentage of Eye Closure) tracking
   - `PERCLOSCalculator` class
   - Tracks eye closure state over time window
   - Calculates PERCLOS percentage

4. **blink_analyzer.py** - Blink analysis
   - `BlinkAnalyzer` class
   - Tracks blink rate (blinks per minute)
   - Calculates average blink duration
   - Detects microsleep events
   - Tracks current eye closure duration

5. **yawn_detector.py** - Yawn detection using LAR
   - `calculate_lar()` - Calculate Lip Aspect Ratio
   - `YawnDetector` class
   - LAR smoothing for noise reduction
   - Frame validation for accuracy
   - Yawn count and duration tracking

6. **head_pose_estimator.py** - Head pose estimation
   - `rotation_matrix_to_euler_angles()` - Convert rotation matrix to angles
   - `HeadPoseEstimator` class
   - Estimates yaw, pitch, roll
   - Determines attentiveness (looking at road)

7. **face_detector.py** - MediaPipe face detection
   - `FaceDetector` class
   - Face landmark detection
   - Eye and mouth landmark extraction
   - Face mesh visualization

8. **score_calculator.py** - Drowsiness score calculation
   - `ScoreCalculator` class
   - Calculates score (0-100) from all metrics
   - Classifies driver state
   - Implements weightage system:
     - PERCLOS: up to 85 points (primary)
     - Continuous closure/microsleep: up to 70 points
     - Yawning: up to 50 points
     - Blink rate: up to 30 points
     - Blink duration: up to 20 points
     - Instantaneous EAR: up to 10 points

9. **visualizer.py** - Overlay drawing
   - `draw_overlay()` - Draws all metrics on frame
   - State and score display
   - Metric values display
   - Yawn detection indicator

10. **camera_utils.py** - Camera handling
    - `open_camera()` - Robust camera initialization
    - Backend selection for Windows
    - Retry logic

11. **alerter.py** - Two-Level Alert System
    - `AlertEngine` class
    - Level 1: Triggers when drowsiness symptoms detected (state-based)
    - Level 2: Escalates only if Level 1 persists
    - Audio and visual feedback
    - Symptom-based detection (not just score)

12. **main.py** - Main entry point
    - Orchestrates all modules
    - Main detection loop
    - Frame processing and display
    - Alert system integration
    - Supabase cloud logging integration

13. **supabase_logger.py** - Supabase cloud integration
    - `SupabaseLogger` class
    - Logs periodic snapshots, alerts, and state changes
    - Session management and summaries
    - Efficient data logging strategy

## How to Run

```bash
cd modular
python main.py
```

## Score Calculation Weightage

The drowsiness score is calculated with the following weightage:

| Metric | Max Points | Priority |
|--------|------------|----------|
| PERCLOS | 85 | Highest |
| Continuous Closure/Microsleep | 70 | Very High |
| Yawning | 50 | High |
| Blink Rate | 30 | Medium |
| Blink Duration | 20 | Medium |
| Instantaneous EAR | 10 | Low |

**Total possible score: 265 points (clamped to 100)**

## State Classification

States are classified based on:
1. **Hard drowsy rule** (highest priority):
   - PERCLOS >= 30% OR
   - Closed duration >= 0.6s OR
   - Blink duration >= 0.48s
   → Forces state to DROWSY or VERY_DROWSY

2. **PERCLOS bands**:
   - < 10%: ALERT
   - 10-30%: SLIGHTLY_DROWSY
   - > 30%: DROWSY

3. **Score thresholds** (fallback):
   - <= 25: ALERT
   - 25-55: SLIGHTLY_DROWSY
   - 55-80: DROWSY
   - > 80: VERY_DROWSY

## Two-Level Alert System

The alert system is **symptom-based** (not just score-based), meaning it triggers when drowsiness symptoms are detected.

### Level 1 Alert (Warning)
- **Trigger**: Driver state indicates drowsiness symptoms OR yawn frequency threshold exceeded
  - **State-based**: States `SLIGHTLY_DROWSY`, `DROWSY`, `VERY_DROWSY`, `INATTENTIVE`
  - **Yawn-based** (Research-backed thresholds):
    - ≥ 2 yawns/min → Unusual (Moderate risk) → Level 1 Alert
    - ≥ 3 yawns/min → Strong drowsiness indicator (High risk) → Level 1 Alert
    - ≥ 4 yawns/min → Critical/Unsafe → Level 1 Alert
    - Uses rolling 1-minute window for frequency calculation
- **Duration**: Must persist for `LEVEL1_DURATION_SECONDS` (default: 3 seconds)
- **Behavior**:
  - Audio: Warning beep every 2 seconds (800 Hz)
  - Visual: Orange alert indicator on screen with yawn frequency display
  - Console: Warning message printed with trigger reason and yawn frequency
  - On-screen display: Shows "Yawn Freq: X.X/min (RISK_LEVEL)" with color coding

### Level 2 Alert (Emergency)
- **Trigger**: 3 Level 1 alerts occur within a 30-second window (frequency-based escalation)
- **Behavior**:
  - Audio: Continuous emergency alarm (1000 Hz, every 0.5 seconds)
  - Visual: Red emergency indicator on screen
  - Console: Emergency message printed
  - Indicates driver is unresponsive to Level 1 warnings (persistent drowsiness)

### Alert Reset
- **Automatic**: When driver state returns to `ALERT` (symptoms clear)
- **Manual**: Press `r` key to manually reset alerts

### Key Features
- ✅ **Symptom-based**: Triggers on actual drowsiness symptoms, not just score
- ✅ **Progressive escalation**: Level 2 only triggers if Level 1 persists
- ✅ **Clear transition logic**: Well-defined conditions for each level
- ✅ **Visual feedback**: On-screen indicators show alert level
- ✅ **Audio feedback**: Different tones for Level 1 vs Level 2

## Benefits of Modular Structure

1. **Easy to understand**: Each module has a single responsibility
2. **Easy to debug**: Can trace calculations through each module
3. **Easy to modify**: Change one detection type without affecting others
4. **Easy to test**: Each module can be tested independently
5. **Clear weightage**: Score calculation shows exactly how each metric contributes

