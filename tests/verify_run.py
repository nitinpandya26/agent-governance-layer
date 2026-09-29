import sys
sys.path.insert(0, ".")

from audit.logger import verify_chain_against_anchor

run_id = sys.argv[1]
result = verify_chain_against_anchor(run_id)

print(f"Chain valid (forward walk): {result['chain_valid']}")
if not result["anchor_found"]:
    print("Anchor: none recorded for this run yet (run finalize_run, or this "
          "predates anchoring) — no protection against a full chain rewrite.")
else:
    print(f"Anchor matches current chain head: {result['anchor_matches']}")
    if result["anchor_matches"] is False:
        print("MISMATCH: the chain head no longer matches what was anchored — "
              "the chain was rewritten after anchoring.")
