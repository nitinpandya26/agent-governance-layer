import { useEffect, useMemo, useState } from "react";
import { api, OverrideStats } from "../api";

// Doc step 6 / Alan Law's feedback (docs/linkedin_feedback.md): surface the
// policy override rate as a trend split by rule, not one aggregate number -
// a rise on a single rule usually means traffic shifted, a rise across all
// of them points at the model or prompt. Plain inline SVG; no charting
// library needed for a handful of lines over a handful of days.

const RULE_COLORS = [
  "#2f6f4f", // above_auto_approve_limit - expected to dominate per Alan's prediction
  "#b5542c",
  "#5468b0",
  "#9c5fa8",
  "#c2932f",
];

export default function OverrideTrend() {
  const [stats, setStats] = useState<OverrideStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.overrideRate().then(setStats).catch((err) => setError(String(err)));
  }, []);

  const rules = useMemo(() => {
    if (!stats) return [];
    return Object.keys(stats.totals.by_rule).sort((a, b) => stats.totals.by_rule[b] - stats.totals.by_rule[a]);
  }, [stats]);

  if (error) return <div className="panel error">Couldn't load override rate: {error}</div>;
  if (!stats) return <div className="panel">Loading…</div>;

  const { by_day, totals } = stats;
  const topRule = rules[0];

  if (by_day.length === 0) {
    return (
      <div className="panel">
        <h2>Policy override rate</h2>
        <p className="muted">No approval proposals logged yet - submit some requests first.</p>
      </div>
    );
  }

  const width = 760;
  const height = 240;
  const padding = { top: 20, right: 20, bottom: 36, left: 44 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;
  const maxRate = Math.max(0.1, ...by_day.map((d) => d.override_rate));

  const x = (i: number) => padding.left + (by_day.length === 1 ? plotW / 2 : (i / (by_day.length - 1)) * plotW);
  const y = (rate: number) => padding.top + plotH - (rate / maxRate) * plotH;

  function lineFor(rule: string | null) {
    return by_day
      .map((d, i) => {
        const rate = rule ? (d.by_rule[rule] ?? 0) / Math.max(1, d.approve_proposals) : d.override_rate;
        return `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(rate).toFixed(1)}`;
      })
      .join(" ");
  }

  return (
    <div className="panel">
      <h2>Policy override rate</h2>
      <p className="muted">
        Approvals the agent proposed that the policy gate didn't allow outright, over time, split by which rule
        fired - a rising rate on one rule points at a traffic shift, a rise across all of them points at the model
        or prompt (docs/linkedin_feedback.md, Alan Law).
      </p>

      <div className="totals-row">
        <div className="total-card">
          <div className="total-value">{(totals.override_rate * 100).toFixed(1)}%</div>
          <div className="total-label">
            overall override rate ({totals.overridden} of {totals.approve_proposals} approvals)
          </div>
        </div>
        {topRule && (
          <div className="total-card">
            <div className="total-value mono">{topRule}</div>
            <div className="total-label">
              most-frequent rule ({totals.by_rule[topRule]} of {totals.overridden} overrides) — the predicted
              dominant rule was <code>above_auto_approve_limit</code>
            </div>
          </div>
        )}
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="trend-svg" role="img" aria-label="Override rate over time">
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <g key={f}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + plotH * (1 - f)}
              y2={padding.top + plotH * (1 - f)}
              className="grid-line"
            />
            <text x={padding.left - 8} y={padding.top + plotH * (1 - f) + 4} className="axis-label" textAnchor="end">
              {(maxRate * f * 100).toFixed(0)}%
            </text>
          </g>
        ))}

        <path d={lineFor(null)} className="trend-line trend-total" fill="none" />
        {rules.map((rule, i) => (
          <path
            key={rule}
            d={lineFor(rule)}
            fill="none"
            stroke={RULE_COLORS[i % RULE_COLORS.length]}
            strokeWidth={2}
            opacity={0.85}
          />
        ))}

        {by_day.map((d, i) => (
          <text key={d.date} x={x(i)} y={height - 8} className="axis-label" textAnchor="middle">
            {d.date.slice(5)}
          </text>
        ))}
      </svg>

      <div className="legend">
        <span className="legend-item">
          <span className="legend-swatch legend-total" /> overall
        </span>
        {rules.map((rule, i) => (
          <span key={rule} className="legend-item">
            <span className="legend-swatch" style={{ background: RULE_COLORS[i % RULE_COLORS.length] }} />
            <code>{rule}</code>
          </span>
        ))}
      </div>
    </div>
  );
}
