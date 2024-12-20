from datetime import datetime
from difflib import SequenceMatcher
from statistics import mean

from g4f.Provider import Raycast
from g4f.client import Client
from pymongo import MongoClient


# another idea of table:
# get score prediciton from like 5 sources
# get whats common from them, like 1 x 2, goals, etc.


class DatabaseManager:
    def __init__(self):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['bet-assistant']
        self.tips_collection = self.db['Tips']

    # TODO - this doesnt catch everything
    def get_existing_match(self, match_name):
        matches = self.tips_collection.find({})
        for match in matches:
            similarity = SequenceMatcher(None, match_name, match["match"]).ratio()
            if similarity > 0.75:
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
                "analysis": match["analysis"],
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

        # Sort match_data_list by sum of unique sources, then by mean of confidence
        #  TODO - need to tune this to get best results to bet first
        #   rigth now some games 3 star tips are still hidden down
        match_data_list.sort(
            key=lambda x: (len(set(tip["source"] for tip in x["tips"])), mean(tip["confidence"] for tip in x["tips"])),
            reverse=True)

        return match_data_list

    def analyse_data(self):
        client = Client(provider=Raycast)

        prompt = "I have the match: %s\n" \
                 "I have this table of tips which represent the content of the tip and the last number is the " \
                 "confidence (float from 1 to 3), separated by comma:\n" \
                 "%s" \
                 "I want you to create me the best single bet out of all these tips. Take much into " \
                 "consideration the confidence and what all the tips have in common. It is important not to " \
                 "just choose the high confidence, but to weight it against all tips\n" \
                 "Respond shortly and summarised.\n" \
                 "Dont repeat the tips table, just give your answer in maximum two sentences."
        # TODO - fetch or refresh the table
        # TODO - this needs speeding up
        matches = self.tips_collection.find({})
        for match in matches:
            tips_table = ""
            for tip in match["tips"]:
                tips_table += tip["tip"] + ", " + str(tip["confidence"]) + "\n"

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt % (match["match"], tips_table)}],
            )

            print(response.choices[0].message.content)

            self.tips_collection.update_one(
                {"_id": match["_id"]},
                {"$set": {"analysis": response.choices[0].message.content}}
            )

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
                "analysis": "N/A",
                "tips": [tip_data]
            }
            self.tips_collection.insert_one(match_data)

    def reset_db(self):
        self.tips_collection.delete_many({})
