import sys
sys.path.insert(0, ".")
import json

from audit.logger import get_trace, verify_chain

# paste any run_id from data/run_results.json here
run_id = "99ea0340-9cb1-41a6-9d04-768f4ddecb6f"

print(f"Chain valid: {verify_chain(run_id)}\n")
trace = get_trace(run_id)
for event in trace:
    print(f"--- Step {event['seq']}: {event['event_type']} ---")
    print(json.dumps(event['payload'], indent=2))
    print()