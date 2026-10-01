import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Check,
  Database,
  ShieldCheck,
  ChartNoAxesCombined,
  Upload,
  ChevronRight,
  Activity,
} from "lucide-react";
import AskYourData from "../components/AskYourData";
import Sidebar from "../components/Sidebar";
import FileUpload from "../components/FileUpload";
import DatasetOverview from "../components/DatasetOverview";
import QualityCard from "../components/QualityCard";
import DataPreview from "../components/DataPreview";
import StatisticsPanel from "../components/StatisticsPanel";
import ChartCard, { CorrelationCard } from "../components/ChartCard";
import { uploadDataset, loadDataset, errorMessage } from "../services/api";
export default function App() {
  const [active, setActive] = useState("Overview"),
    [report, setReport] = useState(null),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [progress, setProgress] = useState(0),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function restore() {
    const id = new URLSearchParams(location.search).get("dataset");
    if (!id) {
      setReport(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setReport(await loadDataset(id));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    restore();
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  useEffect(() => {
    if (notice) {
      const timer = setTimeout(() => setNotice(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [notice]);
  function reset() {
    history.pushState({}, "", location.pathname);
    setReport(null);
    setError("");
    setNotice("");
    setActive("Overview");
  }
  async function upload(file) {
    setBusy(true);
    setError("");
    setProgress(0);
    try {
      const result = await uploadDataset(file, setProgress);
      const data = await loadDataset(result.dataset_id);
      history.pushState({}, "", `?dataset=${result.dataset_id}`);
      setReport(data);
      setActive("Overview");
      setNotice("Dataset analyzed successfully. Your workspace is ready.");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="app">
      <Sidebar active={active} setActive={setActive} onNew={reset} />
      <main>
        <header className="topbar">
          <span>
            Workspace <ChevronRight size={14} />{" "}
            <b>{report ? active : "Overview"}</b>
          </span>
          <span className="engine-status">
            <span className="status-dot" />
            Phase 3 · Analysis workspace
          </span>
        </header>
        <div className="content">
          {notice && (
            <div className="success" role="status">
              <Check size={16} />
              {notice}
            </div>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
              <button onClick={reset}>Start a new upload</button>
            </div>
          )}
          {loading ? (
            <div className="skeleton" aria-label="Loading dataset">
              <div />
              <div />
              <div />
            </div>
          ) : report ? (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">DATASET WORKSPACE</div>
                  <h1>{report.overview.filename}</h1>
                  <p>Your data, a little clearer. Explore the details below.</p>
                </div>
                <button className="secondary" onClick={reset}>
                  <Upload size={16} />
                  New dataset
                </button>
              </div>
              <DatasetOverview
                overview={report.overview}
                quality={report.quality}
              />
              <div hidden={active !== "Ask Your Data"}>
                <AskYourData
                  key={report.overview.dataset_id}
                  overview={report.overview}
                />
              </div>
              {active === "Overview" && (
                <>
                  <section className="card">
                    <div className="card-title">
                      <h2>Dataset at a glance</h2>
                      <span className="pill">
                        {report.overview.file_type.toUpperCase()}
                      </span>
                    </div>
                    <div className="type-grid">
                      {Object.entries(report.overview.type_counts).map(
                        ([t, n]) => (
                          <div key={t}>
                            <span className={`type-dot ${t}`} />
                            <b>{n}</b>
                            <span>{t} columns</span>
                          </div>
                        ),
                      )}
                    </div>
                  </section>
                  <DataPreview
                    preview={report.preview}
                    columns={report.overview.column_info}
                  />
                  <QualityCard quality={report.quality} />
                </>
              )}
              {active === "Data Quality" && (
                <QualityCard quality={report.quality} />
              )}{" "}
              {active === "Statistics" && (
                <StatisticsPanel statistics={report.statistics} />
              )}{" "}
              {active === "Visualizations" && (
                <>
                  <div className="section-heading">
                    <h2>Patterns, made visible</h2>
                    <p>Deterministic charts selected from your column types.</p>
                  </div>
                  <div className="chart-grid">
                    {report.visualizations.map((c, i) => (
                      <ChartCard key={i} chart={c} />
                    ))}
                  </div>
                  {!report.visualizations.length && (
                    <p className="empty">
                      No charts are available for these columns.
                    </p>
                  )}
                  <CorrelationCard correlations={report.correlations} />
                </>
              )}
            </>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span className="status-dot" /> YOUR DATA. A CLEARER
                    PICTURE.
                  </div>
                  <h1>
                    From raw data to
                    <br />
                    <span className="accent">real understanding.</span>
                  </h1>
                  <p>
                    Autonomous Intelligence for Your Data
                    <br />
                    <span>
                      Upload a dataset. Explore its quality, patterns, and
                      possibilities.
                    </span>
                  </p>
                </div>
                <div className="hero-art" aria-hidden="true">
                  <div className="art-grid" />
                  <div className="art-label">
                    <Activity size={16} /> DATA, CONNECTED
                  </div>
                  <div className="art-bars">
                    {[34, 56, 44, 78, 64, 92, 82].map((n, i) => (
                      <i key={i} style={{ height: n + "%" }} />
                    ))}
                  </div>
                  <div className="art-foot">
                    <span className="status-dot" /> Clarity in every column
                    <ArrowUpRight size={16} />
                  </div>
                </div>
              </div>
              <FileUpload onUpload={upload} busy={busy} progress={progress} />
              <div className="trust-line">
                <ShieldCheck size={14} />
                Pandas calculations stay local<span>·</span>Ask Your Data uses
                Gemini summaries<span>·</span>Your original data stays unchanged
              </div>
              <div className="section-heading">
                <div className="eyebrow">A SOLID FOUNDATION</div>
                <h2>One upload. A complete first look.</h2>
              </div>
              <div className="feature-grid">
                {[
                  [
                    Database,
                    "01",
                    "Know your dataset",
                    "Understand every column, data type, and record at a glance.",
                  ],
                  [
                    ShieldCheck,
                    "02",
                    "Find the gaps",
                    "Spot missing values, duplicates, and potential outliers.",
                  ],
                  [
                    ChartNoAxesCombined,
                    "03",
                    "See the patterns",
                    "Explore distributions, trends, and relationships in your data.",
                  ],
                ].map(([Icon, n, title, desc]) => (
                  <div className="feature" key={n}>
                    <div className="feature-top">
                      <Icon size={21} />
                      <span>{n}</span>
                    </div>
                    <h3>{title}</h3>
                    <p>{desc}</p>
                  </div>
                ))}
              </div>
              <div className="phase-note">
                <span className="pill">BUILT FOR WHAT’S NEXT</span>
                <p>
                  Explore your dashboard, then ask the AI analyst a question.
                </p>
                <span>Foundation → Intelligence</span>
              </div>
            </>
          )}
          <footer>
            <span>
              DataAgent AI <span className="muted">/ Foundation workspace</span>
            </span>
            <span>Pandas analysis · Gemini interpretation</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
