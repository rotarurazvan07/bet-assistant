import inspect
import re
from datetime import datetime

CURRENT_TIME = datetime.now()


def fractional_to_decimal_odds(fractional_odds):
    numerator, denominator = map(int, fractional_odds.split('/'))
    decimal_odds = numerator / denominator + 1
    return round(decimal_odds, 2)


def normalize_match_name(match_name):
    """
    Normalize match names to improve similarity checks.
    Replaces stray separators and fixes cases like 'vAtletico'.
    """
    # Handle stray single 'v' attached to words (e.g., "vAtletico")
    match_name = re.sub(r"\s[v](?=[A-Z])", " vs ", match_name)

    # Handle common separators like "v", "-", ":", "," and normalize to "vs"
    match_name = re.sub(r"\b\s?(vs|v|-|:|,|@)\s?\b", " vs ", match_name, flags=re.IGNORECASE)

    # Remove extra spaces and make lowercase
    match_name = " ".join(match_name.split()).lower()

    return match_name


def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))
