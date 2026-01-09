# Cloud Integration Summary

## ✅ What Was Implemented

### 1. **Supabase Logger Module** (`supabase_logger.py`)
- Efficient cloud logging with periodic snapshots (every 5 seconds)
- Immediate logging of alert events (Level 1/2)
- State change tracking
- Session management with summaries

### 2. **Configuration** (`config.py`)
- Added `SUPABASE_ENABLED` flag to enable/disable logging
- Added `SUPABASE_SNAPSHOT_INTERVAL_SECONDS` to control snapshot frequency

### 3. **Main Integration** (`main.py`)
- Automatic session start/end
- Periodic snapshot logging
- Alert event logging
- State change tracking
- Session summary on exit

### 4. **Database Schema** (`SUPABASE_SCHEMA.sql`)
- Complete SQL schema for 4 tables:
  - `driving_sessions` - Session metadata
  - `driver_snapshots` - Periodic state snapshots
  - `alert_events` - Alert triggers
  - `state_changes` - State transitions
- Indexes for efficient querying
- Row Level Security (RLS) policies

### 5. **Documentation**
- `SUPABASE_SETUP.md` - Complete setup guide
- Updated `README.md` with Supabase module info

## 📊 Data Logged to Supabase

### Periodic Snapshots (every 5 seconds)
- Driver state (ALERT, SLIGHTLY_DROWSY, DROWSY, etc.)
- Drowsiness score (0-100)
- PERCLOS percentage
- Blink rate (blinks/min)
- Yawn count and frequency
- Alert level (0, 1, 2)
- Head pose angles (yaw, pitch, roll)
- Eye Aspect Ratio (EAR)
- Looking at road status

### Alert Events (immediate)
- Alert type (LEVEL1/LEVEL2)
- Alert level
- Driver state at alert time
- Drowsiness score and PERCLOS
- Trigger reason

### State Changes
- Previous state → New state
- Drowsiness metrics at transition

### Session Summaries
- Session duration
- Average and maximum drowsiness scores
- Total alert counts (Level 1 and Level 2)

## 🚀 Quick Start

1. **Install required packages:**
   ```bash
   pip install supabase python-dotenv
   ```
   Or: `pip install -r requirements.txt`

2. **Configure credentials (choose one method):**
   
   **Method A: .env file (Recommended)**
   ```bash
   # Copy example file
   cp .env.example .env
   
   # Edit .env and add your credentials
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=your-anon-key
   ```
   
   **Method B: Environment variables**
   ```bash
   export SUPABASE_URL="https://xxxxx.supabase.co"
   export SUPABASE_KEY="your-anon-key"
   ```

3. **Create database tables:**
   - Run `SUPABASE_SCHEMA.sql` in Supabase SQL Editor

4. **Run the system:**
   ```bash
   python main.py
   ```

## 📈 Next Steps: Dashboard

You can now build dashboards to visualize the data:

1. **Use Supabase Dashboard** - Built-in data browser
2. **Build Custom Dashboard** - Use Supabase REST API or JavaScript client
3. **Real-time Updates** - Use Supabase Realtime subscriptions

### Example Dashboard Queries

```sql
-- Recent sessions
SELECT * FROM driving_sessions 
ORDER BY started_at DESC LIMIT 10;

-- Session snapshots
SELECT * FROM driver_snapshots 
WHERE session_id = 'session_xxx' 
ORDER BY timestamp ASC;

-- Alert statistics
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE alert_level = 1) as level1,
    COUNT(*) FILTER (WHERE alert_level = 2) as level2
FROM alert_events
WHERE timestamp >= NOW() - INTERVAL '24 hours';
```

## 🔧 Configuration

In `config.py`:
- `SUPABASE_ENABLED = True` - Enable/disable cloud logging
- `SUPABASE_SNAPSHOT_INTERVAL_SECONDS = 5` - Snapshot frequency

## 📝 Notes

- System works offline if Supabase is not configured
- Logging is non-blocking (won't slow down detection)
- Only essential metrics are logged to reduce data volume
- Session automatically starts when system runs
- Session summary logged on exit (Ctrl+Q)

