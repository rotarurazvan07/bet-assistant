from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
from scrape_kit import (
    BufferedStorageManager,
    SimilarityEngine,
    DedupConfig,
    get_logger,
)

from .core.Match import Match, asdict

logger = get_logger(__name__)


def _is_empty(value) -> bool:
    """Return True for None, any NaN/NA/NaT variant, or empty/whitespace string."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


class MatchesManager(BufferedStorageManager):
    """
    Buffered SQLite match store with fuzzy-dedup on insert and merge.
    
    Leverages Scrape-Kit v2 DedupConfig for standardized deduplication and merging.
    """

    def __init__(self, db_path: str, similarity_config: dict | None = None) -> None:
        self.similarity_engine = SimilarityEngine(similarity_config) if similarity_config else None
        super().__init__(db_path, "matches")

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
            self.create_index("matches", ["datetime"])
            self.create_index("matches", ["home_team_name"])
            self.create_index("matches", ["away_team_name"])
            self.conn.commit()

    def fetch_matches(self) -> pd.DataFrame:
        buf = self.ensure_buffer()
        if buf.empty:
            return pd.DataFrame()

        data = []
        for _, row in buf.iterrows():
            try:
                data.append({
                    "home_name": row["home_team_name"],
                    "away_name": row["away_team_name"],
                    "datetime": datetime.fromisoformat(row["datetime"]),
                    "scores": self.deserialize_json(row["predictions_scores"]) or [],
                    "odds": self.deserialize_json(row["odds"]),
                    "result_url": row["result_url"],
                })
            except Exception as exc:
                logger.warning(f"Skipping malformed row: {exc}")
        return pd.DataFrame(data)

    def add_match(self, match: Match) -> None:
        """Add or update a match using the DedupConfig logic."""
        config = self._get_dedup_config()
        data = {
            "home_team_name": match.home_team,
            "away_team_name": match.away_team,
            "datetime": match.datetime.isoformat(),
            "predictions_scores": json.dumps([s.__dict__ for s in match.predictions]) if match.predictions else None,
            "odds": json.dumps(asdict(match.odds)) if match.odds else None,
            "result_url": match.result_url,
        }
        
        self.upsert_with_dedup(data, config)

    def _get_dedup_config(self) -> DedupConfig:
        """Define how matches are deduplicated and merged."""
        return DedupConfig(
            similarity_fn=self._is_match_similar,
            merge_strategy=self._merge_matches,
            source_field="predictions_scores",
            source_key="source"
        )

    def _is_match_similar(self, a: dict, b: dict) -> bool:
        """Check if two match records are the same using fuzzy team names and date proximity."""
        # 1. Date check (+/- 1 day)
        try:
            dt_a = datetime.fromisoformat(a["datetime"]).date()
            dt_b = datetime.fromisoformat(b["datetime"]).date()
            if abs((dt_a - dt_b).days) > 1:
                return False
        except:
            return False

        # 2. Team similarity
        if not self.similarity_engine:
            return a["home_team_name"].lower() == b["home_team_name"].lower() and \
                   a["away_team_name"].lower() == b["away_team_name"].lower()

        h_ok, _ = self.similarity_engine.is_similar(a["home_team_name"], b["home_team_name"])
        if not h_ok: return False
        
        a_ok, _ = self.similarity_engine.is_similar(a["away_team_name"], b["away_team_name"])
        return a_ok

    def _merge_matches(self, existing: dict, new: dict) -> dict:
        """Custom merge logic for match records."""
        # 1. Merge predictions (avoid source duplicates)
        ex_preds = self.deserialize_json(existing.get("predictions_scores")) or []
        new_preds = self.deserialize_json(new.get("predictions_scores")) or []
        
        ex_sources = {p.get("source") for p in ex_preds if p.get("source")}
        for p in new_preds:
            if p.get("source") not in ex_sources:
                ex_preds.append(p)
                ex_sources.add(p.get("source"))
        
        existing["predictions_scores"] = json.dumps(ex_preds)

        # 2. Update Datetime (prefer specific time over midnight)
        try:
            dt_ex = datetime.fromisoformat(existing["datetime"])
            dt_new = datetime.fromisoformat(new["datetime"])
            if dt_ex.hour == 0 and dt_ex.minute == 0 and (dt_new.hour != 0 or dt_new.minute != 0):
                existing["datetime"] = new["datetime"]
        except:
            pass

        # 3. Merge Odds (patch missing values)
        ex_odds = self.deserialize_json(existing.get("odds")) or {}
        new_odds = self.deserialize_json(new.get("odds")) or {}
        for k, v in new_odds.items():
            if _is_empty(ex_odds.get(k)) and not _is_empty(v):
                ex_odds[k] = v
        existing["odds"] = json.dumps(ex_odds)

        # 4. Result URL
        if not existing.get("result_url") and new.get("result_url"):
            existing["result_url"] = new["result_url"]

        return existing

    def merge_databases(self, chunks_dir: str) -> None:
        """Perform a high-speed merge of chunk databases with deduplication."""
        logger.info(f"Merging match chunks from {chunks_dir}...")
        report = self.merge_with_dedup(
            input_dir=chunks_dir,
            dedup_config=self._get_dedup_config()
        )
        logger.info(f"Merge complete: Processed {report.processed_rows} rows from {report.processed_chunks} chunks.")

    def reset_matches_db(self) -> None:
        self.clear_database("matches")
