import { useEffect, useRef, useState } from "react";
import { Sparkles, Send, LoaderCircle, RotateCcw } from "lucide-react";
import {
  analyzeQuestion,
  analyzeML,
  agentStatus,
  errorMessage,
} from "../services/api";
import ChartCard, { CorrelationCard } from "./ChartCard";
import AgentActivity from "./AgentActivity";
import MLResultCard from "./MLResultCard";
import MLControls from "./MLControls";

function readConversation(key) {
  try {
    const value = JSON.parse(sessionStorage.getItem(key));
    return value && Array.isArray(value.turns)
      ? value
      : { sessionId: null, turns: [] };
  } catch {
    return { sessionId: null, turns: [] };
  }
}
export default function AskYourData({ overview }) {
  const key = `dataagent-chat:${overview.dataset_id}`;
  const [chat, setChat] = useState(() => readConversation(key));
  const [query, setQuery] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [status, setStatus] = useState(null);
  const mounted = useRef(true);
  const [elapsed, setElapsed] = useState(0);
  const [busyKind, setBusyKind] = useState("question");
  useEffect(() => {
    if (!busy) return;
    setElapsed(0);
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [busy]);
  async function runML(tool, columns, label) {
    if (busy) return;
    setBusyKind("experiment");
    setBusy(true);
    setError("");
    try {
      const result = await analyzeML(
        overview.dataset_id,
        tool,
        columns,
        chat.sessionId,
      );
      if (mounted.current)
        setChat((previous) => ({
          sessionId: result.session_id,
          turns: [
            ...previous.turns,
            {
              query: label + (columns.length ? `: ${columns[0]}` : ""),
              result,
            },
          ].slice(-10),
        }));
    } catch (e) {
      if (mounted.current) setError(errorMessage(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  useEffect(() => {
    mounted.current = true;
    agentStatus()
      .then((v) => {
        if (mounted.current) setStatus(v);
      })
      .catch(() => {});
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(chat));
    } catch {
      /* The in-memory conversation remains usable if browser storage is full. */
    }
  }, [chat, key]);
  function reset() {
    setChat({ sessionId: null, turns: [] });
    setError("");
    setQuery("");
  }
  async function ask(text = query) {
    const question = text.trim();
    if (!question || busy) return;
    setBusyKind("question");
    setBusy(true);
    setError("");
    try {
      const result = await analyzeQuestion(
        overview.dataset_id,
        question,
        chat.sessionId,
      );
      if (!mounted.current) return;
      setChat((previous) => ({
        sessionId: result.session_id,
        turns: [...previous.turns, { query: question, result }].slice(-10),
      }));
      setQuery("");
    } catch (e) {
      if (mounted.current) setError(errorMessage(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  const numeric = overview.column_info.find(
    (c) => c.type === "numerical" && !/(^|_)(id|uuid|index|recordid|identifier)($|_)/i.test(c.name),
  )?.name;
  const prompts = [
    "Find the most important patterns in this dataset.",
    ...(numeric
      ? [`What is the average ${numeric}?`, `Are there outliers in ${numeric}?`]
      : []),
    "Which columns contain missing values?",
  ];
  return (
    <section className="ask-workspace">
      <div className="card-title">
        <div>
          <div className="eyebrow">ASK YOUR DATA</div>
          <h2>
            <Sparkles size={20} /> AI Data Analyst
          </h2>
          <p>Ask questions about {overview.filename}</p>
        </div>
        <button className="secondary" disabled={busy} onClick={reset}>
          <RotateCcw size={14} />
          New conversation
        </button>
      </div>
      <div className="agent-disclosure">
        Basic statistical questions are calculated locally. For AI questions,
        Gemini receives your question, column metadata and compact analysis
        summaries. Full datasets and scatter samples stay on this backend.
        Numerical findings are calculated by Pandas.
      </div>
      {status && !status.configured && (
        <div className="error" role="status">
          Gemini setup required: add GEMINI_API_KEY to backend/.env, then
          restart the backend. Basic statistical questions and the dashboard
          remain available.
        </div>
      )}
      <MLControls overview={overview} busy={busy} onRun={runML} />
      {!chat.turns.length && (
        <div className="agent-welcome card">
          <Sparkles size={25} />
          <h3>What would you like to understand?</h3>
          <p>
            I can inspect patterns, compare groups, explore associations, and
            create charts from your data.
          </p>
          <div className="prompt-grid">
            {prompts.map((prompt) => (
              <button
                disabled={busy}
                className="secondary"
                key={prompt}
                onClick={() => ask(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="conversation" aria-live="polite">
        {chat.turns.map((turn, i) => (
          <article key={i} className="conversation-turn">
            <div className="user-question">
              <small>YOU</small>
              <p>{turn.query}</p>
            </div>
            <div className="agent-answer card">
              <div className="card-title">
                <h3>
                  <Sparkles size={16} />{" "}
                  {turn.result.source === "local"
                    ? "LOCAL ANALYTICS"
                    : "GEMINI ANALYST"}
                </h3>
                <span className="pill">{turn.result.status}</span>
              </div>
              {turn.result.insights?.length > 0 ? (
                turn.result.insights.map((r, j) => (
                  <MLResultCard key={j} result={r} />
                ))
              ) : (
                <p className="answer-summary">{turn.result.answer}</p>
              )}
              {!turn.result.insights?.length &&
                turn.result.findings.length > 0 && (
                  <>
                    <h3>Key findings · verified evidence</h3>
                    <ul className="finding-list">
                      {turn.result.evidence.map((e) => (
                        <li key={e.id}>
                          <span className="pill">
                            {e.id} · {e.tool}
                          </span>
                          <p>{e.text}</p>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              {!turn.result.insights?.length &&
                turn.result.potential_explanation && (
                  <>
                    <h3>Potential explanation</h3>
                    <p>{turn.result.potential_explanation}</p>
                  </>
                )}
              {turn.result.insights?.length > 0 &&
                turn.result.errors.length > 0 && (
                  <details className="ml-details">
                    <summary>Analysis notices</summary>
                    {turn.result.errors.map((e, j) => (
                      <p key={j}>{e}</p>
                    ))}
                  </details>
                )}
              {!turn.result.insights?.length &&
                turn.result.errors.map((e, j) => (
                  <div className="error" key={j}>
                    {e}
                  </div>
                ))}
              <div className="chart-grid">
                {turn.result.charts.map((c, j) =>
                  c.kind === "heatmap" ? (
                    <CorrelationCard key={j} correlations={c.correlations} />
                  ) : (
                    <ChartCard key={j} chart={c} />
                  ),
                )}
              </div>
              <AgentActivity result={turn.result} />
              {turn.result.suggested_next_analysis.length > 0 && (
                <div className="next-analysis">
                  <h3>Suggested next analysis</h3>
                  {turn.result.suggested_next_analysis.map((s, j) => (
                    <button disabled={busy} key={j} onClick={() => ask(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
      {busy && (
        <div className="agent-busy" role="status">
          <LoaderCircle size={18} className="spin" />
          <div>
            Analyzing your question… {elapsed}s elapsed
            <small>
              {busyKind === "experiment"
                ? "Checking usable records, testing methods, and preparing a reliability summary."
                : "Choosing an appropriate method and checking the results. Gemini requests use bounded retries."}
              {" "}The verified activity log appears when the run finishes. The browser waits up to 170 seconds.
            </small>
          </div>
        </div>
      )}
      {error && (
        <div className="error" role="alert">
          {error}
          <button disabled={busy} onClick={reset}>
            New conversation
          </button>
        </div>
      )}
      <form
        className="question-form"
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
      >
        <label htmlFor="agent-question">Ask an analytical question</label>
        <textarea
          id="agent-question"
          rows={3}
          maxLength={2000}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={busy}
          placeholder="What patterns should I investigate?"
        />
        <div>
          <small>
            {query.length}/2000 · Follow-ups use the last 3 turns in this
            dataset session.
          </small>
          <button
            className="primary"
            disabled={busy || !query.trim()}
            type="submit"
          >
            <Send size={15} />
            {busy ? "Analyzing…" : "Ask analyst"}
          </button>
        </div>
      </form>
    </section>
  );
}
