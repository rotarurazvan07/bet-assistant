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

  prob_score    — confidence in the predicted outcome
                  floor (cfg.probability_floor) → 0.0 ; 100 % → 1.0

  sources_score — number of independent data sources backing the pick
                  0 → 0.0 ; highest count in pool → 1.0

  balance_score — proximity of pick odds to the ideal per-leg target
                  perfect match → 1.0 ; at/beyond tolerance edge → 0.0

Two top-level levers control how these axes are combined:

  quality_vs_balance   0.0 = balance only  │  1.0 = quality only
  prob_vs_sources      0.0 = sources only  │  1.0 = probability only

Formula:
  quality = prob_vs_sources × prob_score + (1 − prob_vs_sources) × sources_score
  final   = quality_vs_balance × quality + (1 − quality_vs_balance) × balance_score

Picks inside the ±tolerance band are "Tier 1" and always rank above "Tier 2"
picks, preventing the slip from drifting far from the target total odds.
"""

from __future__ import annotations

import math
import os
import sqlite3
import traceback
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import yaml
from bs4 import BeautifulSoup
import threading
from pathlib import Path

# (prob_col, odds_col, display_label)
MARKET_MAP: Dict[str, List[Tuple[str, str, str]]] = {
    "result":         [("prob_home",     "odds_home",     "1"),
                       ("prob_draw",     "odds_draw",     "X"),
                       ("prob_away",     "odds_away",     "2")],
    "over_under_2.5": [("prob_over",     "odds_over",     "Over 2.5"),
                       ("prob_under",    "odds_under",    "Under 2.5")],
    "btts":           [("prob_btts_yes", "odds_btts_yes", "BTTS Yes"),
                       ("prob_btts_no",  "odds_btts_no",  "BTTS No")],
}

@dataclass
class BetSlipConfig:
    """
    Full configuration for the slip builder.

    ┌─ SCOPE ──────────────────────────────────────────────────────────────────┐
    │ date_from / date_to        ISO 'YYYY-MM-DD' window. None = no limit.     │
    │ excluded_urls              result_urls to skip entirely.                 │
    │ included_market_types      None = all; or list from MARKET_MAP keys.     │
    ├─ SHAPE ──────────────────────────────────────────────────────────────────┤
    │ target_odds      [1.10–1000]  Desired cumulative odds.                   │
    │ target_legs      [1–10]       Desired number of legs.                    │
    │ max_legs_overflow[0–5]        Extra legs allowed beyond target.          │
    ├─ QUALITY GATE ───────────────────────────────────────────────────────────┤
    │ probability_floor[0–100]   Minimum prediction confidence (%).            │
    │ min_odds         [1.01–10] Minimum bookmaker odds (filters near-certs).  │
    ├─ ODDS TOLERANCE ─────────────────────────────────────────────────────────┤
    │ tolerance_factor [0.05–0.80] ±band around ideal per-leg odds.            │
    │                              None = auto-derived.                        │
    ├─ STOP CONDITION ─────────────────────────────────────────────────────────┤
    │ stop_threshold     [0.50–1.00] Stop when odds ≥ target × this.          │
    │                                None = auto-derived.                      │
    │ min_legs_fill_ratio[0.50–1.00] Min fraction of legs before early stop.  │
    ├─ SCORING ────────────────────────────────────────────────────────────────┤
    │ quality_vs_balance [0–1]  0 = balance only, 1 = quality only.           │
    │ prob_vs_sources    [0–1]  Within quality: 0 = sources, 1 = probability. │
    └──────────────────────────────────────────────────────────────────────────┘
    """

    # Scope
    date_from:              Optional[str]        = None
    date_to:                Optional[str]        = None
    excluded_urls:          Optional[List[str]]  = None
    included_market_types:  Optional[List[str]]  = None

    # Shape
    target_odds:            float          = 3.0
    target_legs:            int            = 3
    max_legs_overflow:      Optional[int]  = None

    # Quality gate
    probability_floor:      float          = 50.0
    min_odds:               float          = 1.05

    # Odds tolerance
    tolerance_factor:       Optional[float] = None

    # Stop condition
    stop_threshold:         Optional[float] = None
    min_legs_fill_ratio:    float           = 0.70

    # Scoring weights
    quality_vs_balance:     float           = 0.5
    prob_vs_sources:        float           = 0.5

    def __post_init__(self) -> None:
        self.target_odds          = max(1.10,  min(1000.0, self.target_odds))
        self.target_legs          = max(1,     min(10,     self.target_legs))
        self.probability_floor    = max(0.0,   min(100.0,  self.probability_floor))
        self.min_odds             = max(1.01,  min(10.0,   self.min_odds))
        self.min_legs_fill_ratio  = max(0.50,  min(1.00,   self.min_legs_fill_ratio))
        self.quality_vs_balance   = max(0.0,   min(1.0,    self.quality_vs_balance))
        self.prob_vs_sources      = max(0.0,   min(1.0,    self.prob_vs_sources))

        if self.tolerance_factor is not None:
            self.tolerance_factor = max(0.05, min(0.80, self.tolerance_factor))
        if self.stop_threshold is not None:
            self.stop_threshold = max(0.50, min(1.00, self.stop_threshold))
        if self.max_legs_overflow is not None:
            self.max_legs_overflow = max(0, min(5, self.max_legs_overflow))


# ── Built-in risk profiles ────────────────────────────────────────────────────

PROFILES: Dict[str, BetSlipConfig] = {

    # Short-odds doubles — tight balance, high confidence
    "low_risk": BetSlipConfig(
        target_odds=2.0,
        target_legs=2,
        probability_floor=65.0,
        min_odds=1.10,
        quality_vs_balance=0.35,
        prob_vs_sources=0.60,
        tolerance_factor=0.20,
        stop_threshold=0.95,
        min_legs_fill_ratio=0.80,
        included_market_types=["result", "btts"],
    ),

    # Balanced 3-leg accumulator
    "medium_risk": BetSlipConfig(
        target_odds=5.0,
        target_legs=3,
        probability_floor=50.0,
        quality_vs_balance=0.50,
        prob_vs_sources=0.50,
    ),

    # Longer accumulator, quality over odds precision
    "high_risk": BetSlipConfig(
        target_odds=15.0,
        target_legs=5,
        probability_floor=50.0,
        quality_vs_balance=0.70,
        prob_vs_sources=0.50,
        min_legs_fill_ratio=0.60,
    ),

    # Well-sourced picks with a minimum price floor
    "value_hunter": BetSlipConfig(
        target_odds=8.0,
        target_legs=4,
        probability_floor=52.0,
        min_odds=1.30,
        quality_vs_balance=0.65,
        prob_vs_sources=0.30,
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
    return round(0.40 / (cfg.target_legs ** 0.5), 4)


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


def _score_probability(prob: float, cfg: BetSlipConfig) -> float:
    span = 100.0 - cfg.probability_floor
    return 1.0 if span <= 0 else max(0.0, min(1.0, (prob - cfg.probability_floor) / span))


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
) -> Tuple[int, float]:
    tolerance     = _resolve_tolerance(cfg)
    deviation     = abs(opt["odds"] - ideal_odds) / ideal_odds
    tier          = 1 if deviation <= tolerance else 2

    prob_score    = _score_probability(opt["prob"],    cfg)
    sources_score = _score_sources(opt["sources"],     max_sources)
    balance_score = _score_balance(opt["odds"], ideal_odds, tolerance)

    quality = cfg.prob_vs_sources * prob_score + (1 - cfg.prob_vs_sources) * sources_score
    final   = cfg.quality_vs_balance * quality + (1 - cfg.quality_vs_balance) * balance_score
    return tier, round(final, 6)

def _parse_score(raw: str) -> Tuple[int, int]:
    h, a = raw.split(":")
    return int(h), int(a)


def _determine_outcome(home: int, away: int, market: str, market_type: str) -> str:
    if market_type == "result":
        if market == "1" and home > away:  return "Won"
        if market == "2" and away > home:  return "Won"
        if market == "X" and home == away: return "Won"
        return "Lost"

    if market_type == "btts":
        scored = home > 0 and away > 0
        if market == "BTTS Yes" and scored:     return "Won"
        if market == "BTTS No"  and not scored: return "Won"
        return "Lost"

    if market_type == "over_under_2.5":
        total = home + away
        if market == "Over 2.5"  and total >= 3: return "Won"
        if market == "Under 2.5" and total <  3: return "Won"
        return "Lost"

    return "Pending"


def _check_match_result(url: str, market: str, market_type: str) -> Dict[str, Any]:
    """
    Scrape a result page and return the match status for a given market.

    Returns
    -------
    {
        "status":  "LIVE" | "FT" | "PENDING" | "ERROR",
        "score":   "H:A"  (empty string when unavailable),
        "minute":  "66'"  (only when LIVE),
        "outcome": "Won" | "Lost" | "" (only set when FT),
    }
    """
    try:
        from bet_framework.WebScraper import WebScraper
        html = WebScraper.fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        result: Dict[str, Any] = {"status": "PENDING", "score": "", "minute": "", "outcome": ""}

        score_div = soup.find("div", class_="text-base font-bold min-sm:text-xl text-center")
        if not score_div:
            return result

        raw_score        = score_div.get_text(strip=True)
        result["score"]  = raw_score

        status_container = soup.find(id="status-container")
        status_text      = status_container.get_text(strip=True) if status_container else ""

        if "FT" in status_text or "Finished" in status_text:
            result["status"] = "FT"
            try:
                h, a = _parse_score(raw_score)
                result["outcome"] = _determine_outcome(h, a, market, market_type)
            except Exception:
                pass
        else:
            result["status"] = "LIVE"
            parent = score_div.parent
            if parent:
                text   = parent.get_text(separator=" | ", strip=True)
                parts  = [p.strip() for p in text.split("|")]
                for part in parts:
                    if "'" in part and part[0].isdigit():
                        result["minute"] = part
                        break

        return result

    except Exception as e:
        return {"status": "ERROR", "score": "", "minute": "", "outcome": "", "error": str(e)}

class BetAssistant:
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

    stats = assistant.stats()
    """

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(
        self,
        db_path:     str,
        config_path: Optional[str] = None,
    ) -> None:
        """
        Parameters
        ----------
        db_path     : Path to the SQLite file (created if it doesn't exist).
        """
        self._conn   = sqlite3.connect(db_path, check_same_thread=False)
        self._cur    = self._conn.cursor()
        self._lock   = threading.Lock()
        self._df     = pd.DataFrame()
        self.db_path = db_path

        self._init_db()
        self._file_mtime = os.path.getmtime(self.db_path)

    def reopen_if_changed(self):
        with self._lock:
            try:
                current_mtime = os.path.getmtime(self.db_path)
            except (OSError, AttributeError):
                return
            if current_mtime == self._file_mtime:
                return
            try:
                print("[BetAssistant] File change detected, reopening connection...")
                self._conn.close()
            except Exception:
                pass
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._cur  = self._conn.cursor()
            self._file_mtime = current_mtime

            print("[BetAssistant] Reopened successfully.")

    def _init_db(self) -> None:
        self._cur.executescript("""
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
        self._conn.commit()

    def close(self) -> None:
        """Flush and close the SQLite connection."""
        self._conn.commit()
        self._conn.close()

    def __enter__(self) -> "BetAssistant":
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

        rows: List[dict] = []
        for idx, row in df.iterrows():
            try:
                match_key = (
                    f"{row['home_name']}_{row['away_name']}"
                    f"_{row['datetime']}"
                )
                match_id   = f"match_{idx}_{hashlib.md5(match_key.encode()).hexdigest()}"
                dt         = row['datetime']
                odds       = row.get("odds") or {}
                scores     = row.get("scores") or []
                probs      = self._calc_probabilities(scores)
                n_sources  = len({s.get("source", "") for s in scores if s.get("source")})

                rows.append({
                    "match_id":      match_id,
                    "datetime":      dt,
                    "home":          row["home_name"],
                    "away":          row["away_name"],
                    "sources":       n_sources,
                    "result_url":    row.get("result_url"),
                    # Probabilities
                    "prob_home":     probs["result"]["home"],
                    "prob_draw":     probs["result"]["draw"],
                    "prob_away":     probs["result"]["away"],
                    "prob_over":     probs["over_under_2.5"]["over"],
                    "prob_under":    probs["over_under_2.5"]["under"],
                    "prob_btts_yes": probs["btts"]["yes"],
                    "prob_btts_no":  probs["btts"]["no"],
                    # Odds
                    "odds_home":     odds.get("home",   0.0),
                    "odds_draw":     odds.get("draw",   0.0),
                    "odds_away":     odds.get("away",   0.0),
                    "odds_over":     odds.get("over",   0.0),
                    "odds_under":    odds.get("under",  0.0),
                    "odds_btts_yes": odds.get("btts_y", 0.0),
                    "odds_btts_no":  odds.get("btts_n", 0.0),
                })
            except Exception as e:
                print(f"[BetAssistant] Skipping row {idx}: {e}")
                traceback.print_exc()

        self._df = pd.DataFrame(rows)

    # ── Match browsing ────────────────────────────────────────────────────────

    def filter_matches(
        self,
        search_text:  Optional[str] = None,
        date_from:    Optional[str] = None,
        date_to:      Optional[str] = None,
        min_sources:  Optional[int] = None,
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
            mask = (
                out["home"].str.contains(search_text, case=False, na=False) |
                out["away"].str.contains(search_text, case=False, na=False)
            )
            out = out[mask]

        if date_from:
            out = out[out["datetime"] >= pd.to_datetime(date_from)]

        if date_to:
            end = pd.to_datetime(date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            out = out[out["datetime"] <= end]

        if min_sources and min_sources > 1:
            out = out[out["sources"] >= min_sources]

        return out

    # ── Slip building ─────────────────────────────────────────────────────────

    def build_slip(
        self,
        profile_or_config: str | BetSlipConfig = "medium_risk",
        extra_excluded_urls: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
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
            match, market, market_type, prob, odds,
            result_url, sources, tier, score
        """
        if self._df.empty:
            return []

        cfg = get_profile(profile_or_config) if isinstance(profile_or_config, str) else profile_or_config

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
    ) -> List[Dict[str, Any]]:
        """
        Convenience wrapper that automatically excludes all URLs that are
        already present in the slip database (active pending slips + settled).
        """
        excluded = self.get_excluded_urls()
        return self.build_slip(profile_or_config, extra_excluded_urls=excluded)

    # ── Slip persistence ──────────────────────────────────────────────────────

    def save_slip(
        self,
        profile:   str,
        legs:      List[Dict[str, Any]],
        units:     float = 1.0,
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
        with self._lock:
            total_odds  = math.prod(leg["odds"] for leg in legs)
            date_today  = pd.Timestamp.now().strftime("%Y-%m-%d")

            self._cur.execute(
                "INSERT INTO slips (date_generated, profile, total_odds, units) VALUES (?, ?, ?, ?)",
                (date_today, profile, total_odds, units),
            )
            slip_id = self._cur.lastrowid

            for leg in legs:
                dt = leg.get("datetime")
                if hasattr(dt, "isoformat"):
                    dt = dt.isoformat()

                self._cur.execute(
                    """INSERT INTO legs
                    (slip_id, match_name, match_datetime, market, market_type, odds, result_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (slip_id, leg["match"], dt, leg["market"], leg["market_type"],
                    leg["odds"], leg["result_url"]),
                )

            self._conn.commit()
            return slip_id

    # ── Slip retrieval ────────────────────────────────────────────────────────

    def get_slips(self, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all slips with their legs, optionally filtered by profile.

        Slip-level status is derived from leg statuses:
            Lost    — at least one leg is Lost
            Pending — no legs Lost but at least one Pending
            Won     — all legs Won
        """
        self.reopen_if_changed()

        query = """
            SELECT
                s.slip_id, s.date_generated, s.profile, s.total_odds, s.units,
                l.match_name, l.match_datetime, l.market, l.market_type, l.odds, l.status, l.result_url
            FROM slips s
            LEFT JOIN legs l ON s.slip_id = l.slip_id
        """
        params: list = []
        if profile and profile != "all":
            query  += " WHERE s.profile = ?"
            params.append(profile)
        query += " ORDER BY s.date_generated DESC, s.slip_id DESC"

        with self._lock:
            self._cur.execute(query, params)
            rows = self._cur.fetchall()
        return self._rows_to_slips(rows)

    def delete_slip(self, slip_id: int) -> None:
        with self._lock:
            self._cur.execute("DELETE FROM legs  WHERE slip_id = ?", (slip_id,))
            self._cur.execute("DELETE FROM slips WHERE slip_id = ?", (slip_id,))
            self._conn.commit()

    def get_excluded_urls(self) -> List[str]:
        """
        Return all result_urls that must be excluded from new slip generation.

        Rule 1 — Settled (Won/Lost) legs are excluded forever.
        Rule 2 — Pending legs are excluded only while their slip is still alive
                 (i.e. the slip has no Lost leg yet).
        """
        self.reopen_if_changed()

        try:
            with self._lock:
                self._cur.execute("""
                    SELECT DISTINCT result_url FROM legs
                    WHERE status IN ('Won', 'Lost', 'Live')
                       OR (
                           status = 'Pending'
                           AND slip_id NOT IN (
                               SELECT slip_id FROM legs WHERE status = 'Lost'
                           )
                       )
                """)
                return [r[0] for r in self._cur.fetchall() if r[0] is not None]
        except Exception as e:
            print(f"[BetAssistant] get_excluded_urls error: {e}")
            return []

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_slips(self) -> Dict[str, int]:
        self.reopen_if_changed()

        with self._lock:
            self._cur.execute("SELECT leg_id, result_url, market, market_type, match_name FROM legs WHERE status IN ('Pending', 'Live')")
            pending = self._cur.fetchall()

        checked = settled = errors = 0
        live_matches: List[Dict[str, Any]] = []

        for leg_id, url, market, market_type, match_name in pending:
            checked += 1
            info = _check_match_result(url, market, market_type)

            if info["status"] == "ERROR":
                errors += 1
                print(f"[BetAssistant] Validation error on leg {leg_id}: {info.get('error')}")

            elif info["status"] == "FT" and info["outcome"] in ("Won", "Lost"):
                self._cur.execute("UPDATE legs SET status = ? WHERE leg_id = ?", (info["outcome"], leg_id))
                settled += 1

            elif info["status"] == "LIVE":
                self._cur.execute("UPDATE legs SET status = 'Live' WHERE leg_id = ?", (leg_id,))
                live_matches.append({
                    "leg_id":     leg_id,
                    "match_name": match_name,
                    "score":      info["score"],
                    "minute":     info["minute"],
                })

        with self._lock:
            self._conn.commit()
        return {"checked": checked, "settled": settled, "live": live_matches, "errors": errors}

    def update_leg(self, leg_id: int, status: str) -> None:
        """Manually override a leg outcome ('Won', 'Lost', or 'Pending')."""
        with self._lock:
            self._cur.execute("UPDATE legs SET status = ? WHERE leg_id = ?", (status, leg_id))
            self._conn.commit()

    # ── Statistics ────────────────────────────────────────────────────────────

    def stats(self, profile: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate statistics over all settled slips.

        Returns
        -------
        {
            total_settled, total_won_count,
            win_rate        (%),
            total_units_bet,
            gross_return,
            net_profit,
            roi_percentage  (%)
        }
        """
        slips    = self.get_slips(profile)
        settled  = [s for s in slips if s["slip_status"] in ("Won", "Lost")]
        won      = [s for s in settled if s["slip_status"] == "Won"]

        n_settled    = len(settled)
        n_won        = len(won)
        stakes       = sum(s["units"]                    for s in settled)
        gross_return = sum(s["total_odds"] * s["units"]  for s in won)
        net_profit   = gross_return - stakes

        return {
            "total_settled":   n_settled,
            "total_won_count": n_won,
            "win_rate":        round((n_won / n_settled * 100) if n_settled else 0.0, 2),
            "total_units_bet": round(stakes, 2),
            "gross_return":    round(gross_return, 2),
            "net_profit":      round(net_profit, 2),
            "roi_percentage":  round((net_profit / stakes * 100) if stakes else 0.0, 2),
        }

    def stats_by_profile(self) -> Dict[str, Dict[str, Any]]:
        """Return the same stats broken down by profile name."""
        with self._lock:
            self._cur.execute("""
                SELECT s.profile, s.total_odds, s.units,
                        CASE
                            WHEN SUM(CASE WHEN l.status = 'Lost'    THEN 1 ELSE 0 END) > 0 THEN 'Lost'
                            WHEN SUM(CASE WHEN l.status = 'Pending' THEN 1 ELSE 0 END) > 0 THEN 'Pending'
                        ELSE 'Won'
                    END AS slip_status
                FROM slips s
                LEFT JOIN legs l ON s.slip_id = l.slip_id
                GROUP BY s.slip_id
                HAVING slip_status IN ('Won', 'Lost')
            """)

        agg: Dict[str, dict] = defaultdict(
            lambda: {"settled": 0, "won": 0, "stakes": 0.0, "gross": 0.0}
        )
        for profile, total_odds, units, status in self._cur.fetchall():
            agg[profile]["settled"] += 1
            agg[profile]["stakes"]  += units
            if status == "Won":
                agg[profile]["won"]   += 1
                agg[profile]["gross"] += total_odds * units

        result: Dict[str, Dict[str, Any]] = {}
        for name, d in agg.items():
            net = d["gross"] - d["stakes"]
            result[name] = {
                "profile":    name,
                "settled":    d["settled"],
                "won":        d["won"],
                "win_rate":   round(d["won"] / d["settled"] * 100, 1) if d["settled"] else 0.0,
                "stakes":     round(d["stakes"], 2),
                "net_profit": round(net, 2),
                "roi":        round(net / d["stakes"] * 100, 1) if d["stakes"] else 0.0,
            }
        return result

    def stats_by_market(self, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return per-market-type win/loss counts across all settled legs.

        Useful for identifying which markets are performing best.
        """
        where  = "AND s.profile = ?" if (profile and profile != "all") else ""
        params = [profile] if where else []

        with self._lock:
            self._cur.execute(f"""
                SELECT l.market_type, l.market, l.status, COUNT(*) AS cnt
                FROM legs l
                JOIN slips s ON l.slip_id = s.slip_id
                WHERE l.status IN ('Won', 'Lost') {where}
                GROUP BY l.market_type, l.market, l.status
            """, params)

        return [
            {"market_type": r[0], "market": r[1], "status": r[2], "count": r[3]}
            for r in self._cur.fetchall()
        ]

    def balance_history(self, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return a chronological list of settled slips for balance-curve charts.

        Each entry: {date, profile, total_odds, units, status}
        """
        where  = "WHERE s.profile = ?" if (profile and profile != "all") else ""
        params = [profile] if where else []

        with self._lock:
            self._cur.execute(f"""
                SELECT s.date_generated, s.profile, s.total_odds, s.units,
                    CASE
                        WHEN SUM(CASE WHEN l.status = 'Lost'    THEN 1 ELSE 0 END) > 0 THEN 'Lost'
                        WHEN SUM(CASE WHEN l.status = 'Pending' THEN 1 ELSE 0 END) > 0 THEN 'Pending'
                        ELSE 'Won'
                    END AS slip_status
                FROM slips s
                LEFT JOIN legs l ON s.slip_id = l.slip_id
                {where}
                GROUP BY s.slip_id
                HAVING slip_status IN ('Won', 'Lost')
                ORDER BY s.date_generated ASC
            """, params)

        return [
            {"date": r[0], "profile": r[1], "total_odds": r[2],
             "units": r[3], "status": r[4]}
            for r in self._cur.fetchall()
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # Private helpers
    # ══════════════════════════════════════════════════════════════════════════

    # ── Probability calculation ───────────────────────────────────────────────

    @staticmethod
    def _calc_probabilities(scores: list) -> Dict[str, Dict[str, float]]:
        """Derive result / over-under / BTTS probabilities from historical scores."""
        empty = {
            "result":         {"home": 0.0, "draw": 0.0, "away": 0.0},
            "over_under_2.5": {"over": 0.0, "under": 0.0},
            "btts":           {"yes":  0.0, "no":    0.0},
        }
        if not scores:
            return empty

        total = len(scores)
        home_w = draw_w = away_w = 0
        over   = under  = 0
        btts_y = btts_n = 0

        try:
            for s in scores:
                h = s.get("home", 0) or 0
                a = s.get("away", 0) or 0

                if   h > a: home_w += 1
                elif h < a: away_w += 1
                else:        draw_w += 1

                if h + a > 2.5: over  += 1
                else:            under += 1

                if h > 0 and a > 0: btts_y += 1
                else:                btts_n += 1

        except Exception as e:
            print(f"[BetAssistant] Probability calc error: {e}")
            return empty

        def pct(n: int) -> float:
            return round((n / total) * 100, 1) if total else 0.0

        return {
            "result":         {"home": pct(home_w), "draw": pct(draw_w), "away": pct(away_w)},
            "over_under_2.5": {"over": pct(over),   "under": pct(under)},
            "btts":           {"yes":  pct(btts_y),  "no":   pct(btts_n)},
        }

    # ── Candidate collection ──────────────────────────────────────────────────

    def _collect_candidates(self, cfg: BetSlipConfig) -> List[dict]:
        # TODO - this wont work unless datetimes are fixed first!
        # now       = pd.Timestamp.now()
        # date_from = max(pd.to_datetime(cfg.date_from), now) if cfg.date_from else now
        date_from = pd.to_datetime(cfg.date_from) if cfg.date_from else None
        date_to   = (pd.to_datetime(cfg.date_to) + pd.Timedelta(days=1)) if cfg.date_to else None
        excluded  = set(cfg.excluded_urls or [])
        markets   = cfg.included_market_types

        candidates = []
        for _, row in self._df.iterrows():
            if date_from and row["datetime"] < date_from:
                continue
            if date_to   and row["datetime"] >= date_to:
                continue
            if not row["result_url"]:
                continue
            if row["result_url"] in excluded:
                continue

            match_name = f"{row['home']} vs {row['away']}"

            for m_type, market_cols in MARKET_MAP.items():
                if markets and m_type not in markets:
                    continue
                for prob_col, odds_col, label in market_cols:
                    prob = float(row.get(prob_col, 0))
                    odds = float(row.get(odds_col, 0))
                    if prob >= cfg.probability_floor and odds >= cfg.min_odds:
                        candidates.append({
                            "match":       match_name,
                            "datetime":    row["datetime"],
                            "market":      label,
                            "market_type": m_type,
                            "prob":        prob,
                            "odds":        odds,
                            "result_url":  row["result_url"],
                            "sources":     int(row["sources"]),
                        })

        return candidates

    # ── Leg selection loop ────────────────────────────────────────────────────

    @staticmethod
    def _select_legs(candidates: List[dict], cfg: BetSlipConfig) -> List[dict]:
        stop_threshold = _resolve_stop_threshold(cfg)
        max_legs       = _resolve_max_legs(cfg)
        min_legs       = max(1, int(cfg.target_legs * cfg.min_legs_fill_ratio))
        max_sources    = max((c["sources"] for c in candidates), default=1)

        selected:     List[dict] = []
        seen_matches: set        = set()
        total_odds:   float      = 1.0

        while len(selected) < max_legs:
            if total_odds >= cfg.target_odds * stop_threshold and len(selected) >= min_legs:
                break

            remaining_target = cfg.target_odds / total_odds
            remaining_legs   = max(1, cfg.target_legs - len(selected))
            ideal_per_leg    = remaining_target ** (1.0 / remaining_legs)

            scored = [
                {**c, **dict(zip(("tier", "score"),
                                 _score_pick(c, ideal_per_leg, max_sources, cfg)))}
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

        return selected

    # ── DB row → structured slip ──────────────────────────────────────────────

    @staticmethod
    def _rows_to_slips(rows: list) -> List[Dict[str, Any]]:
        """
        Group flat SQL rows into nested slip + legs dicts.

        Slip status derivation:
            Lost    — any leg is Lost
            Pending — no Lost leg, but at least one Pending
            Won     — all legs Won
        """
        slips: Dict[int, dict] = {}

        for (slip_id, date, profile, total_odds, units,
             match, dt, market, market_type, odds, status, result_url) in rows:

            if slip_id not in slips:
                slips[slip_id] = {
                    "slip_id":        slip_id,
                    "date_generated": date,
                    "profile":        profile,
                    "total_odds":     total_odds,
                    "units":          units,
                    "legs":           [],
                    "slip_status":    "Won",
                }

            if match:
                slips[slip_id]["legs"].append({
                    "match_name":  match,
                    "datetime":    datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S"),
                    "market":      market,
                    "market_type": market_type,
                    "odds":        odds,
                    "status":      status,
                    "result_url":  result_url,
                })

            if status == "Lost":
                slips[slip_id]["slip_status"] = "Lost"
            elif status == "Live" and slips[slip_id]["slip_status"] not in ("Lost",):
                slips[slip_id]["slip_status"] = "Live"
            elif status == "Pending" and slips[slip_id]["slip_status"] not in ("Lost", "Live"):
                slips[slip_id]["slip_status"] = "Pending"

        return list(slips.values())