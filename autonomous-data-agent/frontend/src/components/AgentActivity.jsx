import { CheckCircle2, AlertCircle, ListChecks } from "lucide-react";
const names = {
  ml_suitability: "Checking your data",
  regression: "Testing number predictions",
  classification: "Testing outcome predictions",
  clustering: "Finding similar groups",
  anomaly_detection: "Finding unusual records",
  feature_importance: "Finding important factors",
  model_evaluation: "Checking reliability",
};
export default function AgentActivity({ result }) {
  return (
    <details className="agent-activity">
      <summary>
        <ListChecks size={16} />
        Agent Activity{" "}
        <span>
          {result.tools_used.length} tools · {result.iterations} iterations ·{" "}
          {result.execution_seconds}s
        </span>
      </summary>
      {result.plan.length > 0 && (
        <div className="agent-plan">
          <h3>Initial analysis plan</h3>
          <p className="muted">
            The agent may adapt this plan after observing results.
          </p>
          <ol>
            {result.plan.map((step, i) => (
              <li key={i}>
                <b>{names[step.tool] || step.tool}</b> · {step.purpose}{" "}
                {step.columns.length > 0 && (
                  <small>({step.columns.join(", ")})</small>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
      <ul className="activity-list">
        {result.activities.map((item, i) => (
          <li key={i}>
            {item.status === "completed" ? (
              <CheckCircle2 size={15} />
            ) : (
              <AlertCircle size={15} />
            )}
            <div>
              <b>
                {names[item.tool] || item.action}
                {item.tool && !names[item.tool] ? ` · ${item.tool}` : ""}
              </b>
              <small>{item.summary}</small>
              {item.parameters?.columns?.length > 0 && (
                <small>Columns: {item.parameters.columns.join(", ")}</small>
              )}
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}
