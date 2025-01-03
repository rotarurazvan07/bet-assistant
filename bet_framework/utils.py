import inspect
import math
import re
from datetime import datetime

import unicodedata
from rapidfuzz import fuzz

CURRENT_TIME = datetime.now()
HOME = "home"
DRAW = "draw"
AWAY = "away"
# X2 & -1-3
def get_value_bet(score):
    value_bet = ""
    if score.home >= score.away:
        value_bet += "1X & "
    else:
        value_bet += "X2 & "
    total_goals = score.home + score.away
    if total_goals >= 3.5:
        value_bet += "2+"
    else:
        value_bet += str(max(0, int(math.floor(total_goals - 2 + 0.5)))) + "-" + str(max(4, int(math.floor(total_goals + 2 + 0.5))))
    return value_bet

def get_fav_dc(match):
    # check which side is predicted:
    if match.statistics.scores.home > match.statistics.scores.away:
        # Home favorite
        return match.statistics.probabilities.draw + match.statistics.probabilities.home
    elif match.statistics.scores.home < match.statistics.scores.away:
        # Away favorite
        return match.statistics.probabilities.draw + match.statistics.probabilities.away
    elif match.statistics.scores.home == match.statistics.scores.away:
        # in case of draw, return draw chance + whichever has more chances
        return match.statistics.probabilities.draw + max(match.statistics.probabilities.home, match.statistics.probabilities.away)

def analyze_betting_predictions(predictions, threshold=66):
    total_predictions = len(predictions)
    if total_predictions < 3:
        return ["No predictions available for analysis."]
    # TODO - improve it, make more dynamic, not just 2.5 but variations, etc
    # Count statistics
    over_2_5 = sum(1 for sc in predictions if sc.home + sc.away > 2.5) / total_predictions * 100
    btts = sum(1 for sc in predictions if sc.home > 0 and sc.away > 0) / total_predictions * 100
    home_wins = sum(1 for sc in predictions if sc.home > sc.away) / total_predictions * 100
    away_wins = sum(1 for sc in predictions if sc.away > sc.home) / total_predictions * 100
    draws = sum(1 for sc in predictions if sc.home == sc.away) / total_predictions * 100

    # Handicap analysis
    handicap_home = sum(1 for sc in predictions if sc.home - sc.away >= 2) / total_predictions * 100
    handicap_away = sum(1 for sc in predictions if sc.away - sc.home >= 2) / total_predictions * 100

    # Prepare betting suggestions
    suggestions = []

    # Over/Under 2.5
    if over_2_5 >= threshold:
        suggestions.append(f"Bet on Over 2.5 goals ({over_2_5:.2f}% of predictions).")
    elif 100 - over_2_5 >= threshold:
        suggestions.append(f"Bet on Under 2.5 goals ({100 - over_2_5:.2f}% of predictions).")
    else:
        suggestions.append("Avoid betting on Over/Under 2.5 goals.")

    # Both Teams to Score (BTTS)
    if btts >= threshold:
        suggestions.append(f"Bet on Both Teams to Score (BTTS) ({btts:.2f}% of predictions).")
    elif 100 - btts >= threshold:
        suggestions.append(f"Bet on No BTTS ({100 - btts:.2f}% of predictions).")
    else:
        suggestions.append("Avoid betting on BTTS.")

    # End result
    if home_wins >= threshold:
        suggestions.append(f"Bet on Home team win ({home_wins:.2f}% of predictions).")
    elif away_wins >= threshold:
        suggestions.append(f"Bet on Away team win ({away_wins:.2f}% of predictions).")
    elif draws >= threshold:
        suggestions.append(f"Bet on Draw ({draws:.2f}% of predictions).")
    else:
        suggestions.append("Avoid betting on end result.")

    # Handicap
    if handicap_home >= threshold:
        suggestions.append(f"Bet on Home team handicap -1 ({handicap_home:.2f}% of predictions).")
    elif handicap_away >= threshold:
        suggestions.append(f"Bet on Away team handicap -1 ({handicap_away:.2f}% of predictions).")
    else:
        suggestions.append("Avoid betting on handicap.")

    return suggestions

