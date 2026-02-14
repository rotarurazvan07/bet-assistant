import glob
import os
import sqlite3
from datetime import datetime
import json
import threading
from typing import Optional
import pandas as pd

from bet_framework.SimilarityEngine import SimilarityEngine

from .core.Match import *
from .utils import log

class DatabaseManager:
    def __init__(self, db_path: str = None):
        # Enable WAL mode for concurrent reads/writes
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.row_factory = sqlite3.Row

        self.similarity_engine = SimilarityEngine()
        self.db_lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        """Create the matches table if it doesn't exist."""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_team_name TEXT NOT NULL,
                away_team_name TEXT NOT NULL,
                datetime TEXT NOT NULL,
                predictions_scores TEXT,
                odds TEXT,
                result_url TEXT
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
        home_team = row['home_team_name']
        away_team = row['away_team_name']
        result_url = row ['result_url']

        # Parse predictions
        predictions = []
        if row['predictions_scores']:
            predictions = [Score(**s) for s in self._deserialize_json(row['predictions_scores'])]

        # Parse odds
        odds = None
        if row['odds']:
            odds = Odds(**self._deserialize_json(row['odds']))

        return Match(
            home_team=home_team,
            away_team=away_team,
            datetime=datetime_obj,
            predictions=predictions,
            odds=odds,
            result_url=result_url
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
                away_team_name,
                datetime,
                predictions_scores,
                odds,
                result_url
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
                result_url = row['result_url']
                dt_str = row['datetime']
                dt = datetime.fromisoformat(dt_str)

                # Deserialize only what we need
                scores_data = self._deserialize_json(row['predictions_scores']) if row['predictions_scores'] else []
                odds_data = self._deserialize_json(row['odds']) if row['odds'] else None

                data.append({
                    'home_name': home_name,
                    'away_name': away_name,
                    'datetime': dt,
                    'scores': scores_data,
                    'odds': odds_data,
                    'result_url': result_url
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

        found_match_row = found_match_row_id = None
        max_score = -1

        for row in cursor:
            # TODO - similirity on both names then compute here, similiraty engine to be generic
            db_match_name = f"{row['home_team_name']} vs {row['away_team_name']}"
            is_similar, score = self.similarity_engine.is_similar(db_match_name, match_name)
            if is_similar and score > max_score:
                max_score = score
                found_match_row = dict(row)
                found_match_row_id = row['id']
        return found_match_row, found_match_row_id

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
                    match.home_team + " vs " + match.away_team,
                    match.datetime
                )

            if found_match:
                log(f"Adding {match.home_team} vs {match.away_team} to match: {found_match['home_team_name']} vs {found_match['away_team_name']}")

                # Prepare updates
                updates = {}

                # Add scores
                if match.predictions:
                    existing_scores = self._deserialize_json(found_match['predictions_scores']) or []
                    for score in match.predictions:
                        score_dict = score.__dict__
                        if score_dict not in existing_scores:
                            existing_scores.append(score_dict)
                    updates['predictions_scores'] = json.dumps(existing_scores)

                if match.odds is not None:
                    current_odds = self._deserialize_json(found_match.get('odds')) or {}
                    new_odds_map = asdict(match.odds)
                    patch = {
                        k: v for k, v in new_odds_map.items()
                        if current_odds.get(k) is None and v is not None
                    }

                    if patch:
                        updated_odds = {**current_odds, **patch}
                        updates['odds'] = self._serialize_json(updated_odds)

                if match.result_url is not None and found_match["result_url"] is None:
                    updates['result_url'] = match.result_url

                # Execute all updates at once
                with self.db_lock:
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
                log(f"Creating new match: {match.home_team} vs {match.away_team} [{str(match.datetime)}]")

                # Prepare match data
                odds = self._serialize_json(match.odds) if match.odds else None

                scores = json.dumps([s.__dict__ for s in match.predictions]) if match.predictions else None

                with self.db_lock:
                    cursor = self.conn.execute('''
                        INSERT INTO matches (
                            home_team_name,
                            away_team_name,
                            datetime, predictions_scores, odds, result_url
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        match.home_team,
                        match.away_team,
                        match.datetime.isoformat(), scores, odds, match.result_url
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

    def merge_databases(self, chunks_dir: str):
        """
        Iterates through all .db files in chunks_dir, converts their rows
        into Match objects, and merges them into the current database
        using the similarity-aware add_match logic.
        """
        # 1. Find all chunk files
        # We use absolute paths to ensure we don't accidentally try to merge the main DB
        chunk_files = [
            f for f in os.listdir(chunks_dir)
            if f.endswith(".db")
            and f != self.db_path
        ]

        print(chunk_files)

        # Identify current DB to avoid self-merging
        # We can't use self.conn.path in all versions, so we rely on path comparison
        log(f"Merging {len(chunk_files)} databases from {chunks_dir}...")

        for chunk_path in chunk_files:
            log(f"🔄 Processing chunk: {os.path.basename(chunk_path)}")

            try:
                # 2. Open the chunk as a temporary DatabaseManager
                # This gives us access to _row_to_match and the connection logic
                chunk_mgr = DatabaseManager(chunk_path)

                # 3. Fetch all raw rows from the chunk
                cursor = chunk_mgr.conn.execute("SELECT * FROM matches")
                chunk_rows = cursor.fetchall()

                for row in chunk_rows:
                    # 4. Convert row back into a proper Match object
                    # This handles the JSON deserialization of scores and odds
                    match_obj = chunk_mgr._row_to_match(row)

                    # 5. Add to the MAIN database (self)
                    # This triggers the similarity engine check automatically
                    self.add_match(match_obj)

                # 6. Cleanup chunk connection
                chunk_mgr.close()
                log(f"✅ Successfully merged {os.path.basename(chunk_path)}")

            except Exception as e:
                print(f"⚠️ Failed to merge chunk {chunk_path}: {e}")
                continue

        log("🏁 All database chunks have been merged.")

    def close(self):
        self.conn.commit()
        # 1. Flush the logs into the main file
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        # 2. Transition back to a single-file mode (deletes the -wal file)
        self.conn.execute("PRAGMA journal_mode=DELETE;")
        # 3. Clean up the connection
        self.conn.close()