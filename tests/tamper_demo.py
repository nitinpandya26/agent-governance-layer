"""Reproducible tamper demo: shows what the forward-walk check catches, and
what only the external anchor catches.

Creates its own throwaway run (no LLM calls), records it to a temporary
anchor file so the real audit/chain_anchors.jsonl is not touched, then:

  1. Verifies the untouched run (both checks should pass).
  2. Edits one early event's payload directly in Postgres, and recomputes
     that event's hash and every downstream prev_hash/hash so the chain
     is internally consistent again - the attack a forward walk cannot see.
  3. Verifies again: the forward walk still passes, the anchor check fails.

Run with:
  uv run python tests/tamper_demo.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from psycopg2.extras import Json

import audit.logger as logger
from audit.logger import (
    _compute_hash,
    create_run,
    finalize_run,
    get_connection,
    log_event,
    verify_chain,
    verify_chain_against_anchor,
)

# Keep the demo's anchor out of the real, committed anchor file.
logger.ANCHOR_FILE = Path(tempfile.mkdtemp()) / "demo_anchors.jsonl"

run_id = create_run({"request_id": "tamper_demo", "amount": 2500, "note": "throwaway demo run"})
log_event(run_id, "intake", {"request": {"amount": 2500, "destination_country": "US"}})
log_event(run_id, "tool_call", {"tool": "check_kyc_status", "result": {"kyc_verified": True}})
log_event(run_id, "agent_decision", {"decision": "approve", "confidence": 0.95})
log_event(run_id, "policy_check", {"result": {"outcome": "allow"}})
finalize_run(run_id, "allowed")  # writes the anchor for the final chain head

print(f"Demo run: {run_id}")
print("\n--- 1. Untouched run ---")
before = verify_chain_against_anchor(run_id)
print(f"Forward walk verify_chain(): {verify_chain(run_id)}")
print(f"Anchor matches current chain head: {before['anchor_matches']}")

# --- 2. The attack: edit an early event and recompute everything after it ---
conn = get_connection()
with conn.cursor() as cur:
    cur.execute(
        "SELECT seq, payload, prev_hash FROM audit_events WHERE run_id = %s ORDER BY seq ASC",
        (run_id,),
    )
    rows = cur.fetchall()

    target_seq, payload, prev_hash = rows[1]  # the tool_call event
    payload["result"]["kyc_verified"] = False  # the lie
    new_hash = _compute_hash(payload, prev_hash)
    cur.execute(
        "UPDATE audit_events SET payload = %s, hash = %s WHERE run_id = %s AND seq = %s",
        (Json(payload), new_hash, run_id, target_seq),
    )

    prev = new_hash
    for seq, downstream_payload, _ in rows[2:]:
        h = _compute_hash(downstream_payload, prev)
        cur.execute(
            "UPDATE audit_events SET prev_hash = %s, hash = %s WHERE run_id = %s AND seq = %s",
            (prev, h, run_id, seq),
        )
        prev = h
conn.commit()
conn.close()

print("\n--- 2. After editing seq 2 and recomputing every downstream hash ---")
after = verify_chain_against_anchor(run_id)
print(f"Forward walk verify_chain(): {verify_chain(run_id)}")
print(f"Anchor matches current chain head: {after['anchor_matches']}")
if after["anchor_matches"] is False:
    print("MISMATCH: the chain was rewritten after it was anchored.")
