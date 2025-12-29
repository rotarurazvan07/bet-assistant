from pymongo import MongoClient

from bet_framework.SimilarityEngine import SimilarityEngine

from .core.Match import *
from .core.Tip import Tip
from .utils import log
from .SettingsManager import settings_manager

class DatabaseManager:
    def __init__(self, client: MongoClient = None):
        """Initialize DatabaseManager using config from SettingsManager (if present).

        Config keys (in `config/database_config.yaml` or loaded into SettingsManager under
        the key `database`) include: host, port, db_name, matches_collection, username, password.
        """
        # Accept either 'database' or 'database_config' as the config key
        settings_manager.load_settings("config")
        cfg = settings_manager.get_config('database_config')

        host = cfg.get('host', 'localhost')
        port = cfg.get('port', 27017)
        db_name = cfg.get('db_name', 'bet-assistant')
        collection_name = cfg.get('matches_collection', 'Matches')

        # Allow providing an external client for testing/override
        if client:
            self.client = client
        else:
            # Support optional username/password
            username = cfg.get('username')
            password = cfg.get('password')
            if username and password:
                self.client = MongoClient(host=host, port=port, username=username, password=password)
            else:
                self.client = MongoClient(host, port)

        self.similarity_engine = SimilarityEngine()

        self.db = self.client[db_name]
        self.matches_collection = self.db[collection_name]

    def fetch_matches(self):
        matches = []
        for match_data in self.matches_collection.find():
            matches.append(Match(home_team=Team(match_data["home_team"]["name"], match_data["home_team"]["league_points"], match_data["home_team"]["form"], TeamStatistics(**match_data["home_team"]["statistics"]) if match_data["home_team"]["statistics"] else None),
                                 away_team=Team(match_data["away_team"]["name"], match_data["away_team"]["league_points"], match_data["away_team"]["form"], TeamStatistics(**match_data["away_team"]["statistics"]) if match_data["away_team"]["statistics"] else None),
                                 datetime=match_data["datetime"],
                                 h2h=H2H(**match_data["h2h"]) if match_data["h2h"] else None,
                                 predictions=MatchPredictions(
                                     [Score(**score) for score in match_data["predictions"]["scores"]],
                                     [Probability(**probability) for probability in match_data["predictions"]["probabilities"]],
                                     [Tip.from_dict(tip) for tip in match_data["predictions"]["tips"]]
                                 ))),

        return matches

    def _find_match(self, match_name, match_date):
        for match in self.matches_collection.find():
            if abs((match_date.date() - match["datetime"].date()).days) <= 1:
                if self.similarity_engine.is_similar(match["home_team"]["name"] + " vs " + match["away_team"]["name"],  match_name):
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
                    {"$addToSet": {"predictions.tips": tip.to_dict()}}
                )
            if score:
                self.matches_collection.update_one(
                    {"_id": match["_id"]},
                    {"$addToSet": {"predictions.scores": score.__dict__}}
                )
            if probability:
                self.matches_collection.update_one(
                    {"_id": match["_id"]},
                    {"$addToSet": {"predictions.probabilities": probability.__dict__}}
                )
            return match["_id"]
        else:
            log(f"{match_name} was not found on forebet, investigate")

    def add_match(self, match, match_id=None):
        try:
            if match_id:
                found_match = self.matches_collection.find_one({"_id": match_id})
            else:
                found_match = self._find_match(match.home_team.name + " vs " + match.away_team.name, match.datetime)
            if found_match:
                log(f"Adding {match.home_team.name} vs {match.away_team.name} to match: {found_match['home_team']['name']} vs {found_match['away_team']['name']}")
                if match.predictions.tips:
                    for tip in match.predictions.tips:
                        self.update_match(tip=tip, match_id=found_match["_id"])

                if match.predictions.scores:
                    for score in match.predictions.scores:
                        self.update_match(score=score, match_id=found_match["_id"])

                if match.predictions.probabilities:
                    for probability in match.predictions.probabilities:
                        self.update_match(probability=probability, match_id=found_match["_id"])

                if found_match["h2h"] is None and match.h2h is not None:
                    self.matches_collection.update_one(
                        {"_id": found_match["_id"]},
                        {"$set": {"h2h": match.h2h}}
                    )

                return found_match["_id"]
            else:
                log(f"Creating new match: {match.home_team.name} vs {match.away_team.name} [{str(match.datetime)}]")
                self.matches_collection.insert_one(match.to_dict())
        except Exception as e:
            print(f"Caught {e} while adding to db")

    def reset_matches_db(self):
        self.matches_collection.delete_many({})
