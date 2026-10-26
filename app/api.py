"""Read-only JSON API for the React dashboard (dashboard/). Deliberately
thin - every function here reuses audit/logger.py's existing queries rather
than talking to Postgres directly, so there's exactly one place that owns
the DB access and the hash-chain logic. The server-rendered Jinja UI in
app/main.py is untouched; this is additive, not a replacement.
"""
from fastapi import APIRouter, HTTPException

from audit.logger import (
    get_override_stats,
    get_trace,
    is_overridden,
    list_runs,
    verify_chain_against_anchor,
    verify_chain_against_timestamp,
)

router = APIRouter(prefix="/api")


def _flag(run: dict) -> dict:
    """Attach a `flagged` boolean to a run dict from list_runs(): true if
    the policy gate didn't allow it outright (escalated/denied), whether or
    not that was also an override of the agent's own proposal - a reviewer
    scanning the table wants every non-clean outcome surfaced, not just the
    override subset."""
    policy = run.get("policy")
    outcome = policy.get("result", {}).get("outcome") if policy else None
    return {
        **run,
        "flagged": outcome is not None and outcome != "allow",
        "overridden": is_overridden(run.get("decision"), policy),
    }


@router.get("/runs")
def api_list_runs():
    return [_flag(run) for run in list_runs()]


@router.get("/runs/{run_id}")
def api_run_detail(run_id: str):
    trace = get_trace(run_id)
    if not trace:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "trace": trace}


@router.get("/runs/{run_id}/verify")
def api_run_verify(run_id: str):
    trace = get_trace(run_id)
    if not trace:
        raise HTTPException(status_code=404, detail="run not found")
    anchor = verify_chain_against_anchor(run_id)
    timestamp = verify_chain_against_timestamp(run_id)
    return {"run_id": run_id, "anchor": anchor, "timestamp": timestamp}


@router.get("/override-rate")
def api_override_rate():
    return get_override_stats()
