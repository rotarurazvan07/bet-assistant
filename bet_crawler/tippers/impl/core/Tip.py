class Tip:
    def __init__(self, match_name, match_time, tip, confidence, source="", odds="N/A"):
        self.match_name = match_name
        self.match_time = match_time
        self.tip = tip
        self.confidence = confidence
        self.odds = odds
        self.source = source