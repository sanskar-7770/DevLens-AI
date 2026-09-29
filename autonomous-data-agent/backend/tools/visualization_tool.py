import numpy as np
from .trend_tool import analyze_trends

def analyze_distribution(df, types):
    charts = []
    for c in [c for c, t in types.items() if t == "numerical"][:6]:
        s = df[c].dropna()
        if s.empty: continue
        counts, edges = np.histogram(s, bins=min(20, max(1, s.nunique())))
        charts.append({"kind": "histogram", "title": f"{c} distribution", "x_label": c, "y_label": "Rows", "data": [{"x": f"{edges[i]:.3g}–{edges[i+1]:.3g}", "y": int(v)} for i, v in enumerate(counts)]})
    return charts

def analyze_categories(df, types):
    charts = []
    for c in [c for c, t in types.items() if t in ("categorical", "boolean")][:6]:
        counts = df[c].dropna().astype(str).value_counts()
        data = [{"x": k, "y": int(v)} for k, v in counts.head(10).items()]
        if len(counts) > 10: data.append({"x": "Other (remaining categories)", "y": int(counts.iloc[10:].sum())})
        if data: charts.append({"kind": "bar", "title": f"{c} frequency", "x_label": c, "y_label": "Rows", "data": data})
    return charts

def generate_visualizations(df, types):
    charts = analyze_distribution(df, types) + analyze_categories(df, types) + analyze_trends(df, types)
    nums = [c for c, t in types.items() if t == "numerical"]
    if len(nums) >= 2:
        x, y = nums[:2]
        sample = df[[x, y]].dropna()
        sample = sample.sample(min(500, len(sample)), random_state=42)
        charts.append({"kind": "scatter", "title": f"{x} vs {y}", "x_label": x, "y_label": y, "data": [{"x": a, "y": b} for a, b in sample.itertuples(index=False, name=None)]})
    return charts
