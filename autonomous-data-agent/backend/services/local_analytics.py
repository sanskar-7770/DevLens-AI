"""Conservative local question grammar. Unsupported/ambiguous requests go to Gemini."""
import re
import time
import json
from models.agent import AnalyzeResponse, Evidence, Activity
from utils.serialization import clean


def normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def answer_local(request, df, report, session_id):
    started = time.monotonic()
    q = normalize(request.query)
    # Do not silently ignore filters, grouping, comparisons or compound requests.
    if re.search(r"\b(where|when|after|before|between|among|per|by|versus|vs|and|or|excluding|only|if|than|for)\b", q):
        return None
    columns = [c for c in df.columns if normalize(c) and re.search(r"(?<!\w)" + re.escape(normalize(c)) + r"(?!\w)", q)]
    if re.search(r"^which developer has (?:the )?(?:most|least|highest|lowest) ", q):
        columns = [c for c in columns if normalize(c) not in ("developer", "developer name")]
    facts = []
    status = "completed"
    operation = None
    selected = columns
    if re.fullmatch(r"(?:how many|number of|count of|count|what is the number of) (?:data )?rows(?: (?:are )?in (?:this |the )?dataset)?", q):
        facts = [f"The dataset has {len(df)} rows."]; operation = "row_count"
    elif re.fullmatch(r"(?:how many|number of|count of|count|what is the number of) columns(?: (?:are )?in (?:this |the )?dataset)?", q):
        facts = [f"The dataset has {len(df.columns)} columns."]; operation = "column_count"
    elif re.fullmatch(r"(?:list |show |what are (?:the )?)?(?:dataset )?column names|(?:list|show) (?:the )?columns", q):
        facts = ["Columns: " + ", ".join(map(str, df.columns))]; operation = "column_names"
    elif re.fullmatch(r"(?:which columns (?:have|contain)|show|list|count|how many)? ?missing values(?: (?:in )?(?:this |the )?dataset)?", q):
        facts = [f"{c}: {int(df[c].isna().sum())} missing values." for c in df.columns if df[c].isna().any()] or ["No columns contain missing values."]
        operation = "missing_values"
    elif re.fullmatch(r"(?:summarize|summarise|give me an overview of|overview of|overview)(?: (?:this|the))?(?: dataset)?", q):
        facts = [f"The dataset has {len(df)} rows and {len(df.columns)} columns.", "Columns: " + ", ".join(map(str, df.columns)), f"Missing cells: {int(df.isna().sum().sum())}. Duplicate rows: {int(df.duplicated().sum())}."]
        operation = "dataset_summary"
    elif len(columns) == 1:
        c = columns[0]
        # Remove the exact metric name, then validate every remaining word.
        rest = re.sub(r"(?<!\w)" + re.escape(normalize(c)) + r"(?!\w)", "", q)
        allowed = set("what is are the a an of in this dataset column number values value average mean minimum min maximum max sum total count non null unique distinct basic statistics stats show give me highest lowest record row records rows which developer has most least commits please".split())
        if any(w not in allowed for w in rest.split()):
            return None
        s = df[c].dropna()
        ops = []
        for name, pattern in [("mean",r"\b(average|mean)\b"),("min",r"\b(minimum|min|lowest|least)\b"),("max",r"\b(maximum|max|highest|most)\b"),("sum",r"\b(sum|total)\b"),("unique",r"\b(unique|distinct)\b"),("count",r"\bcount\b"),("statistics",r"\b(statistics|stats)\b")]:
            if re.search(pattern, rest): ops.append(name)
        if len(ops) != 1: return None
        operation = ops[0]
        numeric = report['overview']['column_info']
        is_numeric = any(i['name']==c and i['type']=='numerical' for i in numeric)
        if operation in ('mean','min','max','sum') and not is_numeric:
            facts = [f"{c} is not a numerical column. Choose a numerical column for {operation}."]; status = "insufficient"
        elif operation == 'unique':
            facts = [f"{c} has {s.nunique()} distinct non-missing values.", "Distinct values (first 20, original order): " + json.dumps(clean(s.drop_duplicates().head(20).tolist()), ensure_ascii=False)]
        elif operation == 'count':
            facts = [f"{c} has {len(s)} non-missing values; {len(df)-len(s)} are missing."]
        elif operation == 'statistics':
            if is_numeric:
                facts = [f"{c}: " + json.dumps(clean({'count':len(s),'mean':s.mean(),'min':s.min(),'max':s.max(),'sum':s.sum(min_count=1),'median':s.median(),'std':s.std()}))]
            else:
                facts = [f"{c}: {len(s)} non-missing values, {s.nunique()} distinct values."]
        elif s.empty:
            facts = [f"{c} has no non-missing numeric values; {operation} is unavailable."]; status = "insufficient"
        else:
            value = clean(getattr(s, operation)())
            facts = [f"{operation}({c}) = {value}. Missing values are excluded."]
            if operation in ('min','max') and re.search(r"\b(record|row|records|rows|which|developer)\b", rest):
                matches = df.loc[df[c].eq(value)]
                identities = [x for x in df.columns if normalize(x) in ('developer','developer name','name','employee','employee name')]
                if 'developer' in rest.split() and not identities:
                    facts.append("There is no developer identity column in this dataset, so I cannot identify a developer. The extreme metric value above is verified.")
                    status = "insufficient"
                else:
                    positions = [i+1 for i, yes in enumerate(df[c].eq(value)) if yes]
                    facts.append(f"{len(matches)} tied record(s). Data row positions (1-based, excluding header; first 10): {positions[:10]}.")
                    if identities:
                        facts.append("Matching identities (first 10): " + json.dumps(clean(matches[identities].head(10).to_dict('records')), ensure_ascii=False))
    else:
        return None
    if not operation: return None
    evidence = [Evidence(id=f"L.{i+1}",tool="local_analytics",text=t) for i,t in enumerate(facts)]
    result = AnalyzeResponse(source="local", model=None, status=status,dataset_id=str(request.dataset_id),session_id=session_id,query=request.query,
        plan=[],activities=[Activity(action="Calculated locally with Pandas",status="completed",tool="local_analytics",parameters={"operation":operation,"columns":selected})],
        tools_used=["local_analytics"],iterations=0,execution_seconds=round(time.monotonic()-started,3),answer=facts[0],findings=facts,evidence=evidence,
        potential_explanation="",suggested_next_analysis=[],charts=[],errors=[])
    turn = {"query":request.query,"answer":result.answer,"calls":[{"tool":"local_analytics","arguments":{"columns":selected,"operation":operation}}],"evidence":[e.model_dump() for e in evidence],"status":status}
    return result, turn
