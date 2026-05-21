from __future__ import annotations

import json
from datetime import datetime
from typing import NamedTuple

import pandas as pd
from scrape_kit import (
    BufferedStorageManager,
    SimilarityEngine,
    get_logger,
    time_profiler,
)

from bet_dashboard.backend.core.market_config import MARKET_DEFINITIONS

from .core.Match import Match, Odds, Score, asdict

logger = get_logger(__name__)


class NearMiss(NamedTuple):
    home_a: str
    away_a: str
    home_b: str
    away_b: str
    score: float
    source_a: str
    source_b: str


def _is_empty(value) -> bool:
    """Return True for None, any NaN/NA/NaT variant, or empty/whitespace string."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        # pd.isna raises TypeError for non-scalar containers (list, dict, Odds…)
        pass
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


class MatchesManager(BufferedStorageManager):
    """
    Buffered SQLite match store with fuzzy-dedup on insert.

    Every add_match() call lands directly in the in-memory DataFrame via
    BufferedStorageManager.insert().  flush() writes the whole buffer back
    with DELETE + append (preserving schema/indexes unlike parent's replace).
    """

    def __init__(self, db_path: str, similarity_config: dict | None = None) -> None:
        if similarity_config:
            self.similarity_engine: SimilarityEngine | None = SimilarityEngine(similarity_config)
        else:
            self.similarity_engine = None
        self._near_misses: list[NearMiss] = []
        super().__init__(db_path, "matches")

    # ── Schema ────────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        with self.db_lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    home_team_name     TEXT NOT NULL,
                    away_team_name     TEXT NOT NULL,
                    datetime           TEXT NOT NULL,
                    predictions_scores TEXT,
                    odds               TEXT,
                    result_url         TEXT,
                    league             TEXT
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_datetime  ON matches(datetime)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_home_team ON matches(home_team_name)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_away_team ON matches(away_team_name)")

            # Schema Migration: Add league column to matches if it doesn't exist
            cursor = self.conn.execute("PRAGMA table_info(matches)")
            columns = [row[1] for row in cursor.fetchall()]
            if "league" not in columns:
                self.conn.execute("ALTER TABLE matches ADD COLUMN league TEXT")

            self.conn.commit()

    # ── Similarity search inside the buffer ───────────────────────────────────

    def _find(self, home: str, away: str, dt: datetime) -> tuple[dict | None, int | None]:
        buf = self.ensure_buffer()
        if buf.empty:
            return None, None

        target = pd.Timestamp(dt.date().isoformat())
        dates = pd.to_datetime(buf["datetime"].str[:10], errors="coerce")
        mask = (dates >= target - pd.Timedelta(days=1)) & (dates <= target + pd.Timedelta(days=1))

        best, best_idx, max_score = None, None, -1.0
        for idx, row in buf[mask].iterrows():
            rh, ra = row["home_team_name"], row["away_team_name"]
            # Exact match always wins
            if rh.lower() == home.lower() and ra.lower() == away.lower():
                return row.to_dict(), idx

            # Fuzzy matching only if similarity_engine is available
            if self.similarity_engine is not None:
                ok_h, sc_h = self.similarity_engine.is_similar(rh, home)
                if not ok_h:
                    # Near-miss: check away too for score tracking
                    if sc_h >= 30:
                        _, sc_a = self.similarity_engine.is_similar(ra, away)
                        combined = (sc_h + sc_a) / 2
                        if 40 <= combined < 65:
                            self._near_misses.append(NearMiss(home, away, rh, ra, combined, "", ""))
                    continue
                ok_a, sc_a = self.similarity_engine.is_similar(ra, away)
                if not ok_a:
                    combined = (sc_h + sc_a) / 2
                    if 40 <= combined < 65:
                        self._near_misses.append(NearMiss(home, away, rh, ra, combined, "", ""))
                    continue
                avg = (sc_h + sc_a) / 2
                if avg > max_score:
                    max_score, best, best_idx = avg, row.to_dict(), idx

        return best, best_idx

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_matches(self) -> pd.DataFrame:
        self.reopen_if_changed()
        buf = self.ensure_buffer()
        if buf.empty:
            return pd.DataFrame()

        data = []
        for _, row in buf.iterrows():
            try:
                data.append(
                    {
                        "home_name": row["home_team_name"],
                        "away_name": row["away_team_name"],
                        "datetime": datetime.fromisoformat(row["datetime"]),
                        "scores": self.deserialize_json(row["predictions_scores"]) or [],
                        "odds": self.deserialize_json(row["odds"]),
                        "result_url": row["result_url"],
                        "league": row["league"],
                    }
                )
            except Exception as exc:
                logger.warning(f"skipping malformed row: {exc}")
        return pd.DataFrame(data)

    @time_profiler
    def add_match(self, match: Match) -> int | None:
        """Add or update a match in the buffer.

        Returns the index of the match in the buffer, or None on error.
        """
        try:
            self.ensure_buffer()
            found, idx = self._find(match.home_team, match.away_team, match.datetime)

            # Source-collision guard
            if found is not None and match.predictions:
                ex_src = {
                    s.get("source") for s in (self.deserialize_json(found.get("predictions_scores")) or []) if s.get("source")
                }
                if not {s.source for s in match.predictions if s.source}.isdisjoint(ex_src):
                    logger.warning(f"Source collision — skip {match.home_team} vs {match.away_team}")
                    found = None

            if found is None:
                return self._insert_new_match(match)

            # Update existing match
            changed = self._update_existing_match(match, found, idx)
            if changed:
                self._dirty = True
            return idx

        except Exception as exc:
            logger.error(f"add_match error: {exc}")
            return None

    def _insert_new_match(self, match: Match) -> int:
        """Insert a new match into the buffer."""
        self.insert(
            {
                "home_team_name": match.home_team,
                "away_team_name": match.away_team,
                "datetime": match.datetime.isoformat(),
                "predictions_scores": self.serialize_json([s.__dict__ for s in match.predictions])
                if match.predictions
                else None,
                "odds": self.serialize_json(asdict(match.odds)) if match.odds else None,
                "result_url": match.result_url,
                "league": match.league,
            }
        )
        return len(self._buffer) - 1

    def _update_existing_match(self, match: Match, found: dict, idx: int) -> bool:
        """Update an existing match in the buffer. Returns True if changes were made."""
        changed = False

        if not _is_empty(match.predictions):
            pred_changed = self._update_predictions(match, found, idx)
            changed = pred_changed or changed
            if pred_changed:
                logger.info(
                    f"Updating predictions for {match.home_team} vs {match.away_team} "
                    f"with new source(s): {[s.source for s in match.predictions if s.source]}"
                )

        if not _is_empty(match.datetime):
            dt_changed = self._update_datetime(match, found, idx)
            changed = dt_changed or changed
            if dt_changed:
                logger.info(
                    f"Updating datetime for {match.home_team} vs {match.away_team} "
                    f"from {found.get('datetime')} to {match.datetime}"
                )

        if not _is_empty(match.odds):
            odds_changed = self._update_odds(match, found, idx)
            changed = odds_changed or changed
            if odds_changed:
                logger.info(f"Updating odds for {match.home_team} vs {match.away_team} with new values: {asdict(match.odds)}")

        if not _is_empty(match.result_url) and _is_empty(found.get("result_url")):
            logger.info(f"Updating result_url for {match.home_team} vs {match.away_team} from None to {match.result_url}")
            self._buffer.at[idx, "result_url"] = match.result_url
            changed = True

        if not _is_empty(match.league) and _is_empty(found.get("league")):
            logger.info(f"Updating league for {match.home_team} vs {match.away_team} to {match.league}")
            self._buffer.at[idx, "league"] = match.league
            changed = True

        return changed

    def _update_predictions(self, match: Match, found: dict, idx: int) -> bool:
        """Merge predictions from the new match into existing ones. Returns True if changed."""
        ex = self.deserialize_json(found.get("predictions_scores")) or []
        ex_src = {s.get("source") for s in ex if s.get("source")}
        changed = False

        for s in match.predictions:
            if s.source not in ex_src:
                ex.append(s.__dict__)
                ex_src.add(s.source)
                changed = True

        if changed:
            self._buffer.at[idx, "predictions_scores"] = json.dumps(ex)
        return changed

    def _update_datetime(self, match: Match, found: dict, idx: int) -> bool:
        """Update datetime if existing has midnight time and new has specific time. Returns True if changed."""
        try:
            ex_dt = datetime.fromisoformat(found["datetime"])
            if ex_dt.hour == 0 and ex_dt.minute == 0 and (match.datetime.hour != 0 or match.datetime.minute != 0):
                self._buffer.at[idx, "datetime"] = match.datetime.isoformat()
                return True
        except Exception:
            pass
        return False

    def _update_odds(self, match: Match, found: dict, idx: int) -> bool:
        cur = self.deserialize_json(found.get("odds")) or {}
        patch = {k: v for k, v in asdict(match.odds).items() if _is_empty(cur.get(k)) and not _is_empty(v)}
        if patch:
            self._buffer.at[idx, "odds"] = self.serialize_json({**cur, **patch})
            return True
        return False

    def reset_matches_db(self) -> None:
        self.clear_database("matches")  # clears buffer + dirty flag (inherited)

    def merge_databases(self, chunks_dir: str) -> None:
        self.ensure_buffer()
        logger.info(f"Merging chunks from {chunks_dir}")

        processed = 0
        added = 0
        merged = 0

        def _row(row) -> None:
            nonlocal processed, added, merged
            processed += 1
            initial_count = len(self._buffer) if self._buffer is not None else 0
            try:
                # add_match returns the row index where it landed/updated
                idx = self.add_match(
                    Match(
                        home_team=row["home_team_name"],
                        away_team=row["away_team_name"],
                        datetime=datetime.fromisoformat(row["datetime"]),
                        predictions=[Score(**s) for s in json.loads(row["predictions_scores"])]
                        if row["predictions_scores"]
                        else [],
                        odds=Odds(**json.loads(row["odds"])) if row["odds"] else None,
                        result_url=row["result_url"],
                        league=row["league"],
                    )
                )
                new_count = len(self._buffer) if self._buffer is not None else 0
                if new_count > initial_count:
                    added += 1
                elif idx is not None:
                    merged += 1

                if processed % 100 == 0:
                    logger.info(f"  Processed {processed} rows...")

            except Exception as exc:
                logger.error(f"merge row error: {exc}")

        self.merge_row_by_row(
            chunks_dir,
            "matches",
            row_callback=_row,
            flush_callback=self.flush,
            read_batch_size=2000,
            flush_every_rows=5000,
        )
        self.flush()
        self._log_near_misses()
        self._clear_near_misses()
        logger.info(f"Merge complete: {processed} rows processed ({added} new, {merged} merged into existing).")

    # ── Near-miss logging ──────────────────────────────────────────────────────

    def _log_near_misses(self) -> None:
        """Log near-miss pairs for synonym discovery."""
        if not self._near_misses:
            return
        seen: set[tuple[str, str, str, str]] = set()
        unique: list[NearMiss] = []
        for nm in sorted(self._near_misses, key=lambda x: x.score, reverse=True):
            key = (nm.home_a, nm.away_a, nm.home_b, nm.away_b)
            if key not in seen:
                seen.add(key)
                unique.append(nm)
        logger.warning(f"=== NEAR-MISS REPORT: {len(unique)} pairs (score 40-65) ===")
        for nm in unique:
            logger.warning(
                f"  [{nm.score:.0f}] {nm.home_a} vs {nm.away_a} "
                f"<-> {nm.home_b} vs {nm.away_b}"
            )
        logger.warning("=== END NEAR-MISS REPORT ===")

    def _clear_near_misses(self) -> None:
        """Clear tracked near-misses."""
        self._near_misses.clear()

    # ── Embedded Odds History ──────────────────────────────────────────────────

    @staticmethod
    def _extract_history_from_odds(odds_dict: dict | None) -> list[dict]:
        """Extract the history array from an odds dict, or return empty list."""
        if not odds_dict:
            return []
        return odds_dict.get("history", [])

    @staticmethod
    def _get_current_odds_snapshot(odds_dict: dict | None) -> dict:
        """Extract current odds values (excluding history) for snapshot storage."""
        if not odds_dict:
            return {}
        return {k: v for k, v in odds_dict.items() if k != "history" and v is not None}

    @staticmethod
    def _append_to_history(current_odds: dict, new_snapshot: dict, max_entries: int) -> dict:
        """Append a snapshot to history array, trim to max_entries, return updated odds dict.

        Args:
            current_odds: The current odds dict (may contain history)
            new_snapshot: Dict with timestamp 'ts' and market values
            max_entries: Maximum number of history entries to keep
        """
        if not new_snapshot or not any(v for k, v in new_snapshot.items() if k != "ts"):
            return current_odds

        history = list(current_odds.get("history", []))
        history.append(new_snapshot)

        # Trim to max_entries (keep most recent)
        if len(history) > max_entries:
            history = history[-max_entries:]

        result = {k: v for k, v in current_odds.items() if k != "history"}
        result["history"] = history
        return result

    def get_odds_history_from_row(self, row_idx: int) -> list[dict]:
        """Get odds history from a match row's embedded odds JSON."""
        buf = self.ensure_buffer()
        if buf.empty or row_idx < 0 or row_idx >= len(buf):
            return []

        odds_json = buf.iloc[row_idx].get("odds")
        odds_dict = self.deserialize_json(odds_json) if odds_json else {}
        history = self._extract_history_from_odds(odds_dict)

        # Convert embedded format to API format
        return [{"timestamp": h.get("ts", ""), "odds": {k: v for k, v in h.items() if k != "ts"}} for h in history]

    def calculate_movement_from_odds(self, odds_dict: dict | None) -> dict:
        """Calculate movement from embedded history in odds dict.

        Returns dict with keys like 'home', 'draw', 'away', etc.
        Values are 'up', 'down', 'stable', or None if no data.
        """
        if not odds_dict:
            return {}

        history = self._extract_history_from_odds(odds_dict)
        current = self._get_current_odds_snapshot(odds_dict)

        if not history or not current:
            return {}

        # Compare first historical snapshot to current values
        first_odds = history[0]
        # Derive simplified market keys from central configuration (strip 'odds_' prefix)
        markets = [md.odds_key.replace("odds_", "") for md in MARKET_DEFINITIONS]
        movement = {}

        for market in markets:
            first_val = first_odds.get(market)
            current_val = current.get(market)

            if first_val is None or current_val is None:
                movement[market] = None
            elif current_val > first_val:
                movement[market] = "up"
            elif current_val < first_val:
                movement[market] = "down"
            else:
                movement[market] = "stable"

        return movement

    def calculate_movement_with_strength(self, odds_dict: dict | None) -> dict:
        """Calculate movement with strength metrics for significance filtering.

        Returns dict mapping market -> {direction, change_pct, significant}.
        A movement is significant if |change_pct| >= 5% relative change
        OR |absolute_change| >= 0.10 for low odds (< 2.0).
        Requires at least 2 history snapshots to be considered significant.
        """
        if not odds_dict:
            return {}
        history = self._extract_history_from_odds(odds_dict)
        current = self._get_current_odds_snapshot(odds_dict)
        if not history or not current:
            return {}
        first_odds = history[0]
        markets = [md.odds_key.replace("odds_", "") for md in MARKET_DEFINITIONS]
        has_enough_history = len(history) >= 2
        result: dict = {}
        for market in markets:
            first_val = first_odds.get(market)
            current_val = current.get(market)
            if first_val is None or current_val is None:
                result[market] = {"direction": None, "change_pct": 0.0, "significant": False}
                continue
            if first_val == 0:
                change_pct = 0.0
            else:
                change_pct = round(((current_val - first_val) / abs(first_val)) * 100, 2)
            abs_change = abs(current_val - first_val)
            if current_val > first_val:
                direction = "up"
            elif current_val < first_val:
                direction = "down"
            else:
                direction = "stable"
            significant = False
            if has_enough_history and direction != "stable":
                if abs(change_pct) >= 5.0:
                    significant = True
                elif first_val < 2.0 and abs_change >= 0.10:
                    significant = True
            result[market] = {"direction": direction, "change_pct": change_pct, "significant": significant}
        return result

    def get_movement_for_row(self, row_idx: int) -> dict:
        """Get odds movement for a specific row index."""
        buf = self.ensure_buffer()
        if buf.empty or row_idx < 0 or row_idx >= len(buf):
            return {}

        odds_json = buf.iloc[row_idx].get("odds")
        odds_dict = self.deserialize_json(odds_json) if odds_json else {}
        return self.calculate_movement_from_odds(odds_dict)

    def merge_with_history_preservation(self, fresh_db_path: str, max_history: int = 3, local_tz: str = "UTC") -> None:
        """Merge fresh database while preserving odds history from current data.

        Flow:
        1. Load current matches and prune those with datetime < today (local_tz)
        2. Load fresh database
        3. For each remaining current match, fuzzy-match to fresh DB
        4. On match: append current odds as history entry to fresh row
        5. Replace current buffer with merged fresh data
        """
        from zoneinfo import ZoneInfo

        try:
            tz = ZoneInfo(local_tz)
        except Exception:
            tz = ZoneInfo("UTC")

        now_local = datetime.now(tz)
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        timestamp = now_local.isoformat()

        # Get current matches that are still future (not past)
        current_buf = self.ensure_buffer()
        future_matches = []

        if not current_buf.empty:
            for _idx, row in current_buf.iterrows():
                try:
                    match_dt_str = row.get("datetime", "")
                    match_dt = datetime.fromisoformat(match_dt_str)
                    # Make timezone-aware for comparison
                    if match_dt.tzinfo is None:
                        match_dt = match_dt.replace(tzinfo=tz)
                    if match_dt >= today_start:
                        odds_dict = self.deserialize_json(row.get("odds")) if row.get("odds") else {}
                        future_matches.append(
                            {
                                "home": row["home_team_name"],
                                "away": row["away_team_name"],
                                "datetime": match_dt,
                                "odds": odds_dict,
                            }
                        )
                except Exception as exc:
                    logger.debug(f"Skipping row during history preservation: {exc}")

        logger.info(f"Found {len(future_matches)} future matches with potential history to preserve")

        # Load fresh database into a temporary manager
        import os
        fresh_file_size = os.path.getsize(fresh_db_path) if os.path.exists(fresh_db_path) else -1
        logger.info(f"Loading fresh DB from {fresh_db_path} (size: {fresh_file_size} bytes)")
        fresh_manager = MatchesManager(fresh_db_path, self.similarity_engine._config if self.similarity_engine else None)
        fresh_buf = fresh_manager.ensure_buffer()
        logger.info(f"Fresh buffer: {len(fresh_buf)} rows, columns: {list(fresh_buf.columns) if not fresh_buf.empty else 'N/A'}")

        if fresh_buf.empty:
            logger.warning("Fresh database is empty, nothing to merge")
            return

        # For each future match from current DB, try to find it in fresh DB and transfer history
        transferred = 0
        for match_data in future_matches:
            try:
                if not match_data["odds"]:
                    continue

                # Use fuzzy matching to find corresponding row in fresh DB
                found, fresh_idx = fresh_manager._find(match_data["home"], match_data["away"], match_data["datetime"])

                if found is not None and fresh_idx is not None:
                    # Create snapshot from current odds
                    snapshot = {"ts": timestamp}
                    current_odds = self._get_current_odds_snapshot(match_data["odds"])
                    snapshot.update(current_odds)

                    # Get fresh row's odds and append history
                    fresh_odds_json = fresh_buf.at[fresh_idx, "odds"]
                    fresh_odds = fresh_manager.deserialize_json(fresh_odds_json) if (fresh_odds_json and not pd.isna(fresh_odds_json)) else {}
                    fresh_odds = fresh_odds or {}

                    # Preserve existing history from current match
                    existing_history = self._extract_history_from_odds(match_data["odds"])

                    # Merge histories: existing + new snapshot
                    combined_odds = dict(fresh_odds)
                    combined_odds["history"] = existing_history

                    # Append current snapshot
                    combined_odds = self._append_to_history(combined_odds, snapshot, max_history)

                    # Update fresh buffer
                    fresh_buf.at[fresh_idx, "odds"] = fresh_manager.serialize_json(combined_odds)
                    fresh_manager._dirty = True
                    transferred += 1
            except Exception as exc:
                logger.error(f"History transfer error for {match_data.get('home')} vs {match_data.get('away')}: {exc}")

        logger.info(f"Transferred odds history to {transferred} matches in fresh database")

        # Transfer data via buffer to avoid file locking issues (WinError 32)
        # Capture the merged fresh buffer before closing anything
        merged_buffer = fresh_buf.copy()
        logger.info(f"Captured {len(merged_buffer)} rows from fresh database into memory")

        # Close fresh manager to release file lock
        fresh_manager.close()
        del fresh_manager

        # Clear our database and replace with merged data
        self.reset_matches_db()
        self._buffer = merged_buffer.reset_index(drop=True)
        self._dirty = True
        self.flush()

        logger.info(f"Database merge complete: {len(self._buffer)} rows written to {self.db_path}")
