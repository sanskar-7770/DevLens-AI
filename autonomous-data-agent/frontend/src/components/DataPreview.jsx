import { fmt } from "../utils/format";
export default function DataPreview({ preview, columns }) {
  return (
    <section className="card">
      <div className="card-title">
        <h2>Dataset preview</h2>
        <span className="muted">First {preview.rows.length} rows</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              {columns.map((c) => (
                <th key={c.name}>
                  {c.name}
                  <small>{c.type}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, i) => (
              <tr key={i}>
                <td className="muted">{i + 1}</td>
                {columns.map((c) => (
                  <td key={c.name}>
                    {row[c.name] == null ? (
                      <span className="null">NULL</span>
                    ) : (
                      fmt(row[c.name])
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
