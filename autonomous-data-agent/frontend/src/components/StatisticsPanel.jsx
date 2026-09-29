import { fmt } from "../utils/format";
export default function StatisticsPanel({ statistics }) {
  const keys = [
    "column",
    "type",
    "count",
    "unique",
    "mean",
    "median",
    "min",
    "max",
    "std",
    "p25",
    "p50",
    "p75",
    "top",
    "frequency",
  ];
  return (
    <section className="card">
      <div className="card-title">
        <h2>Descriptive statistics</h2>
        <span className="muted">
          Sample standard deviation · non-null values
        </span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {keys.map((k) => (
                <th key={k}>{k}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {statistics.map((s) => (
              <tr key={s.column}>
                {keys.map((k) => (
                  <td key={k}>{fmt(s[k])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
