"""A new analysis primitive for questions about group averages."""
def compare_groups(df, group_column, value_column):
    grouped = df.groupby(group_column, dropna=True)[value_column].agg(["count", "mean", "median"])
    grouped = grouped[grouped["count"] > 0].sort_values("mean", ascending=False)
    return {"group_column": group_column, "value_column": value_column,
            "total_groups": len(grouped), "groups": [
                {"group": str(k), "count": int(v["count"]), "mean": v["mean"], "median": v["median"]}
                for k, v in grouped.head(20).iterrows()],
            "note": "Top 20 groups by mean; missing group/value cells excluded. Association does not establish causation."}
