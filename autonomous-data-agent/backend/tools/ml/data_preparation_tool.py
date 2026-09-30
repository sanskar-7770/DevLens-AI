"""Train-only screening and preprocessing. Original DataFrames are never mutated."""
import re
import math
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split

MAX_ROWS = 3000
MAX_FEATURES = 20
MIN_SUPERVISED = 40

class Unsuitable(ValueError):
    pass


def friendly(name):
    return re.sub(r"[_-]+", " ", str(name)).strip().title()


def infer_task(df, types, target):
    if target not in df: raise Unsuitable("That outcome is not in this dataset. Choose a column from the list.")
    return "classification" if types[target] in ("categorical", "boolean") or (types[target] == "numerical" and df[target].dropna().nunique() == 2) else "regression"


def prepare(df, types, task, columns):
    supervised = task in ("regression", "classification")
    target = columns[0] if supervised and columns else None
    if supervised and target not in df:
        raise Unsuitable("Choose an existing column to predict. The requested outcome is not in this dataset.")
    if supervised and re.search(r"(^|_)(id|uuid|index|recordid|identifier)($|_)", target.lower()):
        raise Unsuitable("An identifier is a label for a record, not a meaningful outcome to predict. Choose another column.")
    work = df.copy(deep=True)
    warnings = []
    if supervised:
        work = work.loc[work[target].notna()]
        if len(work) < len(df): warnings.append(f"{len(df)-len(work)} records without a known outcome were left out.")
        before = len(work); work = work.drop_duplicates()
        if before != len(work): warnings.append(f"{before-len(work)} exact duplicate records were removed from this experiment to avoid testing copies of training records.")
    if len(work) > MAX_ROWS:
        work = work.sample(MAX_ROWS, random_state=42).sort_index()
        warnings.append(f"This analysis used a reproducible random sample of {MAX_ROWS} records to keep processing fast; rare patterns may be missed.")
    minimum = MIN_SUPERVISED if supervised else 20
    if len(work) < minimum:
        raise Unsuitable(f"There are only {len(work)} usable records. Add at least {minimum} usable records before trying this analysis.")
    chosen = list(columns[1:] if supervised else columns) or [c for c in work if c != target]
    if any(c not in work for c in chosen): raise Unsuitable("One selected column is missing. Choose columns from this dataset.")
    if target in chosen: raise Unsuitable("The outcome cannot also be an input to its own prediction.")
    y = None
    if supervised:
        y = work[target].copy()
        if task == "regression":
            if types[target] != "numerical": raise Unsuitable("Predict a Number needs a numeric outcome. Try Predict an Outcome for categories.")
            y = pd.to_numeric(y, errors="coerce")
            if y.nunique() < 3: raise Unsuitable("This outcome has too little variation to test a number prediction. Try Predict an Outcome for two outcomes.")
        else:
            if types[target] == "datetime": raise Unsuitable("Choose an outcome category, not a date.")
            y = y.astype(str)
            counts = y.value_counts()
            if len(counts) < 2: raise Unsuitable("This dataset contains only one outcome. Add records showing at least two different outcomes.")
            if len(counts) > 20 or counts.min() < 5: raise Unsuitable("Each outcome needs at least five examples, with no more than twenty different outcomes. Add examples of the less common outcomes.")
            if counts.max()/len(y) > .7: warnings.append("Most records belong to one outcome, so a high overall accuracy can be misleading. Check how often each outcome was identified.")
    chronological = False
    date_columns = [c for c in work if types[c] == "datetime"]
    if supervised and date_columns:
        dates = pd.to_datetime(work[date_columns[0]], errors="coerce", utc=True)
        if dates.notna().all() and dates.nunique() >= 5:
            # Keep equal timestamps on one side of the boundary.
            ordered = dates.sort_values(kind="stable")
            cutoff = ordered.iloc[min(len(ordered)-1, int(.8*len(ordered)))]
            train_idx = work.index[dates < cutoff].to_numpy()
            test_idx = work.index[dates >= cutoff].to_numpy()
            chronological = True
            warnings.append(f"Earlier records were used to learn and later records to check predictions, using {friendly(date_columns[0])}. This tests later records, not a future forecast.")
    if supervised and not chronological:
        if task == "classification" and math.ceil(.2*len(work)) < y.nunique(): raise Unsuitable("There are too many outcomes for a useful test set. Add more examples.")
        train_idx, test_idx = train_test_split(work.index.to_numpy(),test_size=.2,random_state=42,stratify=y if task == "classification" else None)
    elif not supervised:
        train_idx, test_idx = work.index.to_numpy(), np.array([],dtype=int)
    if supervised:
        if len(train_idx) < 20 or len(test_idx) < 5: raise Unsuitable("The time split leaves too few records to learn or test. Add more records across different dates.")
        if task == "classification" and (y.loc[train_idx].nunique()<2 or y.loc[train_idx].value_counts().min()<3 or set(y.loc[test_idx])-set(y.loc[train_idx])):
            raise Unsuitable("Some outcomes are not represented in the earlier training records. Add historical examples of every outcome.")
        if task == "regression" and y.loc[train_idx].nunique()<2: raise Unsuitable("The training records contain only one value for the outcome. More varied historical data is needed.")
    training = work.loc[train_idx]
    excluded = {}
    kept = []
    for c in chosen:
        values = training[c]
        token = c.lower().replace('-', '_')
        observed = values.dropna()
        reason = None
        if re.search(r"(^|_)(id|uuid|index|recordid|identifier)($|_)",token) or (len(observed) and observed.astype(str).str.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}").mean()>.8): reason = "identifier"
        elif values.isna().mean() > .8: reason = "mostly missing"
        elif values.nunique() < 2: reason = "no useful variation"
        elif types[c] in ('categorical','boolean') and (values.nunique()>30 or values.nunique()/len(values)>.8): reason = "too many distinct labels"
        elif supervised:
            yt = y.loc[train_idx]
            both = values.notna() & yt.notna()
            if values.loc[both].astype(str).equals(yt.loc[both].astype(str)): reason = "copies the outcome"
            elif types[c] == 'numerical' and task == 'regression' and both.sum() >= 10:
                corr = pd.to_numeric(values.loc[both]).corr(yt.loc[both])
                if pd.notna(corr) and abs(corr)>=.995: reason = "almost exactly mirrors the outcome"
            if reason is None and task == 'classification' and values.nunique() <= 20 and both.sum() >= 20:
                mapping = pd.DataFrame({'input': values.loc[both].astype(str), 'outcome': yt.loc[both].astype(str)})
                if mapping.groupby('input')['outcome'].nunique().max() == 1:
                    reason = "perfectly reveals the outcome in training records"
            if reason is None and (token.startswith(target.lower()+'_') or token.endswith('_'+target.lower())): reason = "may be derived from the outcome"
        if reason: excluded[c] = reason
        else: kept.append(c)
    if len(kept)>MAX_FEATURES:
        for c in kept[MAX_FEATURES:]: excluded[c]='feature processing limit'
        kept=kept[:MAX_FEATURES]
    if not kept: raise Unsuitable("No usable inputs remain after excluding identifiers, empty fields, constants and possible outcome copies. Add independent information known before the outcome.")
    if excluded: warnings.append("Some inputs were excluded: " + "; ".join(f"{friendly(c)} ({r})" for c,r in list(excluded.items())[:8]) + (f"; and {len(excluded)-8} more" if len(excluded)>8 else "") + ".")
    X = pd.DataFrame(index=work.index)
    origins = {}
    for number,c in enumerate(kept):
        if types[c] == 'datetime':
            date = pd.to_datetime(work[c],errors='coerce',utc=True)
            for part in ('year','month','day','dayofweek'):
                name=f'f{number}_{part}'; X[name]=getattr(date.dt,part).astype(float); origins[name]=c
        elif types[c] == 'numerical':
            name=f'f{number}';X[name]=pd.to_numeric(work[c],errors='coerce').astype(float);origins[name]=c
        else:
            name=f'f{number}';X[name]=work[c].map(lambda v: str(v).lower() if pd.notna(v) else np.nan).astype(object);origins[name]=c
    X = X.replace([np.inf,-np.inf],np.nan)
    if supervised:
        warnings.append("Use only information available before the outcome. Automatic checks cannot detect every form of information leakage.")
        if len(work)<200: warnings.append("This dataset is small. More independent records are needed before relying on these predictions.")
    return dict(work=work,X=X,y=y,target=target,features=kept,origins=origins,train_idx=train_idx,test_idx=test_idx,split='chronological' if chronological else 'stratified random' if task=='classification' else 'random',warnings=warnings,excluded=excluded,original_rows=len(df))


def preprocessor(X):
    numbers=X.select_dtypes(include='number').columns.tolist()
    categories=[c for c in X if c not in numbers]
    return ColumnTransformer([
        ('numeric',Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True)),('scale',StandardScaler())]),numbers),
        ('category',Pipeline([('impute',SimpleImputer(strategy='most_frequent',keep_empty_features=True)),('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False,max_categories=30))]),categories),
    ],remainder='drop',verbose_feature_names_out=True)
