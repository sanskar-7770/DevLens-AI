# DataAgent AI — Autonomous Data Analysis Agent

A college portfolio project that turns CSV and Excel datasets into a clear, interactive analysis dashboard. **Phase 1 only:** all analysis is deterministic Python. There is no LLM, agent framework, RAG, database, or autonomous decision-making.

## Features

- Drag-and-drop CSV/XLSX upload, progress, errors, and a built-in sample.
- Column types, unique counts, row/column totals, and a 20-row preview.
- Missing values, duplicate rows, IQR outliers, constants, and high cardinality.
- Numerical descriptive statistics and category modes/frequencies.
- Histograms, frequency bars, mean time trends, sampled scatter plots, and Pearson correlation heatmaps.
- Responsive React dashboard with Overview, Data Quality, Statistics, and Visualizations.
- Local JSON reports survive reloads and backend restarts. The URL contains the dataset ID.

## Stack and architecture

React + Vite + Tailwind CSS + Axios + Recharts + Lucide React; FastAPI + Uvicorn + Pandas + NumPy + OpenPyXL.

```text
Browser → Axios → FastAPI routes → ingestion / analysis services
                                      ↓
                             independent Python tools
                                      ↓
                           compact local JSON report
                                      ↓
                              React dashboard
```

```text
autonomous-data-agent/
  backend/
    main.py                    App, CORS, safe server errors
    routes/datasets.py         Upload and dataset HTTP endpoints
    models/responses.py        Typed upload/overview response contracts
    services/storage.py       Validation, bounded parsing, UUID report storage
    services/analysis.py       Deterministic tool orchestration and quality score
    tools/
      dataset_inspector.py    Types, missing values, duplicates, overview
      statistics_tool.py      Reusable descriptive statistics
      outlier_tool.py         IQR fences and outlier counts
      correlation_tool.py     Pearson correlation matrix
      trend_tool.py           Time-binned mean analysis
      visualization_tool.py   Structured histogram/category/scatter data
    utils/serialization.py    JSON-safe nulls, scalars, dates
    tests/test_api.py          CSV/XLSX integration and edge-case tests
    uploads/                  Generated reports, ignored by Git
    requirements.txt          Compatible dependency ranges
    requirements-lock.txt     Exact tested environment
  frontend/
    src/components/           Upload, sidebar, overview, quality, preview, statistics, charts
    src/pages/App.jsx         Landing/dashboard state and URL restoration
    src/services/api.js       Axios upload/progress and report retrieval
    src/utils/format.js       Shared display formatting
    src/styles.css            Responsive theme and Tailwind entry point
    public/sample.csv         Built-in demo dataset
    package-lock.json         Reproducible frontend dependencies
  data/                       Matching CSV and XLSX sample datasets
```

## Installation and running (Windows PowerShell)

Use Python 3.11+ and Node.js 20.19+ or 22.12+. Tested here with Python 3.14.
Open a terminal in `autonomous-data-agent`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open a second terminal in `autonomous-data-agent`:

```powershell
cd frontend
npm install
npm run dev
```

Visit http://127.0.0.1:5173 and upload either sample under `data/`, or click **Try a sample dataset**. API documentation: http://127.0.0.1:8000/docs.

No API key is needed. Stop each server with Ctrl+C. On macOS/Linux, use `.venv/bin/python` in place of `.venv\Scripts\python.exe`.

Vite proxies `/api` to port 8000. For a separate frontend deployment, set `VITE_API_URL` at build time and set backend `CORS_ORIGINS` to a comma-separated list of exact allowed frontend origins. Environment variables must be supplied by your shell/process manager; no dotenv loader is included. Production static hosting must proxy `/api` or configure the explicit backend URL.

```powershell
# From frontend
npm run build
# From backend
..\.venv\Scripts\python.exe -m pytest -q
```

## API

| Method | Endpoint | Result |
|---|---|---|
| GET | `/api/health` | Status and phase |
| POST | `/api/upload` | Multipart `file`; HTTP 201 with dataset ID and overview |
| GET | `/api/dataset/{dataset_id}/overview` | Metadata, types, unique counts |
| GET | `/api/dataset/{dataset_id}/preview` | First 20 rows |
| GET | `/api/dataset/{dataset_id}/quality` | Score, warnings, per-column checks |
| GET | `/api/dataset/{dataset_id}/statistics` | Per-column descriptive statistics |
| GET | `/api/dataset/{dataset_id}/correlations` | Pearson matrix |
| GET | `/api/dataset/{dataset_id}/visualizations` | Structured chart series |

