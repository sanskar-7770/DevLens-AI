export const fmt = (v) =>
  v == null
    ? "—"
    : typeof v === "number"
      ? new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(v)
      : String(v);
