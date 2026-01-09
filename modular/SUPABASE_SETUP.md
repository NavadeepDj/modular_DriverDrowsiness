# Supabase Cloud Integration Setup Guide

This guide will help you set up Supabase cloud logging for the Driver Drowsiness Detection System.

## 📋 Prerequisites

1. A Supabase account (sign up at [supabase.com](https://supabase.com))
2. A Supabase project created
3. Python package: `supabase-py`

## 🚀 Setup Steps

### Step 1: Install Required Packages

```bash
pip install supabase python-dotenv
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

### Step 2: Get Your Supabase Credentials

1. Go to your Supabase project dashboard
2. Navigate to **Settings** → **API**
3. Copy the following:
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **anon/public key** (the `anon` key, not the `service_role` key)

### Step 3: Configure Credentials

**Option A: .env File (Recommended - Easiest)**

1. Copy the example file:
   ```bash
   # Windows
   copy .env.example .env
   
   # Linux/Mac
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```env
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=your-anon-key-here
   ```

3. The `.env` file is automatically loaded when you run the system.

**Option B: Environment Variables**

```bash
# Windows PowerShell
$env:SUPABASE_URL="https://xxxxx.supabase.co"
$env:SUPABASE_KEY="your-anon-key-here"

# Windows CMD
set SUPABASE_URL=https://xxxxx.supabase.co
set SUPABASE_KEY=your-anon-key-here

# Linux/Mac
export SUPABASE_URL="https://xxxxx.supabase.co"
export SUPABASE_KEY="your-anon-key-here"
```

**Option C: Pass as Arguments (Alternative)**

You can modify `main.py` to pass credentials directly:

```python
supabase_logger = SupabaseLogger(
    supabase_url="https://xxxxx.supabase.co",
    supabase_key="your-anon-key-here"
)
```

### Step 4: Create Database Tables

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Copy and paste the contents of `SUPABASE_SCHEMA.sql`
4. Click **Run** to execute the SQL

This will create the following tables:
- `driving_sessions` - Session metadata and summaries
- `driver_snapshots` - Periodic driver state snapshots
- `alert_events` - Alert triggers (Level 1/2)
- `state_changes` - Driver state transitions

### Step 5: Configure Row Level Security (RLS)

The schema includes RLS policies. For development/testing, you can use public access:

1. In SQL Editor, run:
```sql
-- Allow public access (development only!)
CREATE POLICY "Allow public access" ON driving_sessions FOR ALL USING (true);
CREATE POLICY "Allow public access" ON driver_snapshots FOR ALL USING (true);
CREATE POLICY "Allow public access" ON alert_events FOR ALL USING (true);
CREATE POLICY "Allow public access" ON state_changes FOR ALL USING (true);
```

**⚠️ Warning:** Remove public access policies in production and use proper authentication!

### Step 6: Enable/Disable Logging

In `config.py`, you can control Supabase logging:

```python
SUPABASE_ENABLED = True  # Set to False to disable
SUPABASE_SNAPSHOT_INTERVAL_SECONDS = 5  # Log snapshot every 5 seconds
```

## 📊 What Gets Logged?

### 1. **Periodic Snapshots** (every 5 seconds by default)
- Driver state (ALERT, SLIGHTLY_DROWSY, DROWSY, etc.)
- Drowsiness score (0-100)
- PERCLOS percentage
- Blink rate
- Yawn count and frequency
- Alert level (0, 1, or 2)
- Head pose angles (yaw, pitch, roll)
- Eye Aspect Ratio (EAR)

### 2. **Alert Events** (immediate)
- Level 1 alerts (drowsiness symptoms detected)
- Level 2 alerts (emergency escalation)
- Trigger reason
- Driver state and metrics at alert time

### 3. **State Changes** (when driver state changes)
- Previous state → New state
- Drowsiness score and PERCLOS at transition

### 4. **Session Summaries** (on session end)
- Session duration
- Average and maximum drowsiness scores
- Total alert counts (Level 1 and Level 2)

## 🔍 Querying Data

### Get Recent Sessions
```sql
SELECT 
    session_id,
    started_at,
    duration_seconds,
    avg_drowsiness_score,
    max_drowsiness_score,
    total_alerts
FROM driving_sessions
ORDER BY started_at DESC
LIMIT 10;
```

### Get Snapshots for a Session
```sql
SELECT 
    timestamp,
    driver_state,
    drowsiness_score,
    perclos,
    alert_level
FROM driver_snapshots
WHERE session_id = 'session_1234567890'
ORDER BY timestamp ASC;
```

### Get Alert Statistics
```sql
SELECT 
    COUNT(*) as total_alerts,
    COUNT(*) FILTER (WHERE alert_level = 1) as level1_count,
    COUNT(*) FILTER (WHERE alert_level = 2) as level2_count
FROM alert_events
WHERE timestamp >= NOW() - INTERVAL '24 hours';
```

## 📈 Dashboard Integration

You can build dashboards using:
- **Supabase Dashboard** - Built-in data browser
- **Supabase Realtime** - Real-time subscriptions for live updates
- **Custom Dashboards** - Use Supabase REST API or JavaScript client

### Example: Real-time Dashboard with Supabase JS

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

// Subscribe to new snapshots
const subscription = supabase
  .channel('driver_snapshots')
  .on('postgres_changes', 
    { event: 'INSERT', schema: 'public', table: 'driver_snapshots' },
    (payload) => {
      console.log('New snapshot:', payload.new)
      // Update your dashboard UI
    }
  )
  .subscribe()

// Query recent sessions
const { data: sessions } = await supabase
  .from('driving_sessions')
  .select('*')
  .order('started_at', { ascending: false })
  .limit(10)
```

## 🛠️ Troubleshooting

### "Supabase credentials not provided"
- Make sure `SUPABASE_URL` and `SUPABASE_KEY` environment variables are set
- Or pass them directly when initializing `SupabaseLogger`

### "supabase-py not installed"
```bash
pip install supabase
```

### "Table does not exist"
- Run the SQL schema from `SUPABASE_SCHEMA.sql` in your Supabase SQL Editor

### "Permission denied" or RLS errors
- Check your RLS policies in Supabase
- For development, you can temporarily allow public access (see Step 5)

### Data not appearing
- Check Supabase logs in the dashboard
- Verify the logger is initialized (look for "✅ Supabase logger initialized" message)
- Check that `SUPABASE_ENABLED = True` in `config.py`

## 📝 Notes

- **Data Volume**: Snapshots are logged every 5 seconds by default. Adjust `SUPABASE_SNAPSHOT_INTERVAL_SECONDS` to reduce/increase frequency.
- **Performance**: The logger runs asynchronously and won't block the main detection loop.
- **Offline Mode**: If Supabase is not configured, the system will run normally without cloud logging.

## 🔒 Security Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** for credentials
3. **Enable RLS** with proper authentication in production
4. **Use service role key** only on backend servers (never in client code)
5. **Monitor API usage** in Supabase dashboard to detect anomalies

