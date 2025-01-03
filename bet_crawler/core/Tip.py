class Tip:
    def __init__(self, tip, confidence, source="", odds=0):
        self.tip = tip
        self.confidence = confidence
        self.odds = odds
        self.source = source