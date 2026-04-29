from __future__ import annotations

import math
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from datetime import datetime, timedelta

import pandas as pd
from core.config_helpers import _yaml_to_config, ensure_default_profiles
from core.ticker_service import TickerService
from core.ws import ws_manager
from scrape_kit import SettingsManager, configure
from bet_framework.BetAssistant import BetAssistant, BetSlipConfig
from bet_framework.core.types import Outcome
from bet_framework.MatchesManager import MatchesManager

# Import analytics utilities
from core.analytics_utils import calculate_overall_edge, calculate_rolling_edge, calculate_kelly_recommendation, get_rolling_edge_trend, _get_status_value, calculate_streak_metrics, calculate_profit_factor, calculate_biggest_win_loss


class AppLogic:
    """
    Unified application logic combining DashboardLogic and service orchestration.

    Lifecycle:
        1. Created at startup → starts TickerService daemon threads
        2. Lifespan sets event loop on ws_manager so broadcast_sync works
        3. TickerServices call _do_pull / _do_generate / _do_verify → broadcast events
        4. API routes call delegating methods that broadcast after state changes
    """

    def _get_status_value(self, status) -> str:
        """Extract value from enum or return string representation."""
        if hasattr(status, "value"):
            return status.value
        return str(status)

    def __init__(
        self,
        matches_db_path: str,
        slips_db_path: str,
        config_path: str,
    ) -> None:
        self._matches_db_path = matches_db_path
        self._slips_db_path = slips_db_path
        self._config_path = config_path

        configure(config_path)
        self._settings = SettingsManager(config_path)
        ensure_default_profiles(config_path + "/profiles", self._settings)

        # Initialize core assistants
        self._assistant = BetAssistant(slips_db_path)
        self._matches_manager = MatchesManager(matches_db_path)
        self._manual_excluded: set[str] = set()

        # Pre-load match data
        self.refresh_data()

        # Initialize services
        svc_cfg = self._settings.get("services") or {}
        self._services: dict[str, TickerService] = {
            "puller": TickerService(
                "puller",
                self._do_pull,
                hour=int(svc_cfg.get("pull_hour", 6)),
            ),
            "generator": TickerService(
                "generator",
                self._do_generate,
                hour=int(svc_cfg.get("generate_hour", 8)),
            ),
            "verifier": TickerService(
                "verifier",
                self._do_verify,
                interval=60,
            ),
        }

        # Apply any saved toggle states
        toggles = svc_cfg.get("toggles", {})
        for name, enabled in toggles.items():
            svc = self._services.get(name)
            if svc and hasattr(svc, "set_enabled"):
                svc.set_enabled(enabled)

    # ── Broadcast helper ───────────────────────────────────────────────────────

    def _broadcast_slips_updated(self, live_data: dict | None = None) -> None:
        """Broadcast slips updated event."""
        payload = {
            "event": "slips_updated",
            "timestamp": datetime.now().isoformat(),
        }
        if live_data:
            payload["live_data"] = live_data
        ws_manager.broadcast_sync(payload)

    def _broadcast_matches_updated(self) -> None:
        """Broadcast matches updated event."""
        ws_manager.broadcast_sync(
            {
                "event": "matches_updated",
                "timestamp": self.last_pull_timestamp,
            }
        )

    # ── TickerService callbacks ───────────────────────────────────────────────

    def _do_pull(self) -> None:
        try:
            self.pull_matches_db(self._matches_db_path)
            self._broadcast_matches_updated()
        except Exception as exc:
            print(f"[Puller] ERROR: {exc}")

    def _do_generate(self) -> None:
        try:
            profiles = self._get_active_profiles()
            if profiles:
                self.generate_slips(profiles)
            self._broadcast_slips_updated()
        except Exception as exc:
            print(f"[Generator] ERROR: {exc}")

    def _do_verify(self) -> None:
        try:
            result = self.validate_slips()
            live_data = {
                item.match_name: {
                    "score": item.score,
                    "minute": item.minute,
                }
                for item in result.live
            }
            self._broadcast_slips_updated(live_data)
        except Exception as exc:
            print(f"[Verifier] ERROR: {exc}")

    # ── Manual excluded URLs (server-lifetime) ────────────────────────────────

    def add_excluded(self, url: str) -> None:
        self._manual_excluded.add(url)

    def remove_excluded(self, url: str) -> None:
        self._manual_excluded.discard(url)

    def clear_excluded(self) -> None:
        self._manual_excluded.clear()

    def get_manual_excluded(self) -> list[str]:
        return sorted(self._manual_excluded)

    def _combined_excluded(self) -> list[str]:
        """Merge manual exclusions + DB exclusions (pending legs)."""
        return list(self._manual_excluded | set(self.get_excluded_urls()))

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def match_df(self) -> pd.DataFrame:
        """Current match DataFrame (read-only reference)."""
        return self._assistant._df

    @property
    def last_pull_timestamp(self) -> str:
        """Returns the last modification time of the matches database."""
        try:
            mtime = os.path.getmtime(self._matches_db_path)
            return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Unknown"

    @property
    def logic(self) -> AppLogic:
        """Return self for backward compatibility with routers."""
        return self

    @property
    def services(self) -> dict[str, TickerService]:
        return self._services

    @property
    def settings(self) -> SettingsManager:
        return self._settings

    @property
    def config_path(self) -> str:
        return self._config_path

    # ── Match data ────────────────────────────────────────────────────────────

    def refresh_data(self) -> pd.DataFrame:
        raw_df = self._matches_manager.fetch_matches()
        self._assistant.load_matches(raw_df)
        return self._assistant._df.copy()

    def filter_matches(
        self,
        search_text: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> pd.DataFrame:
        """Return a filtered view of the loaded match DataFrame."""
        return self._assistant.filter_matches(search_text=search_text, date_from=date_from, date_to=date_to)

    def pull_matches_db(self, matches_db_path: str) -> str:
        repo = os.environ.get("REPO", "rotarurazvan07/bet-assistant")
        url = f"https://github.com/{repo}/releases/download/latest-db/final_matches.db"

        # Validate URL scheme to prevent file:// or other dangerous schemes (B310)
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            raise ValueError(f"Only HTTPS/HTTP URLs are allowed, got: {parsed.scheme}")

        try:
            urllib.request.urlretrieve(url, matches_db_path)
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to download DB from Release: {e}")

        self.refresh_data()
        return "Pull successful"

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
        return self._assistant.build_slip(cfg, extra_excluded_urls=extra_excluded_urls)

    def build_preview(self, cfg: BetSlipConfig) -> list[CandidateLeg]:
        # Only use manual exclusions for preview - pending slip matches should show with warning
        return self.build_slip(cfg, extra_excluded_urls=list(self._manual_excluded))

    def generate_slips(self, profiles: dict[str, tuple]) -> dict[str, Any]:
        """
        Build and save slips for the given profiles.

        Parameters
        ----------
        profiles : {profile_name: (BetSlipConfig, units, count, target_payout)}
        """
        results = {}
        for name, (cfg, units, count, target_payout) in profiles.items():
            for _ in range(count):
                legs = self._assistant.build_slip_auto_exclude(cfg)
                if not legs:
                    break

                # Dynamic units calculation if target_payout is set
                final_units = units
                if target_payout and target_payout > 0:
                    total_odds = math.prod(leg.odds for leg in legs)
                    if total_odds > 0:
                        # Round to 1 decimal place to match dashboard convention
                        final_units = round(target_payout / total_odds, 1) or 0.1

                slip_id = self._assistant.save_slip(name, legs, final_units)
                results[name] = results.get(name, [])
                results[name].append(slip_id)
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
        return result

    # ── Slip retrieval ────────────────────────────────────────────────────────

    def get_slips(
        self,
        profile: str | list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Any]:
        """
        Return all slips with their legs, optionally filtered by profile and date horizon.
        """
        # Normalize "all" to None for backend
        if profile == "all":
            profile = None

        # Delegate to BetAssistant which now handles list of profiles efficiently
        slips = self._assistant.get_slips(profile)

        if date_from:
            slips = [s for s in slips if s.date_generated.split("T")[0] >= date_from]
        if date_to:
            slips = [s for s in slips if s.date_generated.split("T")[0] <= date_to]
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

    def get_excluded_urls(self) -> list[str]:
        """URLs that must be excluded from new slip generation."""
        return self._assistant.get_excluded_urls()

    def stats(
        self,
        profile: str | list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        slips = self.get_slips(profile, date_from, date_to)
        settled = [s for s in slips if _get_status_value(s.slip_status) in ("Won", "Lost")]
        won = [s for s in settled if _get_status_value(s.slip_status) == "Won"]
        pending = [s for s in slips if _get_status_value(s.slip_status) == "Pending"]

        n_settled = len(settled)
        n_won = len(won)
        stakes = sum(s.units for s in settled)
        gross_return = sum(s.total_odds * s.units for s in won)
        net_profit = gross_return - stakes
        actual_win_rate = round((n_won / n_settled * 100) if n_settled else 0.0, 2)

        # ── New value metrics ────────────────────────────────────────────────
        avg_odds = round(sum(s.total_odds for s in settled) / n_settled, 3) if n_settled else 0.0
        implied_win_rate = round(
            (sum(1.0 / s.total_odds for s in settled if s.total_odds > 0) / n_settled * 100)
            if n_settled else 0.0, 2
        )

        # Calculate overall edge using the new unified function
        edge = calculate_overall_edge(settled)

        # ── Staking consistency ──────────────────────────────────────────────
        avg_units = round(sum(s.units for s in settled) / n_settled, 2) if n_settled else 0.0
        units_std = 0.0
        if n_settled > 1:
            _mean = avg_units
            units_std = round(
                (sum((s.units - _mean) ** 2 for s in settled) / (n_settled - 1)) ** 0.5, 2
            )

        # ── Sharpe ratio (daily P&L) ─────────────────────────────────────────
        daily_pnl: dict[str, float] = {}
        for s in settled:
            day = s.date_generated[:10]
            pnl = (s.total_odds - 1) * s.units if _get_status_value(s.slip_status) == "Won" else -s.units
            daily_pnl[day] = daily_pnl.get(day, 0.0) + pnl

        sharpe_ratio: float | None = None
        if len(daily_pnl) >= 7:
            vals = list(daily_pnl.values())
            _m = sum(vals) / len(vals)
            _std = (sum((v - _m) ** 2 for v in vals) / len(vals)) ** 0.5
            sharpe_ratio = round((_m / _std * (252 ** 0.5)) if _std > 0 else 0.0, 2)

        # Best and worst day P&L
        best_day_pnl = max(daily_pnl.values()) if daily_pnl else None
        worst_day_pnl = min(daily_pnl.values()) if daily_pnl else None

        kelly_rec = calculate_kelly_recommendation(n_won, n_settled, avg_odds, gross_return)
        edge_analysis = get_rolling_edge_trend(settled)
        
        # ── New advanced metrics ───────────────────────────────────────────────
        # Calculate biggest win/loss
        biggest_win_loss = calculate_biggest_win_loss(settled)
        biggest_win_units = biggest_win_loss["biggest_win_units"]
        biggest_loss_units = biggest_win_loss["biggest_loss_units"]
        
        # Calculate streak metrics
        streak_metrics = calculate_streak_metrics(slips)  # Pass all slips, not just settled ones
        current_streak = streak_metrics["current_streak"]
        longest_win_streak = streak_metrics["longest_win_streak"]
        longest_loss_streak = streak_metrics["longest_loss_streak"]
        
        # Calculate profit factor
        profit_factor = calculate_profit_factor(settled)

        return {
            "total_settled": n_settled,
            "total_won_count": n_won,
            "win_rate": actual_win_rate,
            "implied_win_rate": implied_win_rate,
            "edge": edge,
            "total_units_bet": round(stakes, 2),
            "gross_return": round(gross_return, 2),
            "net_profit": round(net_profit, 2),
            "roi_percentage": round((net_profit / stakes * 100) if stakes else 0.0, 2),
            "avg_odds": avg_odds,
            "avg_units": avg_units,
            "units_std": units_std,
            "pending_count": len(pending),
            "sharpe_ratio": sharpe_ratio,
            "kelly_suggested_units": kelly_rec,
            "edge_trend": edge_analysis["trend"],
            "recent_edge_value": edge_analysis["value"],
            # New advanced metrics
            "biggest_win_units": biggest_win_units,
            "biggest_loss_units": biggest_loss_units,
            "best_day_pnl": round(best_day_pnl, 2) if best_day_pnl is not None else None,
            "worst_day_pnl": round(worst_day_pnl, 2) if worst_day_pnl is not None else None,
            "current_streak": current_streak,
            "longest_win_streak": longest_win_streak,
            "longest_loss_streak": longest_loss_streak,
            "profit_factor": profit_factor,
        }

    # ── Analytics ─────────────────────────────────────────────────────────────

    def daily_summary(
        self,
        profile: str | list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        from core.analytics_utils import calculate_daily_summary
        slips = self.get_slips(profile or "all", date_from, date_to)
        return calculate_daily_summary(slips, profile, date_from, date_to)

    def market_accuracy(
        self,
        profile: str | list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        from core.analytics_utils import calculate_market_accuracy
        slips = self.get_slips(profile or "all", date_from, date_to)
        return calculate_market_accuracy(slips)

    def correlation_data(
        self,
        profile: str | list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        from core.analytics_utils import calculate_correlation_data
        slips = self.get_slips(profile or "all", date_from, date_to)
        settled = [s for s in slips if self._get_status_value(s.slip_status) in ("Won", "Lost")]
        return calculate_correlation_data(settled)

    # ── Builder ───────────────────────────────────────────────────────────────

    # build_preview is already defined above

    # ── Slips (with broadcast) ────────────────────────────────────────────────

    def validate_and_broadcast(self) -> Any:
        result = self.validate_slips()
        live_data = {
            item.match_name: {
                "score": item.score,
                "minute": item.minute,
            }
            for item in result.live
        }
        self._broadcast_slips_updated(live_data)
        return result

    def generate_and_broadcast(self) -> dict:
        profiles = self._get_active_profiles()
        result: dict = {}
        if profiles:
            result = self.generate_slips(profiles)
        self._broadcast_slips_updated()
        return result

    def save_slip_and_broadcast(self, profile: str, legs: list, units: float) -> int:
        slip_id = self.save_slip(profile, legs, units)
        self._broadcast_slips_updated()
        return slip_id

    def delete_slip_and_broadcast(self, slip_id: int) -> None:
        self.delete_slip(slip_id)
        self._broadcast_slips_updated()

    def pull_and_broadcast(self) -> str:
        msg = self.pull_matches_db(self._matches_db_path)
        self._broadcast_matches_updated()
        return msg

    # ── Services ──────────────────────────────────────────────────────────────

    def toggle_service(self, name: str) -> bool:
        svc = self._services.get(name)
        if not svc:
            return False
        new_state = not getattr(svc, "enabled", True)
        if hasattr(svc, "set_enabled"):
            svc.set_enabled(new_state)
        # Persist toggle state
        cfg = self._settings.get("services") or {}
        toggles = cfg.get("toggles", {})
        toggles[name] = new_state
        cfg["toggles"] = toggles
        self._settings.write("services", cfg)
        ws_manager.broadcast_sync(
            {
                "event": "service_toggled",
                "name": name,
                "enabled": new_state,
                "timestamp": datetime.now().isoformat(),
            }
        )
        return new_state

    def save_service_settings(self, pull_hour: int, generate_hour: int) -> None:
        cfg = self._settings.get("services") or {}
        cfg["pull_hour"] = pull_hour
        cfg["generate_hour"] = generate_hour
        self._settings.write("services", cfg)
        self._services["puller"].update_config(hour=pull_hour, trigger_now=False)
        self._services["generator"].update_config(hour=generate_hour, trigger_now=False)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_active_profiles(self) -> dict[str, tuple]:
        """Convert stored profiles to dict of {name: (BetSlipConfig, units, count, target_payout)}."""
        profiles_raw = self._settings.get("profiles") or {}
        return {
            name: (_yaml_to_config(cfg), cfg.get("units", 1.0), cfg.get("run_daily_count", 0), cfg.get("target_payout"))
            for name, cfg in profiles_raw.items()
            if cfg.get("run_daily_count")
        }
