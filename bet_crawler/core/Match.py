H2H_WIN_WEIGHT = 3


class Match:
    # h2h_results is a list that contains results of head to head matches (home vs away) in the form of
    # (home_wins, draws, away_wins)
    def __init__(self, home_team, away_team, datetime, statistics, value=None):
        self.home_team = home_team # A Team object
        self.away_team = away_team # A Team object
        self.datetime = datetime # python datetime
        self.statistics = statistics # a MatchStatistics.py object
        if value:
            self.value = value # integer
        else:
            self.value = self._calculate_value() # integer

    def to_dict(self):
        return {
            "home_team": self.home_team.to_dict(),
            "away_team": self.away_team.to_dict(),
            "datetime": self.datetime,
            "statistics": self.statistics.to_dict(),
            "value": self.value
        }

    def _calculate_value(self):
        home_team_score = self.home_team.get_team_score()
        away_team_score = self.away_team.get_team_score()

        if self.statistics.h2h:
            h2h_home_wins = self.statistics.h2h.home
            h2h_draws = self.statistics.h2h.draw
            h2h_away_wins = self.statistics.h2h.away
            h2h_bias = H2H_WIN_WEIGHT * (h2h_home_wins - h2h_away_wins)

            # negative value of h2h_bias means the bias is for the away team, and it gets added with that score
            # add the bias to the corresponding team
            if h2h_bias < 0:
                away_team_score += abs(h2h_bias)
            else:
                home_team_score += h2h_bias

        return abs(home_team_score - away_team_score)
