import glob
import os
import sqlite3
from datetime import datetime
import json
import threading
from typing import Optional
import pandas as pd
import time

from bet_framework.SimilarityEngine import SimilarityEngine

from .core.Match import *
from .utils import log


class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self.similarity_engine = SimilarityEngine()
        self.db_lock = threading.Lock()
        self._create_tables()
        self._file_mtime = os.path.getmtime(self.db_path)

        # ── In-memory buffer ──────────────────────────────────────────────────
        # Loaded lazily on first add_match call, flushed explicitly via
        # flush() or implicitly via close(). Column layout mirrors the DB.
        self._buffer: Optional[pd.DataFrame] = None   # None = not yet loaded
        self._pending_new_rows = []                   # List of new row dicts (O(1) append)
        self._buffer_dirty: bool = False              # True when pending writes exist
        # ──────────────────────────────────────────────────────────────────────

    # ─────────────────────────────── schema ──────────────────────────────────

    def _create_tables(self):
        """Create the matches table if it doesn't exist."""
        with self.db_lock:
            with self.conn:
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
                self.conn.execute('CREATE INDEX IF NOT EXISTS idx_datetime   ON matches(datetime)')
                self.conn.execute('CREATE INDEX IF NOT EXISTS idx_home_team  ON matches(home_team_name)')
                self.conn.execute('CREATE INDEX IF NOT EXISTS idx_away_team  ON matches(away_team_name)')

    # ─────────────────────────────── (de)serialization ───────────────────────

    def _serialize_json(self, obj):
        if obj is None:
            return None
        if hasattr(obj, '__dict__'):
            return json.dumps(obj.__dict__)
        return json.dumps(obj)

    def _deserialize_json(self, json_str):
        if json_str is None:
            return None
        return json.loads(json_str)

    def _row_to_match(self, row) -> Match:
        datetime_obj = datetime.fromisoformat(row['datetime'])
        predictions = []
        if row['predictions_scores']:
            predictions = [Score(**s) for s in self._deserialize_json(row['predictions_scores'])]
        odds = None
        if row['odds']:
            odds = Odds(**self._deserialize_json(row['odds']))
        return Match(
            home_team=row['home_team_name'],
            away_team=row['away_team_name'],
            datetime=datetime_obj,
            predictions=predictions,
            odds=odds,
            result_url=row['result_url']
        )

    # ─────────────────────────────── in-memory buffer ────────────────────────

    def _ensure_buffer(self):
        """Load the entire matches table into the in-memory DataFrame (once)."""
        if self._buffer is not None:
            return

        cursor = self.conn.execute(
            'SELECT id, home_team_name, away_team_name, datetime, '
            'predictions_scores, odds, result_url FROM matches'
        )
        rows = cursor.fetchall()

        if rows:
            self._buffer = pd.DataFrame(
                [dict(r) for r in rows],
                columns=['id', 'home_team_name', 'away_team_name', 'datetime',
                         'predictions_scores', 'odds', 'result_url']
            )
        else:
            self._buffer = pd.DataFrame(
                columns=['id', 'home_team_name', 'away_team_name', 'datetime',
                         'predictions_scores', 'odds', 'result_url']
            )

        # Use a high starting sentinel for new rows (negative = not yet in DB)
        self._next_temp_id = -1

    def _find_match_in_buffer(self, home_team: str, away_team: str, match_date):
        """
        Similarity search entirely inside the in-memory buffer (both DataFrame and pending list).
        Returns the BEST match based on average similarity score.
        Returns (row_dict | None, index | None, is_pending | bool).
        """
        date_str = match_date.date().isoformat()
        target = pd.Timestamp(date_str)

        best_row = None
        best_idx = None
        best_is_pending = False
        max_score = -1

        # 1. Search in DataFrame buffer
        if self._buffer is not None and not self._buffer.empty:
            dt_dates = pd.to_datetime(self._buffer['datetime'].str[:10], errors='coerce')
            mask = (dt_dates >= target - pd.Timedelta(days=1)) & (dt_dates <= target + pd.Timedelta(days=1))
            window = self._buffer[mask]

            for idx, row in window.iterrows():
                row_home = row['home_team_name']
                row_away = row['away_team_name']

                # Fast path: exact case-insensitive match (score is 100)
                if row_home.lower() == home_team.lower() and row_away.lower() == away_team.lower():
                    return row.to_dict(), idx, False

                is_sim_h, score_h = self.similarity_engine.is_similar(row_home, home_team)
                if not is_sim_h: continue
                is_sim_a, score_a = self.similarity_engine.is_similar(row_away, away_team)
                if not is_sim_a: continue

                avg = (score_h + score_a) / 2
                if avg > max_score:
                    max_score = avg
                    best_row = row.to_dict()
                    best_idx = idx
                    best_is_pending = False

        # 2. Search in pending list
        for i, row in enumerate(self._pending_new_rows):
            row_date = pd.Timestamp(row['datetime'][:10])
            if abs((row_date - target).days) > 1:
                continue

            row_home = row['home_team_name']
            row_away = row['away_team_name']

            # Fast path: exact
            if row_home.lower() == home_team.lower() and row_away.lower() == away_team.lower():
                return row, i, True

            is_sim_h, score_h = self.similarity_engine.is_similar(row_home, home_team)
            if not is_sim_h: continue
            is_sim_a, score_a = self.similarity_engine.is_similar(row_away, away_team)
            if not is_sim_a: continue

            avg = (score_h + score_a) / 2
            if avg > max_score:
                max_score = avg
                best_row = row
                best_idx = i
                best_is_pending = True

        return best_row, best_idx, best_is_pending

    def flush(self):
        """
        Write all pending in-memory changes to SQLite in a single transaction.
        Call this explicitly after a bulk add_match session for best performance.
        """
        if not self._buffer_dirty or self._buffer is None:
            return

        with self.db_lock:
            try:
                with self.conn:
                    # Use to_dict('records') to get a list of dicts.
                    # Mixing pandas Series and dicts in a list triggers 'dtype' errors during pd.DataFrame() conversion.
                    all_rows = self._buffer.to_dict('records') if self._buffer is not None else []
                    all_rows.extend(self._pending_new_rows)

                    cursor = self.conn.cursor()
                    for row in all_rows:
                        row_id = row['id']

                        if isinstance(row_id, (float, int)) and row_id < 0:
                            # New row — INSERT
                            cursor.execute('''
                                INSERT INTO matches
                                    (home_team_name, away_team_name, datetime,
                                     predictions_scores, odds, result_url)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                row['home_team_name'],
                                row['away_team_name'],
                                row['datetime'],
                                row['predictions_scores'],
                                row['odds'],
                                row['result_url']
                            ))
                            # Back-fill the real DB id so future lookups stay consistent
                            row['id'] = float(cursor.lastrowid)
                        else:
                            # Existing row — UPDATE
                            cursor.execute('''
                                UPDATE matches
                                SET predictions_scores = ?,
                                    odds              = ?,
                                    result_url        = ?
                                WHERE id = ?
                            ''', (
                                row['predictions_scores'],
                                row['odds'],
                                row['result_url'],
                                int(row_id)
                            ))

                    # Sync back to memory ONLY after successful commit (end of context)
                    self._buffer = pd.DataFrame(all_rows)
                    self._pending_new_rows = []
                    self._buffer_dirty = False

            except Exception as e:
                log(f"[DB] Flush failed: {e}")
                raise

    # ─────────────────────────────── public API ───────────────────────────────

    def fetch_matches(self) -> pd.DataFrame:
        """
        Fetch matches as a DataFrame. If there is a dirty buffer, flush first
        so the caller always sees a consistent view.
        """
        self.reopen_if_changed()

        if self._buffer_dirty:
            self.flush()

        cursor = self.conn.execute('''
            SELECT home_team_name, away_team_name, datetime,
                   predictions_scores, odds, result_url
            FROM matches
            ORDER BY datetime DESC
        ''')
        rows = cursor.fetchall()
        if not rows:
            return pd.DataFrame()

        data = []
        for row in rows:
            try:
                data.append({
                    'home_name':  row['home_team_name'],
                    'away_name':  row['away_team_name'],
                    'datetime':   datetime.fromisoformat(row['datetime']),
                    'scores':     self._deserialize_json(row['predictions_scores']) if row['predictions_scores'] else [],
                    'odds':       self._deserialize_json(row['odds']) if row['odds'] else None,
                    'result_url': row['result_url']
                })
            except Exception as e:
                print(f"Error processing row: {e}")
        return pd.DataFrame(data)

    def add_match(self, match, match_id=None):
        """
        Add or update a match entirely in-memory. No DB I/O happens here.
        Call flush() (or close()) to persist changes.
        """
        start_time = time.perf_counter()
        try:
            self._ensure_buffer()

            # ── Locate existing match ─────────────────────────────────────────
            found_row = None
            found_idx = None

            if match_id:
                # Direct id lookup in buffer
                id_mask = self._buffer['id'] == float(match_id)
                if id_mask.any():
                    found_idx = self._buffer[id_mask].index[0]
                    found_row = self._buffer.loc[found_idx].to_dict()
            else:
                # Use unified search in DataFrame buffer AND pending list
                found_row, found_idx, is_pending = self._find_match_in_buffer(
                    match.home_team, match.away_team, match.datetime
                )

                # Caution: this is a heuristic and may not always be correct.
                # Source unicity check: prevent merging if target match already contains
                # predictions from the same source(s) as the incoming match.
                if found_row is not None and match.predictions:
                    existing_scores = self._deserialize_json(found_row['predictions_scores']) or []
                    existing_sources = {s.get('source') for s in existing_scores if s.get('source') is not None}
                    new_sources = {s.source for s in match.predictions if s.source is not None}

                    if not new_sources.isdisjoint(existing_sources):
                        log(
                            f"⚠️ Collision detected: Source already exists in target match. "
                            f"Skipping merge for {match.home_team} vs {match.away_team} | "
                            f"{found_row['home_team_name']} vs {found_row['away_team_name']} | "
                            f"{found_row['predictions_scores']} | with new sources:"
                            f"{new_sources}"
                        )

                        found_row = None

            # ── Update existing ───────────────────────────────────────────────
            if found_row is not None:
                log(f"Adding {match.home_team} vs {match.away_team} to match: "
                    f"{found_row['home_team_name']} vs {found_row['away_team_name']}")

                changed = False

                # --- predictions_scores ---
                if match.predictions:
                    existing_scores = self._deserialize_json(found_row['predictions_scores']) or []
                    existing_sources = {s.get('source') for s in existing_scores if s.get('source') is not None}
                    for score in match.predictions:
                        if score.source not in existing_sources:
                            existing_scores.append(score.__dict__)
                            existing_sources.add(score.source)
                            changed = True
                    if changed:
                        ser = json.dumps(existing_scores)
                        found_row['predictions_scores'] = ser
                        if not is_pending:
                            self._buffer.at[found_idx, 'predictions_scores'] = ser

                # --- datetime ---
                # Update if incoming has a specific hour/minute and existing is roughly midnight (likely just a date placeholder)
                if match.datetime is not None:
                    try:
                        existing_dt = datetime.fromisoformat(found_row['datetime'])
                        if (existing_dt.hour == 0 and existing_dt.minute == 0 and 
                            (match.datetime.hour != 0 or match.datetime.minute != 0)):
                            log(f"Enriching time for {match.home_team} vs {match.away_team}: "
                                f"{existing_dt.isoformat()} -> {match.datetime.isoformat()}")
                            found_row['datetime'] = match.datetime.isoformat()
                            if not is_pending:
                                self._buffer.at[found_idx, 'datetime'] = match.datetime.isoformat()
                            changed = True
                    except Exception as e:
                        log(f"Error checking datetime update: {e}")

                # --- odds ---
                if match.odds is not None:
                    current_odds = self._deserialize_json(found_row.get('odds')) or {}
                    new_odds_map = asdict(match.odds)
                    # We patch if the EXISTING key is missing or is None (null in JSON)
                    # and the NEW value is a valid number.
                    patch = {k: v for k, v in new_odds_map.items()
                             if (k not in current_odds or current_odds[k] is None) and v is not None}
                    if patch:
                        updated_odds = {**current_odds, **patch}
                        ser = self._serialize_json(updated_odds)
                        found_row['odds'] = ser
                        if not is_pending:
                            self._buffer.at[found_idx, 'odds'] = ser
                        changed = True

                # --- result_url ---
                if match.result_url is not None and found_row.get('result_url') is None:
                    found_row['result_url'] = match.result_url
                    if not is_pending:
                        self._buffer.at[found_idx, 'result_url'] = match.result_url
                    changed = True

                if changed:
                    self._buffer_dirty = True

                return int(found_row['id']) if found_row['id'] >= 0 else found_row['id']

            # ── Insert new ────────────────────────────────────────────────────
            else:
                log(f"Creating new match: {match.home_team} vs {match.away_team} [{match.datetime}]")

                new_row = {
                    'id':                 float(self._next_temp_id),   # negative sentinel
                    'home_team_name':     match.home_team,
                    'away_team_name':     match.away_team,
                    'datetime':           match.datetime.isoformat(),
                    'predictions_scores': json.dumps([s.__dict__ for s in match.predictions]) if match.predictions else None,
                    'odds':               self._serialize_json(match.odds) if match.odds else None,
                    'result_url':         match.result_url,
                }
                self._next_temp_id -= 1

                self._pending_new_rows.append(new_row)
                self._buffer_dirty = True

                # Return the temp id (negative); real id assigned on flush()
                return new_row['id']

        except Exception as e:
            print(f"Caught {e} while adding to db")
            return None
        finally:
            duration = (time.perf_counter() - start_time) * 1000
            log(f"[DB] add_match took {duration:.2f}ms")

    def reset_matches_db(self):
        """Delete all matches from the database and clear the buffer."""
        with self.db_lock:
            with self.conn:
                self.conn.execute('DELETE FROM matches')
        self._buffer = None
        self._buffer_dirty = False

    def merge_databases(self, chunks_dir: str):
        """
        Merge all .db chunk files in chunks_dir into the current database.

        Strategy: load every chunk's rows directly into the in-memory buffer
        (via add_match) and flush once per chunk file. This avoids a commit
        after every single row while still keeping per-chunk atomicity so a
        failed chunk doesn't corrupt the main DB.
        """
        chunk_files = [
            f for f in os.listdir(chunks_dir)
            if f.endswith(".db") and f != os.path.basename(self.db_path)
        ]
        print(chunk_files)
        log(f"Merging {len(chunk_files)} databases from {chunks_dir}...")

        self._ensure_buffer()   # pre-load main DB into memory once

        for chunk_filename in chunk_files:
            chunk_path = os.path.join(chunks_dir, chunk_filename)
            log(f"🔄 Processing chunk: {chunk_filename}")
            try:
                chunk_conn = sqlite3.connect(chunk_path)
                chunk_conn.row_factory = sqlite3.Row

                cursor = chunk_conn.execute("SELECT * FROM matches")
                chunk_rows = cursor.fetchall()   # read all at once — no repeated I/O
                chunk_conn.close()

                for row in chunk_rows:
                    # Re-use the existing _row_to_match helper through a lightweight path:
                    # build a temporary Match object so similarity logic is unchanged.
                    datetime_obj = datetime.fromisoformat(row['datetime'])
                    predictions = []
                    if row['predictions_scores']:
                        predictions = [Score(**s) for s in json.loads(row['predictions_scores'])]
                    odds = None
                    if row['odds']:
                        odds = Odds(**json.loads(row['odds']))

                    match_obj = Match(
                        home_team=row['home_team_name'],
                        away_team=row['away_team_name'],
                        datetime=datetime_obj,
                        predictions=predictions,
                        odds=odds,
                        result_url=row['result_url']
                    )
                    self.add_match(match_obj)   # in-memory only

                # Flush once per chunk — single transaction per chunk file
                self.flush()
                log(f"✅ Successfully merged {chunk_filename}")

            except Exception as e:
                print(f"⚠️ Failed to merge chunk {chunk_path}: {e}")
                continue

        log("🏁 All database chunks have been merged.")

    def reopen_if_changed(self):
        """
        Check if the database file has been replaced on disk.
        If the mtime changed, close the old connection and open a fresh one.
        Called automatically by fetch_matches() before any read.
        """
        try:
            current_mtime = os.path.getmtime(self.db_path)
        except OSError:
            return  # file temporarily unavailable, do nothing

        if current_mtime == self._file_mtime:
            return  # nothing changed

        print(f"[DB] File change detected ({self.db_path}), reopening connection...")

        with self.db_lock:
            try:
                self.conn.close()
            except Exception:
                pass

            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

            # Clear in-memory buffer so it reloads from the new file
            self._buffer        = None
            self._pending_new_rows = []
            self._buffer_dirty  = False
            self._file_mtime    = current_mtime

        print("[DB] Reopened successfully.")
        
    def close(self):
        """Flush any pending writes and close the connection."""
        try:
            self.flush()
        except Exception as e:
            log(f"[DB] Final flush during close failed: {e}")
        self.conn.close()


