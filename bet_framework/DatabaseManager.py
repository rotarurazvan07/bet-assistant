import sqlite3
from datetime import datetime
import json
from typing import Optional
import pandas as pd

from bet_framework.SimilarityEngine import SimilarityEngine

from .core.Match import *
from .core.Tip import Tip
from .utils import log


class DatabaseManager:
    def __init__(self, db_path: str = None):
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

        # Create indexes for fast read performance
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_datetime ON matches(datetime)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_home_team ON matches(home_team_name)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_away_team ON matches(away_team_name)
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

    def fetch_matches(self) -> pd.DataFrame:
        """
        Optimized method to fetch matches directly as a DataFrame.
        Skips Match object creation and only deserializes fields needed by BettingAnalyzer.

        This is MUCH faster than fetch_matches() -> Match objects -> DataFrame conversion.
        """
        # Only select columns we actually need - skip statistics which are heavy
        cursor = self.conn.execute('''
            SELECT
                home_team_name,
                home_team_league_points,
                home_team_form,
                away_team_name,
                away_team_league_points,
                away_team_form,
                datetime,
                h2h,
                predictions_scores,
                predictions_probabilities,
                odds
            FROM matches
            ORDER BY datetime DESC
        ''')

        rows = cursor.fetchall()

        if not rows:
            return pd.DataFrame()

        # Build DataFrame rows with minimal deserialization
        data = []
        for row in rows:
            try:
                # Basic fields (no deserialization needed)
                home_name = row['home_team_name']
                away_name = row['away_team_name']
                home_lp = row['home_team_league_points'] or 0
                away_lp = row['away_team_league_points'] or 0
                home_form = row['home_team_form'] or ''
                away_form = row['away_team_form'] or ''
                dt_str = row['datetime']
                dt = datetime.fromisoformat(dt_str)

                # Deserialize only what we need
                h2h_data = self._deserialize_json(row['h2h']) if row['h2h'] else None
                scores_data = self._deserialize_json(row['predictions_scores']) if row['predictions_scores'] else []
                probs_data = self._deserialize_json(row['predictions_probabilities']) if row['predictions_probabilities'] else []
                odds_data = self._deserialize_json(row['odds']) if row['odds'] else None

                data.append({
                    'home_name': home_name,
                    'away_name': away_name,
                    'home_league_points': home_lp,
                    'away_league_points': away_lp,
                    'home_form': home_form,
                    'away_form': away_form,
                    'datetime': dt,
                    'h2h': h2h_data,
                    'scores': scores_data,
                    'probabilities': probs_data,
                    'odds': odds_data,
                })

            except Exception as e:
                print(f"Error processing row: {e}")
                continue

        return pd.DataFrame(data)

    def _find_match(self, match_name, match_date):
        """Find a match by name and date using similarity matching."""
        # Optimized: Use date filter in SQL first, then iterate only on matching dates
        date_str = match_date.date().isoformat()

        cursor = self.conn.execute('''
            SELECT * FROM matches
            WHERE date(datetime) BETWEEN date(?, '-1 day') AND date(?, '+1 day')
        ''', (date_str, date_str))

        for row in cursor:
            db_match_name = f"{row['home_team_name']} vs {row['away_team_name']}"
            if self.similarity_engine.is_similar(db_match_name, match_name):
                return dict(row), row['id']
        return None, None

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
        self.conn.commit()
        # 1. Flush the logs into the main file
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        # 2. Transition back to a single-file mode (deletes the -wal file)
        self.conn.execute("PRAGMA journal_mode=DELETE;")
        # 3. Clean up the connection
        self.conn.close()