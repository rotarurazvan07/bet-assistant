H2H_WIN_WEIGHT = 3

class MatchStatistics:
    def __init__(self, forebet_score, forebet_probability, h2h_result, odds):
        self.forebet_score = tuple(forebet_score)
        self.forebet_probability  = tuple(forebet_probability)
        self.h2h_result = tuple(h2h_result)
        self.odds = odds

class Match:
    # h2h_results is a list that contains results of head to head matches (home vs away) in the form of
    # (home_wins, draws, away_wins)
    def __init__(self, home_team, away_team, match_datetime, match_statistics):
        self.home_team = home_team
        self.away_team = away_team
        self.match_datetime = match_datetime
        self.match_statistics = match_statistics
        self.match_value = self._calculate_value(self.home_team, self.away_team, self.match_statistics.h2h_result)

    def _calculate_value(self, home_team, away_team, h2h_results):
        home_team_score = home_team.get_team_score()
        away_team_score = away_team.get_team_score()

        h2h_home_wins = h2h_results[0]
        h2h_draws = h2h_results[1]
        h2h_away_wins = h2h_results[2]
        h2h_bias = H2H_WIN_WEIGHT * (h2h_home_wins - h2h_away_wins)

        # negative value of h2h_bias means the bias is for the away team, and it gets added with that score
        # add the bias to the corresponding team
        if h2h_bias < 0:
            away_team_score += abs(h2h_bias)
        else:
            home_team_score += h2h_bias

        return abs(home_team_score - away_team_score)

    def to_dict(self):
        return {
            "home_team": self.home_team.__dict__,
            "away_team": self.away_team.__dict__,
            "match_datetime": self.match_datetime,
            "match_statistics": self.match_statistics.__dict__,
            "match_value": self.match_value
        }
