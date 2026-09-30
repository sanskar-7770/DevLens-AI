"""Only these validated, read-only callables are accessible to the agent."""
from dataclasses import dataclass
from typing import Callable
from models.agent import ToolArguments
from tools.dataset_inspector import inspect_dataset, detect_missing_values
from tools.statistics_tool import generate_statistics
from tools.correlation_tool import calculate_correlation
from tools.outlier_tool import detect_outliers
from tools.trend_tool import analyze_trends
from tools.visualization_tool import analyze_distribution, analyze_categories, generate_visualizations
from tools.group_tool import compare_groups
from utils.serialization import clean
ML_TOOLS = {"ml_suitability", "regression", "classification", "clustering", "anomaly_detection", "feature_importance", "model_evaluation"}

class ToolInputError(Exception):
    pass

@dataclass(frozen=True)
class ToolSpec:
    description: str
    minimum: int
    maximum: int
    kinds: tuple
    function: Callable


def inspection(df, types, args):
    return {"result": {**inspect_dataset(df), "missing": detect_missing_values(df)}}


def column_info(df, types, args):
    return {"result": {**inspect_dataset(df[args.columns]), "missing": detect_missing_values(df[args.columns])}}


def statistics(df, types, args):
    return {"result": generate_statistics(df[args.columns], {c: types[c] for c in args.columns})}


def outliers(df, types, args):
    return {"result": detect_outliers(df[args.columns], {c: types[c] for c in args.columns})}


def correlation(df, types, args):
    target = args.columns[0]
    others = args.columns[1:] or [c for c, t in types.items() if t == "numerical" and c != target]
    if not others:
        raise ToolInputError("Correlation needs at least two numerical columns.")
    pairs = []
    for start in range(0, len(others), 19):
        columns = [target] + others[start:start+19]
        matrix = calculate_correlation(df[columns], {c: "numerical" for c in columns})
        for index, other in enumerate(columns[1:], 1):
            value = clean(matrix["matrix"][0][index])
            pairs.append({"column": other, "r": value, "paired_rows": int(df[[target, other]].dropna().shape[0])})
    pairs.sort(key=lambda p: abs(p["r"]) if p["r"] is not None else -1, reverse=True)
    return {"result": {"target": target, "method": "Pearson", "relationships": pairs[:20], "compared_columns": len(others), "note": "Ranked by absolute Pearson r; pairwise non-null observations. Correlation is not causation."}}


def distribution(df, types, args):
    charts = analyze_distribution(df[args.columns], {c: types[c] for c in args.columns})
    return {"result": {"column": args.columns[0], "bins": charts[0]["data"] if charts else []}, "charts": charts}


def categories(df, types, args):
    charts = analyze_categories(df[args.columns], {c: types[c] for c in args.columns})
    return {"result": {"column": args.columns[0], "frequencies": charts[0]["data"] if charts else []}, "charts": charts}


def trend(df, types, args):
    charts = analyze_trends(df[args.columns], {c: types[c] for c in args.columns})
    return {"result": {"date_column": args.columns[0], "value_column": args.columns[1], "aggregation": "mean per time bin", "points": charts[0]["data"] if charts else []}, "charts": charts}


def grouped(df, types, args):
    result = compare_groups(df, *args.columns)
    chart = {"kind": "bar", "title": f"Mean {args.columns[1]} by {args.columns[0]}", "x_label": args.columns[0], "y_label": f"Mean {args.columns[1]}", "data": [{"x": g["group"], "y": g["mean"]} for g in result["groups"]]}
    return {"result": result, "charts": [chart] if chart["data"] else []}


def visualization(df, types, args):
    selected = df[args.columns]
    selected_types = {c: types[c] for c in args.columns}
    if args.chart_type == "heatmap":
        matrix = calculate_correlation(selected, selected_types)
        return {"result": matrix, "charts": [{"kind": "heatmap", "correlations": matrix}]}
    charts = [c for c in generate_visualizations(selected, selected_types) if c["kind"] == args.chart_type]
    # Chart samples are for React only. The provider receives aggregate facts instead.
    result = {"kind": args.chart_type, "columns": args.columns, "chart_count": len(charts)}
    if args.chart_type == "scatter":
        result.update(correlation(df, types, args)["result"])
    return {"result": result, "charts": charts}


TOOLS = {
    "inspect_dataset": ToolSpec("Dataset overview and missing counts. columns=[]", 0, 0, (), inspection),
    "column_info": ToolSpec("Types, uniqueness and missing counts for selected columns", 1, 20, (), column_info),
    "statistics": ToolSpec("Exact descriptive statistics or categorical mode", 1, 6, (), statistics),
    "correlation": ToolSpec("First column is target; one column compares target with ALL other numeric columns; additional columns restrict comparison. Ranked absolute Pearson associations", 1, 20, ("numerical",), correlation),
    "outliers": ToolSpec("IQR potential outlier cell counts and bounds", 1, 6, ("numerical",), outliers),
    "distribution": ToolSpec("Histogram for one numerical column", 1, 1, ("numerical",), distribution),
    "categories": ToolSpec("Category frequencies, top 10 plus remaining aggregate", 1, 1, ("categorical", "boolean"), categories),
    "trend": ToolSpec("Time-binned means; columns=[datetime, numerical]", 2, 2, (), trend),
    "group_comparison": ToolSpec("Rank group means; columns=[categorical/boolean, numerical]", 2, 2, (), grouped),
    "visualization": ToolSpec("Structured chart: histogram(numeric), bar(category), line(date,numeric), scatter(numeric,numeric), heatmap(2-20 numeric)", 1, 20, (), visualization),
}


