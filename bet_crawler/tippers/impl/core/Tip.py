class MatchTips:
    def __init__(self, match_name, match_datetime, analysis, tips):
        self.match_name = match_name
        self.match_datetime = match_datetime
        self.analysis = analysis
        self.tips = tips

    def to_dict(self):
        return {
            "match_name": self.match_name,
            "match_datetime": self.match_datetime,
            "analysis": self.analysis,
            "tips": [tip.__dict__ for tip in self.tips]
        }

class Tip:
    def __init__(self, tip, confidence, source="", odds="N/A"):
        self.tip = tip
        self.confidence = confidence
        self.odds = odds
        self.source = source