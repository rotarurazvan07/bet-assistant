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
  stats_by_profile()               Per-profile stats dict.
  stats_by_market(profile)         Per-market win/loss list.
  balance_history(profile)         Chronological settled slip list.
  get_settled_legs(profile)        Flat list of settled leg dicts with result_url.
  match_df                         Property: current match DataFrame (read-only).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import os
import subprocess
import pandas as pd

from bet_framework.BetAssistant import BetAssistant, BetSlipConfig
from bet_framework.MatchesManager import MatchesManager

class DashboardLogic:
    """
    Mediator between the Dash UI and the BetAssistant + MatchesManager.

    Parameters
    ----------
    db_path   : Path to the SQLite file used by BetAssistant (slips + legs).
    """

    def __init__(self, matches_db_path: str, slips_db_path: str) -> None:
        self._matches_db_path  = matches_db_path
        self._slips_db_path    = slips_db_path
        self._assistant        = BetAssistant(slips_db_path)
        self._matches_manager       = MatchesManager(matches_db_path)

    # ── Match data ────────────────────────────────────────────────────────────

    def refresh_data(self) -> pd.DataFrame:
        raw_df = self._matches_manager.fetch_matches()
        self._assistant.load_matches(raw_df)
        return self._assistant._df.copy()

    def filter_matches(
        self,
        search_text: Optional[str] = None,
        date_from:   Optional[str] = None,
        date_to:     Optional[str] = None,
    ) -> pd.DataFrame:
        """Return a filtered view of the loaded match DataFrame."""
        return self._assistant.filter_matches(
            search_text=search_text,
            date_from=date_from,
            date_to=date_to,
        )

    def pull_matches_db(self, matches_db_path: str) -> str:
        repo     = os.environ.get("REPO",          "rotarurazvan07/bet-assistant")
        artifact = os.environ.get("ARTIFACT_NAME", "all-matches-combined-db")
        cmd = (
            f"rm -f {matches_db_path} && "
            f"gh run download -R {repo} -n {artifact} --dir {os.path.dirname(os.path.abspath(matches_db_path))}"
        )
        subprocess.run(cmd, shell=True, check=True)
        self.refresh_data()
        return "Pull successful"

    @property
    def match_df(self) -> pd.DataFrame:
        """Current match DataFrame (read-only reference)."""
        return self._assistant._df

    # ── Slip building ─────────────────────────────────────────────────────────

    def build_slip(
        self,
        cfg: BetSlipConfig,
        extra_excluded_urls: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build a bet slip from a BetSlipConfig.

        Returns list of leg dicts:
            match, market, market_type, prob, odds, result_url, sources, tier, score
        """
        return self._assistant.build_slip(cfg, extra_excluded_urls=extra_excluded_urls)

    def generate_slips(self, profiles: Dict[str, tuple]) -> Dict[str, Any]:
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
                if legs:
                    slip_id       = self._assistant.save_slip(name, legs, units)
                    results[name] = results.get(name, [])
                    results[name].append(slip_id)
        return results

    # ── Slip persistence ──────────────────────────────────────────────────────

    def save_slip(
        self,
        profile: str,
        legs:    List[Dict[str, Any]],
        units:   float = 1.0,
    ) -> int:
        """Persist a bet slip; return the new slip_id."""
        return self._assistant.save_slip(profile, legs, units)

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_slips(self) -> Dict[str, Any]:
        """
        Scrape live / finished results and update leg statuses.

        Returns
        -------
        {
            "checked":  int,
            "settled":  int,
            "errors":   int,
            "live":     [{"leg_id", "match_name", "score", "minute"}, …]
        }
        """
        return self._assistant.validate_slips()

    # ── Slip retrieval ────────────────────────────────────────────────────────

    def get_slips(self, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return all slips with their legs, optionally filtered by profile.

        Each slip dict:
            slip_id, date_generated, profile, total_odds, units,
            slip_status, legs: [{match_name, market, market_type, odds, status, result_url}]
        """
        return self._assistant.get_slips(profile)

    def get_pending_urls(self) -> set:
        """result_urls already present in pending/live slip legs."""
        slips = self.get_slips()
        urls  = set()
        for slip in slips:
            if slip["slip_status"] == "Pending":
                for leg in slip["legs"]:
                    if leg["status"] in ("Pending", "Live"):
                        urls.add(leg["result_url"])
        return urls

    def delete_slip(self, slip_id: int) -> None:
        self._assistant.delete_slip(slip_id)

    # ── Statistics ────────────────────────────────────────────────────────────

    def stats(self, profile: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate stats over settled slips.

        Returns: total_settled, total_won_count, win_rate, total_units_bet,
                 gross_return, net_profit, roi_percentage
        """
        return self._assistant.stats(profile)

    def stats_by_profile(self) -> Dict[str, Dict[str, Any]]:
        """Per-profile breakdown of stats."""
        return self._assistant.stats_by_profile()

    def stats_by_market(self, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        """Per-market-type win/loss counts across settled legs."""
        return self._assistant.stats_by_market(profile)

    def balance_history(self, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        """Chronological list of settled slips for balance-curve charts."""
        return self._assistant.balance_history(profile)

    def get_settled_legs(
        self, profile: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Flat list of all settled legs (Won / Lost) with their result_url.

        Used by the source-reliability chart to join against the match DataFrame.

        Each item: {result_url, status, market, market_type}
        """
        slips = self.get_slips(profile)
        legs: List[Dict[str, Any]] = []
        for slip in slips:
            for leg in slip.get("legs", []):
                if leg.get("status") in ("Won", "Lost"):
                    legs.append({
                        "result_url":  leg["result_url"],
                        "status":      leg["status"],
                        "market":      leg["market"],
                        "market_type": leg["market_type"],
                    })
        return legs

    # ── Profile helpers ───────────────────────────────────────────────────────

    def get_excluded_urls(self) -> List[str]:
        """URLs that must be excluded from new slip generation."""
        return self._assistant.get_excluded_urls()