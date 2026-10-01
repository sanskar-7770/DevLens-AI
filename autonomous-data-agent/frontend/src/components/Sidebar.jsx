import {
  Database,
  LayoutDashboard,
  ShieldCheck,
  ChartNoAxesCombined,
  Table2,
  Sparkles,
  MessageSquare,
  FileText,
  ArrowUpRight,
} from "lucide-react";
export default function Sidebar({ active, setActive, onNew }) {
  const items = [
    ["Overview", LayoutDashboard],
    ["Data Quality", ShieldCheck],
    ["Statistics", Table2],
    ["Visualizations", ChartNoAxesCombined],
    ["Ask Your Data", MessageSquare],
  ];
  return (
    <aside className="sidebar">
      <a
        className="brand"
        href="#"
        onClick={(e) => {
          e.preventDefault();
          onNew();
        }}
      >
        <span className="brand-icon">
          <Database size={21} />
        </span>
        DataAgent<span className="brand-ai">AI</span>
      </a>
      <div className="workspace-label">WORKSPACE</div>
      <nav>
        {items.map(([label, Icon]) => (
          <button
            key={label}
            className={active === label ? "nav-item active" : "nav-item"}
            onClick={() => setActive(label)}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </nav>
      <div className="workspace-label future-label">
        COMING NEXT <span>PHASE 4</span>
      </div>
      {[[FileText, "Reports"]].map(([Icon, label]) => (
        <button
          className="nav-item future"
          key={label}
          disabled
          title="Coming in Phase 4"
        >
          <Icon size={18} />
          {label}
          <span>SOON</span>
        </button>
      ))}
      <div className="sidebar-bottom">
        <div className="phase-card">
          <span className="status-dot" /> Phase 3 · Data analyst
          <p>
            Great insights start with
            <br />
            understanding your data.
          </p>
          <span>
            Analysis engine ready <ArrowUpRight size={14} />
          </span>
        </div>
        <div className="profile">
          <div className="avatar">DA</div>
          <div>
            Personal workspace<small>Local analysis environment</small>
          </div>
        </div>
      </div>
    </aside>
  );
}
