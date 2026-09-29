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
  return typeof e.response?.data?.detail === "string"
    ? e.response.data.detail
    : "Could not connect to the analysis server. Check that the backend is running and try again.";
}
