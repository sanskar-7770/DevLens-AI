"""Facts displayed to the user are generated from Python outputs, never invented by an LLM."""
import json
from models.agent import Evidence


def facts(tool, result, iteration):
    lines = []
    if isinstance(result, dict) and result.get("kind") == "ml":
        lines = result["facts"] + result.get("warnings", [])[:3]
    elif tool in ("inspect_dataset", "column_info"):
        lines.append(f"Dataset selection: {result['rows']} rows, {result['columns']} columns.")
        missing = [r for r in result['missing'] if r['count']]
        lines += [f"{r['column']}: {r['count']} missing cells ({r['percentage']}%)." for r in missing]
        if not missing: lines.append("No missing cells in the selected columns.")
    elif tool == "statistics":
        for r in result:
            if r['type'] == 'numerical':
                lines.append(f"{r['column']}: mean={r['mean']}, median={r['median']}, min={r['min']}, max={r['max']}, sample standard deviation={r['std']}; {r['count']} non-null values.")
            else:
                lines.append(f"{r['column']}: {r['unique']} unique non-null values; most frequent={r['top']!r}, frequency={r['frequency']}.")
    elif tool == "outliers":
        lines += [f"{r['column']}: {r['count']} potential IQR outliers; lower fence={r['lower_bound']}, upper fence={r['upper_bound']}." for r in result]
    elif tool == "correlation" or (tool == "visualization" and 'relationships' in result):
        for r in result['relationships'][:8]:
            lines.append(f"{result['target']} vs {r['column']}: Pearson r={r['r']}, paired rows={r['paired_rows']}. Association does not establish causation.")
    elif tool == "group_comparison":
        for r in result['groups'][:8]:
            lines.append(f"{result['group_column']}={r['group']!r}: mean {result['value_column']}={r['mean']}, median={r['median']}, non-null count={r['count']}.")
        if not result['groups']: lines.append("No complete group/value observations are available.")
    elif tool == "trend":
        points = result['points']
        if len(points) >= 2:
            lines.append(f"{result['value_column']}: first time-bin mean={points[0]['y']} at {points[0]['x']}; last time-bin mean={points[-1]['y']} at {points[-1]['x']}; {len(points)} bins. Endpoints alone do not establish a sustained trend.")
        else: lines.append("Fewer than two populated time bins; a change over time cannot be established.")
    elif tool in ("distribution", "categories"):
        values = result.get('bins', result.get('frequencies', []))
        lines.append(f"{result['column']}: {sum(v['y'] for v in values)} non-null observations across {len(values)} displayed {'bins' if tool == 'distribution' else 'categories'}.")
    elif tool == "visualization":
        lines.append(f"Generated {result.get('chart_count', 1)} {result.get('kind', 'heatmap')} chart(s) from real dataset values.")
    return [Evidence(id=f"E{iteration}.{i+1}", tool=tool, text=line) for i, line in enumerate(lines[:30])]


def provider_result(output):
    # Never send scatter points or raw preview rows to the provider.
    result = output['result']
    if isinstance(result, dict) and result.get('kind') == 'ml':
        return {k: result[k] for k in ('task','target','suitable','summary','takeaway','reliability','warnings','factors','facts','suggestions')}
    return result