def ml_callable(name):
    def call(df, types, args):
        try:
            from tools.ml.service import run_ml
        except ImportError:
            raise ToolInputError("Prediction tools need the backend ML dependencies. Install backend/requirements.txt and restart the backend.") from None
        return {"result": run_ml(name, df, types, args.columns)}
    return call

for _name, _description, _minimum in [
    ('ml_suitability', 'Check whether a target can be predicted. columns=[target]; does not train.', 1),
    ('regression', 'Predict a Number: train Linear Regression and Random Forest, compare with mean baseline on separate test rows. columns=[numeric target, optional predictors]. Includes suitability, preparation, evaluation, important factors and charts.', 1),
    ('classification', 'Predict an Outcome: train Logistic Regression and Random Forest, compare with most-common baseline. columns=[categorical/boolean or binary target, optional predictors]. Includes all preparation/evaluation/factors.', 1),
    ('clustering', 'Find Similar Groups using multiple inputs. columns=[] automatically selects safe inputs; or select inputs. Groups describe records, not people or their performance.', 0),
    ('anomaly_detection', 'Find Unusual Records using multiple inputs together. columns=[] for automatic safe inputs; use outliers for a single numeric column.', 0),
    ('feature_importance', 'What Matters Most for a prediction; columns=[target, optional predictors]. Reuses the current experiment when available, otherwise evaluates a prediction first.', 1),
    ('model_evaluation', 'How reliable is a prediction? columns=[target, optional predictors]. Reuses current experiment or runs a bounded comparison with baseline.', 1),
]:
    TOOLS[_name] = ToolSpec(_description, _minimum, 20, (), ml_callable(_name))


def catalog():
    return [{"name": name, "description": spec.description, "parameters": ToolArguments.model_json_schema(), "min_columns": spec.minimum, "max_columns": spec.maximum} for name, spec in TOOLS.items()]


def validate(name, args, types):
    if name not in TOOLS:
        raise ToolInputError("Unknown analysis tool. Only registered tools are allowed.")
    spec = TOOLS[name]
    if len(set(args.columns)) != len(args.columns):
        raise ToolInputError("Select distinct columns.")
    if not spec.minimum <= len(args.columns) <= spec.maximum:
        raise ToolInputError(f"{name} needs {spec.minimum} to {spec.maximum} columns.")
    if any(c not in types for c in args.columns):
        raise ToolInputError("An unknown column was requested. Use exact names from dataset metadata.")
    if spec.kinds and any(types[c] not in spec.kinds for c in args.columns):
        raise ToolInputError(f"{name} requires columns of type: {', '.join(spec.kinds)}.")
    if name != "visualization" and args.chart_type is not None:
        raise ToolInputError("chart_type must be null except for visualization.")
    if name in ("trend", "group_comparison"):
        required = ("datetime",) if name == "trend" else ("categorical", "boolean")
        if types[args.columns[0]] not in required or types[args.columns[1]] != "numerical":
            raise ToolInputError("Trend needs a usable datetime and numeric column." if name == "trend" else "Group comparison needs a categorical/boolean column followed by a numeric column.")
    if name == "visualization":
        chart = args.chart_type
        kinds = [types[c] for c in args.columns]
        valid = ((chart == "histogram" and kinds == ["numerical"]) or
                 (chart == "bar" and len(kinds) == 1 and kinds[0] in ("categorical", "boolean")) or
                 (chart == "line" and kinds == ["datetime", "numerical"]) or
                 (chart == "scatter" and kinds == ["numerical", "numerical"]) or
                 (chart == "heatmap" and len(kinds) >= 2 and all(k == "numerical" for k in kinds)))
        if not valid:
            raise ToolInputError("Chart type and column types do not match the visualization schema.")


def execute(name, args, df, types, cache=None):
    validate(name, args, types)
    if name in ML_TOOLS and cache is not None:
        from tools.ml.data_preparation_tool import infer_task
        task = infer_task(df, types, args.columns[0]) if name in ('feature_importance','model_evaluation') else name
        key = (task, tuple(args.columns))
        if key in cache: return cache[key]
        if len(cache) >= 3: raise ToolInputError("This analysis has reached its prediction-experiment limit. Ask a narrower follow-up question.")
        result = clean(TOOLS[name].function(df, types, args))
        cache[key] = result
        return result
    return clean(TOOLS[name].function(df, types, args))
