import sys
sys.path.insert(0, ".")
import json

from agent.graph import build_graph

with open("data/payment_requests.json") as f:
    requests = json.load(f)

graph = build_graph()
result = graph.invoke({"request": requests[0], "run_id": "", "tool_results": {}, "decision": {}})

print(f"Run ID: {result['run_id']}")
print(f"Decision: {json.dumps(result['decision'], indent=2)}")