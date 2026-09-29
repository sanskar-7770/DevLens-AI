import { Rows3, Columns3, ShieldCheck, Database } from "lucide-react";
import { fmt } from "../utils/format";
export default function DatasetOverview({ overview, quality }) {
  return (
    <div className="metrics">
      {[
        [Rows3, "Total rows", fmt(overview.rows), "Records in your dataset"],
        [
          Columns3,
          "Total columns",
          overview.columns,
          "Features ready to explore",
        ],
        [
          ShieldCheck,
          "Data quality",
          `${quality.score}/100`,
          "Rule-based quality score",
        ],
        [
          Database,
          "Missing values",
          `${quality.missing_percentage}%`,
          "Across all dataset cells",
        ],
      ].map(([Icon, label, value, note]) => (
        <div className="metric" key={label}>
          <div className="metric-label">
            {label}
            <Icon size={17} />
          </div>
          <strong>{value}</strong>
          <small>{note}</small>
        </div>
      ))}
    </div>
  );
}
