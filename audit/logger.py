#notes
#Why each function exists:
#create_run — call this once when a new payment request comes in
#log_event — call this at every step (intake, tool call, agent decision, policy check, execution). It automatically finds the last hash and chains onto it, you never compute hashes yourself elsewhere
#verify_chain — this is your proof-of-integrity function. Run it in a demo, edit a row directly in Postgres, run it again, watch it return False. That's your strongest talking point in an interview





import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg2
from psycopg2.extras import Json


def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="governance_db",
        user="governance",
        password="governance_dev_pw",
    )


def _compute_hash(payload: dict, prev_hash: str | None) -> str:
    """Hash = SHA256(prev_hash + canonical JSON of payload).
    Canonical JSON (sorted keys, no extra whitespace) so the same
    payload always hashes the same way, regardless of dict order."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    combined = f"{prev_hash or ''}{canonical}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def create_run(request_payload: dict) -> str:
    """Insert a new row into `runs`, return its id as a string."""
    run_id = str(uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO runs (id, request_payload) VALUES (%s, %s)",
                (run_id, Json(request_payload)),
            )
        conn.commit()
    finally:
        conn.close()
    return run_id


def log_event(run_id: str, event_type: str, payload: dict) -> dict:
    """Append one event to the hash chain for this run.
    Looks up the last event's hash, computes this event's hash on top of it,
    and inserts. Returns the inserted event as a dict."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT seq, hash FROM audit_events WHERE run_id = %s ORDER BY seq DESC LIMIT 1",
                (run_id,),
            )
            row = cur.fetchone()
            next_seq = (row[0] + 1) if row else 1
            prev_hash = row[1] if row else None

            this_hash = _compute_hash(payload, prev_hash)
            event_id = str(uuid4())

            cur.execute(
                """INSERT INTO audit_events
                   (id, run_id, seq, event_type, payload, prev_hash, hash)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (event_id, run_id, next_seq, event_type, Json(payload), prev_hash, this_hash),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "id": event_id,
        "run_id": run_id,
        "seq": next_seq,
        "event_type": event_type,
        "payload": payload,
        "prev_hash": prev_hash,
        "hash": this_hash,
    }


def verify_chain(run_id: str) -> bool:
    """Recompute every hash in sequence and check it matches what's stored.
    Returns False the moment any row's stored hash doesn't match — meaning
    that row (or an earlier one) was tampered with."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT seq, event_type, payload, prev_hash, hash FROM audit_events "
                "WHERE run_id = %s ORDER BY seq ASC",
                (run_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    expected_prev = None
    for seq, event_type, payload, stored_prev_hash, stored_hash in rows:
        if stored_prev_hash != expected_prev:
            return False
        recomputed = _compute_hash(payload, stored_prev_hash)
        if recomputed != stored_hash:
            return False
        expected_prev = stored_hash

    return True

def get_trace(run_id: str) -> list[dict]:
    """Return every event for a run, in order — the full reconstructable trace."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT seq, event_type, payload, created_at FROM audit_events "
                "WHERE run_id = %s ORDER BY seq ASC",
                (run_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {"seq": seq, "event_type": event_type, "payload": payload, "created_at": created_at.isoformat()}
        for seq, event_type, payload, created_at in rows
    ]