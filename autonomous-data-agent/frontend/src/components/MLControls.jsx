import { useState } from "react";
import { friendly } from "./MLResultCard";
const choices = [
  ["regression", "Predict a Number"],
  ["classification", "Predict an Outcome"],
  ["clustering", "Find Similar Groups"],
  ["anomaly_detection", "Find Unusual Records"],
  ["feature_importance", "What Matters Most"],
];
export default function MLControls({ overview, busy, onRun }) {
  const [tool, setTool] = useState("regression"),
    [target, setTarget] = useState("");
  const needsTarget = !["clustering", "anomaly_detection"].includes(tool);
  const columns = overview.column_info.filter((c) => !/(^|_)(id|uuid|index|recordid|identifier)($|_)/i.test(c.name)).filter((c) =>
    tool === "regression" ? c.type === "numerical" : c.type !== "datetime",
  );
  const selected = columns.some((c) => c.name === target)
    ? target
    : columns[0]?.name || "";
  return (
    <details className="ml-controls card">
      <summary>Explore predictions and patterns</summary>
      <p>
        Choose what you want to learn. These experiments run locally and do not
        require Gemini.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onRun(
            tool,
            needsTarget ? [selected] : [],
            choices.find(([v]) => v === tool)[1],
          );
        }}
      >
        <label>
          What would you like to do?
          <select
            value={tool}
            disabled={busy}
            onChange={(e) => {
              setTool(e.target.value);
              setTarget("");
            }}
          >
            {choices.map(([v, text]) => (
              <option key={v} value={v}>
                {text}
              </option>
            ))}
          </select>
        </label>
        {needsTarget && (
          <label>
            Which outcome should we investigate?
            <select
              value={selected}
              disabled={busy}
              onChange={(e) => setTarget(e.target.value)}
            >
              {columns.map((c) => (
                <option key={c.name} value={c.name}>
                  {friendly(c.name)}
                </option>
              ))}
            </select>
          </label>
        )}
        <p className="muted">
          {needsTarget
            ? "We will check the available inputs and test predictions on separate records. This does not forecast future records."
            : "We will compare records using usable inputs. Groups and unusual patterns are suggestions to investigate."}
        </p>
        <button
          type="submit"
          className="primary"
          disabled={busy || (needsTarget && !selected)}
        >
          Explore my data
        </button>
      </form>
    </details>
  );
}
