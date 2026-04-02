"""
BetAssistant — All-in-one sports betting toolkit.
══════════════════════════════════════════════════

Combines three concerns into a single, self-contained module:

  1. ANALYSIS & SLIP BUILDING  — Score and select picks from a match DataFrame.
  2. SLIP STORAGE              — Persist slips/legs in a local SQLite database.
  3. RESULT VALIDATION         — Scrape live / full-time scores and settle legs.

No external database manager is required.  Feed match data via load_matches(df)
and the module handles everything else.

──────────────────────────────────────────────────────────────────────────────
SCORING MODEL
──────────────────────────────────────────────────────────────────────────────
Every candidate pick is scored on three normalised axes (each 0.0 → 1.0):

  consensus_score — agreement between independent data sources on the predicted outcome
                    floor (cfg.consensus_floor) → 0.0 ; 100 % → 1.0

  sources_score — number of independent data sources backing the pick
                  0 → 0.0 ; highest count in pool → 1.0

  balance_score — proximity of pick odds to the ideal per-leg target
                  perfect match → 1.0 ; at/beyond tolerance edge → 0.0

Two top-level levers control how these axes are combined:

  quality_vs_balance   0.0 = balance only  │  1.0 = quality only
  consensus_vs_sources 0.0 = sources only  │  1.0 = consensus only

Formula:
  quality = consensus_vs_sources × consensus_score + (1 − consensus_vs_sources) × sources_score
  final   = quality_vs_balance × quality + (1 − quality_vs_balance) × balance_score

Picks inside the ±tolerance band are "Tier 1" and always rank above "Tier 2"
picks, preventing the slip from drifting far from the target total odds.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from scrape_kit import BaseStorageManager, get_logger, scrape

logger = get_logger(__name__)

# (cons_col, odds_col, display_label)
MARKET_MAP: dict[str, list[tuple[str, str, str]]] = {
    "result": [
        ("cons_home", "odds_home", "1"),
        ("cons_draw", "odds_draw", "X"),
        ("cons_away", "odds_away", "2"),
    ],
    "over_under_2.5": [
        ("cons_over", "odds_over", "Over 2.5"),
        ("cons_under", "odds_under", "Under 2.5"),
    ],
    "btts": [
        ("cons_btts_yes", "odds_btts_yes", "BTTS Yes"),
        ("cons_btts_no", "odds_btts_no", "BTTS No"),
    ],
}


@dataclass
class BetSlipConfig:
    """
    Full configuration for the slip builder.

    ┌─ SCOPE ──────────────────────────────────────────────────────────────────┐
    │ date_from / date_to        ISO 'YYYY-MM-DD' window. None = no limit.     │
    │ excluded_urls              result_urls to skip entirely.                 │
    │ included_markets           None = all; or list of labels (1, X, 2, etc). │
    ├─ SHAPE ──────────────────────────────────────────────────────────────────┤
    │ target_odds      [1.10–1000]  Desired cumulative odds.                   │
    │ target_legs      [1–10]       Desired number of legs.                    │
    │ max_legs_overflow[0–5]        Extra legs allowed beyond target.          │
    ├─ QUALITY GATE ───────────────────────────────────────────────────────────┤
    │ consensus_floor    [0–100]   Minimum source agreement percentage.        │
    │ min_odds           [1.01–10] Minimum bookmaker odds (filters near-certs).  │
    ├─ ODDS TOLERANCE ─────────────────────────────────────────────────────────┤
    │ tolerance_factor   [0.05–0.80] ±band around ideal per-leg odds.            │
    │                              None = auto-derived.                        │
    ├─ STOP CONDITION ─────────────────────────────────────────────────────────┤
    │ stop_threshold     [0.50–1.00] Stop when odds ≥ target × this.          │
    │                                None = auto-derived.                      │
    │ min_legs_fill_ratio[0.50–1.00] Min fraction of legs before early stop.  │
    ├─ SCORING ────────────────────────────────────────────────────────────────┤
    │ quality_vs_balance [0–1]  0 = balance only, 1 = quality only.           │
    │ consensus_vs_sources [0–1]  Within quality: 0 = sources, 1 = consensus. │
    └──────────────────────────────────────────────────────────────────────────┘
    """

    # Scope
    date_from: str | None = None
    date_to: str | None = None
    excluded_urls: list[str] | None = None
    included_markets: list[str] | None = None

    # Shape
    target_odds: float = 3.0
    target_legs: int = 3
    max_legs_overflow: int | None = None

    # Quality gate
    consensus_floor: float = 50.0
    min_odds: float = 1.05

    # Odds tolerance
    tolerance_factor: float | None = None

    # Stop condition
    stop_threshold: float | None = None
    min_legs_fill_ratio: float = 0.70

    # Scoring weights
    quality_vs_balance: float = 0.5
    consensus_vs_sources: float = 0.5

    def __post_init__(self) -> None:
        self.target_odds = max(1.10, min(1000.0, self.target_odds))
        self.target_legs = max(1, min(10, self.target_legs))
        self.consensus_floor = max(0.0, min(100.0, self.consensus_floor))
        self.min_odds = max(1.01, min(10.0, self.min_odds))
        self.min_legs_fill_ratio = max(0.50, min(1.00, self.min_legs_fill_ratio))
        self.quality_vs_balance = max(0.0, min(1.0, self.quality_vs_balance))
        self.consensus_vs_sources = max(0.0, min(1.0, self.consensus_vs_sources))

        if self.tolerance_factor is not None:
            self.tolerance_factor = max(0.05, min(0.80, self.tolerance_factor))
        if self.stop_threshold is not None:
            self.stop_threshold = max(0.50, min(1.00, self.stop_threshold))
        if self.max_legs_overflow is not None:
            self.max_legs_overflow = max(0, min(5, self.max_legs_overflow))


# ── Built-in risk profiles ────────────────────────────────────────────────────

PROFILES: dict[str, BetSlipConfig] = {
    # Short-odds doubles — tight balance, high confidence
    "low_risk": BetSlipConfig(
        target_odds=2.0,
        target_legs=2,
        consensus_floor=65.0,
        min_odds=1.10,
        quality_vs_balance=0.35,
        consensus_vs_sources=0.60,
        tolerance_factor=0.20,
        stop_threshold=0.95,
        min_legs_fill_ratio=0.80,
        included_markets=["1", "2", "X", "BTTS Yes", "BTTS No"],
    ),
    # Balanced 3-leg accumulator
    "medium_risk": BetSlipConfig(
        target_odds=5.0,
        target_legs=3,
        consensus_floor=50.0,
        quality_vs_balance=0.50,
        consensus_vs_sources=0.50,
    ),
    # Longer accumulator, quality over odds precision
    "high_risk": BetSlipConfig(
        target_odds=15.0,
        target_legs=5,
        consensus_floor=50.0,
        quality_vs_balance=0.70,
        consensus_vs_sources=0.50,
        min_legs_fill_ratio=0.60,
    ),
    # Well-sourced picks with a minimum price floor
    "value_hunter": BetSlipConfig(
        target_odds=8.0,
        target_legs=4,
        consensus_floor=52.0,
        min_odds=1.30,
        quality_vs_balance=0.65,
        consensus_vs_sources=0.30,
        min_legs_fill_ratio=0.65,
    ),
}


def get_profile(name: str) -> BetSlipConfig:
    """Return a deep copy of a named built-in profile."""
    import copy

    if name not in PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Available: {list(PROFILES)}")
    return copy.deepcopy(PROFILES[name])


def _resolve_tolerance(cfg: BetSlipConfig) -> float:
    """
    Auto-derived tolerance: wider for few legs, tighter for many.
    1 leg → 0.40 │ 2 → 0.28 │ 3 → 0.23 │ 5 → 0.18 │ 10 → 0.13
    """
    if cfg.tolerance_factor is not None:
        return cfg.tolerance_factor
    return round(0.40 / (cfg.target_legs**0.5), 4)


def _resolve_stop_threshold(cfg: BetSlipConfig) -> float:
    """
    Auto-derived stop: tight for singles, slightly looser for longer accas.
    1 leg → 0.98 │ 2 → 0.93 │ 3 → 0.91 │ 5 → 0.90 │ 10 → 0.89
    """
    if cfg.stop_threshold is not None:
        return cfg.stop_threshold
    return round(0.88 + (0.1 / cfg.target_legs), 4)


def _resolve_max_legs(cfg: BetSlipConfig) -> int:
    if cfg.max_legs_overflow is not None:
        return cfg.target_legs + cfg.max_legs_overflow
    if cfg.target_legs == 1:
        return 1
    if cfg.target_legs < 5:
        return cfg.target_legs + 1
    return cfg.target_legs + 2


def _score_consensus(consensus: float, cfg: BetSlipConfig) -> float:
    span = 100.0 - cfg.consensus_floor
    return (
        1.0
        if span <= 0
        else max(0.0, min(1.0, (consensus - cfg.consensus_floor) / span))
    )


def _score_sources(sources: int, max_sources: int) -> float:
    return 0.0 if max_sources <= 0 else min(1.0, sources / max_sources)


def _score_balance(odds: float, ideal: float, tolerance: float) -> float:
    deviation = abs(odds - ideal) / ideal
    return max(0.0, 1.0 - (deviation / tolerance))


def _score_pick(
    opt: dict,
    ideal_odds: float,
    max_sources: int,
    cfg: BetSlipConfig,
) -> tuple[int, float]:
    tolerance = _resolve_tolerance(cfg)
    deviation = abs(opt["odds"] - ideal_odds) / ideal_odds
    tier = 1 if deviation <= tolerance else 2

    consensus_score = _score_consensus(opt.get("consensus", 0.0), cfg)
    sources_score = _score_sources(opt["sources"], max_sources)
    balance_score = _score_balance(opt["odds"], ideal_odds, tolerance)

    quality = (
        cfg.consensus_vs_sources * consensus_score
        + (1 - cfg.consensus_vs_sources) * sources_score
    )
    final = (
        cfg.quality_vs_balance * quality + (1 - cfg.quality_vs_balance) * balance_score
    )
    return tier, round(final, 6)


def _parse_score(raw: str) -> tuple[int, int]:
    h, a = raw.split(":")
    return int(h), int(a)


def _determine_outcome(home: int, away: int, market: str, market_type: str) -> str:
    if market_type == "result":
        if market == "1" and home > away:
            return "Won"
        if market == "2" and away > home:
            return "Won"
        if market == "X" and home == away:
            return "Won"
        return "Lost"

    if market_type == "btts":
        scored = home > 0 and away > 0
        if market == "BTTS Yes" and scored:
            return "Won"
        if market == "BTTS No" and not scored:
            return "Won"
        return "Lost"

    if market_type == "over_under_2.5":
        total = home + away
        if market == "Over 2.5" and total >= 3:
            return "Won"
        if market == "Under 2.5" and total < 3:
            return "Won"
        return "Lost"

    return "Pending"


def _parse_match_result_html(html: str, url: str) -> dict[str, str]:
    """
    Parse a result page HTML and return the match status.
    """
    import re

    from bs4 import BeautifulSoup

    result = {
        "status": "PENDING",
        "score": "",
        "minute": "",
    }

    soup = BeautifulSoup(html, "html.parser")

    # 1. Identify Status (Check Soccervista specific IDs)
    status_container = soup.find(id="status-container")
    gametime_container = soup.find(id="gametime-container")

    status_parts = []
    if status_container:
        status_parts.append(status_container.get_text(strip=True))
    if gametime_container:
        status_parts.append(gametime_container.get_text(strip=True))
    status_text = " ".join(status_parts).strip()

    # Global fallback for status if containers are empty (e.g. initial loads)
    if not status_text:
        all_text_start = soup.get_text(separator=" ", strip=True)[:2000]
        for marker in ["FT", "Finished", "HT"]:
            if marker in all_text_start:
                status_text = marker
                break

    is_finished = "FT" in status_text or "Finished" in status_text
    is_live = False
    minute = ""

    minute_rx = re.compile(r"(\d+'|HT)")
    match_live = minute_rx.search(status_text)
    if match_live:
        is_live = True
        minute = match_live.group(1)

    # Heuristic: search globally for minutes if specialized tags missed it
    if not (is_finished or is_live):
        match_live = minute_rx.search(soup.get_text()[:2000])
        if match_live:
            is_live = True
            minute = match_live.group(1)

    # If match hasn't started yet, don't look for scores (prevents future stat leaks)
    if not (is_finished or is_live):
        return result

    # 2. Identify Score (Prioritize Soccervista livescore-container)
    score_container = soup.find(id="livescore-container")
    score_text = score_container.get_text(strip=True) if score_container else ""

    score_rx = re.compile(r"(\d{1,2})\s*:\s*(\d{1,2})")
    match_score = score_rx.search(score_text)

    if not match_score:
        # Fallback to fuzzy search for X:Y in common score-like classes
        score_div = soup.find("div", class_=re.compile(r"font-bold.*text-center", re.I))
        if score_div:
            match_score = score_rx.search(score_div.get_text(strip=True))

    if not match_score:
        # Last resort: global search for the FIRST X:Y pattern in page header
        match_score = score_rx.search(soup.get_text()[:2000])

    if match_score:
        # Successfully found score for an active/finished match
        result["score"] = f"{match_score.group(1)}:{match_score.group(2)}"

    if is_finished:
        result["status"] = "FT"
    elif is_live:
        result["status"] = "LIVE"
        result["minute"] = minute

    return result


class BetAssistant(BaseStorageManager):
    """
    All-in-one betting assistant.

    Initialise with a path to an SQLite database (created automatically) and
    an optional path to a YAML settings file or directory.

    Match data is fed in via load_matches(df) — no external database manager
    is involved.

    Typical workflow
    ────────────────
    assistant = BetAssistant("bets.db")
    assistant.load_matches(my_dataframe)

    slip_legs = assistant.build_slip("medium_risk")
    slip_id   = assistant.save_slip("medium_risk", slip_legs)

    assistant.validate_slips()                   # settle finished legs

    """

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(
        self,
        db_path: str,
        config_path: str | None = None,
    ) -> None:
        """
        Parameters
        ----------
        db_path     : Path to the SQLite file (created if it doesn't exist).
        """
        super().__init__(db_path)
        self._df = pd.DataFrame()

    def _create_tables(self) -> None:
        with self.db_lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS slips (
                    slip_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_generated TEXT,
                    profile        TEXT,
                    total_odds     REAL,
                    units          REAL DEFAULT 1.0
                );

                CREATE TABLE IF NOT EXISTS legs (
                    leg_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    slip_id     INTEGER,
                    match_name  TEXT,
                    match_datetime TEXT,
                    market      TEXT,
                    market_type TEXT,
                    odds        REAL,
                    result_url  TEXT,
                    status      TEXT DEFAULT 'Pending',
                    FOREIGN KEY(slip_id) REFERENCES slips(slip_id)
                );
            """)
            self.conn.commit()

    def close(self) -> None:
        """Flush and close the SQLite connection."""
        self.flush_and_close()

    def __enter__(self) -> BetAssistant:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_matches(self, df: pd.DataFrame) -> None:
        """
        Ingest a raw match DataFrame and build the internal flat representation.

        Expected columns (all others are ignored):
            home_name, away_name, datetime, result_url, odds (dict), scores (list)

        The 'scores' column must be a list of dicts with keys:
            home, away, source  (source used to count unique data providers)
        """
        if df.empty:
            self._df = pd.DataFrame()
            return

        rows: list[dict] = []
        for idx, row in df.iterrows():
            try:
                match_key = f"{row['home_name']}_{row['away_name']}_{row['datetime']}"
                match_id = f"match_{idx}_{hashlib.md5(match_key.encode()).hexdigest()}"
                dt = row["datetime"]
                odds = row.get("odds") or {}
                scores = row.get("scores") or []
                cons_data = self._calc_consensus(scores)
                n_sources = len(
                    {s.get("source", "") for s in scores if s.get("source")}
                )

                rows.append(
                    {
                        "match_id": match_id,
                        "datetime": dt,
                        "home": row["home_name"],
                        "away": row["away_name"],
                        "sources": n_sources,
                        "result_url": row.get("result_url"),
                        # Consensus
                        "cons_home": cons_data["result"]["home"],
                        "cons_draw": cons_data["result"]["draw"],
                        "cons_away": cons_data["result"]["away"],
                        "cons_over": cons_data["over_under_2.5"]["over"],
                        "cons_under": cons_data["over_under_2.5"]["under"],
                        "cons_btts_yes": cons_data["btts"]["yes"],
                        "cons_btts_no": cons_data["btts"]["no"],
                        # Odds
                        "odds_home": odds.get("home", 0.0),
                        "odds_draw": odds.get("draw", 0.0),
                        "odds_away": odds.get("away", 0.0),
                        "odds_over": odds.get("over", 0.0),
                        "odds_under": odds.get("under", 0.0),
                        "odds_btts_yes": odds.get("btts_y", 0.0),
                        "odds_btts_no": odds.get("btts_n", 0.0),
                    }
                )
            except Exception as e:
                logger.info(f"[BetAssistant] Skipping row {idx}: {e}")

        self._df = pd.DataFrame(rows)

    # ── Match browsing ────────────────────────────────────────────────────────

    def filter_matches(
        self,
        search_text: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_sources: int | None = None,
    ) -> pd.DataFrame:
        """
        Return a filtered view of the loaded match DataFrame.

        Parameters
        ----------
        search_text  : Substring match on home or away team name (case-insensitive).
        date_from    : ISO date string; include only matches on or after this date.
        date_to      : ISO date string; include only matches on or before this date.
        min_sources  : Keep only rows with at least this many data sources.
        """
        if self._df.empty:
            return self._df.copy()

        out = self._df.copy()

        if search_text:
            mask = out["home"].str.contains(search_text, case=False, na=False) | out[
                "away"
            ].str.contains(search_text, case=False, na=False)
            out = out[mask]

        if date_from:
            out = out[out["datetime"] >= pd.to_datetime(date_from)]

        if date_to:
            end = (
                pd.to_datetime(date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            )
            out = out[out["datetime"] <= end]

        if min_sources and min_sources > 1:
            out = out[out["sources"] >= min_sources]

        return out

    # ── Slip building ─────────────────────────────────────────────────────────

    def build_slip(
        self,
        profile_or_config: str | BetSlipConfig = "medium_risk",
        extra_excluded_urls: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build a bet slip and return its legs as a list of dicts.

        Parameters
        ----------
        profile_or_config   : A named profile string (e.g. "low_risk") or a
                              fully constructed BetSlipConfig instance.
        extra_excluded_urls : Additional result_urls to exclude on top of any
                              already listed in the config (e.g. live URLs).

        Returns
        -------
        List of leg dicts, each containing:
            match, market, market_type, consensus, odds,
            result_url, sources, tier, score
        """
        if self._df.empty:
            return []

        cfg = (
            get_profile(profile_or_config)
            if isinstance(profile_or_config, str)
            else profile_or_config
        )

        if extra_excluded_urls:
            current = list(cfg.excluded_urls or [])
            cfg.excluded_urls = current + extra_excluded_urls

        candidates = self._collect_candidates(cfg)
        if not candidates:
            return []

        return self._select_legs(candidates, cfg)

    def build_slip_auto_exclude(
        self,
        profile_or_config: str | BetSlipConfig = "medium_risk",
    ) -> list[dict[str, Any]]:
        """
        Convenience wrapper that automatically excludes all URLs that are
        already present in the slip database (active pending slips + settled).
        """
        excluded = self.get_excluded_urls()
        return self.build_slip(profile_or_config, extra_excluded_urls=excluded)

    # ── Slip persistence ──────────────────────────────────────────────────────

    def save_slip(
        self,
        profile: str,
        legs: list[dict[str, Any]],
        units: float = 1.0,
    ) -> int:
        """
        Persist a bet slip and its legs to the database.

        Parameters
        ----------
        profile : Descriptive label stored alongside the slip (e.g. "medium_risk").
        legs    : List of leg dicts as returned by build_slip().
        units   : Stake size in units (default 1.0).

        Returns
        -------
        The auto-assigned slip_id.
        """
        with self.db_lock:
            total_odds = math.prod(leg["odds"] for leg in legs)
            date_today = pd.Timestamp.now().strftime("%Y-%m-%d")

            cursor = self.conn.execute(
                "INSERT INTO slips (date_generated, profile, total_odds, units) VALUES (?, ?, ?, ?)",
                (date_today, profile, total_odds, units),
            )
            slip_id = cursor.lastrowid

            for leg in legs:
                dt = leg.get("datetime")
                if hasattr(dt, "isoformat"):
                    dt = dt.isoformat()

                self.conn.execute(
                    """INSERT INTO legs
                    (slip_id, match_name, match_datetime, market, market_type, odds, result_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        slip_id,
                        leg["match"],
                        dt,
                        leg["market"],
                        leg["market_type"],
                        leg["odds"],
                        leg["result_url"],
                    ),
                )

            self.conn.commit()
            return slip_id

    # ── Slip retrieval ────────────────────────────────────────────────────────

    def get_slips(self, profile: str | None = None) -> list[dict[str, Any]]:
        """
        Fetch all slips with their legs, optionally filtered by profile.

        Slip-level status is derived from leg statuses:
            Lost    — at least one leg is Lost
            Pending — no legs Lost but at least one Pending
            Won     — all legs Won
        """
        query = """
            SELECT
                s.slip_id, s.date_generated, s.profile, s.total_odds, s.units,
                l.match_name, l.match_datetime, l.market, l.market_type, l.odds, l.status, l.result_url
            FROM slips s
            LEFT JOIN legs l ON s.slip_id = l.slip_id
        """
        params: list = []
        if profile and profile != "all":
            query += " WHERE s.profile = ?"
            params.append(profile)
        query += " ORDER BY s.date_generated DESC, s.slip_id DESC"

        rows = self.fetch_rows(query, params)
        return self._rows_to_slips(rows)

    def delete_slip(self, slip_id: int) -> None:
        with self.db_lock:
            self.conn.execute("DELETE FROM legs  WHERE slip_id = ?", (slip_id,))
            self.conn.execute("DELETE FROM slips WHERE slip_id = ?", (slip_id,))
            self.conn.commit()

    def get_excluded_urls(self) -> list[str]:
        """
        Return all result_urls that must be excluded from new slip generation.

        Rule 1 — Settled (Won/Lost) legs are excluded forever.
        Rule 2 — Pending legs are excluded only while their slip is still alive
                 (i.e. the slip has no Lost leg yet).
        """
        try:
            rows = self.fetch_rows("""
                SELECT DISTINCT result_url FROM legs
                WHERE status IN ('Won', 'Lost', 'Live')
                   OR (
                       status = 'Pending'
                       AND slip_id NOT IN (
                           SELECT slip_id FROM legs WHERE status = 'Lost'
                       )
                   )
            """)
            return [r[0] for r in rows if r[0] is not None]
        except Exception as e:
            logger.info(f"[BetAssistant] get_excluded_urls error: {e}")
            return []

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_slips(self) -> dict[str, Any]:
        self.reopen_if_changed()

        pending = self.fetch_rows(
            "SELECT leg_id, result_url, market, market_type, match_name FROM legs WHERE status IN ('Pending', 'Live')"
        )

        checked = len(pending)
        errors = [0]
        live_matches: list[dict[str, Any]] = []
        settled_matches: list[dict[str, Any]] = []

        url_to_legs = {}
        for row in pending:
            leg_id, url, market, market_type, match_name = tuple(row)
            if url not in url_to_legs:
                url_to_legs[url] = []
            url_to_legs[url].append((leg_id, market, market_type, match_name))

        urls = list(url_to_legs.keys())
        if not urls:
            return {"checked": 0, "settled": [], "live": [], "errors": 0}

        def _handle_url(url: str, html: str) -> None:
            try:
                base_info = _parse_match_result_html(html, url)

                for leg_id, market, market_type, match_name in url_to_legs[url]:
                    info = {
                        "status": base_info["status"],
                        "score": base_info["score"],
                        "minute": base_info["minute"],
                        "outcome": "",
                    }

                    if info["status"] == "FT" and info["score"]:
                        try:
                            h, a = _parse_score(info["score"])
                            info["outcome"] = _determine_outcome(
                                h, a, market, market_type
                            )
                        except Exception:
                            pass

                    if info["status"] == "FT" and info["outcome"] in ("Won", "Lost"):
                        with self.db_lock:
                            self.conn.execute(
                                "UPDATE legs SET status = ? WHERE leg_id = ?",
                                (info["outcome"], leg_id),
                            )
                            self.conn.commit()
                        settled_matches.append(
                            {
                                "leg_id": leg_id,
                                "match_name": match_name,
                                "market": market,
                                "score": info["score"],
                                "outcome": info["outcome"],
                            }
                        )

                    elif info["status"] == "LIVE" and info["score"]:
                        with self.db_lock:
                            self.conn.execute(
                                "UPDATE legs SET status = 'Live' WHERE leg_id = ?",
                                (leg_id,),
                            )
                            self.conn.commit()
                        live_matches.append(
                            {
                                "leg_id": leg_id,
                                "match_name": match_name,
                                "market": market,
                                "score": info["score"],
                                "minute": info["minute"],
                            }
                        )

            except Exception as e:
                errors[0] += 1
                logger.error(f"[BetAssistant] parse error on {url}: {e}")

        try:
            scrape(
                urls,
                _handle_url,
                mode="fast",
                max_concurrency=10,
            )
        except Exception as e:
            logger.error(f"[BetAssistant] Scrape failure: {e}")
            errors[0] += 1

        return {
            "checked": checked,
            "settled": settled_matches,
            "live": live_matches,
            "errors": errors[0],
        }

    def update_leg(self, leg_id: int, status: str) -> None:
        """Manually override a leg outcome ('Won', 'Lost', or 'Pending')."""
        with self.db_lock:
            self.conn.execute(
                "UPDATE legs SET status = ? WHERE leg_id = ?", (status, leg_id)
            )
            self.conn.commit()

    # ══════════════════════════════════════════════════════════════════════════
    # Private helpers
    # ══════════════════════════════════════════════════════════════════════════

    # ── Consensus calculation ─────────────────────────────────────────────────

    @staticmethod
    def _calc_consensus(scores: list) -> dict[str, dict[str, float]]:
        """Derive result / over-under / BTTS consensus from historical scores."""
        empty = {
            "result": {"home": 0.0, "draw": 0.0, "away": 0.0},
            "over_under_2.5": {"over": 0.0, "under": 0.0},
            "btts": {"yes": 0.0, "no": 0.0},
        }
        if not scores:
            return empty

        total = len(scores)
        home_w = draw_w = away_w = 0
        over = under = 0
        btts_y = btts_n = 0

        try:
            for s in scores:
                h = s.get("home", 0) or 0
                a = s.get("away", 0) or 0

                if h > a:
                    home_w += 1
                elif h < a:
                    away_w += 1
                else:
                    draw_w += 1

                if h + a > 2.5:
                    over += 1
                else:
                    under += 1

                if h > 0 and a > 0:
                    btts_y += 1
                else:
                    btts_n += 1

        except Exception as e:
            logger.info(f"[BetAssistant] Consensus calc error: {e}")
            return empty

        def pct(n: int) -> float:
            return round((n / total) * 100, 1) if total else 0.0

        return {
            "result": {"home": pct(home_w), "draw": pct(draw_w), "away": pct(away_w)},
            "over_under_2.5": {"over": pct(over), "under": pct(under)},
            "btts": {"yes": pct(btts_y), "no": pct(btts_n)},
        }

    # ── Candidate collection ──────────────────────────────────────────────────

    def _collect_candidates(self, cfg: BetSlipConfig) -> list[dict]:
        # TODO - this wont work unless datetimes are fixed first!
        # now       = pd.Timestamp.now()
        # date_from = max(pd.to_datetime(cfg.date_from), now) if cfg.date_from else now
        date_from = pd.to_datetime(cfg.date_from) if cfg.date_from else None
        date_to = (
            (pd.to_datetime(cfg.date_to) + pd.Timedelta(days=1))
            if cfg.date_to
            else None
        )
        excluded = set(cfg.excluded_urls or [])
        markets = cfg.included_markets

        candidates = []
        for _, row in self._df.iterrows():
            if date_from and row["datetime"] < date_from:
                continue
            if date_to and row["datetime"] >= date_to:
                continue
            url = row.get("result_url")
            if (
                pd.isna(url)
                or not str(url).strip()
                or str(url).strip().lower() in ("none", "null")
            ):
                continue
            if url in excluded:
                continue

            match_name = f"{row['home']} vs {row['away']}"

            for m_type, market_cols in MARKET_MAP.items():
                for cons_col, odds_col, label in market_cols:
                    if markets and label not in markets:
                        continue
                    consensus = float(row.get(cons_col, 0))
                    odds = float(row.get(odds_col, 0))
                    if consensus >= cfg.consensus_floor and odds >= cfg.min_odds:
                        candidates.append(
                            {
                                "match": match_name,
                                "datetime": row["datetime"],
                                "market": label,
                                "market_type": m_type,
                                "consensus": consensus,
                                "odds": odds,
                                "result_url": row["result_url"],
                                "sources": int(row["sources"]),
                            }
                        )

        return candidates

    # ── Leg selection loop ────────────────────────────────────────────────────

    @staticmethod
    def _select_legs(candidates: list[dict], cfg: BetSlipConfig) -> list[dict]:
        stop_threshold = _resolve_stop_threshold(cfg)
        max_legs = _resolve_max_legs(cfg)
        min_legs = max(1, int(cfg.target_legs * cfg.min_legs_fill_ratio))
        max_sources = max((c["sources"] for c in candidates), default=1)

        selected: list[dict] = []
        seen_matches: set = set()
        total_odds: float = 1.0

        while len(selected) < max_legs:
            if (
                total_odds >= cfg.target_odds * stop_threshold
                and len(selected) >= min_legs
            ):
                break

            remaining_target = cfg.target_odds / total_odds
            remaining_legs = max(1, cfg.target_legs - len(selected))
            ideal_per_leg = remaining_target ** (1.0 / remaining_legs)

            scored = [
                {
                    **c,
                    **dict(
                        zip(
                            ("tier", "score"),
                            _score_pick(c, ideal_per_leg, max_sources, cfg),
                        )
                    ),
                }
                for c in candidates
                if c["match"] not in seen_matches
            ]

            if not scored:
                break

            scored.sort(key=lambda x: (x["tier"], -x["score"]))
            best = scored[0]
            selected.append(best)
            seen_matches.add(best["match"])
            total_odds *= best["odds"]

        if len(selected) < min_legs:
            return []

        return selected

    # ── DB row → structured slip ──────────────────────────────────────────────

    @staticmethod
    def _rows_to_slips(rows: list) -> list[dict[str, Any]]:
        """
        Group flat SQL rows into nested slip + legs dicts.

        Slip status derivation:
            Lost    — any leg is Lost
            Pending — no Lost leg, but at least one Pending
            Won     — all legs Won
        """
        slips: dict[int, dict] = {}

        for (
            slip_id,
            date,
            profile,
            total_odds,
            units,
            match,
            dt,
            market,
            market_type,
            odds,
            status,
            result_url,
        ) in rows:
            if slip_id not in slips:
                slips[slip_id] = {
                    "slip_id": slip_id,
                    "date_generated": date,
                    "profile": profile,
                    "total_odds": total_odds,
                    "units": units,
                    "legs": [],
                    "slip_status": "Won",
                }

            if match:
                slips[slip_id]["legs"].append(
                    {
                        "match_name": match,
                        "datetime": datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S"),
                        "market": market,
                        "market_type": market_type,
                        "odds": odds,
                        "status": status,
                        "result_url": result_url,
                    }
                )

            if status == "Lost":
                slips[slip_id]["slip_status"] = "Lost"
            elif status == "Live" and slips[slip_id]["slip_status"] not in ("Lost",):
                slips[slip_id]["slip_status"] = "Live"
            elif status == "Pending" and slips[slip_id]["slip_status"] not in (
                "Lost",
                "Live",
            ):
                slips[slip_id]["slip_status"] = "Pending"

        return list(slips.values())
