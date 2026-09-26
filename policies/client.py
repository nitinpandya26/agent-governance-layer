import os

import requests

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
DECISION_PATH = "/v1/data/governance/decision/result"


def evaluate(policy_input: dict) -> dict:
    """Send a decision input to the OPA server and return its result.

    Returns {"outcome": "allow" | "deny" | "escalate", "deny_reasons": [...],
    "escalate_reasons": [...]}. Raises requests.RequestException if OPA is
    unreachable or returns a non-2xx status — the caller decides how to
    handle a policy engine that's down (fail closed vs. fail open).
    """
    response = requests.post(
        f"{OPA_URL}{DECISION_PATH}",
        json={"input": policy_input},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()["result"]
