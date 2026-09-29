def detect_outliers(df, types):
    result = []
    for c, kind in types.items():
        if kind != "numerical": continue
        s = df[c].dropna()
        q1, q3 = s.quantile([.25, .75])
        low, high = q1-1.5*(q3-q1), q3+1.5*(q3-q1)
        result.append({"column": c, "count": int(((s < low) | (s > high)).sum()), "lower_bound": low, "upper_bound": high})
    return result
