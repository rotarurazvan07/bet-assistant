from pymongo import MongoClient

from bet_crawler.core.Match import Match
from bet_crawler.core.MatchStatistics import MatchStatistics, Score, Probability, H2H
from bet_crawler.core.Team import Team, TeamStatistics
from bet_crawler.core.Tip import Tip
from bet_framework.utils import log, is_match


class DatabaseManager:
    def __init__(self):
        self.client = MongoClient('localhost', 27017)
        self.db = self.client['bet-assistant']
        self.matches_collection = self.db['Matches']

    def fetch_matches(self):
        matches = []
        for match_data in self.matches_collection.find():
            matches.append(Match(Team(match_data["home_team"]["name"], match_data["home_team"]["league_points"], match_data["home_team"]["form"], TeamStatistics(**match_data["home_team"]["statistics"]) if match_data["home_team"]["statistics"] else None),
                                 Team(match_data["away_team"]["name"], match_data["away_team"]["league_points"], match_data["away_team"]["form"], TeamStatistics(**match_data["away_team"]["statistics"]) if match_data["away_team"]["statistics"] else None),
                                 match_data["datetime"],
                                 MatchStatistics(
                                     [Score(**score) for score in match_data["statistics"]["scores"]],
                                     [Probability(**probability) for probability in match_data["statistics"]["probabilities"]],
                                     H2H(**match_data["statistics"]["h2h"]) if match_data["statistics"]["h2h"] else None,
                                     match_data["statistics"]["odds"],
                                     [Tip(**tip) for tip in match_data["statistics"]["tips"]]
                                 ),
                                 match_data["value"]))
        return matches

    def _find_match(self, match_name, match_date):
        for match in self.matches_collection.find():
            if abs((match_date.date() - match["datetime"].date()).days) <= 1:
                if is_match(match["home_team"]["name"] + " vs " + match["away_team"]["name"],  match_name):
                    return match
        return None

    def update_match(self, match_name=None, match_date=None, tip=None, score=None, probability=None, match_id=None):
        if match_id:
            match = self.matches_collection.find_one({"_id": match_id})
        else:
            match = self._find_match(match_name, match_date)
        if match:
            # TODO fails on odds change
            if tip:
                self.matches_collection.update_one(
                    {"_id": match["_id"]},
                    {"$addToSet": {"statistics.tips": tip.__dict__}}
                )
            if score:
                self.matches_collection.update_one(
                    {"_id": match["_id"]},
                    {"$addToSet": {"statistics.scores": score.__dict__}}
                )
            if probability:
                self.matches_collection.update_one(
                    {"_id": match["_id"]},
                    {"$addToSet": {"statistics.probabilities": probability.__dict__}}
                )
            return match["_id"]
        else:
            log(f"{match_name} was not found on forebet, investigate")

    def add_match(self, match, match_id=None):
        if match_id:
            found_match = self.matches_collection.find_one({"_id": match_id})
        else:
            found_match = self._find_match(match.home_team.name + " vs " + match.away_team.name, match.datetime)
        if found_match:
            log(f"Adding {match.home_team.name} vs {match.away_team.name} to match: {found_match["home_team"]["name"]} vs {found_match["away_team"]["name"]}")
            for tip in match.statistics.tips:
                self.update_match(tip=tip, match_id=found_match["_id"])

            for score in match.statistics.scores:
                self.update_match(score=score, match_id=found_match["_id"])

            for probability in match.statistics.probabilities:
                self.update_match(probability=probability, match_id=found_match["_id"])

            if found_match["statistics"]["h2h"] is None:
                self.matches_collection.update_one(
                    {"_id": found_match["_id"]},
                    {"$set": {"statistics.h2h": match.statistics.h2h}}
                )

            return found_match["_id"]
        else:
            log(f"Creating new match: {match.home_team.name} vs {match.away_team.name}")
            self.matches_collection.insert_one(match.to_dict())

    def reset_matches_db(self):
        self.matches_collection.delete_many({})
