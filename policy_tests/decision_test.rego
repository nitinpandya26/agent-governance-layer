package governance.decision

import rego.v1

base_request := {
	"requester": "cust_001",
	"amount": 2500,
	"currency": "USD",
	"destination_country": "US",
	"category": "travel",
	"memo": "Conference travel reimbursement",
}

base_context := {"kyc_status": "verified"}

base_action := {
	"decision": "approve",
	"confidence": 0.92,
	"tools_called": ["lookup_customer", "check_kyc_status", "get_account_balance"],
}

# ---------- allow ----------

test_clean_approval_is_allowed if {
	result.outcome == "allow" with input as {
		"request": base_request,
		"context": base_context,
		"proposed_action": base_action,
	}
}

test_reject_decision_is_never_blocked if {
	action := object.union(base_action, {"decision": "reject"})
	result.outcome == "allow" with input as {
		"request": object.union(base_request, {"destination_country": "RU"}),
		"context": {"kyc_status": "unverified"},
		"proposed_action": action,
	}
}

# ---------- deny ----------

test_restricted_country_is_denied if {
	req := object.union(base_request, {"destination_country": "Iran"})
	result.outcome == "deny" with input as {
		"request": req,
		"context": base_context,
		"proposed_action": base_action,
	}
	{"policy": "restricted_country", "message": "destination Iran is on the restricted list"} in result.deny_reasons
		with input as {"request": req, "context": base_context, "proposed_action": base_action}
}

test_restricted_category_is_denied if {
	req := object.union(base_request, {"category": "shell_company_transfer"})
	result.outcome == "deny" with input as {
		"request": req,
		"context": base_context,
		"proposed_action": base_action,
	}
}

test_unverified_kyc_is_denied if {
	result.outcome == "deny" with input as {
		"request": base_request,
		"context": {"kyc_status": "unverified"},
		"proposed_action": base_action,
	}
}

test_missing_required_tool_call_is_denied if {
	action := object.union(base_action, {"tools_called": ["lookup_customer"]})
	result.outcome == "deny" with input as {
		"request": base_request,
		"context": base_context,
		"proposed_action": action,
	}
}

test_deny_takes_priority_over_escalate if {
	req := object.union(base_request, {"destination_country": "Iran", "amount": 50000})
	result.outcome == "deny" with input as {
		"request": req,
		"context": base_context,
		"proposed_action": base_action,
	}
}

# ---------- escalate ----------

test_amount_above_limit_is_escalated if {
	req := object.union(base_request, {"amount": 15000})
	result.outcome == "escalate" with input as {
		"request": req,
		"context": base_context,
		"proposed_action": base_action,
	}
}

test_low_confidence_is_escalated if {
	action := object.union(base_action, {"confidence": 0.4})
	result.outcome == "escalate" with input as {
		"request": base_request,
		"context": base_context,
		"proposed_action": action,
	}
}
