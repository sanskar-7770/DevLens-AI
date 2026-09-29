import { CheckCircle2, TriangleAlert } from "lucide-react";
export default function QualityCard({ quality: q }) {
  return (
    <section className="card">
      <div className="card-title">
        <h2>Data quality</h2>
        <span className="pill">IQR + completeness checks</span>
      </div>
      <div className="quality-summary">
        <div className="score">
          {q.score}
          <small>/100</small>
        </div>
        <div>
          <h3>A closer look at data health</h3>
          <p>
            {q.duplicates} duplicate rows · {q.outlier_count} potential outlier
            cells
          </p>
          <small>
            Heuristic score: 50% completeness, 30% uniqueness, 20% numeric
            inliers.
          </small>
        </div>
      </div>
      <div className="warnings">
        {q.warnings.length ? (
          q.warnings.map((w, i) => (
            <div key={i}>
              <TriangleAlert size={16} />
              <span>{w}</span>
            </div>
          ))
        ) : (
          <div>
            <CheckCircle2 size={17} />
            No issues found by the current checks.
          </div>
        )}
      </div>
    </section>
  );
}
