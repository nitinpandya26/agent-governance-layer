import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, TraceEvent, VerifyResponse } from "../api";
import StatusPill from "./StatusPill";

const EVENT_LABELS: Record<string, string> = {
  intake: "Intake",
  tool_call: "Tool call",
  agent_decision: "Agent decision",
  policy_check: "Policy check",
};

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [trace, setTrace] = useState<TraceEvent[] | null>(null);
  const [verify, setVerify] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    api
      .runDetail(runId)
      .then((r) => setTrace(r.trace))
      .catch((err) => setError(String(err)));
  }, [runId]);

  function runVerify() {
    if (!runId) return;
    api.runVerify(runId).then(setVerify).catch((err) => setError(String(err)));
  }

  if (error) return <div className="panel error">Couldn't load run: {error}</div>;
  if (!trace) return <div className="panel">Loading…</div>;

  const decisionEvent = trace.find((e) => e.event_type === "agent_decision");
  const policyEvent = trace.find((e) => e.event_type === "policy_check");
  const policyResult = policyEvent?.payload.result as
    | { outcome: string; deny_reasons: { policy: string; message: string }[]; escalate_reasons: { policy: string; message: string }[] }
    | undefined;

  return (
    <div className="panel">
      <div className="detail-header">
        <Link to="/" className="back-link">
          &larr; All runs
        </Link>
        <h2 className="mono">{runId}</h2>
        <button className="btn-outline" onClick={runVerify}>
          Verify hash chain + anchors
        </button>
      </div>

      {verify && (
        <div className={`verify-box ${verify.anchor.chain_valid ? "verify-ok" : "verify-bad"}`}>
          <div>
            <strong>Chain integrity:</strong> {verify.anchor.chain_valid ? "valid" : "TAMPERED — hash mismatch"}
          </div>
          <div>
            <strong>Git anchor:</strong>{" "}
            {verify.anchor.anchor_found
              ? verify.anchor.anchor_matches
                ? "found, matches current head"
                : "found, MISMATCH — chain was rewritten after anchoring"
              : "not anchored yet / anchor not pushed"}
          </div>
          <div>
            <strong>OpenTimestamps:</strong>{" "}
            {verify.timestamp.snapshot_found
              ? verify.timestamp.confirmed
                ? `Bitcoin-confirmed (block ${verify.timestamp.confirmed_heights.join(", ")})`
                : "stamped, pending Bitcoin confirmation"
              : "not yet stamped (run scripts/timestamp_anchor.py)"}
          </div>
        </div>
      )}

      {policyResult && (
        <div className="summary-row">
          <div>
            <span className="label">Agent proposed</span>
            <StatusPill label={String(decisionEvent?.payload.decision)} kind={String(decisionEvent?.payload.decision)} />
          </div>
          <div>
            <span className="label">Policy outcome</span>
            <StatusPill label={policyResult.outcome} kind={policyResult.outcome} />
          </div>
          <div>
            <span className="label">Policy version</span>
            <span className="mono">{String(policyEvent?.payload.policy_version)}</span>
          </div>
        </div>
      )}

      {policyResult && [...policyResult.deny_reasons, ...policyResult.escalate_reasons].length > 0 && (
        <div className="reasons-box">
          {[...policyResult.deny_reasons, ...policyResult.escalate_reasons].map((reason, i) => (
            <div key={i} className="reason-line">
              <code>{reason.policy}</code> {reason.message}
            </div>
          ))}
        </div>
      )}

      <ol className="trace-list">
        {trace.map((event) => (
          <li key={event.seq} className="trace-item">
            <div className="trace-item-head">
              <span className="trace-seq">#{event.seq}</span>
              <strong>{EVENT_LABELS[event.event_type] ?? event.event_type}</strong>
              <span className="muted mono">{event.created_at.slice(0, 19).replace("T", " ")}</span>
            </div>
            <pre className="trace-payload">{JSON.stringify(event.payload, null, 2)}</pre>
          </li>
        ))}
      </ol>
    </div>
  );
}
