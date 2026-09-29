import math
import numpy as np
import pandas as pd
from datetime import datetime, date

def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, np.generic): return clean(value.item())
    if value is None or value is pd.NA or value is pd.NaT: return None
    if isinstance(value, float) and not math.isfinite(value): return None
    if isinstance(value, (datetime, date)): return value.isoformat()
    return value
