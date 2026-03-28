from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
from scrape_kit import (
    BufferedStorageManager,
    SimilarityEngine,
    get_logger,
    time_profiler,
)
from scrape_kit.errors import StorageError

from .core.Match import Match, Odds, Score, asdict

logger = get_logger(__name__)


class MatchesManager(BufferedStorageManager):
    """
    Buffered SQLite match store with fuzzy-dedup on insert.

    Every add_match() call lands directly in the in-memory DataFrame via
    BufferedStorageManager.insert().  flush() writes the whole buffer back
    with DELETE + append (preserving schema/indexes unlike parent's replace).
    """

    def __init__(self, db_path: str, similarity_config: dict | None = None) -> None:
        if similarity_config:
            self.similarity_engine: SimilarityEngine | None = SimilarityEngine(
                similarity_config
            )
        else:
            self.similarity_engine = None
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
                    result_url         TEXT
                )
            """)
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_datetime  ON matches(datetime)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_home_team ON matches(home_team_name)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_away_team ON matches(away_team_name)"
            )
            self.conn.commit()

    # ── Flush: DELETE + append preserves indexes (unlike parent's replace) ────

    def flush(self) -> None:
        if not self._dirty or self._buffer is None:
            return
        with self.db_lock:
            try:
                self.conn.execute("DELETE FROM matches")
                if not self._buffer.empty:
                    self._buffer.to_sql(
                        "matches", self.conn, if_exists="append", index=False
                    )
                self.conn.commit()
                self._dirty = False
            except Exception as exc:
                raise StorageError(f"MatchesManager flush failed: {exc}") from exc

    # ── Similarity search inside the buffer ───────────────────────────────────

    def _find(
        self, home: str, away: str, dt: datetime
    ) -> tuple[dict | None, int | None]:
        buf = self.ensure_buffer()
        if self.similarity_engine is None or buf.empty:
            return None, None

        target = pd.Timestamp(dt.date().isoformat())
        dates = pd.to_datetime(buf["datetime"].str[:10], errors="coerce")
        mask = (dates >= target - pd.Timedelta(days=1)) & (
            dates <= target + pd.Timedelta(days=1)
        )

        best, best_idx, max_score = None, None, -1.0
        for idx, row in buf[mask].iterrows():
            rh, ra = row["home_team_name"], row["away_team_name"]
            if rh.lower() == home.lower() and ra.lower() == away.lower():
                return row.to_dict(), idx
            ok_h, sc_h = self.similarity_engine.is_similar(rh, home)
            if not ok_h:
                continue
            ok_a, sc_a = self.similarity_engine.is_similar(ra, away)
            if not ok_a:
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
                        "scores": self.deserialize_json(row["predictions_scores"])
                        or [],
                        "odds": self.deserialize_json(row["odds"]),
                        "result_url": row["result_url"],
                    }
                )
            except Exception as exc:
                logger.warning(f"skipping malformed row: {exc}")
        return pd.DataFrame(data)

    @time_profiler
    def add_match(self, match: Match) -> int | None:
        try:
            self.ensure_buffer()
            found, idx = self._find(match.home_team, match.away_team, match.datetime)

            # Source-collision guard
            if found is not None and match.predictions:
                ex_src = {
                    s.get("source")
                    for s in (
                        self.deserialize_json(found.get("predictions_scores")) or []
                    )
                    if s.get("source")
                }
                if not {s.source for s in match.predictions if s.source}.isdisjoint(
                    ex_src
                ):
                    logger.warning(
                        f"Source collision — skip {match.home_team} vs {match.away_team}"
                    )
                    found = None

            if found is not None:
                changed = False

                if match.predictions:
                    ex = self.deserialize_json(found.get("predictions_scores")) or []
                    ex_src = {s.get("source") for s in ex if s.get("source")}
                    for s in match.predictions:
                        if s.source not in ex_src:
                            ex.append(s.__dict__)
                            ex_src.add(s.source)
                            changed = True
                    if changed:
                        self._buffer.at[idx, "predictions_scores"] = json.dumps(ex)

                if match.datetime:
                    try:
                        ex_dt = datetime.fromisoformat(found["datetime"])
                        if (
                            ex_dt.hour == 0
                            and ex_dt.minute == 0
                            and (match.datetime.hour != 0 or match.datetime.minute != 0)
                        ):
                            self._buffer.at[idx, "datetime"] = (
                                match.datetime.isoformat()
                            )
                            changed = True
                    except Exception:
                        pass

                if match.odds:
                    cur = self.deserialize_json(found.get("odds")) or {}
                    patch = {
                        k: v
                        for k, v in asdict(match.odds).items()
                        if cur.get(k) is None and v is not None
                    }
                    if patch:
                        self._buffer.at[idx, "odds"] = self.serialize_json(
                            {**cur, **patch}
                        )
                        changed = True

                if match.result_url and not found.get("result_url"):
                    self._buffer.at[idx, "result_url"] = match.result_url
                    changed = True

                if changed:
                    self._dirty = True
                return idx

            # New row — lands directly in self._buffer via parent insert()
            self.insert(
                {
                    "home_team_name": match.home_team,
                    "away_team_name": match.away_team,
                    "datetime": match.datetime.isoformat(),
                    "predictions_scores": self.serialize_json(
                        [s.__dict__ for s in match.predictions]
                    )
                    if match.predictions
                    else None,
                    "odds": self.serialize_json(asdict(match.odds))
                    if match.odds
                    else None,
                    "result_url": match.result_url,
                }
            )
            return len(self._buffer) - 1

        except Exception as exc:
            logger.error(f"add_match error: {exc}")
            return None

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
                        predictions=[
                            Score(**s) for s in json.loads(row["predictions_scores"])
                        ]
                        if row["predictions_scores"]
                        else [],
                        odds=Odds(**json.loads(row["odds"])) if row["odds"] else None,
                        result_url=row["result_url"],
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
            chunks_dir, "matches", row_callback=_row, flush_callback=self.flush
        )
        logger.info(
            f"Merge complete: {processed} rows processed ({added} new, {merged} merged into existing)."
        )
