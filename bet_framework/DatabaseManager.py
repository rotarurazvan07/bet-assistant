from datetime import datetime

from pymongo import MongoClient
from rapidfuzz import fuzz

from bet_crawler.tippers.impl.core.Tip import MatchTips
from bet_crawler.tippers.impl.core.Tip import Tip
from bet_crawler.value_finder.Match import Match, MatchStatistics
from bet_crawler.value_finder.Team import Team
from utils import normalize_match_name


# another idea of table:
# get score prediciton from like 5 sources
# get whats common from them, like 1 x 2, goals, etc.

class DatabaseManager:
    def __init__(self):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['bet-assistant']
        self.tips_collection = self.db['Tips']
        self.value_matches_collection = self.db['ValueMatches']

    def fetch_tips_data(self):
        match_tips_list = []
        for match_data in self.tips_collection.find():
            # delete _id, not used
            match_tips_list.append(MatchTips(match_data["match_name"],
                                             match_data["match_datetime"],
                                             match_data["analysis"],
                                             [Tip(**tip) for tip in match_data["tips"]]))
        return match_tips_list

    def add_or_update_tip(self, tip, match_name, match_time):
        # Convert match time to structured format
        match_name = normalize_match_name(match_name)
        match_date = datetime.strptime(match_time, "%Y-%m-%d - %H:%M")

        existing_match = None
        for match_tips in self.tips_collection.find():
            match_score = fuzz.ratio(match_tips["match_name"], match_name)
            if match_score > 80:  # Threshold for similarity
                existing_match = match_tips
                break

        if existing_match:
            # Update existing match: append the new tip if it doesn't already exist
            tips = existing_match["tips"]
            tips.append(tip.__dict__)
            self.tips_collection.update_one(
                {"_id": existing_match["_id"]},
                {"$set": {"tips": tips}}
            )
        else:
            self.tips_collection.insert_one(MatchTips(match_name, match_date, "N/A", [tip]).to_dict())

    def reset_tips_db(self):
        self.tips_collection.delete_many({})

    def fetch_value_matches_data(self):
        matches = []
        for match_data in self.value_matches_collection.find():
            # delete _id, not used
            matches.append(Match(Team(**match_data["home_team"]),
                                 Team(**match_data["away_team"]),
                                 match_data["match_datetime"],
                                 MatchStatistics(**match_data["match_statistics"])))
        return matches

    def add_value_match(self, match):
        self.value_matches_collection.insert_one(match.to_dict())

    def reset_value_matches_db(self):
        self.value_matches_collection.delete_many({})