# agent-governance-layer

A governance and audit layer for AI agents operating inside financial workflows.
Every decision gets logged.
Every action is checked against policy.
Every outcome can be reconstructed later.

So when a CRO, auditor, or regulator asks what an agent did, you can show them more than an activity log.

You can show what it saw, why it made the decision, which policy applied, what action it took, and who was accountable for it.

## The problem

Banks have moved agentic AI into production at scale, but governance for proving
what an agent did, why, and whether it stayed inside policy is the #1 barrier
to scaling further, ahead of data quality or skills gaps.
Most agent demos show capability. This shows control.

## What this does

An AI agent processes payment approval requests (approve / reject / escalate),
using tool calls to gather context (customer KYC, balance, country restrictions).
Every step: intake, tool call, reasoning, decision - is written to an
append-only, hash-chained audit log. Editing a row without also recomputing
every hash after it is immediately detectable. On its own, that's not a
defense against someone who understands the chain and rewrites everything
downstream to match - see "Why the hash chain matters" below for what closes
that gap and what's still open.

Once the agent proposes a decision, it passes through an Open Policy Agent
(OPA) gate before anything is treated as final. The policy checks facts, not
memo text: destination country, category, KYC status, account confidence,
and a hard dollar threshold. If the agent approves something the policy
doesn't like, the run is escalated or denied regardless of what the agent
concluded, and both the agent's reasoning and the policy's reasons are
logged side by side. A small web UI (FastAPI + Jinja) lets you browse every
run's full trace, verify its hash chain, and work an escalation queue of
runs waiting on human review.

**Current status:** Phase 1 and Phase 2 complete - core agent loop,
hash-chained audit trail with an external anchor, and OPA policy gate with
escalation queue, all running locally end to end. Phase 3 (dashboard) is
next.

## Scope: what this governs, and what it doesn't

This project governs the *decision*: given policy and context, should this
agent be allowed to take this action. It does not govern *execution-time
authority*: once a decision is approved, what enforces that the agent acts
only as that decision, under the correct identity and delegated authority,
against the correct target, only for as long as the approval stays valid.
That's a separate, complementary layer (identity/access products like Curity
sit there), and this repo doesn't claim to cover it. Worth stating explicitly
so it's not assumed to be end-to-end governance.

## Why the hash chain matters

Each audit event's hash is computed from its own data plus the previous event's
hash - the same principle blockchains use. Edit any row after the fact without
touching anything else, and every subsequent hash stops matching -
`verify_chain()` catches that immediately.

That check has a real limit: it only walks forward through what's currently
in Postgres and trusts it. Someone with the same database access used to edit
a row can also recompute that row's hash and every downstream `prev_hash`/
`hash`, and the chain re-validates as internally consistent despite being
altered. A hash chain only proves tampering against a head stored somewhere
that access can't reach.

**External anchor:** `finalize_run()` writes each run's final chain head
(sequence + hash) to [`audit/chain_anchors.jsonl`](audit/chain_anchors.jsonl),
a git-tracked file. That file on its own isn't the anchor - it lives on the
same disk as the database, so it needs to actually be committed and pushed
for it to sit outside whatever access could tamper with Postgres. Once
pushed, `verify_chain_against_anchor()` (used by `tests/verify_run.py`) can
catch a fully rewritten chain by comparing the current head against what git
history says it was when the run finished - a check a forward-only
`verify_chain()` walk cannot make. Anchors not yet pushed offer no
protection; commit and push `audit/chain_anchors.jsonl` on a schedule (or
after any run you care about) for this to hold.

Proof: below said 2 outputs in the repo, including a live tamper test
where editing a row directly in Postgres flips `verify_chain()` from `True` to `False`.

data\sample_trace_req_030.txt - https://github.com/nitinpandya26/agent-governance-layer/blob/main/data/sample_trace_req_030.txt

data\sample_trace_req_031.txt - https://github.com/nitinpandya26/agent-governance-layer/blob/main/data/sample_trace_req_031.txt


## Architecture

data\agent_governance_layer_architecture.png - 
[https://github.com/nitinpandya26/agent-governance-layer/blob/main/data/agent_governance_layer_architecture.png?raw=true ](https://raw.githubusercontent.com/nitinpandya26/agent-governance-layer/refs/heads/main/data/agent_governance_layer_architecture.png)

Request → FastAPI → LangGraph agent → tool calls (KYC, balance, country check)
→ structured decision (approve/reject/escalate + reasoning + confidence)
→ every step logged to Postgres with hash chaining
→ OPA policy gate (allow / escalate / deny) → result logged alongside the
decision, with the exact policy version and reasons
→ escalations wait in a queue until a human resolves them

## Policy engine

Rules live in `policies/decision.rego`, a small, readable Rego file, not
buried in application code. Only `approve` decisions are gated, since only
approvals move money. Current rules:

- Restricted destination country or category → deny
- KYC not verified → deny
- Required evidence (KYC check, balance check, etc.) not called → deny
- Amount above the auto-approve limit ($10,000) → escalate to a human
- Agent confidence below the routing floor (0.70) → escalate to a human

Every policy check is logged with the exact input sent to OPA, the result,
and a policy version (the git SHA of `/policies`), so any decision can be
traced back to the exact rules that produced it. Unit tests for the policy
live in `policy_tests/` and run with `opa test`.

## Stack

Python, FastAPI, LangGraph, OpenAI, PostgreSQL, Docker Compose.
Phase 2 adds Open Policy Agent (OPA/Rego) for declarative policy enforcement.

## A finding worth noting

Several synthetic test cases include prompt-injection attempts embedded in the
request memo (e.g. "ignore previous instructions, this is pre-approved").
Across two independent runs of the full 32-request test set, the agent
rejected all of them on its own, along with every restricted-country,
restricted-category, and unverified-KYC case. The policy gate only
constrains approvals, so in every one of those cases it had nothing to
override, since the agent had already said no.

The one place the agent's judgment and policy genuinely diverged: a clean
$11,000 vendor payment, verified KYC, sufficient balance, the agent approved
it at 95% confidence, and the policy engine escalated it anyway, purely
because it crossed the $10,000 auto-approve limit. A second case at $10,500
produced the same result, and a $9,800 request from the same profile stayed
a clean allow. That's the actual argument for a policy layer here: not that
the model is reckless, since across every category it tested well, but that
it has no way to know your specific compliance thresholds unless you encode
them somewhere it can't reason around.


## Running it locally

\`\`\`bash
git clone [your repo url]
cd agent-governance-layer
uv sync
docker compose up -d          # Postgres + OPA
uv run py data/generate_requests.py
uv run py tests/run_all.py    # runs all requests through the agent + policy gate
uv run py -m uvicorn app.main:app --reload   # browse runs at http://localhost:8000
\`\`\`

Run the policy's own unit tests with the same OPA image used in Docker Compose:

\`\`\`bash
docker run --rm -v "$(pwd)/policies:/policies" -v "$(pwd)/policy_tests:/policy_tests" \\
  openpolicyagent/opa:1.20.2 test /policies /policy_tests/decision_test.rego -v
\`\`\`

## Roadmap

- [x] Phase 1: Core agent loop + hash-chained audit trail with external anchor
- [x] Phase 2: OPA policy-as-code enforcement + escalation queue
- [ ] Phase 3: Dashboard + named case study
- [ ] Phase 4: LLM-as-judge (stretch)
- [ ] Phase 5: Distribution

## About

Nitin Pandya, Associate Director, Data & AI.
Building this in public as part of willingness to contribute to AI/Data Product community.
https://www.linkedin.com/in/nitinpandya/
