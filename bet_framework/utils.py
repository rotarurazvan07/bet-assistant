import inspect

def fractional_to_decimal_odds(fractional_odds):
    numerator, denominator = map(int, fractional_odds.split('/'))
    decimal_odds = numerator / denominator + 1
    return round(decimal_odds, 2)

def log(message):
    func = inspect.currentframe().f_back.f_code
    print("%s: %s" % (func.co_name, message))

# calculate_match_value and get_team_score moved into MatchAnalyzer