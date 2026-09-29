import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { fmt } from "../utils/format";
export default function ChartCard({ chart: c }) {
  const axes = (
    <>
      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#edf0f3" />
      <XAxis
        dataKey="x"
        type={c.kind === "scatter" ? "number" : "category"}
        tick={{ fontSize: 10 }}
        tickLine={false}
        axisLine={false}
        minTickGap={35}
      />
      <YAxis
        dataKey={c.kind === "scatter" ? "y" : undefined}
        type="number"
        tick={{ fontSize: 11 }}
        tickLine={false}
        axisLine={false}
      />
      <Tooltip cursor={{ fill: "#f0f5f3" }} />
    </>
  );
  return (
    <section className="card chart-card">
      <div className="card-title">
        <h2>{c.title}</h2>
        <span className="pill">{c.kind}</span>
      </div>
      <div className="axis-caption">{c.y_label}</div>
      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          {c.kind === "line" ? (
            <LineChart data={c.data}>
              {axes}
              <Line
                dataKey="y"
                name={c.y_label}
                stroke="#21896b"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          ) : c.kind === "scatter" ? (
            <ScatterChart>
              {axes}
              <Scatter
                name={c.y_label}
                data={c.data}
                fill="#21896b"
                fillOpacity={0.65}
              />
            </ScatterChart>
          ) : (
            <BarChart data={c.data}>
              {axes}
              <Bar
                dataKey="y"
                name={c.y_label}
                fill="#319b7e"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      <div className="x-caption">{c.x_label}</div>
    </section>
  );
}
export function CorrelationCard({ correlations: c }) {
  return (
    <section className="card">
      <div className="card-title">
        <h2>Correlation matrix</h2>
        <span className="pill">Pearson · up to 20 numeric columns</span>
      </div>
      {c.columns.length < 2 ? (
        <p className="empty">
          Add at least two numerical columns to explore relationships.
        </p>
      ) : (
        <>
          <p className="muted">
            −1 inverse · 0 no linear association · +1 positive · — undefined
          </p>
          <div className="table-scroll">
            <table className="heatmap">
              <thead>
                <tr>
                  <th />
                  {c.columns.map((n) => (
                    <th key={n}>{n}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {c.matrix.map((row, i) => (
                  <tr key={c.columns[i]}>
                    <th>{c.columns[i]}</th>
                    {row.map((v, j) => (
                      <td
                        key={j}
                        title={`${c.columns[i]} / ${c.columns[j]}: ${fmt(v)}`}
                        style={{
                          background:
                            v == null
                              ? "#f3f4f6"
                              : v < 0
                                ? `rgba(224,135,109,${0.12 + Math.abs(v) * 0.65})`
                                : `rgba(49,155,126,${0.08 + v * 0.65})`,
                        }}
                      >
                        {fmt(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
