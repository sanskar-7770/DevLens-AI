import axios from "axios";
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 120000,
});
export async function uploadDataset(file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  return (
    await api.post("/upload", form, {
      onUploadProgress: (e) =>
        onProgress(Math.round((e.loaded / (e.total || e.loaded)) * 100)),
    })
  ).data;
}
export async function loadDataset(id) {
  const sections = [
    "overview",
    "quality",
    "preview",
    "statistics",
    "visualizations",
    "correlations",
  ];
  const values = await Promise.all(
    sections.map((s) =>
      api.get(`/dataset/${encodeURIComponent(id)}/${s}`).then((r) => r.data),
    ),
  );
  return Object.fromEntries(sections.map((s, i) => [s, values[i]]));
}
export function errorMessage(e) {
  if (typeof e.response?.data?.detail === "string")
    return e.response.data.detail;
  if (e.response?.status === 422)
    return "Enter a valid analytical question (1–2000 characters) and select an uploaded dataset.";
  if (e.response?.status === 404)
    return "Dataset not found. Upload your file again.";
  return typeof e.response?.data?.detail === "string"
    ? e.response.data.detail
    : "Could not connect to the analysis server. Check that the backend is running and try again.";
}

export async function analyzeQuestion(datasetId, query, sessionId) {
  return (
    await api.post(
      "/agent/analyze",
      { dataset_id: datasetId, query, session_id: sessionId || null },
      { timeout: 170000 },
    )
  ).data;
}
export async function agentStatus() {
  return (await api.get("/agent/status")).data;
}

export async function analyzeML(datasetId, tool, columns, sessionId) {
  return (
    await api.post(
      "/ml/analyze",
      { dataset_id: datasetId, tool, columns, session_id: sessionId || null },
      { timeout: 170000 },
    )
  ).data;
}
