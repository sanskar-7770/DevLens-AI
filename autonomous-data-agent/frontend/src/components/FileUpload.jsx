import { useRef, useState } from "react";
import {
  UploadCloud,
  ArrowRight,
  FileSpreadsheet,
  LoaderCircle,
} from "lucide-react";
export default function FileUpload({ onUpload, busy, progress }) {
  const input = useRef();
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState("");
  function choose(file) {
    if (!file || busy) return;
    if (!/\.(csv|xlsx)$/i.test(file.name)) {
      setError("Choose a CSV or XLSX file.");
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setError("Maximum file size is 25 MB.");
      return;
    }
    setError("");
    onUpload(file);
  }
  async function sample() {
    try {
      const response = await fetch("/sample.csv");
      if (!response.ok) throw new Error();
      choose(
        new File([await response.blob()], "developer_activity.csv", {
          type: "text/csv",
        }),
      );
    } catch {
      setError("Could not load the sample dataset.");
    }
  }
  return (
    <>
      <div
        className={`upload-zone ${drag ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          choose(e.dataTransfer.files[0]);
        }}
      >
        <div className="upload-icon">
          {busy ? (
            <LoaderCircle className="spin" size={28} />
          ) : (
            <UploadCloud size={28} />
          )}
        </div>
        <h2>
          {busy
            ? progress < 100
              ? "Uploading your dataset…"
              : "Inspecting your dataset…"
            : "Your next insight starts here"}
        </h2>
        <p>
          {busy
            ? "Profiling columns, checking quality, and preparing charts."
            : "Drag and drop your dataset to uncover the story behind your numbers."}
        </p>
        <input
          ref={input}
          type="file"
          accept=".csv,.xlsx"
          hidden
          onChange={(e) => {
            choose(e.target.files[0]);
            e.target.value = "";
          }}
        />
        <button
          className="primary"
          disabled={busy}
          onClick={() => input.current.click()}
        >
          {busy ? "Processing" : "Browse Files"}
          {!busy && <ArrowRight size={16} />}
        </button>
        {!busy && (
          <button className="sample-button" onClick={sample}>
            Try a sample dataset
          </button>
        )}
        {busy ? (
          <div
            className="progress"
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <i style={{ width: `${progress}%` }} />
          </div>
        ) : (
          <div className="file-hint">
            <FileSpreadsheet size={14} /> CSV / XLSX <span>·</span> Maximum file
            size: 25 MB
          </div>
        )}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </>
  );
}
