def calculate_correlation(df, types):
    columns = [c for c, t in types.items() if t == "numerical"][:20]
    matrix = df[columns].corr(min_periods=2)
    return {"columns": columns, "matrix": matrix.values.tolist(), "method": "Pearson", "limit": 20}
