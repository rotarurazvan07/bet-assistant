"""
dashboard/logic.py
══════════════════
DashboardLogic — pure business layer.

Wraps BetAssistant (slip storage, building, validation, stats) together with
MatchesManager (match data source).  The dashboard UI classes never touch
BetAssistant or MatchesManager directly.

Public API
──────────
  refresh_data(db_path)            Load / reload matches from the source DB.
  filter_matches(search, from, to) Filtered match DataFrame view.
  build_slip(cfg)                  Build a bet slip from a BetSlipConfig.
  save_slip(profile, legs, units)  Persist a slip; return slip_id.
  validate_slips()                 Scrape live results; return validation summary.
  get_slips(profile)               All slips (+ legs) optionally filtered.
  stats(profile)                   Aggregate stats dict.
  balance_history(profile)         Chronological settled slip list.
  get_settled_legs(profile)        Flat list of settled leg dicts with result_url.
  match_df                         Property: current match DataFrame (read-only).
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

import pandas as pd

from bet_framework.core.types import Outcome

from bet_framework.BetAssistant import BetAssistant, BetSlipConfig
from bet_framework.MatchesManager import MatchesManager


class DashboardLogic:
    """
    Mediator between the Dash UI and the BetAssistant + MatchesManager.

    All state lives here (server-side singleton). Callbacks only read from
    this object — they never own data in client-side dcc.Stores.

    The ``slips_version`` counter is bumped on slip/status changes.
    The ``matches_version`` counter is bumped on match data changes.
    Lightweight polling callbacks detect changes without re-querying.
    """

    def __init__(self, matches_db_path: str, slips_db_path: str) -> None:
        self._matches_db_path = matches_db_path
        self._slips_db_path = slips_db_path
        self._assistant = BetAssistant(slips_db_path)
        self._matches_manager = MatchesManager(matches_db_path)
        self.slips_version = 0  # bumped on slip/status changes
        self.matches_version = 0  # bumped on match data changes

        # Caches for heavy operations
        self._filter_cache_key = None
        self._filter_cache_df = None
        self._build_slip_cache = {}

        # Pre-load match data so it's ready before any browser connects
        self.refresh_data()

    # ── Match data ────────────────────────────────────────────────────────────

    def refresh_data(self) -> pd.DataFrame:
        raw_df = self._matches_manager.fetch_matches()
        self._assistant.load_matches(raw_df)
        self.bump_matches_version()
        return self._assistant._df.copy()

    def bump_slips_version(self) -> None:
        """Manually increment the slips version to trigger UI refreshes."""
        self.slips_version += 1

    def bump_matches_version(self) -> None:
        """Increment the matches version to trigger match data UI refreshes."""
        self.matches_version += 1
        self._filter_cache_key = None
        self._filter_cache_df = None
        self._build_slip_cache.clear()

    def filter_matches(
        self,
        search_text: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> pd.DataFrame:
        """Return a filtered view of the loaded match DataFrame."""
        key = (search_text, date_from, date_to)
        if self._filter_cache_key == key and self._filter_cache_df is not None:
            return self._filter_cache_df

        df = self._assistant.filter_matches(
            search_text=search_text, date_from=date_from, date_to=date_to
        )
        self._filter_cache_key = key
        self._filter_cache_df = df
        return df

    def pull_matches_db(self, matches_db_path: str) -> str:
        import urllib.error
        import urllib.request

        repo = os.environ.get("REPO", "rotarurazvan07/bet-assistant")
        url = f"https://github.com/{repo}/releases/download/latest-db/final_matches.db"

        try:
            urllib.request.urlretrieve(url, matches_db_path)
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to download DB from Release: {e}")

        self.refresh_data()
        return "Pull successful"

    @property
    def last_pull_timestamp(self) -> str:
        """Returns the last modification time of the matches database."""
        try:
            mtime = os.path.getmtime(self._matches_db_path)
            from datetime import datetime

            return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Unknown"

    @property
    def match_df(self) -> pd.DataFrame:
        """Current match DataFrame (read-only reference)."""
        return self._assistant._df

    # ── Slip building ─────────────────────────────────────────────────────────

    def build_slip(
        self,
        cfg: BetSlipConfig,
        extra_excluded_urls: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build a bet slip from a BetSlipConfig.

        Returns list of leg dicts:
            match, market, market_type, consensus, odds, result_url, sources, tier, score
        """
        cfg_hash = repr(cfg)
        key = (cfg_hash, tuple(extra_excluded_urls) if extra_excluded_urls else None)

        if getattr(self, "_build_slip_cache", None) is None:
            self._build_slip_cache = {}

        if key in self._build_slip_cache:
            return self._build_slip_cache[key]

        res = self._assistant.build_slip(cfg, extra_excluded_urls=extra_excluded_urls)
        self._build_slip_cache[key] = res
        return res

    def generate_slips(self, profiles: dict[str, tuple]) -> dict[str, Any]:
        """
        Build and save slips for the given profiles.

        Parameters
        ----------
        profiles : {profile_name: (BetSlipConfig, units)}
        """
        results = {}
        for name, (cfg, units, count) in profiles.items():
            for _ in range(count):
                legs = self._assistant.build_slip_auto_exclude(cfg)
                if not legs:
                    break

                slip_id = self._assistant.save_slip(name, legs, units)
                results[name] = results.get(name, [])
                results[name].append(slip_id)
        self.bump_slips_version()
        return results

    # ── Slip persistence ──────────────────────────────────────────────────────

    def save_slip(
        self,
        profile: str,
        legs: list[dict[str, Any]],
        units: float = 1.0,
    ) -> int:
        """Persist a bet slip; return the new slip_id."""
        slip_id = self._assistant.save_slip(profile, legs, units)
        self.bump_slips_version()
        return slip_id

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_slips(self) -> dict[str, Any]:
        """
        Scrape live / finished results and update leg statuses.

        Returns
        -------
        {
            "checked":  int,
            "settled":  int,
            "errors":   int,
            "live":     [{"leg_id", "match_name", "score", "minute"}, ...]
        }
        """
        result = self._assistant.validate_slips()
        self.bump_slips_version()
        return result

    # ── Slip retrieval ────────────────────────────────────────────────────────

    def get_slips(
        self,
        profile: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[BetSlip]:
        """
        Return all slips with their legs, optionally filtered by profile and date horizon.
        """
        if profile == "all":
            profile = None

        slips = self._assistant.get_slips(profile)

        if date_from:
            slips = [
                s
                for s in slips
                if s.date_generated.split("T")[0] >= date_from
            ]
        if date_to:
            slips = [
                s
                for s in slips
                if s.date_generated.split("T")[0] <= date_to
            ]
        return slips

    def get_pending_urls(self) -> set:
        """result_urls already present in pending/live slip legs."""
        slips = self.get_slips()
        urls = set()
        for slip in slips:
            if slip.slip_status == "Pending":
                for leg in slip.legs:
                    if leg.status in ("Pending", "Live"):
                        urls.add(leg.result_url)
        return urls

    def delete_slip(self, slip_id: int) -> None:
        self._assistant.delete_slip(slip_id)
        self.bump_slips_version()

    # ── Statistics ────────────────────────────────────────────────────────────

    def stats(
        self,
        profile: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        slips = self.get_slips(profile, date_from, date_to)
        settled = [s for s in slips if s.slip_status in ("Won", "Lost")]
        won = [s for s in settled if s.slip_status == "Won"]

        n_settled = len(settled)
        n_won = len(won)
        stakes = sum(s.units for s in settled)
        gross_return = sum(s.total_odds * s.units for s in won)
        net_profit = gross_return - stakes

        return {
            "total_settled": n_settled,
            "total_won_count": n_won,
            "win_rate": round((n_won / n_settled * 100) if n_settled else 0.0, 2),
            "total_units_bet": round(stakes, 2),
            "gross_return": round(gross_return, 2),
            "net_profit": round(net_profit, 2),
            "roi_percentage": round((net_profit / stakes * 100) if stakes else 0.0, 2),
        }

    # ── Analytics ─────────────────────────────────────────────────────────────
    def daily_summary(
        self,
        profile: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        slips = self.get_slips(profile or "all", date_from, date_to)
        settled_slips = [s for s in slips if s.slip_status in (Outcome.WON, Outcome.LOST)]

        settled_slips.sort(key=lambda x: x.date_generated)

        daily_stats = {}
        for s in settled_slips:
            day = s.date_generated
            if day not in daily_stats:
                daily_stats[day] = {
                    "date": day,
                    "slips_count": 0,
                    "units_bet": 0.0,
                    "units_won": 0.0,
                    "won_count": 0,
                }

            stats = daily_stats[day]
            stats["slips_count"] += 1
            stats["units_bet"] += s.units
            if s.slip_status == Outcome.WON:
                stats["units_won"] += s.total_odds * s.units
                stats["won_count"] += 1

        summary = []
        cum_bet = 0.0
        cum_profit = 0.0
        cum_won_count = 0
        cum_settled_count = 0

        sorted_days = sorted(daily_stats.keys())
        for day in sorted_days:
            stats = daily_stats[day]
            profit = stats["units_won"] - stats["units_bet"]

            cum_bet += stats["units_bet"]
            cum_profit += profit
            cum_won_count += stats["won_count"]
            cum_settled_count += stats["slips_count"]

            summary.append(
                {
                    "date": day,
                    "slips_count": stats["slips_count"],
                    "units_bet": round(stats["units_bet"], 2),
                    "units_won": round(stats["units_won"], 2),
                    "net_profit": round(profit, 2),
                    "cumulative_profit": round(cum_profit, 2),
                    "cumulative_bet": round(cum_bet, 2),
                    "roi_percentage": round(
                        (cum_profit / cum_bet * 100) if cum_bet else 0, 2
                    ),
                    "win_rate": round(
                        (cum_won_count / cum_settled_count * 100)
                        if cum_settled_count
                        else 0,
                        2,
                    ),
                }
            )

        return summary

    def market_accuracy(
        self,
        profile: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        slips = self.get_slips(profile or "all", date_from, date_to)

        market_stats = {}
        for slip in slips:
            for leg in slip.legs:
                if leg.status not in (Outcome.WON, Outcome.LOST):
                    continue

                mtype = leg.market or "Unknown"
                if mtype not in market_stats:
                    market_stats[mtype] = {
                        "market": mtype,
                        "won": 0,
                        "lost": 0,
                        "total": 0,
                    }

                market_stats[mtype]["total"] += 1
                if leg.status == Outcome.WON:
                    market_stats[mtype]["won"] += 1
                else:
                    market_stats[mtype]["lost"] += 1

        results = []
        for m in market_stats.values():
            m["accuracy"] = round((m["won"] / m["total"] * 100) if m["total"] else 0, 2)
            results.append(m)

        return sorted(results, key=lambda x: x["total"], reverse=True)

    def correlation_data(
        self,
        profile: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        slips = self.get_slips(profile or "all", date_from, date_to)
        settled = [s for s in slips if s.slip_status in (Outcome.WON, Outcome.LOST)]

        data = []
        for s in settled:
            data.append(
                {
                    "legs_count": len(s.legs),
                    "total_odds": round(s.total_odds, 2),
                    "units": s.units,
                    "status": s.slip_status,
                    "profit": round(
                        (s.total_odds * s.units - s.units)
                        if s.slip_status == Outcome.WON
                        else -s.units,
                        2,
                    ),
                }
            )
        return data

    # ── Profile helpers ───────────────────────────────────────────────────────

    def get_excluded_urls(self) -> list[str]:
        """URLs that must be excluded from new slip generation."""
        return self._assistant.get_excluded_urls()
