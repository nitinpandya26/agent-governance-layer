import { NavLink, Route, Routes } from "react-router-dom";
import RunsTable from "./components/RunsTable";
import RunDetail from "./components/RunDetail";
import OverrideTrend from "./components/OverrideTrend";

export default function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">AGL</span>
          <div>
            <div className="brand-title">Decision Review Dashboard</div>
            <div className="brand-sub">Agent Governance Layer</div>
          </div>
        </div>
        <nav className="toplinks">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Runs
          </NavLink>
          <NavLink to="/trend" className={({ isActive }) => (isActive ? "active" : "")}>
            Override rate
          </NavLink>
          <a href="/" className="back-link">
            &larr; Back to app
          </a>
        </nav>
      </header>

      <main className="content">
        <Routes>
          <Route path="/" element={<RunsTable />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/trend" element={<OverrideTrend />} />
        </Routes>
      </main>
    </div>
  );
}
