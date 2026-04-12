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
import re
from datetime import datetime
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup
from scrape_kit import BaseStorageManager, get_logger, scrape

from bet_framework.core.consensus import calc_consensus
from bet_framework.core.outcomes import determine_outcome, parse_score
from bet_framework.core.scoring import (
    resolve_max_legs,
    resolve_stop_threshold,
    score_pick,
)
from bet_framework.core.Slip import (
    BetLeg,
    BetSlip,
    BetSlipConfig,
    CandidateLeg,
    LegOutcomeInfo,
    MatchResultInfo,
    ValidationReport,
    get_profile,
)
from bet_framework.core.types import MarketLabel, MarketType, MatchStatus, Outcome
from bet_framework.core.utils import coerce_datetime_str, is_valid_url

logger = get_logger(__name__)

# (cons_col, odds_col, display_label)
MARKET_MAP: dict[MarketType, list[tuple[str, str, MarketLabel]]] = {
    MarketType.RESULT: [
        ("cons_home", "odds_home", MarketLabel.HOME),
        ("cons_draw", "odds_draw", MarketLabel.DRAW),
        ("cons_away", "odds_away", MarketLabel.AWAY),
    ],
    MarketType.OVER_UNDER_25: [
        ("cons_over", "odds_over", MarketLabel.OVER_25),
        ("cons_under", "odds_under", MarketLabel.UNDER_25),
    ],
    MarketType.BTTS: [
        ("cons_btts_yes", "odds_btts_yes", MarketLabel.BTTS_YES),
        ("cons_btts_no", "odds_btts_no", MarketLabel.BTTS_NO),
    ],
}


def _parse_match_result_html(html: str, url: str) -> MatchResultInfo:
    """
    Parse a result page HTML and return the MatchResultInfo.
    """
    result = MatchResultInfo(status=MatchStatus.PENDING)
    soup = BeautifulSoup(html, "html.parser")

    status_text = _extract_status_text(soup)
    is_finished, is_live, minute = _determine_match_status(status_text, soup)

    # If match hasn't started yet, don't look for scores (prevents future stat leaks)
    if not (is_finished or is_live):
        return result

    score = _extract_score(soup)
    if score:
        result.score = score

    if is_finished:
        result.status = "FT"
    elif is_live:
        result.status = "LIVE"
        result.minute = minute

    return result


def _extract_status_text(soup: BeautifulSoup) -> str:
    """Extract status text from specialized containers or fallback to global search."""
    status_container = soup.find(id="status-container")
    gametime_container = soup.find(id="gametime-container")

    status_parts = []
    if status_container:
        status_parts.append(status_container.get_text(strip=True))
    if gametime_container:
        status_parts.append(gametime_container.get_text(strip=True))
    status_text = " ".join(status_parts).strip()

    # Global fallback for status if containers are empty
    if not status_text:
        all_text_start = soup.get_text(separator=" ", strip=True)[:2000]
        for marker in [MatchStatus.FT, MatchStatus.FINISHED, MatchStatus.HT]:
            if marker in all_text_start:
                status_text = marker
                break

    return status_text


def _determine_match_status(status_text: str, soup: BeautifulSoup) -> tuple[bool, bool, str]:
    """
    Determine if match is finished or live, and extract minute if live.
    Returns: (is_finished, is_live, minute)
    """
    is_finished = MatchStatus.FT in status_text or MatchStatus.FINISHED in status_text
    minute_rx = re.compile(r"(\d+'|HT)")

    # Check status_text for minute
    match_live = minute_rx.search(status_text)
    if match_live:
        return is_finished, True, match_live.group(1)

    # Heuristic: search globally for minutes if specialized tags missed it
    if not is_finished:
        match_live = minute_rx.search(soup.get_text()[:2000])
        if match_live:
            return is_finished, True, match_live.group(1)

    return is_finished, False, ""


