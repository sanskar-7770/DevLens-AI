from tools.dataset_inspector import inspect_dataset, detect_column_types, detect_missing_values, detect_duplicates
from tools.outlier_tool import detect_outliers
from tools.statistics_tool import generate_statistics
from tools.correlation_tool import calculate_correlation
from tools.visualization_tool import generate_visualizations
from utils.serialization import clean

def analyze(df):
    types = detect_column_types(df)
    missing = detect_missing_values(df)
    duplicates = detect_duplicates(df)
    outliers = detect_outliers(df, types)
    missing_fraction = sum(r["count"] for r in missing) / df.size
    numeric_cells = sum(int(df[c].notna().sum()) for c, t in types.items() if t == "numerical")
    outlier_count = sum(r["count"] for r in outliers)
    constants = [c for c in df if df[c].nunique() <= 1]
    high = [c for c, t in types.items() if t == "categorical" and df[c].nunique() > 50 and df[c].nunique()/len(df) > .9]
    # Transparent heuristic: completeness 50%, duplicates 30%, IQR outliers 20%.
    score = round(max(0, 100 * (1 - .5*missing_fraction - .3*duplicates/len(df) - .2*outlier_count/max(1, numeric_cells))), 1)
    warnings = [f"Column {r['column']} contains {r['percentage']}% missing values." for r in missing if r['count']]
    warnings += [f"Column {r['column']} contains {r['count']} potential outliers." for r in outliers if r['count']]
    warnings += [f"Column {c} is constant or entirely empty." for c in constants]
    warnings += [f"Column {c} has high cardinality; it may be an identifier." for c in high]
    if duplicates: warnings.append(f"{duplicates} duplicate rows detected (excluding first occurrences).")
    return clean({"overview": inspect_dataset(df), "preview": {"columns": list(df.columns), "rows": df.head(20).to_dict(orient="records")}, "quality": {"score": score, "missing_percentage": round(missing_fraction*100, 2), "missing": missing, "duplicates": duplicates, "outlier_count": outlier_count, "outliers": outliers, "constant_columns": constants, "high_cardinality_columns": high, "warnings": warnings}, "statistics": generate_statistics(df, types), "correlations": calculate_correlation(df, types), "visualizations": generate_visualizations(df, types)})
