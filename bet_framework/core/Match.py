class H2H:
    def __init__(self, home, draw, away):
        self.home = home
        self.draw = draw
        self.away = away


class Match:
    # h2h_results is a list that contains results of head to head matches (home vs away) in the form of
    # (home_wins, draws, away_wins)
    def __init__(self, home_team, away_team, datetime, h2h, predictions, odds):
        self.home_team = home_team # A Team object
        self.away_team = away_team # A Team object
        self.datetime = datetime # python datetime
        self.predictions = predictions # a MatchPredictions.py object
        self.h2h = h2h
        self.odds = odds # Odds object

    def to_dict(self):
        return {
            "home_team": self.home_team.to_dict(),
            "away_team": self.away_team.to_dict(),
            "datetime": self.datetime,
            "predictions": self.predictions.to_dict(),
            "h2h": self.h2h.__dict__ if self.h2h else None,
            "odds": self.odds.__dict__ if self.odds else None,
        }


class Probability:
    def __init__(self, source, home, draw, away):
        self.source = source
        self.home = float(home)
        self.draw = float(draw)
        self.away = float(away)

class Score:
    def __init__(self, source, home, away):
        self.source = source
        self.home = float(home)
        self.away = float(away)

class Odds:
    def __init__(self, home, draw, away, over, under, btts_y, btts_n):
        self.home = home
        self.draw = draw
        self.away = away
        self.over = over
        self.under = under
        self.btts_y = btts_y
        self.btts_n = btts_n

class MatchPredictions:
    def __init__(self, scores, probabilities, tips):
        self.scores = scores # list of Score objects
        self.tips = tips # list of Tip objects
        self.probabilities = probabilities # list of Probability objects

    def to_dict(self):
        return {
            "scores": [score.__dict__ for score in self.scores] if self.scores else [],
            "tips": [tip.to_dict() for tip in self.tips] if self.tips else [],
            "probabilities": [probability.__dict__ for probability in self.probabilities] if self.probabilities else [],
        }


class TeamStatistics:
    def __init__(self, avg_corners, avg_offsides, avg_gk_saves, avg_yellow_cards, avg_fouls, avg_tackles,
                 avg_scored, avg_conceded, avg_shots_on_target, avg_possession):
        self.avg_corners = avg_corners
        self.avg_offsides = avg_offsides
        self.avg_gk_saves = avg_gk_saves
        self.avg_yellow_cards = avg_yellow_cards
        self.avg_fouls = avg_fouls
        self.avg_tackles = avg_tackles
        self.avg_scored = avg_scored
        self.avg_conceded = avg_conceded
        self.avg_shots_on_target = avg_shots_on_target
        self.avg_possession = avg_possession

class Team:
    def __init__(self, name, league_points, form, statistics):
        self.name = name
        self.league_points = league_points
        self.form = form  # list containing latest matches results
        self.statistics = statistics

    def to_dict(self):
        return {
            "name": self.name,
            "league_points": self.league_points,
            "form": self.form,
            "statistics": self.statistics.__dict__ if self.statistics else None
        }