def fractional_to_decimal_odds(fractional_odds):
    numerator, denominator = map(int, fractional_odds.split('/'))
    decimal_odds = numerator / denominator + 1
    return round(decimal_odds, 2)

def soundex(name):
    """Simple Soundex implementation."""
    name = name.upper()
    replacements = {
        "BFPV": "1", "CGJKQSXZ": "2", "DT": "3",
        "L": "4", "MN": "5", "R": "6"
    }
    soundex_code = name[0]  # First letter of the name
    for char in name[1:]:
        for key, value in replacements.items():
            if char in key:
                if soundex_code[-1] != value:  # Avoid duplicates
                    soundex_code += value
    soundex_code = soundex_code[:4].ljust(4, "0")  # Pad with zeros
    return soundex_code[:4]

acronyms = {
    " utd": "",
    " united": "",
    "al ": "",
    "cd ": "",
    "nk ": "",
    "ns ": "",
    " town": "",
    " city": "",
    "borussia ": "",
}

team_shorts = {
    "sporting cp": "sporting lisbon cp",
    "qpr": "queens park rangers",
}

def is_match(match1, match2):
    match1 = normalize_match_name(match1)
    match2 = normalize_match_name(match2)

    home1 = match1[0]
    away1 = match1[1]

    home2 = match2[0]
    away2 = match2[1]

    # replace acronyms with full names
    for k, v in acronyms.items():
        if k in home1 and k in home2:
            home1 = home1.replace(k, v)
            home2 = home2.replace(k, v)
        if k in away1 and k in away2:
            away1 = away1.replace(k, v)
            away2 = away2.replace(k, v)

    for k, v in team_shorts.items():
        home1 = home1.replace(k, v)
        home2 = home2.replace(k, v)
        away1 = away1.replace(k, v)
        away2 = away2.replace(k, v)

    home_match_score = hybrid_match(home1, home2)
    away_match_score = hybrid_match(away1, away2)

    return (home_match_score + away_match_score) / 2 > 65


def hybrid_match(string1, string2):
    """Combines multiple methods to determine match accuracy."""
    # Token-based similarity
    token_score = fuzz.token_set_ratio(string1, string2)

    # Substring presence
    substr_presence = any(word in string2 for word in string1.split())
    substr_score = 100 if substr_presence else 0

    # Phonetic similarity using Soundex
    soundex1 = soundex(string1.split()[0])  # Get Soundex of the first word
    soundex2 = soundex(string2.split()[0])
    phonetic_score = 100 if soundex1 == soundex2 else 0

    # Levenshtein ratio similarity
    ratio_score = fuzz.ratio(string1, string2)

    # Combine scores with weights
    final_score = (
        0.5 * token_score +
        0.1 * substr_score +
        0.1 * phonetic_score +
        0.3 * ratio_score
    )

    return final_score

# should return tuple of (home, away)
def normalize_match_name(match_name):
    """
    Normalize match names to improve similarity checks.
    Replaces stray separators and fixes cases like 'vAtletico'.
    """
    # Decompose Unicode characters into base character + diacritical marks
    match_name = unicodedata.normalize('NFD', match_name)
    # Filter out diacritical marks
    match_name = ''.join(char for char in match_name if unicodedata.category(char) != 'Mn')
    # Remove punctuation and other stuff
    translator = str.maketrans('', '', '(),.`')
    match_name = match_name.translate(translator)

    # Handle stray single 'v' attached to words (e.g., "vAtletico")
    match_name = re.sub(r"\s[v](?=[A-Z])", " vs ", match_name)

    # Handle common separators like "v", "-", ":", "," and normalize to "vs"
    match_name = re.sub(r"\b\s?(vs|v|-|:|,|@)\s?\b", " vs ", match_name, flags=re.IGNORECASE)

    # Remove extra spaces and make lowercase
    match_name = " ".join(match_name.split()).lower()

    return match_name.split(" vs ")


def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))
