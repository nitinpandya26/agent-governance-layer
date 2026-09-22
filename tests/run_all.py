import sys
sys.path.insert(0, ".")
import json
import time

from agent.graph import build_graph

with open("data/payment_requests.json") as f:
    requests = json.load(f)

graph = build_graph()
run_ids = []

for i, req in enumerate(requests):
    print(f"[{i+1}/{len(requests)}] Processing {req['request_id']}...")
    try:
        result = graph.invoke({"request": req, "run_id": "", "tool_results": {}, "decision": {}})
        run_ids.append({"request_id": req["request_id"], "run_id": result["run_id"], "decision": result["decision"]["decision"]})
        print(f"  -> {result['decision']['decision']} (confidence {result['decision']['confidence']})")
    except Exception as e:
        print(f"  -> ERROR: {e}")
    time.sleep(0.5)  # gentle on rate limits

with open("data/run_results.json", "w") as f:
    json.dump(run_ids, f, indent=2)

print(f"\nDone. {len(run_ids)}/{len(requests)} completed. Results saved to data/run_results.json")