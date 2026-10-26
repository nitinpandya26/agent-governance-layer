import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, Run } from "../api";
import StatusPill from "./StatusPill";

type Filter = "all" | "flagged" | "clean";
type SortKey = "created_at" | "amount";

export default function RunsTable() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    api
      .listRuns()
      .then(setRuns)
      .catch((err) => setError(String(err)));
  }, []);

  const visible = useMemo(() => {
    if (!runs) return [];
    const filtered = runs.filter((r) => {
      if (filter === "flagged") return r.flagged;
      if (filter === "clean") return !r.flagged;
      return true;
    });
    const sorted = [...filtered].sort((a, b) => {
      const av = sortKey === "amount" ? a.request_payload.amount : a.created_at;
      const bv = sortKey === "amount" ? b.request_payload.amount : b.created_at;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDesc ? -cmp : cmp;
    });
    return sorted;
  }, [runs, filter, sortKey, sortDesc]);

  const flaggedCount = runs?.filter((r) => r.flagged).length ?? 0;

  if (error) {
    return <div className="panel error">Couldn't load runs: {error}</div>;
  }
  if (!runs) {
    return <div className="panel">Loading…</div>;
  }

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDesc((d) => !d);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <div className="filter-group" role="tablist" aria-label="Filter runs">
          <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>
            All <span className="count">{runs.length}</span>
          </button>
          <button className={filter === "flagged" ? "active" : ""} onClick={() => setFilter("flagged")}>
            Flagged <span className="count count-flagged">{flaggedCount}</span>
          </button>
          <button className={filter === "clean" ? "active" : ""} onClick={() => setFilter("clean")}>
            Clean <span className="count">{runs.length - flaggedCount}</span>
          </button>
        </div>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th className="sortable" onClick={() => toggleSort("created_at")}>
              Submitted {sortKey === "created_at" ? (sortDesc ? "↓" : "↑") : ""}
            </th>
            <th>Requester</th>
            <th className="sortable" onClick={() => toggleSort("amount")}>
              Amount {sortKey === "amount" ? (sortDesc ? "↓" : "↑") : ""}
            </th>
            <th>Destination</th>
            <th>Category</th>
            <th>Agent decision</th>
            <th>Policy outcome</th>
            <th>Flag</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((run) => {
            const req = run.request_payload;
            const outcome = run.policy?.result.outcome;
            return (
              <tr key={run.id} className={run.flagged ? "row-flagged" : ""}>
                <td className="mono muted">{run.created_at.slice(0, 19).replace("T", " ")}</td>
                <td>
                  <Link to={`/runs/${run.id}`}>{req.requester_name || req.requester}</Link>
                </td>
                <td className="mono">
                  {req.amount.toFixed(2)} {req.currency}
                </td>
                <td>{req.destination_country}</td>
                <td>{req.category}</td>
                <td>
                  {run.decision ? (
                    <StatusPill label={run.decision.decision} kind={run.decision.decision} />
                  ) : (
                    <span className="muted">pending</span>
                  )}
                </td>
                <td>
                  {outcome ? (
                    <StatusPill label={outcome} kind={outcome} />
                  ) : (
                    <span className="muted">pending</span>
                  )}
                </td>
                <td>
                  {run.overridden ? (
                    <span className="flag-badge flag-override" title="Agent approved; policy overrode it">
                      override
                    </span>
                  ) : run.flagged ? (
                    <span className="flag-badge flag-generic">flagged</span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            );
          })}
          {visible.length === 0 && (
            <tr>
              <td colSpan={8} className="empty-row">
                No runs match this filter.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
