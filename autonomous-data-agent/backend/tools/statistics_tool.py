def generate_statistics(df, types):
    result = []
    for c, kind in types.items():
        s = df[c].dropna()
        row = {"column": c, "type": kind, "count": len(s), "unique": int(s.nunique())}
        if kind == "numerical":
            row.update({"mean": s.mean(), "median": s.median(), "min": s.min(), "max": s.max(), "std": s.std(), "p25": s.quantile(.25), "p50": s.quantile(.5), "p75": s.quantile(.75)})
        else:
            counts = s.astype(str).value_counts()
            row.update({"top": str(counts.index[0]) if len(counts) else None, "frequency": int(counts.iloc[0]) if len(counts) else 0})
        result.append(row)
    return result

calculate_statistics = generate_statistics
