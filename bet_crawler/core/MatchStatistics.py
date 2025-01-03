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

class H2H:
    def __init__(self, home, draw, away):
        self.home = home
        self.draw = draw
        self.away = away

# def Odds(home, draw, away):
#     return {
#         HOME: home,
#         DRAW: draw,
#         AWAY: away
#     }

class MatchStatistics:
    def __init__(self, scores, probabilities, h2h, odds, tips):
        self.scores = scores # list of Score objects
        self.tips = tips # list of Tip objects
        self.probabilities = probabilities # list of Probability objects
        self.h2h = h2h # a H2H dictionary
        self.odds = odds # int

    def to_dict(self):
        return {
            "scores": [score.__dict__ for score in self.scores] if self.scores else [],
            "tips": [tip.__dict__ for tip in self.tips] if self.tips else [],
            "probabilities": [probability.__dict__ for probability in self.probabilities] if self.probabilities else [],
            "h2h": self.h2h.__dict__ if self.h2h else None,
            "odds": self.odds
        }
