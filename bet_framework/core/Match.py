from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional

@dataclass
class H2H:
    home: int
    draw: int
    away: int

@dataclass
class Probability:
    source: str
    home: float
    draw: float
    away: float

@dataclass
class Score:
    source: str
    home: float
    away: float

@dataclass
class Odds:
    home: float
    draw: float
    away: float
    over: float
    under: float
    btts_y: float
    btts_n: float

@dataclass
class TeamStatistics:
    avg_corners: float
    avg_offsides: float
    avg_gk_saves: float
    avg_yellow_cards: float
    avg_fouls: float
    avg_tackles: float
    avg_scored: float
    avg_conceded: float
    avg_shots_on_target: float
    avg_possession: float

class Team:
    def __init__(self, name: str, league_points: int, form: List[str], statistics: Optional[TeamStatistics]):
        self.name = name
        self.league_points = league_points
        self.form = form
        self.statistics = statistics

    def to_dict(self):
        return {
            "name": self.name,
            "league_points": self.league_points,
            "form": self.form,
            "statistics": asdict(self.statistics) if self.statistics else None
        }

class MatchPredictions:
    def __init__(self, scores: List[Score], probabilities: List[Probability], tips: List[any]):
        self.scores = scores
        self.probabilities = probabilities
        self.tips = tips

    def to_dict(self):
        return {
            "scores": [asdict(s) for s in self.scores],
            "probabilities": [asdict(p) for p in self.probabilities],
            "tips": [t.to_dict() if hasattr(t, 'to_dict') else str(t) for t in self.tips]
        }

class Match:
    def __init__(self, home_team: Team, away_team: Team, datetime: datetime, h2h: H2H, predictions: MatchPredictions, odds: Odds):
        self.home_team = home_team
        self.away_team = away_team
        self.datetime = datetime
        self.h2h = h2h
        self.predictions = predictions
        self.odds = odds

    def to_dict(self):
        return {
            "home_team": self.home_team.to_dict(),
            "away_team": self.away_team.to_dict(),
            "datetime": self.datetime.isoformat() if isinstance(self.datetime, datetime) else self.datetime,
            "h2h": asdict(self.h2h) if self.h2h else None,
            "predictions": self.predictions.to_dict(),
            "odds": asdict(self.odds) if self.odds else None,
        }