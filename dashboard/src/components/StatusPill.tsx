interface Props {
  label: string;
  // Loosely typed on purpose: this renders both strongly-typed decision/
  // outcome values (approve/reject/escalate, allow/deny/escalate) and
  // values read out of a trace event's untyped JSON payload. Unknown
  // values just fall back to the unstyled default pill look via CSS.
  kind: string;
}

// One shared pill component so decision badges and policy-outcome badges
// read as the same visual language across the table and detail view.
export default function StatusPill({ label, kind }: Props) {
  return <span className={`pill pill-${kind}`}>{label}</span>;
}
