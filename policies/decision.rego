package governance.decision

import rego.v1

# thresholds
auto_approve_limit := 10000
confidence_floor := 0.70

restricted_countries := {"North Korea", "Iran"}
restricted_categories := {"crypto_exchange", "shell_company_transfer"}
required_tools := {"lookup_customer", "check_kyc_status", "get_account_balance"}

# only approvals move money, so only approvals are constrained
is_approval if input.proposed_action.decision == "approve"

# ---------- deny ----------

deny_reasons contains r if {
    is_approval
    restricted_countries[input.request.destination_country]
    r := {
        "policy": "restricted_country",
        "message": sprintf("destination %v is on the restricted list", [input.request.destination_country]),
    }
}

deny_reasons contains r if {
    is_approval
    restricted_categories[input.request.category]
    r := {
        "policy": "restricted_category",
        "message": sprintf("category %v is prohibited", [input.request.category]),
    }
}

deny_reasons contains r if {
    is_approval
    input.context.kyc_status != "verified"
    r := {
        "policy": "kyc_not_verified",
        "message": sprintf("kyc status is %v", [input.context.kyc_status]),
    }
}

deny_reasons contains r if {
    is_approval
    missing := required_tools - {t | some t in input.proposed_action.tools_called}
    count(missing) > 0
    r := {
        "policy": "required_evidence_missing",
        "message": sprintf("approval proposed without calling %v", [missing]),
    }
}

# ---------- escalate ----------

escalate_reasons contains r if {
    is_approval
    input.request.amount > auto_approve_limit
    r := {
        "policy": "above_auto_approve_limit",
        "message": sprintf("amount %v exceeds auto-approve limit %v", [input.request.amount, auto_approve_limit]),
    }
}

escalate_reasons contains r if {
    is_approval
    input.proposed_action.confidence < confidence_floor
    r := {
        "policy": "low_confidence_routing",
        "message": "model confidence below routing floor; human review required",
    }
}

# NOTE on what this floor actually catches: `confidence` is self-reported by
# the model in its own structured output, uncalibrated and unverified. This
# rule routes *honest uncertainty* (the model saying "I'm not sure") to a
# human. It is not a defense against a manipulated model that comes out
# confidently wrong — nothing here checks the stated confidence against
# anything real, so a fooled model reporting high confidence sails straight
# through this rule. The actual defense against a fooled model is that every
# *fact* this policy checks (kyc_status, tools_called, request fields) is
# sourced from tool_results/the raw request upstream, never from the model's
# own proposal - see the fact-sourcing comment in agent/graph.py's
# policy_gate_node. Don't read this rule as covering more than it does.

# ---------- outcome ----------

default outcome := "allow"

outcome := "deny" if count(deny_reasons) > 0

outcome := "escalate" if {
    count(deny_reasons) == 0
    count(escalate_reasons) > 0
}

result := {
    "outcome": outcome,
    "deny_reasons": deny_reasons,
    "escalate_reasons": escalate_reasons,
}
