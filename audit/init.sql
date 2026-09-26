CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress, allowed, escalated, denied
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ  -- set when a human resolves an escalated run
);

CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id),
    seq INTEGER NOT NULL,              -- order within this run: 1, 2, 3...
    event_type TEXT NOT NULL,          -- 'intake', 'tool_call', 'agent_decision', 'policy_check'
    payload JSONB NOT NULL,            -- the actual data for this event
    prev_hash TEXT,                    -- hash of the previous event in this run (null for the first)
    hash TEXT NOT NULL,                -- hash of (this payload + prev_hash)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, seq)
);

CREATE INDEX idx_audit_events_run_id ON audit_events(run_id);


--Design notes:
--UUID instead of auto-incrementing numbers — harder to enumerate, standard for audit systems
--JSONB for payload — lets each event type store differently-shaped data without a separate table per type
--UNIQUE (run_id, seq) — prevents two events accidentally sharing a sequence number, which would break the hash chain