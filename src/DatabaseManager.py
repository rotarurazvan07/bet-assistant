from statistics import mean

from pymongo import MongoClient
from fuzzywuzzy import fuzz
from datetime import datetime
# another idea of table:
# get score prediciton from like 5 sources
# get whats common from them, like 1 x 2, goals, etc.

class DatabaseManager:
    def __init__(self):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['bet-assistant']
        self.tips_collection = self.db['Tips']

    def get_existing_match(self, match_name):
        matches = self.tips_collection.find({})
        for match in matches:
            if fuzz.ratio(match['match'], match_name) > 80:
                return match
        return None

    def fetch_match_data(self, start_date, end_date):
        matches = self.tips_collection.find()
        match_data_list = []

        for match in matches:
            match_date = datetime.strptime(match["match_day"], '%Y-%m-%d')

            # Filter matches based on start_date and end_date
            if start_date and match_date < start_date:
                continue
            if end_date and match_date > end_date:
                continue
            match_data = {
                "match": match["match"],
                "match_day": match["match_day"],
                "match_time": match["match_time"],
                "tips": []
            }
            for tip in match["tips"]:
                match_data["tips"].append({
                    "tip": tip["tip"],
                    "confidence": round(tip["confidence"], 2),
                    "source": tip["source"],
                    "odds": tip["odds"]
                })
            # Sort tips by confidence in descending order after each append
            match_data["tips"].sort(key=lambda tip: tip["confidence"], reverse=True)

            match_data_list.append(match_data)

        # Sort match_data_list by the sum of confidence values in the tips list in descending order
        match_data_list.sort(key=lambda x: (len(x["tips"]), mean(tip["confidence"] for tip in x["tips"])), reverse=True)

        return match_data_list

    def add_or_update_match(self, tip):
        # TODO - if match date has N/A and a good date comes in, update it
        match_date = datetime.strptime(tip.match_time, "%Y-%m-%d - %H:%M")

        match_day = str(match_date.date())
        match_time = '%02d:%02d' % (match_date.hour, match_date.minute)
        if match_time == "23:59": match_time = "N/A"

        existing_match = self.get_existing_match(tip.match_name)

        tip_data = {
            "tip": tip.tip,
            "confidence": tip.confidence,
            "source": tip.source,
            "odds": tip.odds
        }

        if existing_match:
            # Update existing match with new tips
            self.tips_collection.update_one(
                {"_id": existing_match["_id"]},
                {"$addToSet": {"tips": tip_data}}
            )
        else:
            # Insert new match document
            match_data = {
                "match": tip.match_name,
                "match_day": match_day,
                "match_time": match_time,
                "tips": [tip_data]
            }
            self.tips_collection.insert_one(match_data)

    def reset_db(self):
        self.tips_collection.delete_many({})