Errors use `detail`: 413 oversized upload, 415 unsupported type, 422 invalid/empty/over-limit dataset, 404 missing dataset, 500 unexpected processing failure. Dataset IDs are validated UUIDs; filesystem paths are never returned.

## Quality score and interpretation

This is a transparent heuristic, **not an ML prediction**:

```text
M = missing cells / all cells
D = duplicate rows after their first occurrence / all rows
O = numeric outlier cells / non-missing numeric cells (0 when none exist)
score = round(100 × (1 − 0.50M − 0.30D − 0.20O), 1), clamped to 0–100
```

Outliers lie strictly below Q1 − 1.5×IQR or above Q3 + 1.5×IQR. When IQR is zero, values outside the equal fences still count. Counts represent cells, not distinct rows. Outliers are candidates for review, not necessarily errors. Constants (at most one distinct non-null value, including entirely empty columns) and high-cardinality categorical columns (>50 unique values and >90% uniqueness) generate warnings without score penalties. High scores do not guarantee useful data.

Statistics ignore null values. Standard deviation is the sample estimate (ddof=1). Undefined values and non-finite numbers serialize as null. Input infinities are treated as missing for analysis. No cleaning is written back to the uploaded dataset.

## Scope, limits, and reliability

- Maximum file size: 25 MiB (displayed as 25 MB). Maximum 100,000 data rows, 200 columns, and 2,000,000 cells.
- CSV must be UTF-8 (optional BOM), comma-delimited, with consistent row widths and unique non-empty headers. Standard pandas NA markers are recognized.
- XLSX uses the first worksheet. Expanded ZIP content is limited to 100 MiB; row/column bounds are checked during read-only iteration. Formulas are never executed; cached values are used, or missing values when no cache exists.
- Boolean columns use native booleans or true/false strings. Date strings are conservatively recognized when all non-null values begin with year-month-day and parse successfully; native Excel datetimes are supported. Ambiguous date strings remain categorical.
- Histograms: first 6 numeric columns, up to 20 bins. Categories: first 6 categorical/boolean columns, top 10 plus an Other aggregate. Nulls are excluded from these counts.
- Trends: first datetime/numeric pair, up to 60 time bins over the entire range, with means and the earliest observed date as the label. Scatter: first numeric pair, reproducible sample of up to 500 complete observations. Correlations: first 20 numeric columns, pairwise complete Pearson estimates, minimum 2 observations. Constant columns have undefined correlations.
- Files are processed in memory; only compact JSON analysis reports (including preview cells) are retained in `backend/uploads`. Original uploads are not retained. Reports have no automatic expiration: remove unneeded report JSON files locally. The local report folder is ignored by Git.
- This is a single-user local college prototype. There is no authentication, tenant isolation, rate limiting, or public-service deployment hardening. Run on loopback as documented. Multipart uploads may spool to OS temporary storage before application-level validation; public deployments need an ingress request-size cap.
- Missing or removed report IDs show a recoverable error with a new-upload action.

## Verification

13 automated tests cover both file formats, profiling, missing values, duplicates, IQR outliers, score arithmetic, descriptive statistics, correlations, all chart-data types, report reload, invalid files, limits, and safe names. Live HTTP checks also upload both sample formats through Vite's proxy and retrieve all six sections. The frontend production build passes.

## Phase 2 plan (not implemented)

Add `backend/agents/planner.py` and `backend/agents/analyst.py` above the existing service/tool boundary. The future flow is user → planner → tool selection → Python tools → observation → replanning → final insight. Tool functions accept DataFrames and explicit type maps and have no FastAPI dependencies, so adapters can expose them without rewriting statistical logic. LLM configuration, LangChain/LangGraph/CrewAI, RAG, natural-language querying, autonomous planning, and generated reports belong to Phase 2. The sidebar entries are disabled placeholders only.
