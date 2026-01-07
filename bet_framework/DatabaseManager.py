from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware
from datetime import datetime
import json

from bet_framework.SimilarityEngine import SimilarityEngine

from .core.Match import *
from .core.Tip import Tip
from .utils import log
from .SettingsManager import settings_manager


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class DateTimeStorage(JSONStorage):
    """Custom TinyDB storage that serializes datetime objects."""
    def __init__(self, path, **kwargs):
        super().__init__(path, **kwargs)

    def write(self, data):
        # Serialize with custom encoder
        self._handle.seek(0)
        serialized = json.dumps(data, cls=DateTimeEncoder, **self.kwargs)
        self._handle.write(serialized)
        self._handle.flush()
        self._handle.truncate()


class DatabaseManager:
    def __init__(self, db_path: str = None):
        settings_manager.load_settings("config")
        cfg = settings_manager.get_config('database_config')

        # Allow providing an external db_path for testing/override
        if db_path is None:
            db_path = cfg.get('db_path', 'data/matches.json')

        self.db = TinyDB(db_path, storage=CachingMiddleware(DateTimeStorage))
        self.matches_collection = self.db.table('matches')
        self.similarity_engine = SimilarityEngine()

    def fetch_matches(self):
        matches = []
        for match_data in self.matches_collection.all():
            # Convert datetime strings back to datetime objects
            datetime_obj = match_data["datetime"]
            if isinstance(datetime_obj, str):
                datetime_obj = datetime.fromisoformat(datetime_obj)

            matches.append(Match(
                home_team=Team(
                    match_data["home_team"]["name"],
                    match_data["home_team"]["league_points"],
                    match_data["home_team"]["form"],
                    TeamStatistics(**match_data["home_team"]["statistics"])
                        if match_data["home_team"]["statistics"] else None
                ),
                away_team=Team(
                    match_data["away_team"]["name"],
                    match_data["away_team"]["league_points"],
                    match_data["away_team"]["form"],
                    TeamStatistics(**match_data["away_team"]["statistics"])
                        if match_data["away_team"]["statistics"] else None
                ),
                datetime=datetime_obj,
                h2h=H2H(**match_data["h2h"]) if match_data["h2h"] else None,
                predictions=MatchPredictions(
                    [Score(**score) for score in match_data["predictions"]["scores"]],
                    [Probability(**probability) for probability in match_data["predictions"]["probabilities"]],
                    [Tip.from_dict(tip) for tip in match_data["predictions"]["tips"]]
                ),
                odds=Odds(**match_data["odds"]) if match_data["odds"] else None
            ))

        return matches

    def _find_match(self, match_name, match_date):
        for match in self.matches_collection.all():
            match_datetime = match["datetime"]
            # Handle both datetime objects and ISO string dates
            if isinstance(match_datetime, str):
                match_datetime = datetime.fromisoformat(match_datetime)
            elif not isinstance(match_datetime, datetime):
                continue

            if abs((match_date.date() - match_datetime.date()).days) <= 1:
                if self.similarity_engine.is_similar(
                    match["home_team"]["name"] + " vs " + match["away_team"]["name"],
                    match_name
                ):
                    return match
        return None

    def update_match(self, match_name=None, match_date=None, tip=None, score=None, probability=None, match_id=None):
        if match_id:
            match = self.matches_collection.get(doc_id=match_id)
        else:
            match = self._find_match(match_name, match_date)

        if match:
            match_doc_id = match.doc_id
            updated_match = match.copy()

            # Handle tip updates
            if tip:
                existing_tips = updated_match.get("predictions", {}).get("tips", [])
                tip_dict = tip.to_dict()
                if tip_dict not in existing_tips:
                    existing_tips.append(tip_dict)
                    if "predictions" not in updated_match:
                        updated_match["predictions"] = {}
                    updated_match["predictions"]["tips"] = existing_tips

            # Handle score updates
            if score:
                existing_scores = updated_match.get("predictions", {}).get("scores", [])
                score_dict = score.__dict__
                if score_dict not in existing_scores:
                    existing_scores.append(score_dict)
                    if "predictions" not in updated_match:
                        updated_match["predictions"] = {}
                    updated_match["predictions"]["scores"] = existing_scores

            # Handle probability updates
            if probability:
                existing_probs = updated_match.get("predictions", {}).get("probabilities", [])
                prob_dict = probability.__dict__
                if prob_dict not in existing_probs:
                    existing_probs.append(prob_dict)
                    if "predictions" not in updated_match:
                        updated_match["predictions"] = {}
                    updated_match["predictions"]["probabilities"] = existing_probs

            # Update the document
            self.matches_collection.update(updated_match, doc_ids=[match_doc_id])
            return match_doc_id
        else:
            log(f"{match_name} was not found on forebet, investigate")
            return None

    def add_match(self, match, match_id=None):
        try:
            if match_id:
                found_match = self.matches_collection.get(doc_id=match_id)
            else:
                found_match = self._find_match(
                    match.home_team.name + " vs " + match.away_team.name,
                    match.datetime
                )

            if found_match:
                log(f"Adding {match.home_team.name} vs {match.away_team.name} to match: {found_match['home_team']['name']} vs {found_match['away_team']['name']}")

                match_doc_id = found_match.doc_id
                updated_match = found_match.copy()

                # Add tips
                if match.predictions.tips:
                    existing_tips = updated_match.get("predictions", {}).get("tips", [])
                    for tip in match.predictions.tips:
                        tip_dict = tip.to_dict()
                        if tip_dict not in existing_tips:
                            existing_tips.append(tip_dict)
                    if "predictions" not in updated_match:
                        updated_match["predictions"] = {}
                    updated_match["predictions"]["tips"] = existing_tips

                # Add scores
                if match.predictions.scores:
                    existing_scores = updated_match.get("predictions", {}).get("scores", [])
                    for score in match.predictions.scores:
                        score_dict = score.__dict__
                        if score_dict not in existing_scores:
                            existing_scores.append(score_dict)
                    if "predictions" not in updated_match:
                        updated_match["predictions"] = {}
                    updated_match["predictions"]["scores"] = existing_scores

                # Add probabilities
                if match.predictions.probabilities:
                    existing_probs = updated_match.get("predictions", {}).get("probabilities", [])
                    for probability in match.predictions.probabilities:
                        prob_dict = probability.__dict__
                        if prob_dict not in existing_probs:
                            existing_probs.append(prob_dict)
                    if "predictions" not in updated_match:
                        updated_match["predictions"] = {}
                    updated_match["predictions"]["probabilities"] = existing_probs

                # Update h2h if missing
                if found_match.get("h2h") is None and match.h2h is not None:
                    updated_match["h2h"] = match.h2h.__dict__

                # Update odds if missing
                if found_match.get("odds") is None and match.odds is not None:
                    updated_match["odds"] = match.odds.__dict__

                # Write all updates at once
                self.matches_collection.update(updated_match, doc_ids=[match_doc_id])
                return match_doc_id
            else:
                log(f"Creating new match: {match.home_team.name} vs {match.away_team.name} [{str(match.datetime)}]")
                match_dict = match.to_dict()
                return self.matches_collection.insert(match_dict)

        except Exception as e:
            print(f"Caught {e} while adding to db")
            return None

    def reset_matches_db(self):
        self.matches_collection.truncate()