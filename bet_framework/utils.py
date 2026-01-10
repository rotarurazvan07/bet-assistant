import inspect
import math
import re
from datetime import datetime

import unicodedata
from rapidfuzz import fuzz

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
    if match.predictions.scores.home > match.predictions.scores.away:
        # Home favorite
        return match.predictions.probabilities.draw + match.predictions.probabilities.home
    elif match.predictions.scores.home < match.predictions.scores.away:
        # Away favorite
        return match.predictions.probabilities.draw + match.predictions.probabilities.away
    elif match.predictions.scores.home == match.predictions.scores.away:
        # in case of draw, return draw chance + whichever has more chances
        return match.predictions.probabilities.draw + max(match.predictions.probabilities.home, match.predictions.probabilities.away)


# analyze_betting_predictions moved into MatchAnalyzer for cohesion

def fractional_to_decimal_odds(fractional_odds):
    numerator, denominator = map(int, fractional_odds.split('/'))
    decimal_odds = numerator / denominator + 1
    return round(decimal_odds, 2)

def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))

# calculate_match_value and get_team_score moved into MatchAnalyzer