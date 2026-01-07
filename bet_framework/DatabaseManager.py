import sqlite3
from datetime import datetime
import json
from typing import Optional

from bet_framework.SimilarityEngine import SimilarityEngine

from .core.Match import *
from .core.Tip import Tip
from .utils import log
from .SettingsManager import settings_manager


class DatabaseManager:
    def __init__(self, db_path: str = None):
        """Initialize DatabaseManager using config from SettingsManager (if present).

        Config keys (in `config/database_config.yaml` or loaded into SettingsManager under
        the key `database`) include: db_path (defaults to 'data/matches.db').
        """
        settings_manager.load_settings("config")
        cfg = settings_manager.get_config('database_config')

        # Allow providing an external db_path for testing/override
        if db_path is None:
            db_path = cfg.get('db_path', 'data/matches.db')

        # Enable WAL mode for concurrent reads/writes
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.row_factory = sqlite3.Row

        self.similarity_engine = SimilarityEngine()
        self._create_tables()

    def _create_tables(self):
        """Create the matches table if it doesn't exist."""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_team_name TEXT NOT NULL,
                home_team_league_points INTEGER,
                home_team_form TEXT,
                home_team_statistics TEXT,
                away_team_name TEXT NOT NULL,
                away_team_league_points INTEGER,
                away_team_form TEXT,
                away_team_statistics TEXT,
                datetime TEXT NOT NULL,
                h2h TEXT,
                predictions_scores TEXT,
                predictions_probabilities TEXT,
                predictions_tips TEXT,
                odds TEXT
            )
        ''')
        self.conn.commit()

    def _serialize_json(self, obj):
        """Serialize object to JSON string."""
        if obj is None:
            return None
        if hasattr(obj, '__dict__'):
            return json.dumps(obj.__dict__)
        return json.dumps(obj)

    def _deserialize_json(self, json_str):
        """Deserialize JSON string to dict."""
        if json_str is None:
            return None
        return json.loads(json_str)

    def _row_to_match(self, row) -> Match:
        """Convert a database row to a Match object."""
        # Parse datetime
        datetime_obj = datetime.fromisoformat(row['datetime'])

        # Parse home team
        home_stats = None
        if row['home_team_statistics']:
            home_stats = TeamStatistics(**self._deserialize_json(row['home_team_statistics']))
        home_team = Team(
            row['home_team_name'],
            row['home_team_league_points'],
            row['home_team_form'],
            home_stats
        )

        # Parse away team
        away_stats = None
        if row['away_team_statistics']:
            away_stats = TeamStatistics(**self._deserialize_json(row['away_team_statistics']))
        away_team = Team(
            row['away_team_name'],
            row['away_team_league_points'],
            row['away_team_form'],
            away_stats
        )

        # Parse h2h
        h2h = None
        if row['h2h']:
            h2h = H2H(**self._deserialize_json(row['h2h']))

        # Parse predictions
        scores = []
        if row['predictions_scores']:
            scores = [Score(**s) for s in self._deserialize_json(row['predictions_scores'])]

        probabilities = []
        if row['predictions_probabilities']:
            probabilities = [Probability(**p) for p in self._deserialize_json(row['predictions_probabilities'])]

        tips = []
        if row['predictions_tips']:
            tips = [Tip.from_dict(t) for t in self._deserialize_json(row['predictions_tips'])]

        predictions = MatchPredictions(scores, probabilities, tips)

        # Parse odds
        odds = None
        if row['odds']:
            odds = Odds(**self._deserialize_json(row['odds']))

        return Match(
            home_team=home_team,
            away_team=away_team,
            datetime=datetime_obj,
            h2h=h2h,
            predictions=predictions,
            odds=odds
        )

    def fetch_matches(self):
        """Fetch all matches from the database."""
        cursor = self.conn.execute('SELECT * FROM matches')
        matches = []
        for row in cursor:
            matches.append(self._row_to_match(row))
        return matches

    def _find_match(self, match_name, match_date):
        """Find a match by name and date using similarity matching."""
        cursor = self.conn.execute('SELECT * FROM matches')
        for row in cursor:
            row_datetime = datetime.fromisoformat(row['datetime'])

            if abs((match_date.date() - row_datetime.date()).days) <= 1:
                db_match_name = f"{row['home_team_name']} vs {row['away_team_name']}"
                if self.similarity_engine.is_similar(db_match_name, match_name):
                    return dict(row), row['id']
        return None, None

    def update_match(self, match_name=None, match_date=None, tip=None, score=None, probability=None, match_id=None):
        """Update a match with new predictions."""
        if match_id:
            cursor = self.conn.execute('SELECT * FROM matches WHERE id = ?', (match_id,))
            row = cursor.fetchone()
            if row:
                match_dict = dict(row)
                match_db_id = row['id']
            else:
                match_dict = None
                match_db_id = None
        else:
            match_dict, match_db_id = self._find_match(match_name, match_date)

        if match_dict:
            # Handle tip updates
            if tip:
                existing_tips = self._deserialize_json(match_dict['predictions_tips']) or []
                tip_dict = tip.to_dict()
                if tip_dict not in existing_tips:
                    existing_tips.append(tip_dict)
                    self.conn.execute(
                        'UPDATE matches SET predictions_tips = ? WHERE id = ?',
                        (json.dumps(existing_tips), match_db_id)
                    )

            # Handle score updates
            if score:
                existing_scores = self._deserialize_json(match_dict['predictions_scores']) or []
                score_dict = score.__dict__
                if score_dict not in existing_scores:
                    existing_scores.append(score_dict)
                    self.conn.execute(
                        'UPDATE matches SET predictions_scores = ? WHERE id = ?',
                        (json.dumps(existing_scores), match_db_id)
                    )

            # Handle probability updates
            if probability:
                existing_probs = self._deserialize_json(match_dict['predictions_probabilities']) or []
                prob_dict = probability.__dict__
                if prob_dict not in existing_probs:
                    existing_probs.append(prob_dict)
                    self.conn.execute(
                        'UPDATE matches SET predictions_probabilities = ? WHERE id = ?',
                        (json.dumps(existing_probs), match_db_id)
                    )

            self.conn.commit()
            return match_db_id
        else:
            log(f"{match_name} was not found on forebet, investigate")
            return None

    def add_match(self, match, match_id=None):
        """Add or update a match in the database."""
        try:
            if match_id:
                cursor = self.conn.execute('SELECT * FROM matches WHERE id = ?', (match_id,))
                row = cursor.fetchone()
                if row:
                    found_match = dict(row)
                    found_match_id = row['id']
                else:
                    found_match = None
                    found_match_id = None
            else:
                found_match, found_match_id = self._find_match(
                    match.home_team.name + " vs " + match.away_team.name,
                    match.datetime
                )

            if found_match:
                log(f"Adding {match.home_team.name} vs {match.away_team.name} to match: {found_match['home_team_name']} vs {found_match['away_team_name']}")

                # Prepare updates
                updates = {}

                # Add tips
                if match.predictions.tips:
                    existing_tips = self._deserialize_json(found_match['predictions_tips']) or []
                    for tip in match.predictions.tips:
                        tip_dict = tip.to_dict()
                        if tip_dict not in existing_tips:
                            existing_tips.append(tip_dict)
                    updates['predictions_tips'] = json.dumps(existing_tips)

                # Add scores
                if match.predictions.scores:
                    existing_scores = self._deserialize_json(found_match['predictions_scores']) or []
                    for score in match.predictions.scores:
                        score_dict = score.__dict__
                        if score_dict not in existing_scores:
                            existing_scores.append(score_dict)
                    updates['predictions_scores'] = json.dumps(existing_scores)

                # Add probabilities
                if match.predictions.probabilities:
                    existing_probs = self._deserialize_json(found_match['predictions_probabilities']) or []
                    for probability in match.predictions.probabilities:
                        prob_dict = probability.__dict__
                        if prob_dict not in existing_probs:
                            existing_probs.append(prob_dict)
                    updates['predictions_probabilities'] = json.dumps(existing_probs)

                # Update h2h if missing
                if found_match['h2h'] is None and match.h2h is not None:
                    updates['h2h'] = self._serialize_json(match.h2h)

                # Update odds if missing
                if found_match['odds'] is None and match.odds is not None:
                    updates['odds'] = self._serialize_json(match.odds)

                # Execute all updates at once
                if updates:
                    set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
                    values = list(updates.values()) + [found_match_id]
                    self.conn.execute(
                        f'UPDATE matches SET {set_clause} WHERE id = ?',
                        values
                    )
                    self.conn.commit()

                return found_match_id
            else:
                log(f"Creating new match: {match.home_team.name} vs {match.away_team.name} [{str(match.datetime)}]")

                # Prepare match data
                home_stats = self._serialize_json(match.home_team.statistics) if match.home_team.statistics else None
                away_stats = self._serialize_json(match.away_team.statistics) if match.away_team.statistics else None
                h2h = self._serialize_json(match.h2h) if match.h2h else None
                odds = self._serialize_json(match.odds) if match.odds else None

                scores = json.dumps([s.__dict__ for s in match.predictions.scores]) if match.predictions.scores else None
                probabilities = json.dumps([p.__dict__ for p in match.predictions.probabilities]) if match.predictions.probabilities else None
                tips = json.dumps([t.to_dict() for t in match.predictions.tips]) if match.predictions.tips else None

                cursor = self.conn.execute('''
                    INSERT INTO matches (
                        home_team_name, home_team_league_points, home_team_form, home_team_statistics,
                        away_team_name, away_team_league_points, away_team_form, away_team_statistics,
                        datetime, h2h, predictions_scores, predictions_probabilities, predictions_tips, odds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match.home_team.name, match.home_team.league_points, match.home_team.form, home_stats,
                    match.away_team.name, match.away_team.league_points, match.away_team.form, away_stats,
                    match.datetime.isoformat(), h2h, scores, probabilities, tips, odds
                ))
                self.conn.commit()
                return cursor.lastrowid

        except Exception as e:
            print(f"Caught {e} while adding to db")
            return None

    def reset_matches_db(self):
        """Delete all matches from the database."""
        self.conn.execute('DELETE FROM matches')
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.conn.close()