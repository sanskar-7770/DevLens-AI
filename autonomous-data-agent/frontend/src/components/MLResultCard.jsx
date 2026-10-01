import {
  ResponsiveContainer,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { Info, ShieldCheck, Lightbulb } from "lucide-react";
export const friendly = (name) =>
  String(name ?? "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
const number = (v) =>
  v == null
    ? "Not available"
    : typeof v === "number"
      ? v.toLocaleString(undefined, { maximumFractionDigits: 4 })
      : String(v);
const tips = {
  mae: "The average absolute difference between predicted and actual values.",
  rmse: "A prediction-error measure that gives larger mistakes more weight.",
  r2: "Variation captured on test records. Negative values mean worse than guessing their mean.",
  accuracy: "The fraction of test outcomes predicted correctly.",
  precision:
    "How often predicted outcomes were right, averaged equally across outcome types.",
  recall:
    "How often actual outcomes were found, averaged equally across outcome types.",
  f1: "Balances finding an outcome and identifying it correctly; averaged equally across outcome types.",
};
const colors = [
  "#21896b",
  "#ba7945",
  "#6477ba",
  "#a0678c",
  "#7c9549",
  "#5397a8",
];
export function MLChart({ chart }) {
  const groups = [...new Set(chart.data.map((d) => d.group))];
  return (
    <section className="card chart-card ml-chart">
      <h3>{chart.title}</h3>
      <p className="axis-caption">{chart.y_label}</p>
      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          {chart.kind === "scatter" || chart.kind === "groups" ? (
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#e4ede7" />
              <XAxis
                type="number"
                dataKey="x"
                name={chart.x_label}
                tick={{ fontSize: 10 }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name={chart.y_label}
                tick={{ fontSize: 10 }}
              />
              <Tooltip />
              <Legend />
              {chart.kind === "groups" ? (
                groups.map((g, i) => (
                  <Scatter
                    key={g}
                    name={g}
                    data={chart.data.filter((d) => d.group === g)}
                    fill={colors[i % colors.length]}
                    fillOpacity={0.65}
                  />
                ))
              ) : (
                <Scatter
                  name="Test records"
                  data={chart.data}
                  fill="#21896b"
                  fillOpacity={0.7}
                />
              )}
            </ScatterChart>
          ) : (
            <BarChart data={chart.data}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="#e4ede7"
              />
              <XAxis dataKey="x" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar
                dataKey="y"
                name={chart.y_label}
                fill="#21896b"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      <p className="x-caption">{chart.x_label}</p>
    </section>
  );
}
function Metrics({ values, perOutcome = false }) {
  const metricTips = perOutcome ? { ...tips, precision: "How often this predicted outcome was right.", recall: "How often this actual outcome was found.", f1: "Balances finding this outcome and identifying it correctly." } : tips;
  return (
    <dl className="ml-metrics">
      {Object.entries(values || {}).map(([key, value]) => (
        <div key={key}>
          <dt>
            {key.toUpperCase()}{" "}
            {metricTips[key] && (
              <button
                className="metric-help"
                type="button"
                title={metricTips[key]}
                aria-label={`${key}: ${metricTips[key]}`}
              >
                <Info size={13} />
              </button>
            )}
          </dt>
          <dd>{number(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
export default function MLResultCard({ result: r }) {
  const t = r.technical || {};
  return (
    <section className="ml-result" aria-label={r.title}>
      <div className="eyebrow">{r.title}</div>
      <h3 className="ml-conclusion">{r.summary}</h3>
      <div className="ml-takeaway">
        <Lightbulb size={20} />
        <p>{r.takeaway}</p>
      </div>
      <div className="chart-grid">
        {r.charts.map((c, i) => (
          <MLChart key={i} chart={c} />
        ))}
      </div>
      {r.factors.length > 0 && (
        <section className="ml-factors">
          <h3>What Matters Most</h3>
          <p>
            These inputs were useful to this model. Their ranking does not show
            what causes the outcome.
          </p>
          {r.factors.slice(0, 5).map((f) => (
            <div className="factor-row" key={f.column}>
              <span>{friendly(f.column)}</span>
              <meter
                min="0"
                max="1"
                value={f.weight}
                aria-label={`Relative importance of ${friendly(f.column)}`}
              />
              <small>
                {Math.round(f.weight * 100)}% of measured positive importance
              </small>
            </div>
          ))}
          {r.factors.every((f) => !f.weight) && (
            <p>
              No input showed positive measured importance in this experiment.
            </p>
          )}
        </section>
      )}
      {r.groups.length > 0 && (
        <div className="ml-groups">
          {r.groups.map((g) => (
            <section className="card" key={g.name}>
              <h3>{g.name}</h3>
              {r.task === "clustering" && (
                <span className="pill">{g.count} records</span>
              )}
              <ul>
                {g.description.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
      <section className="ml-reliability">
        <h3>
          <ShieldCheck size={17} /> How much should I trust this?
        </h3>
        <p>{r.reliability}</p>
        {r.warnings.length > 0 && (
          <ul>
            {r.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
      </section>
      {r.records.length > 0 && (
        <details className="ml-details">
          <summary>View records worth reviewing</summary>
          <p>
            Data row numbers start at one, excluding the header. Up to ten
            records are shown.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Data row</th>
                  {Object.keys(r.records[0].values).map((c) => (
                    <th key={c}>{friendly(c)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {r.records.map((record) => (
                  <tr key={record.row}>
                    <th>{record.row}</th>
                    {Object.entries(record.values).map(([c, v]) => (
                      <td key={c}>{number(v)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <details className="ml-details">
        <summary>View Technical Details</summary>
        <dl className="ml-metrics">
          {[
            ["Method", t.selected_model || t.algorithm || "Suitability check"],
            ["Target", t.target || r.target || "None"],
            ["Training records", t.train_rows],
            ["Test records", t.test_rows],
            ["Analyzed records", t.used_rows],
            ["Split", t.split],
            ["Random seed", t.seed],
            ["Silhouette score", t.silhouette],
            ["Projection", t.projection],
          ]
            .filter(([, v]) => v !== undefined)
            .map(([k, v]) => (
              <div key={k}>
                <dt
                  title={
                    k === "Silhouette score"
                      ? "Compares closeness within groups with separation between groups; higher is more separated."
                      : undefined
                  }
                >
                  {k}
                </dt>
                <dd>{number(v)}</dd>
              </div>
            ))}
        </dl>
        {t.metrics && (
          <>
            <h4>Held-out test measurements</h4>
            <Metrics values={t.metrics} />
            <h4>Training measurements</h4>
            <Metrics values={t.training_metrics} />
            <h4>Simple baseline</h4>
            <Metrics values={t.baseline} />
          </>
        )}
        {t.comparisons && (
          <details>
            <summary>Compare Methods</summary>
            <p>
              Selection used {t.selection_metric}. The comparison set was not
              used to fit the methods, but was used to choose the winner.
            </p>
            {t.comparisons.map((m) => (
              <div key={m.name}>
                <h4>{m.name}</h4>
                <Metrics values={m.test} />
              </div>
            ))}
          </details>
        )}
        {t.outcomes?.matrix && (
          <details>
            <summary>View Detailed Prediction Matrix</summary>
            <p>Rows are actual outcomes; columns are predicted outcomes.</p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Actual / Predicted</th>
                    {t.outcomes.labels.map((x) => (
                      <th key={x}>{x}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {t.outcomes.matrix.map((row, i) => (
                    <tr key={i}>
                      <th>{t.outcomes.labels[i]}</th>
                      {row.map((n, j) => (
                        <td key={j}>{n}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h4>Per-outcome results</h4>
            {t.outcomes.per_class.map((c) => (
              <div key={c.label}>
                <b>
                  {c.label} · {c.support} test records
                </b>
                <Metrics
                  perOutcome
                  values={{
                    precision: c.precision,
                    recall: c.recall,
                    f1: c.f1,
                  }}
                />
              </div>
            ))}
          </details>
        )}
        {t.features && (
          <p>
            <b>Inputs:</b> {t.features.map(friendly).join(", ")}
          </p>
        )}
        {t.importance_method && (
          <p>
            <b>Importance calculation:</b> {t.importance_method}
          </p>
        )}
        {t.parameters && (
          <dl className="ml-metrics">
            {Object.entries(t.parameters).map(([k, v]) => (
              <div key={k}>
                <dt>{friendly(k)}</dt>
                <dd>{number(v)}</dd>
              </div>
            ))}
          </dl>
        )}
        {t.candidates && (
          <p>
            Group comparisons:{" "}
            {t.candidates
              .map((c) => `${c.groups} groups: ${number(c.silhouette)}`)
              .join(" · ")}
          </p>
        )}
      </details>
    </section>
  );
}
