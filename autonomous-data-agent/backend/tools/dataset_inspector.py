import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype, is_datetime64_any_dtype

def detect_column_types(df):
    types = {}
    for c in df:
        s = df[c]
        if is_bool_dtype(s): kind = "boolean"
        elif is_numeric_dtype(s): kind = "numerical"
        elif is_datetime64_any_dtype(s): kind = "datetime"
        else:
            v = s.dropna().astype(str)
            if len(v) and v.str.lower().isin(["true", "false"]).all(): kind = "boolean"
            elif len(v) and v.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").all() and pd.to_datetime(v, errors="coerce", utc=True).notna().all(): kind = "datetime"
            else: kind = "categorical"
        types[c] = kind
    return types

def detect_missing_values(df):
    return [{"column": c, "count": int(df[c].isna().sum()), "percentage": round(float(df[c].isna().mean()*100), 2)} for c in df]

def detect_duplicates(df):
    return int(df.duplicated().sum())

def inspect_dataset(df):
    types = detect_column_types(df)
    return {"rows": len(df), "columns": len(df.columns), "column_info": [{"name": c, "type": types[c], "dtype": str(df[c].dtype), "unique": int(df[c].nunique())} for c in df], "type_counts": {t: list(types.values()).count(t) for t in ["numerical", "categorical", "datetime", "boolean"]}}
