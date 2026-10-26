// Thin fetch wrappers + types over app/api.py. Types mirror the exact dict
// shapes audit/logger.py returns (see that file's docstrings) - kept here
// rather than generated, since the API is small and read-only.

export interface PolicyReason {
  policy: string;
  message: string;
}

export interface PolicyResult {
  outcome: "allow" | "deny" | "escalate";
  deny_reasons: PolicyReason[];
  escalate_reasons: PolicyReason[];
}

export interface PolicyCheck {
  policy_version: string;
  input: unknown;
  result: PolicyResult;
}

export interface AgentDecision {
  decision: "approve" | "reject" | "escalate";
  reasoning: string;
  confidence: number;
  tools_called: string[];
  facts_relied_on: string[];
}

export interface RequestPayload {
  requester: string;
  requester_name?: string;
  amount: number;
  currency: string;
  destination_country: string;
  category: string;
  memo?: string;
}

export interface Run {
  id: string;
  request_payload: RequestPayload;
  created_at: string;
  decision: AgentDecision | null;
  policy: PolicyCheck | null;
  flagged: boolean;
  overridden: boolean;
}

export interface TraceEvent {
  seq: number;
  event_type: "intake" | "tool_call" | "agent_decision" | "policy_check";
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RunDetailResponse {
  run_id: string;
  trace: TraceEvent[];
}

export interface AnchorVerify {
  chain_valid: boolean;
  anchor_found: boolean;
  anchor_matches: boolean | null;
}

export interface TimestampVerify {
  snapshot_found: boolean;
  confirmed: boolean;
  confirmed_heights: number[];
  snapshot_file: string | null;
}

export interface VerifyResponse {
  run_id: string;
  anchor: AnchorVerify;
  timestamp: TimestampVerify;
}

export interface OverrideDayBucket {
  date: string;
  approve_proposals: number;
  overridden: number;
  override_rate: number;
  by_rule: Record<string, number>;
}

export interface OverrideStats {
  by_day: OverrideDayBucket[];
  totals: OverrideDayBucket;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listRuns: () => getJSON<Run[]>("/api/runs"),
  runDetail: (runId: string) => getJSON<RunDetailResponse>(`/api/runs/${runId}`),
  runVerify: (runId: string) => getJSON<VerifyResponse>(`/api/runs/${runId}/verify`),
  overrideRate: () => getJSON<OverrideStats>("/api/override-rate"),
};
