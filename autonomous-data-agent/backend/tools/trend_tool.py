import pandas as pd

def analyze_trends(df, types):
    dates = [c for c, t in types.items() if t == "datetime"]
    nums = [c for c, t in types.items() if t == "numerical"]
    if not dates or not nums: return []
    date, value = dates[0], nums[0]
    temp = pd.DataFrame({"date": pd.to_datetime(df[date], errors="coerce", utc=True), "value": df[value]}).dropna()
    if temp.empty: return []
    temp["bin"] = pd.cut(temp.date.astype("int64"), bins=min(60, temp.date.nunique()), duplicates="drop")
    grouped = temp.groupby("bin", observed=True).agg(date=("date", "min"), value=("value", "mean"))
    return [{"kind": "line", "title": f"{value} over time", "x_label": date, "y_label": f"Mean {value}", "data": [{"x": r.date.isoformat()[:10], "y": r.value} for r in grouped.itertuples()]}]
