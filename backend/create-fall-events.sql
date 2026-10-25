
CREATE TABLE IF NOT EXISTS fall_events (
    id BIGSERIAL PRIMARY KEY,
    resident_id TEXT,
    resident_name TEXT,
    track_id TEXT,
    probability DOUBLE PRECISION,
    source TEXT NOT NULL
        CHECK (source IN ('uploaded_video', 'live_camera')),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    video_time_seconds DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fall_events_occurred_at
    ON fall_events (occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_fall_events_resident_id
    ON fall_events (resident_id);
