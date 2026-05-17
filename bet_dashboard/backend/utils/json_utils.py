import math
from typing import Any


def sanitize_floats(val: Any) -> Any:
    """
    Recursively clean dictionary/list collections and float values to ensure
    they are JSON-compliant (i.e. mapping float('nan') or float('inf') to None).
    """
    if isinstance(val, dict):
        return {k: sanitize_floats(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_floats(v) for v in val]
    elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val