def _extract_score(soup: BeautifulSoup) -> str | None:
    """
    Extract score from the page. Tries multiple strategies in order of priority.
    Returns score as "X:Y" or None if not found.
    """
    score_rx = re.compile(r"(\d{1,2})\s*:\s*(\d{1,2})")

    # 1. Prioritize Soccervista livescore-container
    score_container = soup.find(id="livescore-container")
    score_text = score_container.get_text(strip=True) if score_container else ""
    match_score = score_rx.search(score_text)

    if not match_score:
        # 2. Fallback: search in common score-like classes
        score_div = soup.find("div", class_=re.compile(r"font-bold.*text-center", re.I))
        if score_div:
            match_score = score_rx.search(score_div.get_text(strip=True))

    if not match_score:
        # 3. Last resort: global search for the FIRST X:Y pattern in page header
        match_score = score_rx.search(soup.get_text()[:2000])

    if match_score:
        return f"{match_score.group(1)}:{match_score.group(2)}"

    return None


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
                # MD5 used for deterministic ID generation, not security (B324 fix)
                match_id = f"match_{idx}_{hashlib.md5(match_key.encode(), usedforsecurity=False).hexdigest()}"
                dt = row["datetime"]
                odds = row.get("odds") or {}
                scores = row.get("scores") or []
                cons_data = calc_consensus(scores)
                n_sources = len({s.get("source", "") for s in scores if s.get("source")})

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
            mask = out["home"].str.contains(search_text, case=False, na=False) | out["away"].str.contains(
                search_text, case=False, na=False
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
        extra_excluded_urls: list[str] | None = None,
    ) -> list[CandidateLeg]:
        """
        Build a list of candidate legs passing the risk profile filters.

        Returns:
            list[CandidateLeg]: Structured leg data.
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
        legs: list[CandidateLeg],
        units: float = 1.0,
    ) -> int:
        """
        Persist a bet slip and its legs to the database.

        Parameters
        ----------
        profile : Descriptive label stored alongside the slip (e.g. "medium_risk").
        legs    : List of CandidateLeg objects.
        units   : Stake size in units (default 1.0).

        Returns
        -------
        The auto-assigned slip_id.
        """
        with self.db_lock:
            total_odds = math.prod(leg.odds for leg in legs)
            date_today = pd.Timestamp.now().strftime("%Y-%m-%d")

            cursor = self.conn.execute(
                "INSERT INTO slips (date_generated, profile, total_odds, units) VALUES (?, ?, ?, ?)",
                (date_today, profile, total_odds, units),
            )
            slip_id = cursor.lastrowid

            for leg in legs:
                # Store market value as string, not enum representation
                market_value = leg.market.value if hasattr(leg.market, "value") else str(leg.market)
                market_type_value = (
                    leg.market_type.value
                    if hasattr(leg.market_type, "value")
                    else str(leg.market_type)
                    if leg.market_type
                    else None
                )
                self.conn.execute(
                    """INSERT INTO legs
                    (slip_id, match_name, match_datetime, market, market_type, odds, result_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        slip_id,
                        leg.match_name,
                        coerce_datetime_str(leg.datetime),
                        market_value,
                        market_type_value,
                        leg.odds,
                        leg.result_url,
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

    def settle_leg_manually(
        self,
        leg_id: int,
        score: str,
        market: str,
        market_type: str,
    ) -> str:
        """
        Manually settle a single leg from a plain score string.

        Parameters
        ----------
        leg_id      : Primary key of the leg row.
        score       : Full-time score in 'H:A' format (e.g. '2:1').
        market      : Leg market label (e.g. '1', 'X', 'Over 2.5').
        market_type : One of 'result', 'btts', 'over_under_2.5'.

        Returns
        -------
        The outcome string ('Won' or 'Lost') written to the database.

        Raises
        ------
        ValueError  : If *score* cannot be parsed.
        """
        h, a = parse_score(score)
        outcome = determine_outcome(h, a, market, market_type)
        self.update_leg(leg_id, outcome)
        logger.info(f"[BetAssistant] Manually settled leg {leg_id} → {outcome} ({score})")
        return outcome

    def score_match(
        self,
        row: dict,
        cfg: BetSlipConfig | str = "medium_risk",
    ) -> list[dict]:
        """
        Score a single match row against a config and return candidate leg dicts.

        Useful for inspecting why a particular match was or was not included in a
        slip, or for building custom selection pipelines.

        Parameters
        ----------
        row : A dict with the same keys produced by :meth:`load_matches`, e.g.:
              home, away, datetime, result_url, sources,
              cons_home, cons_draw, cons_away, ... odds_home, ...
        cfg : A named profile string or a BetSlipConfig instance.

        Returns
        -------
        List of candidate dicts (may be empty) — each contains
        market, market_type, consensus, odds, tier, score.
        """
        if isinstance(cfg, str):
            cfg = get_profile(cfg)

        candidates: list[dict] = []
        url = row.get("result_url")
        if not is_valid_url(url):
            return candidates

        match_name = f"{row['home']} vs {row['away']}"
        for m_type, market_cols in MARKET_MAP.items():
            for cons_col, odds_col, label in market_cols:
                if cfg.included_markets and label not in cfg.included_markets:
                    continue
                consensus = float(row.get(cons_col, 0))
                odds = float(row.get(odds_col, 0))
                if consensus >= cfg.consensus_floor and odds >= cfg.min_odds:
                    opt = {
                        "match": match_name,
                        "datetime": row["datetime"],
                        "market": label,
                        "market_type": m_type,
                        "consensus": consensus,
                        "odds": odds,
                        "result_url": url,
                        "sources": int(row.get("sources", 0)),
                    }
                    ideal = cfg.target_odds ** (1.0 / max(1, cfg.target_legs))
                    max_s = int(row.get("sources", 1)) or 1
                    tier, sc = score_pick(opt, ideal, max_s, cfg)
                    candidates.append({**opt, "tier": tier, "score": sc})

        return candidates

    def build_slip_from_df(
        self,
        df: pd.DataFrame,
        profile_or_config: str | BetSlipConfig = "medium_risk",
        extra_excluded_urls: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        One-shot convenience: load *df*, build a slip, and return legs without
        persisting anything to the database.

        Equivalent to calling :meth:`load_matches` then :meth:`build_slip`,
        but restores the original internal DataFrame afterwards so callers
        that already have data loaded are not affected.
        """
        previous_df = self._df.copy()
        try:
            self.load_matches(df)
            return self.build_slip(profile_or_config, extra_excluded_urls)
        finally:
            self._df = previous_df

    @staticmethod
    def derive_slip_status(legs: list[dict]) -> str:
        """
        Derive the overall slip status from a list of leg dicts (each must have
        a 'status' key).  Delegates to :func:`slip_utils.derive_slip_status`.

        >>> BetAssistant.derive_slip_status([{"status": "Won"}, {"status": "Lost"}])
        'Lost'
        """
        return derive_slip_status([leg["status"] for leg in legs])

    def process_leg_result(
        self,
        leg_id: int,
        info: MatchResultInfo,
        market: MarketLabel,
        market_type: MarketType,
        match_name: str,
    ) -> LegOutcomeInfo | None:
        """
        Evaluate a MatchResultInfo against a specific leg's market, calculate outcome,
        and apply the update to the SQLite database if the leg status has advanced.
        Can be used manually to force-process an explicit match result object against a leg.
        """
        outcome_info = LegOutcomeInfo(
            leg_id=leg_id,
            match_name=match_name,
            market=market,
            score=info.score,
            minute=info.minute,
        )

        if info.status == MatchStatus.FT and info.score:
            try:
                h, a = parse_score(info.score)
                outcome_info.outcome = determine_outcome(h, a, market, market_type)
            except Exception:
                pass

        if info.status == MatchStatus.FT and outcome_info.outcome in (
            Outcome.WON,
            Outcome.LOST,
        ):
            self.update_leg(leg_id, outcome_info.outcome)
            return outcome_info

        elif info.status == MatchStatus.LIVE and info.score:
            self.update_leg(leg_id, Outcome.LIVE)
            return outcome_info

        return None

    def validate_slips(self) -> ValidationReport:
        self.reopen_if_changed()

        pending = self.fetch_rows(
            "SELECT leg_id, result_url, market, market_type, match_name FROM legs WHERE status IN ('Pending', 'Live')"
        )

        checked = len(pending)
        errors = [0]
        live_matches: list[LegOutcomeInfo] = []
        settled_matches: list[LegOutcomeInfo] = []

        url_to_legs = {}
        for row in pending:
            leg_id, url, market, market_type, match_name = tuple(row)
            if url not in url_to_legs:
                url_to_legs[url] = []
            url_to_legs[url].append((leg_id, market, market_type, match_name))

        urls = list(url_to_legs.keys())
        if not urls:
            return ValidationReport(checked=0, settled=[], live=[], errors=0)

        def _handle_url(url: str, html: str) -> None:
            try:
                base_info = _parse_match_result_html(html, url)

                for leg_id, market, market_type, match_name in url_to_legs[url]:
                    outcome_info = self.process_leg_result(leg_id, base_info, market, market_type, match_name)
                    if not outcome_info:
                        continue

                    if base_info.status == MatchStatus.FT and outcome_info.outcome in (
                        Outcome.WON,
                        Outcome.LOST,
                    ):
                        settled_matches.append(outcome_info)

                    elif base_info.status == MatchStatus.LIVE:
                        live_matches.append(outcome_info)

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

        return ValidationReport(
            checked=checked,
            settled=settled_matches,
            live=live_matches,
            errors=errors[0],
        )

    def update_leg(self, leg_id: int, status: str) -> None:
        """Manually override a leg outcome ('Won', 'Lost', or 'Pending')."""
        with self.db_lock:
            self.conn.execute("UPDATE legs SET status = ? WHERE leg_id = ?", (status, leg_id))
            self.conn.commit()

    # ══════════════════════════════════════════════════════════════════════════
    # Private helpers
    # ══════════════════════════════════════════════════════════════════════════

    # ── Consensus calculation ─────────────────────────────────────────────────

    @staticmethod
    def _calc_consensus(scores: list) -> dict[str, dict[str, float]]:
        """Derive result / over-under / BTTS consensus from historical scores."""
        return calc_consensus(scores)

    # ── Candidate collection ──────────────────────────────────────────────────

    def _collect_candidates(self, cfg: BetSlipConfig) -> list[dict]:
        # TODO - this wont work unless datetimes are fixed first!
        # now       = pd.Timestamp.now()
        # date_from = max(pd.to_datetime(cfg.date_from), now) if cfg.date_from else now
        date_from = pd.to_datetime(cfg.date_from) if cfg.date_from else None
        date_to = (pd.to_datetime(cfg.date_to) + pd.Timedelta(days=1)) if cfg.date_to else None
        excluded = set(cfg.excluded_urls or [])
        markets = cfg.included_markets

        candidates = []
        for _, row in self._df.iterrows():
            if date_from and row["datetime"] < date_from:
                continue
            if date_to and row["datetime"] >= date_to:
                continue
            url = row.get("result_url")
            if not is_valid_url(url) or url in excluded:
                continue

            match_name = f"{row['home']} vs {row['away']}"

            for m_type, market_cols in MARKET_MAP.items():
                for cons_col, odds_col, label in market_cols:
                    if markets and label not in markets:
                        continue
                    consensus = float(row.get(cons_col, 0))
                    odds = float(row.get(odds_col, 0))
                    if consensus >= cfg.consensus_floor and odds >= cfg.min_odds:
                        # Apply min_source_edge hard filter
                        if cfg.min_source_edge > 0.0:
                            implied_prob = 1.0 / odds
                            source_edge = (consensus / 100.0) - implied_prob
                            if source_edge < cfg.min_source_edge:
                                continue
                        candidates.append(
                            CandidateLeg(
                                match_name=match_name,
                                datetime=row["datetime"],
                                market=label,
                                market_type=m_type,
                                consensus=consensus,
                                odds=odds,
                                result_url=row["result_url"],
                                sources=int(row["sources"]),
                            )
                        )

        return candidates

    # ── Leg selection loop ────────────────────────────────────────────────────

    @staticmethod
    def _select_legs(candidates: list[CandidateLeg], cfg: BetSlipConfig) -> list[CandidateLeg]:
        stop_threshold = resolve_stop_threshold(cfg)
        max_legs = resolve_max_legs(cfg)
        min_legs = max(1, int(cfg.target_legs * cfg.min_legs_fill_ratio))
        max_sources = max((c.sources for c in candidates), default=1)

        selected: list[CandidateLeg] = []
        seen_matches: set = set()
        total_odds: float = 1.0

        while len(selected) < max_legs:
            if total_odds >= cfg.target_odds * stop_threshold and len(selected) >= min_legs:
                break

            remaining_target = cfg.target_odds / total_odds
            remaining_legs = max(1, cfg.target_legs - len(selected))
            ideal_per_leg = remaining_target ** (1.0 / remaining_legs)

            scored = []
            for c in candidates:
                if c.match_name not in seen_matches:
                    tier, score = score_pick(c, ideal_per_leg, max_sources, cfg)
                    scored.append((tier, score, c))

            if not scored:
                break

            scored.sort(key=lambda x: (x[0], -x[1]))
            tier, score, best = scored[0]

            # Quality floor stop condition: check if best candidate's quality score is too low
            # We need to extract the quality component separately. For simplicity, we'll
            # approximate quality by checking if final score is below threshold, but note
            # that this includes balance component. A more precise implementation would
            # require refactoring score_pick to return quality separately.
            # However, per spec: "check if best candidate's quality score < min_pick_quality"
            # Since quality is part of final score, and balance can be 0-1, we need to
            # compute quality separately or use a heuristic.
            # Let's compute quality score for the best candidate to check against min_pick_quality.
            if cfg.min_pick_quality is not None and cfg.min_pick_quality > 0.0:
                # Recompute quality component for the best candidate
                from bet_framework.core.scoring import score_consensus, score_sources
                consensus_val = best.consensus
                if cfg.consensus_shrinkage_k is not None:
                    from bet_framework.core.scoring import adjusted_consensus
                    consensus_val = adjusted_consensus(consensus_val, best.sources, cfg.consensus_shrinkage_k)
                c_score = score_consensus(consensus_val, cfg)
                s_score = score_sources(best.sources, max_sources)
                quality_score = cfg.consensus_vs_sources * c_score + (1 - cfg.consensus_vs_sources) * s_score
                if quality_score < cfg.min_pick_quality:
                    # Stop building - no high-quality picks remaining
                    break

            # Populate UI-only fields
            best.tier = tier
            best.score = score

            selected.append(best)
            seen_matches.add(best.match_name)
            total_odds *= best.odds

        if len(selected) < min_legs:
            return []

        return selected

    # ── DB row → structured slip ──────────────────────────────────────────────

    @staticmethod
    def _derive_slip_status(leg_statuses: list[str]) -> Outcome:
        """
        Derive the overall slip status from a list of leg statuses.

        Priority: Lost > Live > Pending > Won
        """
        statuses = set(leg_statuses)
        if Outcome.LOST in statuses:
            return Outcome.LOST
        if Outcome.LIVE in statuses:
            return Outcome.LIVE
        if Outcome.PENDING in statuses:
            return Outcome.PENDING
        return Outcome.WON

    @staticmethod
    def _rows_to_slips(rows: list) -> list[BetSlip]:
        """
        Group flat SQL rows from the slips+legs JOIN into nested BetSlip objects.
        """
        slips: dict[int, BetSlip] = {}

        for (
            slip_id,
            date,
            profile,
            total_odds,
            units,
            match,
            dt,
            market,
            m_type,
            odds,
            status,
            url,
        ) in rows:
            if slip_id not in slips:
                slips[slip_id] = BetSlip(
                    slip_id=slip_id,
                    date_generated=date,
                    profile=profile,
                    total_odds=total_odds,
                    units=units,
                    legs=[],
                )

            if match:
                leg_dt = None
                if dt:
                    try:
                        leg_dt = datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
                    except (ValueError, TypeError):
                        leg_dt = dt

                slips[slip_id].legs.append(
                    BetLeg(
                        match_name=match,
                        datetime=leg_dt,
                        market=market,
                        market_type=m_type,
                        odds=odds,
                        status=status,
                        result_url=url,
                    )
                )

        result = []
        for slip in slips.values():
            slip.slip_status = BetAssistant._derive_slip_status([leg.status for leg in slip.legs])
            result.append(slip)

        return result
