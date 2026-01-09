-- Supabase Database Schema for Driver Drowsiness Detection System
-- Run these SQL commands in your Supabase SQL Editor to create the tables

-- ============================================================================
-- Table: driving_sessions
-- Stores driving session metadata and summaries
-- ============================================================================
CREATE TABLE IF NOT EXISTS driving_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'completed', 'cancelled'
    duration_seconds NUMERIC(10, 2),
    avg_drowsiness_score NUMERIC(5, 2),
    max_drowsiness_score NUMERIC(5, 2),
    total_alerts INTEGER DEFAULT 0,
    level1_alerts INTEGER DEFAULT 0,
    level2_alerts INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for querying sessions by date
CREATE INDEX IF NOT EXISTS idx_driving_sessions_started_at ON driving_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_driving_sessions_status ON driving_sessions(status);

-- ============================================================================
-- Table: driver_snapshots
-- Periodic snapshots of driver state (logged every N seconds)
-- ============================================================================
CREATE TABLE IF NOT EXISTS driver_snapshots (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES driving_sessions(session_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    driver_state TEXT NOT NULL, -- 'ALERT', 'SLIGHTLY_DROWSY', 'DROWSY', 'VERY_DROWSY', 'INATTENTIVE', 'NO_FACE'
    drowsiness_score NUMERIC(5, 2) NOT NULL,
    perclos NUMERIC(5, 2) NOT NULL,
    blink_rate NUMERIC(5, 2) NOT NULL,
    yawn_count INTEGER DEFAULT 0,
    yawn_frequency NUMERIC(5, 2) DEFAULT 0,
    alert_level INTEGER NOT NULL DEFAULT 0, -- 0, 1, or 2
    ear NUMERIC(6, 3), -- Eye Aspect Ratio
    head_yaw NUMERIC(6, 2), -- Head yaw angle in degrees
    head_pitch NUMERIC(6, 2), -- Head pitch angle in degrees
    head_roll NUMERIC(6, 2), -- Head roll angle in degrees
    looking_at_road BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_driver_snapshots_session_id ON driver_snapshots(session_id);
CREATE INDEX IF NOT EXISTS idx_driver_snapshots_timestamp ON driver_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_driver_snapshots_driver_state ON driver_snapshots(driver_state);
CREATE INDEX IF NOT EXISTS idx_driver_snapshots_alert_level ON driver_snapshots(alert_level);

-- ============================================================================
-- Table: alert_events
-- Logs when alerts are triggered (Level 1 or Level 2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS alert_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES driving_sessions(session_id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL, -- 'LEVEL1' or 'LEVEL2'
    alert_level INTEGER NOT NULL, -- 1 or 2
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    driver_state TEXT NOT NULL,
    drowsiness_score NUMERIC(5, 2) NOT NULL,
    perclos NUMERIC(5, 2) NOT NULL,
    trigger_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_alert_events_session_id ON alert_events(session_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_timestamp ON alert_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alert_events_alert_type ON alert_events(alert_type);
CREATE INDEX IF NOT EXISTS idx_alert_events_alert_level ON alert_events(alert_level);

-- ============================================================================
-- Table: state_changes
-- Logs significant driver state transitions
-- ============================================================================
CREATE TABLE IF NOT EXISTS state_changes (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES driving_sessions(session_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    old_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    drowsiness_score NUMERIC(5, 2) NOT NULL,
    perclos NUMERIC(5, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_state_changes_session_id ON state_changes(session_id);
CREATE INDEX IF NOT EXISTS idx_state_changes_timestamp ON state_changes(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_state_changes_new_state ON state_changes(new_state);

-- ============================================================================
-- Row Level Security (RLS) Policies
-- Enable RLS and create policies based on your authentication needs
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE driving_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE driver_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE state_changes ENABLE ROW LEVEL SECURITY;

-- Example: Allow all operations for authenticated users
-- Adjust these policies based on your authentication setup
CREATE POLICY "Allow all for authenticated users" ON driving_sessions
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Allow all for authenticated users" ON driver_snapshots
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Allow all for authenticated users" ON alert_events
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Allow all for authenticated users" ON state_changes
    FOR ALL USING (auth.role() = 'authenticated');

-- Alternative: Allow public read/write (for development/testing only)
-- WARNING: Remove these in production and use proper authentication!
-- CREATE POLICY "Allow public access" ON driving_sessions FOR ALL USING (true);
-- CREATE POLICY "Allow public access" ON driver_snapshots FOR ALL USING (true);
-- CREATE POLICY "Allow public access" ON alert_events FOR ALL USING (true);
-- CREATE POLICY "Allow public access" ON state_changes FOR ALL USING (true);

-- ============================================================================
-- Useful Queries for Dashboard
-- ============================================================================

-- Get recent sessions with summary
-- SELECT 
--     session_id,
--     started_at,
--     ended_at,
--     duration_seconds,
--     avg_drowsiness_score,
--     max_drowsiness_score,
--     total_alerts,
--     level1_alerts,
--     level2_alerts
-- FROM driving_sessions
-- ORDER BY started_at DESC
-- LIMIT 10;

-- Get snapshots for a specific session
-- SELECT 
--     timestamp,
--     driver_state,
--     drowsiness_score,
--     perclos,
--     blink_rate,
--     alert_level
-- FROM driver_snapshots
-- WHERE session_id = 'session_1234567890'
-- ORDER BY timestamp ASC;

-- Get all alerts for a session
-- SELECT 
--     timestamp,
--     alert_type,
--     alert_level,
--     driver_state,
--     drowsiness_score,
--     trigger_reason
-- FROM alert_events
-- WHERE session_id = 'session_1234567890'
-- ORDER BY timestamp ASC;

-- Get state changes for a session
-- SELECT 
--     timestamp,
--     old_state,
--     new_state,
--     drowsiness_score,
--     perclos
-- FROM state_changes
-- WHERE session_id = 'session_1234567890'
-- ORDER BY timestamp ASC;

-- Get alert statistics for dashboard
-- SELECT 
--     COUNT(*) as total_alerts,
--     COUNT(*) FILTER (WHERE alert_level = 1) as level1_count,
--     COUNT(*) FILTER (WHERE alert_level = 2) as level2_count,
--     AVG(drowsiness_score) as avg_score_at_alert
-- FROM alert_events
-- WHERE timestamp >= NOW() - INTERVAL '24 hours';

