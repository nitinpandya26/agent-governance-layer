#notes
#Why each function exists:
#create_run — call this once when a new payment request comes in
#log_event — call this at every step (intake, tool call, agent decision, policy check, execution). It automatically finds the last hash and chains onto it, you never compute hashes yourself elsewhere
#verify_chain — this is your proof-of-integrity function. Run it in a demo, edit a row directly in Postgres, run it again, watch it return False. That's your strongest talking point in an interview





import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg2
from psycopg2.extras import Json

# External anchor file for chain heads (see anchor_run/verify_chain_against_anchor
# below). Git-tracked and committed/pushed separately from the app's DB
# credentials, so it is not something the app's own Postgres access can rewrite.
ANCHOR_FILE = Path(__file__).resolve().parent / "chain_anchors.jsonl"


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


def anchor_run(run_id: str) -> dict | None:
    """Append the run's current chain head (last seq + hash) to
    audit/chain_anchors.jsonl. This is called once the run reaches a
    terminal status (see finalize_run).

    This file alone is NOT the external anchor — it lives on the same disk
    as the Postgres data, so anyone with DB access could edit this file too.
    It becomes an actual anchor only once it's committed and pushed to git:
    a git-pushed commit is outside the reach of whatever access let someone
    tamper with the database, so verify_chain_against_anchor() can catch a
    forged chain (one where every downstream hash was also recomputed to
    stay internally consistent) by comparing against the head recorded in
    git history, not just what's currently in Postgres.

    Run `git add audit/chain_anchors.jsonl && git commit && git push`
    periodically to actually lock these heads in. An unpushed anchor
    provides no protection.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT seq, hash FROM audit_events WHERE run_id = %s ORDER BY seq DESC LIMIT 1",
                (run_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    seq, hash_ = row
    entry = {
        "run_id": run_id,
        "seq": seq,
        "hash": hash_,
        "anchored_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(ANCHOR_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    return entry


def _latest_anchor(run_id: str) -> dict | None:
    """Read the last (highest-seq) anchor recorded for this run in the
    local anchor file. Returns None if the file doesn't exist or the run
    was never anchored."""
    if not ANCHOR_FILE.exists():
        return None

    latest = None
    with open(ANCHOR_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry["run_id"] != run_id:
                continue
            if latest is None or entry["seq"] > latest["seq"]:
                latest = entry
    return latest


def verify_chain_against_anchor(run_id: str) -> dict:
    """Stronger check than verify_chain() alone: also compares the current
    chain head against the head recorded in the local anchor file.

    - chain_valid: result of the normal forward hash-chain walk.
    - anchor_found: whether this run has an entry in chain_anchors.jsonl.
    - anchor_matches: whether the anchored hash still matches the current
      chain head. False here means the chain was rewritten after it was
      anchored — the scenario a plain verify_chain() forward walk cannot
      catch, since a rewritten chain re-validates as internally consistent.

    Remember this only defends against tampering that happened after the
    anchor file itself was committed and pushed to git; an anchor entry
    that only exists on local disk offers no protection.
    """
    chain_valid = verify_chain(run_id)

    anchor = _latest_anchor(run_id)
    if anchor is None:
        return {"chain_valid": chain_valid, "anchor_found": False, "anchor_matches": None}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT seq, hash FROM audit_events WHERE run_id = %s ORDER BY seq DESC LIMIT 1",
                (run_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    current_seq, current_hash = row if row else (None, None)
    matches = anchor["seq"] == current_seq and anchor["hash"] == current_hash

    return {"chain_valid": chain_valid, "anchor_found": True, "anchor_matches": matches}


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

def list_runs() -> list[dict]:
    """Return every run with its latest agent_decision and policy_check
    payloads attached (either may be None if that step hasn't run yet),
    newest first."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.id, r.request_payload, r.created_at,
                       (SELECT ae.payload FROM audit_events ae
                        WHERE ae.run_id = r.id AND ae.event_type = 'agent_decision'
                        ORDER BY ae.seq DESC LIMIT 1) AS decision_payload,
                       (SELECT ae.payload FROM audit_events ae
                        WHERE ae.run_id = r.id AND ae.event_type = 'policy_check'
                        ORDER BY ae.seq DESC LIMIT 1) AS policy_payload
                FROM runs r
                ORDER BY r.created_at DESC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": str(run_id),
            "request_payload": request_payload,
            "created_at": created_at.isoformat(),
            "decision": decision_payload,
            "policy": policy_payload,
        }
        for run_id, request_payload, created_at, decision_payload, policy_payload in rows
    ]


def finalize_run(run_id: str, status: str) -> None:
    """Set a run's terminal status (allowed/escalated/denied) and mark it
    completed. Called once the policy gate has produced its outcome.
    Also anchors the run's final chain head locally (see anchor_run) —
    remember to commit/push audit/chain_anchors.jsonl for that anchor to
    actually count as external."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE runs SET status = %s, completed_at = now() WHERE id = %s",
                (status, run_id),
            )
        conn.commit()
    finally:
        conn.close()

    anchor_run(run_id)


def list_escalations() -> list[dict]:
    """Return every run still awaiting human review: status='escalated' and
    not yet resolved, oldest first so the queue reads like a worklist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.id, r.request_payload, r.created_at,
                       (SELECT ae.payload FROM audit_events ae
                        WHERE ae.run_id = r.id AND ae.event_type = 'agent_decision'
                        ORDER BY ae.seq DESC LIMIT 1) AS decision_payload,
                       (SELECT ae.payload FROM audit_events ae
                        WHERE ae.run_id = r.id AND ae.event_type = 'policy_check'
                        ORDER BY ae.seq DESC LIMIT 1) AS policy_payload
                FROM runs r
                WHERE r.status = 'escalated' AND r.resolved_at IS NULL
                ORDER BY r.created_at ASC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": str(run_id),
            "request_payload": request_payload,
            "created_at": created_at.isoformat(),
            "decision": decision_payload,
            "policy": policy_payload,
        }
        for run_id, request_payload, created_at, decision_payload, policy_payload in rows
    ]


def resolve_escalation(run_id: str) -> None:
    """Mark an escalated run as resolved by a human reviewer."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE runs SET resolved_at = now() WHERE id = %s",
                (run_id,),
            )
        conn.commit()
    finally:
        conn.close()


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