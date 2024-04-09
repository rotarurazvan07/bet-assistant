H2H_WIN_WEIGHT = 3


class Match:
    # h2h_results is a list that contains results of head to head matches (home vs away) in the form of
    # (home_wins, draws, away_wins)
    def __init__(self, home_team, away_team, match_datetime, forebet_score, forebet_probability, h2h_results):
        self.home_team = home_team
        self.away_team = away_team

        self.match_datetime = match_datetime

        self.match_statistics = self._MatchStatistics(home_team, away_team,
                                                      forebet_score, forebet_probability,
                                                      h2h_results)

    def get_match_value(self):
        return self.match_statistics.match_value

    # return match data in list form to be written in the Excel file
    def get_match_data(self):
        return [self.home_team.name, self.away_team.name, str(self.match_datetime.date()),
                str(self.match_datetime.time()),
                self.home_team.league_points, self.away_team.league_points,
                self.home_team.form, self.away_team.form,
                self.match_statistics.match_value,
                self.match_statistics.forebet_probability, self.match_statistics.forebet_score]

    class _MatchStatistics:
        def __init__(self, home_team, away_team, forebet_score, forebet_probability, h2h_results):
            self.forebet_score = forebet_score
            self.forebet_probability = forebet_probability
            self.h2h_results = h2h_results

            self.match_value = self._calculate_value(home_team, away_team, h2h_results)

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
