"""AppLogic: unified business logic plus ticker daemons."""

import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pandas as pd

# Import analytics utilities
from core.analytics_utils import (
    _get_status_value,
    calculate_biggest_win_loss,
    calculate_kelly_recommendation,
    calculate_overall_edge,
    calculate_profit_factor,
    calculate_streak_metrics,
    get_rolling_edge_trend,
)
from core.config_helpers import _RUNTIME_ONLY, _yaml_to_config, ensure_default_profiles
from core.ticker_service import TickerService
from core.ws import ws_manager
from scrape_kit import SettingsManager, configure

from bet_framework.BetAssistant import BetAssistant, BetSlipConfig
from bet_framework.core import leagues
from bet_framework.core.Slip import CandidateLeg
from bet_framework.MatchesManager import MatchesManager


class ThreadSafeSettingsManager(SettingsManager):
    """Serialize settings reloads and writes shared by API worker threads."""

    def __init__(self, directory: str) -> None:
        self._access_lock = RLock()
        super().__init__(directory)

    def get(self, *keys: str) -> Any | None:
        with self._access_lock:
            return super().get(*keys)

    def write(self, name: str, data: dict[str, Any], *, subpath: str | Path | None = None) -> None:
        with self._access_lock:
            super().write(name, data, subpath=subpath)

    def delete(self, name: str, *, subpath: str | Path | None = None) -> None:
        with self._access_lock:
            super().delete(name, subpath=subpath)


def _profile_is_active(cfg: dict) -> bool:
    """The gate the generator ticker actually uses — one place, no second opinion.

    A profile is active when ``auto_generate`` is set (the modern flag) OR it
    carries a legacy truthy ``run_daily_count``. An explicit
    ``auto_generate: False`` is authoritative and never overridden by a leftover
    count, which is what "Auto off hides and gates the Daily field, it does not
    rewrite it" means on disk.
    """
    if cfg.get("auto_generate") is False:
        return False
    return bool(cfg.get("auto_generate") or int(cfg.get("run_daily_count") or 0) > 0)


def _order_sort_key(value: Any) -> tuple[int, float]:
    """Sort key for profile ``order`` values that must never raise.

    Hand-edited profile YAML can hold "2" (string) or 2.5 (float) next to an
    int, and a TypeError inside the generator ticker predicate would kill the
    daemon thread (review F4). Numeric values sort first by their number;
    anything unparseable sorts last, alphabetically.
    """
    try:
        return (0, float(value))
    except TypeError, ValueError:
        return (1, 0.0)


def _units_std(settled, n_settled: int, avg_units: float) -> float:
    """Sample standard deviation of stakes (0.0 when fewer than two slips)."""
    if n_settled <= 1:
        return 0.0
    return round((sum((s.units - avg_units) ** 2 for s in settled) / (n_settled - 1)) ** 0.5, 2)


def _daily_pnl_and_sharpe(settled) -> tuple[dict[str, float], float | None]:
    """Aggregate daily P&L and the annualised Sharpe ratio over those days."""
    daily_pnl: dict[str, float] = {}
    for s in settled:
        day = s.date_generated[:10]
        pnl = (s.total_odds - 1) * s.units if _get_status_value(s.slip_status) == "Won" else -s.units
        daily_pnl[day] = daily_pnl.get(day, 0.0) + pnl

    sharpe_ratio: float | None = None
    if len(daily_pnl) >= 3:
        vals = list(daily_pnl.values())
        _m = sum(vals) / len(vals)
        _std = (sum((v - _m) ** 2 for v in vals) / len(vals)) ** 0.5
        sharpe_ratio = round((_m / _std * (252**0.5)) if _std > 0 else 0.0, 2)
    return daily_pnl, sharpe_ratio


def _partition_slips(slips):
    """Split slips into (settled, won, pending) buckets by status."""
    settled = [s for s in slips if _get_status_value(s.slip_status) in ("Won", "Lost")]
    won = [s for s in settled if _get_status_value(s.slip_status) == "Won"]
    pending = [s for s in slips if _get_status_value(s.slip_status) == "Pending"]
    return settled, won, pending


class AppLogic:
    """Unified application logic combining DashboardLogic and service orchestration.

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
        """Load config, open the logic DBs, and wire the WS manager."""
        self._matches_db_path = matches_db_path
        self._slips_db_path = slips_db_path
        self._config_path = config_path

        configure(config_path)
        self._settings = ThreadSafeSettingsManager(config_path)
        ensure_default_profiles(config_path + "/profiles", self._settings)

        # Initialize core assistants
        self._assistant = BetAssistant(slips_db_path)
        self._matches_manager = MatchesManager(matches_db_path)
        self._manual_excluded: set[str] = set()

        # Pre-load match data
        self.refresh_data()

        # ETag tracking for change detection
        self._last_etag: str | None = None
        # Last run tracking for hour-based services
        self._last_generator_run: str | None = None

        # Initialize services
        svc_cfg = self._settings.get("services") or {}
        self._services: dict[str, TickerService] = {
            "puller": TickerService(
                "puller",
                self._do_pull,
                interval=5 * 60,  # Poll every 5 minutes
                predicate=self._check_for_changes,
            ),
            "generator": TickerService(
                "generator",
                self._do_generate,
                interval=60,  # Poll every minute — fire promptly at the window
                predicate=self._is_generator_hour_met,
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

    def _is_generator_hour_met(self) -> bool:
        """Predicate: any active profile's own daily window is due.

        There is no global schedule time anymore: a profile without its own
        generate_hour/generate_minute never fires (per-profile windows only).
        Windows are wall-clock times in the configured ``local_timezone`` —
        the same timezone the Services UI shows Next run in — NOT
        container-local time (UTC in Docker), otherwise the gate skews by
        hours against what the UI displays.
        """
        now = self._local_now()

        # Per-profile windows: fire when one active profile is due.
        profiles_raw = self._settings.get("profiles") or {}
        for name in self._get_active_profiles():
            cfg = profiles_raw.get(name) or {}
            hour, minute = cfg.get("generate_hour"), cfg.get("generate_minute")
            if hour is not None and minute is not None and self._profile_schedule_met(name, cfg, now=now):
                return True

        # No global window: generator fires only on per-profile windows.
        return False

    def _check_for_changes(self) -> bool:
        """HEAD request to check if GitHub release has changed via ETag."""
        repo = os.environ.get("REPO", "rotarurazvan07/bet-assistant")
        url = f"https://github.com/{repo}/releases/download/latest-db/final_matches.db"
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310 - URL is hardcoded HTTPS to GitHub
                etag = resp.headers.get("ETag")
                if etag and etag != self._last_etag:
                    self._last_etag = etag
                    return True
                elif not etag:
                    # No ETag header, always download
                    return True
            return False
        except Exception as exc:
            print(f"[Puller] HEAD request failed: {exc}, will attempt download")
            return True  # On error, try to download anyway

    def _do_pull(self) -> None:
        """Ticker daemon: poll the upstream DB release and hot-swap on change."""
        try:
            print("[Puller] Change detected, downloading...")
            self.pull_matches_db(self._matches_db_path)
            self._broadcast_matches_updated()
        except Exception as exc:
            print(f"[Puller] ERROR: {exc}")

    def get_odds_movement(self, match_id: int) -> dict:
        """Get odds movement direction for a match (from embedded history)."""
        df = self.match_df
        if df.empty or match_id < 0 or match_id >= len(df):
            return {}
        odds_dict = df.iloc[match_id].get("odds")
        if not odds_dict or not isinstance(odds_dict, dict):
            return {}
        return self._matches_manager.calculate_movement_from_odds(odds_dict)

    def get_odds_movement_with_strength(self, match_id: int) -> dict:
        """Get odds movement with strength metrics for a match."""
        df = self.match_df
        if df.empty or match_id < 0 or match_id >= len(df):
            return {}
        odds_dict = df.iloc[match_id].get("odds")
        if not odds_dict or not isinstance(odds_dict, dict):
            return {}
        return self._matches_manager.calculate_movement_with_strength(odds_dict)

    def get_odds_history(self, match_id: int) -> list[dict]:
        """Get all odds snapshots for a match (from embedded history)."""
        df = self.match_df
        if df.empty or match_id < 0 or match_id >= len(df):
            return []
        odds_dict = df.iloc[match_id].get("odds")
        if not odds_dict or not isinstance(odds_dict, dict):
            return []
        history = MatchesManager._extract_history_from_odds(odds_dict)
        return [
            {
                "timestamp": h.get("ts", ""),
                "odds": {k: v for k, v in h.items() if k != "ts"},
            }
            for h in history
        ]

    def _do_generate(self) -> None:
        """Ticker daemon: generate slips for due profiles at their scheduled hour."""
        try:
            profiles = self._get_active_profiles()
            due = {name: tup for name, tup in profiles.items() if self._is_profile_due(name)}
            if due:
                self.generate_slips(due)
                self._claim_profile_runs(due, status="ok")
                self._broadcast_slips_updated()
        except Exception as exc:
            print(f"[Generator] ERROR: {exc}")
            # Mark failing due profiles — status only, no separate stamp map
            due = {name: None for name in (self._get_active_profiles() or {}) if self._is_profile_due(name)}
            if due:
                self._claim_profile_runs(due, status="failed", error=str(exc))

    # ── Per-profile generation schedule (T4) ──────────────────────────────────

    def _profile_cfg(self, name: str) -> dict:
        """Return the stored YAML dict for a profile (empty when missing)."""
        return (self._settings.get("profiles") or {}).get(name) or {}

    def _local_tz(self) -> ZoneInfo:
        """Configured crawler timezone (``scraper_config.local_timezone``)."""
        tz_name = (self._settings.get("scraper_config") or {}).get("local_timezone", "Europe/Bucharest")
        return ZoneInfo(tz_name)

    def _local_now(self) -> datetime:
        """Current wall-clock time in the configured crawler timezone.

        Single source of truth for schedule math: the generator gate, the
        once-per-day guard and the Services UI's Next run all use this
        timezone so they can never disagree with each other. Container-local
        time (UTC in Docker) would skew the gate by hours against the UI.
        """
        return datetime.now(self._local_tz())

    def _profile_schedule_met(self, name: str, cfg: dict | None = None, now: datetime | None = None) -> bool:
        """True when the profile's own daily window has arrived today.

        Per-profile generate_hour/generate_minute only — there is no global
        services window anymore, so a profile without its own window never
        fires. A once-per-day guard blocks re-runs: the date is derived from
        the profile's single ``profile_last_run.at`` entry (stored ISO UTC,
        converted to the local tz — the same clock this gate reads) so the
        guard and the window check can never disagree across midnight.
        ``now`` defaults to the configured crawler timezone (see
        ``_local_now``) so the gate matches the UI's Next run.
        """
        cfg = self._profile_cfg(name) if cfg is None else cfg
        if not _profile_is_active(cfg):
            return False
        now = now or self._local_now()
        today_key = now.strftime("%Y-%m-%d")
        hour, minute = cfg.get("generate_hour"), cfg.get("generate_minute")
        # No global fallback: a profile without its own window never fires.
        if hour is None or minute is None:
            return False
        target = now.replace(
            hour=int(hour),
            minute=int(minute or 0),
            second=0,
            microsecond=0,
        )
        if now < target:
            return False
        return self._last_run_local_date(name) != today_key

    def _last_run_local_date(self, name: str) -> str | None:
        """Local-tz calendar date of the profile's last run, or None.

        Derived from the single ``profile_last_run[name].at`` ISO-UTC entry —
        there is no separate date-only stamp anymore.
        """
        runtime = self._settings.get("runtime_state") or {}
        entry = (runtime.get("profile_last_run") or {}).get(name) or {}
        at = entry.get("at")
        if not at:
            return None
        try:
            return datetime.fromisoformat(str(at)).astimezone(self._local_tz()).strftime("%Y-%m-%d")
        except ValueError:
            return None

    def _is_profile_due(self, name: str, now: datetime | None = None) -> bool:
        """Daemon due-check.

        Legacy profiles (no per-profile hour/minute) are gated by the same
        once-per-day stamp as per-profile ones, so a profile invoked directly
        (manual generation, tests) cannot regenerate twice in one day
        (review F2).
        """
        return self._profile_schedule_met(name, now=now)

    def _claim_profile_runs(self, profiles: dict, *, status: str = "ok", error: str | None = None) -> None:
        """Record one entry per generated profile in ``profile_last_run``.

        Single source of truth for generation state (issue #95 cleanup):
        ``runtime_state.profile_last_run[name] = {"at": <ISO UTC>, "status":
        "ok"|"failed", "error": ...}``. The once-per-day guard derives its
        date from ``at`` (see ``_last_run_local_date``), the Services table
        shows ``at`` as "Last generated" and ``status``/``error`` as the run
        status. Covers both the scheduled ticker and the manual Generate
        button since both call this. Legacy keys (profile_last_generated,
        profile_last_generated_at, profile_run_status, last_time_generated)
        are dropped on write — no read fallback.
        """
        iso_now = datetime.now().astimezone(ZoneInfo("UTC")).isoformat()
        runtime = self._settings.get("runtime_state") or {}
        runs = runtime.get("profile_last_run") or {}
        for name in profiles:
            runs[name] = {"at": iso_now, "status": status, "error": error}
        runtime["profile_last_run"] = runs
        # Drop superseded keys — no legacy fallback.
        for legacy_key in ("profile_last_generated", "profile_last_generated_at", "profile_run_status", "last_time_generated"):
            runtime.pop(legacy_key, None)
        self._settings.write("runtime_state", runtime)

    def delete_profile(self, name: str) -> None:
        """Delete a profile YAML and purge its ``profile_last_run`` entry.

        The stamp must not outlive the profile, or a recreated profile would
        inherit the old once-per-day guard. runtime_state is rewritten only
        when an entry existed, so deleting a never-run profile creates nothing.
        """
        self._settings.delete(name, subpath="profiles")
        runtime = self._settings.get("runtime_state") or {}
        runs = runtime.get("profile_last_run") or {}
        if name in runs:
            runs.pop(name, None)
            runtime["profile_last_run"] = runs
            self._settings.write("runtime_state", runtime)

    def get_profile_schedules(self) -> list[dict]:
        """Profile schedule rows for the Services UI (every saved profile).

        Rows are returned in UI display order and ``order`` reports the
        EFFECTIVE position (0-based index after sorting), not the raw YAML
        value — a new profile with no ``order`` on disk still has a concrete
        position in the table, and the row must reflect that reality. The
        frontend's autosave sends these positional orders back, so the YAML
        materializes them on the next save (issue #95: GET mirrors the UI).

        Other persisted fields report what is on disk so the UI never shows a
        value the system manufactured behind the user's back:

        * ``auto_generate`` reports ``auto_generate`` OR a legacy truthy
          ``run_daily_count`` (the gate the ticker actually uses).
        * ``run_daily_count`` reports the stored number *as stored*, including
          a stored ``0``; a legacy auto-only profile reports ``None``.
        * ``generate_hour``/``generate_minute`` report ``None`` when the
          profile has no window of its own (the UI shows a "--" placeholder;
          no fabricated 08:00).

        Computed scheduler state is reported alongside the persisted values:
        ``last_generated_at``/``last_run_status``/``last_run_error`` come from
        the single ``profile_last_run[name]`` entry (``at``/``status``/
        ``error``), ``next_run_at`` is derived server-side from the window and
        the configured timezone. ``next_run_at`` is ``None`` when auto is off
        or no window is set.
        """
        local_now = self._local_now()
        runtime = self._settings.get("runtime_state") or {}
        last_run_by_profile = runtime.get("profile_last_run") or {}

        rows = []
        for name, cfg in (self._settings.get("profiles") or {}).items():
            active = _profile_is_active(cfg)
            entry = last_run_by_profile.get(name) or {}
            rows.append(
                {
                    "name": name,
                    "auto_generate": active,
                    "generate_hour": cfg.get("generate_hour"),
                    "generate_minute": cfg.get("generate_minute"),
                    "units": cfg.get("units") if cfg.get("units") is not None else 1.0,
                    # Services-tab scope: payout defaults to 1 like units, so the
                    # row (and, after the next save, the YAML) never carries null.
                    "target_payout": cfg.get("target_payout") if cfg.get("target_payout") is not None else 1.0,
                    # Persisted stake_mode wins; fall back to inferring from which
                    # field has a value (legacy profiles have no stake_mode on disk).
                    "stake_mode": cfg.get("stake_mode") or ("payout" if (cfg.get("target_payout") or 0) > 0 else "units"),
                    "run_daily_count": cfg.get("run_daily_count"),
                    "order": cfg.get("order"),
                    "last_generated_at": entry.get("at"),
                    "last_run_status": entry.get("status"),
                    "last_run_error": entry.get("error"),
                    "next_run_at": self._profile_next_run(cfg, active, local_now=local_now),
                }
            )

        # Same comparator as the Services table (Number(order) || 0, then name):
        # unparseable/missing order counts as 0, tie-break alphabetical.
        def _ui_order_key(row: dict) -> tuple:
            try:
                return (float(row["order"]), row["name"])
            except (TypeError, ValueError):
                return (0.0, row["name"])

        rows.sort(key=_ui_order_key)
        for position, row in enumerate(rows):
            row["order"] = position
        return rows

    def _profile_next_run(self, cfg: dict, active: bool, *, local_now: datetime) -> str | None:
        """Next scheduled generation for one profile as a UTC ISO string.

        Server-side truth so the table never shows a time the scheduler would
        not honour. ``None`` when the profile is not active OR has no window of
        its own — a windowless active profile never fires (per-profile windows
        only, no global fallback), so there is no next run and no fabricated
        08:00 default written or displayed.
        """
        if not active:
            return None
        hour, minute = cfg.get("generate_hour"), cfg.get("generate_minute")
        if hour is None or minute is None:
            return None
        first = local_now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        if first <= local_now:
            first += timedelta(days=1)
        return first.astimezone(ZoneInfo("UTC")).isoformat()

    def save_profile_schedules(self, rows: list[dict]) -> None:
        """Merge per-profile schedule rows into each profile's YAML (T4).

        Issue #95 stake semantics: BOTH ``units`` and ``target_payout`` are
        always preserved on disk — ``stake_mode`` ("units"|"payout") only
        selects which one is active at generation time. A null value means
        "not provided" and never clears the persisted value, so switching
        the segmented control can never lose the other field's number.
        """
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            cfg = dict(self._profile_cfg(name))
            if not cfg and name not in (self._settings.get("profiles") or {}):
                continue
            cfg.update(
                {
                    k: row[k]
                    for k in (
                        "auto_generate",
                        "generate_hour",
                        "generate_minute",
                        "run_daily_count",
                        "order",
                    )
                    if k in row
                }
            )
            if row.get("stake_mode") in ("units", "payout"):
                cfg["stake_mode"] = row["stake_mode"]
            # Tri-state: only non-null stake values write through; null = keep.
            if row.get("units") is not None:
                cfg["units"] = row["units"]
            if row.get("target_payout") is not None:
                cfg["target_payout"] = row["target_payout"]
            # Services-tab scope only: both stake fields always land on disk as
            # real numbers (default 1, like units) — a null payout is never
            # persisted through this path. Other write paths (Smart Builder)
            # keep their own tri-state semantics.
            if cfg.get("units") is None:
                cfg["units"] = 1.0
            if cfg.get("target_payout") is None:
                cfg["target_payout"] = 1.0
            if row.get("run_daily_count") is not None:
                cfg["run_daily_count"] = row["run_daily_count"]
            # date_from/date_to/excluded_urls are runtime-only (Build page
            # filters, never persisted) — strip them from the profile file.
            for k in _RUNTIME_ONLY:
                cfg.pop(k, None)
            self._settings.write(name, cfg, subpath="profiles")

    def _do_verify(self) -> None:
        """Ticker daemon: poll live scores and settle active slips."""
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
        """Add a match URL to the manual exclusions table."""
        self._manual_excluded.add(url)

    def remove_excluded(self, url: str) -> None:
        """Remove a match URL from manual exclusions."""
        self._manual_excluded.discard(url)

    def clear_excluded(self) -> None:
        """Clear all manual exclusions."""
        self._manual_excluded.clear()

    def get_manual_excluded(self) -> list[str]:
        """Return manually excluded matches with reasons."""
        return sorted(self._manual_excluded)

    def _combined_excluded(self) -> list[str]:
        """Merge manual exclusions + DB exclusions (pending legs)."""
        return list(self._manual_excluded | set(self.get_excluded_urls()))

    # ── Properties ─────────────────────────────────────────────────────────[...]

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
        """Return service info for puller, generator and verifier."""
        return self._services

    @property
    def settings(self) -> SettingsManager:
        """Return scheduler settings (hour/minute) from config."""
        return self._settings

    @property
    def config_path(self) -> str:
        """Expose the resolved config directory path."""
        return self._config_path

    # ── League helpers ───────────────────────────────────────────────────────··[...]

    def get_leagues(self) -> list[str]:
        # 1. Get leagues from the core framework definitions
        """Return distinct leagues present in the matches DB."""
        framework_leagues = [
            getattr(leagues, name)
            for name in dir(leagues)
            if not name.startswith("__") and isinstance(getattr(leagues, name), str)
        ]

        # 2. Get leagues currently present in the matches database
        df = self._assistant._df
        db_leagues = []
        if df is not None and "league" in df.columns:
            db_leagues = df["league"].dropna().unique().tolist()

        # 3. Merge and sort
        return sorted(set(framework_leagues) | set(db_leagues))

    # ── Match data ─────────────────────────────────────────────────────────[...]

    def refresh_data(self, excluded_sources: list[str] | None = None) -> pd.DataFrame:
        """Reload matches and odds snapshots from the DBs into cache."""
        raw_df = self._matches_manager.fetch_matches()
        self._assistant.load_matches(raw_df, excluded_sources=excluded_sources)
        return self._assistant._df.copy()

    def filter_matches(
        self,
        search_text: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        excluded_sources: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return a filtered view of the loaded match DataFrame.

        If excluded_sources is provided (including empty list), reloads matches with
        consensus recalculated excluding those sources.
        """
        if excluded_sources is not None:
            # Reload matches with excluded sources to recalculate consensus
            # Empty list means include all sources (reload without exclusions)
            self.refresh_data(excluded_sources=excluded_sources)
        return self._assistant.filter_matches(search_text=search_text, date_from=date_from, date_to=date_to)

    def pull_matches_db(self, matches_db_path: str) -> str:
        """Download fresh database and merge with history preservation."""
        import tempfile

        repo = os.environ.get("REPO", "rotarurazvan07/bet-assistant")
        url = f"https://github.com/{repo}/releases/download/latest-db/final_matches.db"

        # Validate URL scheme to prevent file:// or other dangerous schemes (B310)
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            raise ValueError(f"Only HTTPS/HTTP URLs are allowed, got: {parsed.scheme}")

        # Download to temp file first
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            temp_path = tmp.name

        try:
            urllib.request.urlretrieve(url, temp_path)  # nosec B310 - URL is hardcoded HTTPS to GitHub
        except urllib.error.URLError as e:
            os.unlink(temp_path)
            raise RuntimeError(f"Failed to download DB from Release: {e}") from e

        # Get config values for history preservation
        scraper_cfg = self._settings.get("scraper_config") or {}
        max_history = int(scraper_cfg.get("num_days_ahead", 3))
        local_tz = scraper_cfg.get("local_timezone", "Europe/Bucharest")

        # Merge with history preservation
        try:
            self._matches_manager.merge_with_history_preservation(
                fresh_db_path=temp_path,
                max_history=max_history,
                local_tz=local_tz,
            )
        finally:
            # Clean up temp file (best-effort, Windows may still lock it)
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass  # Windows file locking; OS temp cleanup will handle it

        self.refresh_data()
        return "Pull successful"

    # ── Slip building ────────────────────────────────────────────────────────[...]

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
        # Reload matches with config's excluded_sources for complete isolation from other filters
        # Always reload when excluded_sources is explicitly set (including [] for "include all")
        if cfg.excluded_sources is not None:
            self.refresh_data(excluded_sources=cfg.excluded_sources)
        elif hasattr(cfg, "excluded_sources"):  # Field present but None - explicit "no filter"
            # Reload with empty list to ensure all sources are included
            self.refresh_data(excluded_sources=[])
        return self._assistant.build_slip(cfg, extra_excluded_urls=extra_excluded_urls)

    def build_preview(self, cfg: BetSlipConfig) -> list[CandidateLeg]:
        # Only use manual exclusions for preview - pending slip matches should show with warning
        # Reload matches with config's excluded_sources for complete isolation
        """Run the slip builder for a config and return candidate legs."""
        if cfg.excluded_sources is not None:
            self.refresh_data(excluded_sources=cfg.excluded_sources)
        elif hasattr(cfg, "excluded_sources"):
            # Reload with empty list to ensure all sources are included
            self.refresh_data(excluded_sources=[])
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

    # ── Validation ─────────────────────────────────────────────────────────[...]

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

    # ── Slip retrieval ───────────────────────────────────────────────────────··[...]

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
            # Issue #59 spec: pending/live slip legs. A slip whose leg is Live
            # derives slip_status "Live" and must still report its leg URLs.
            if slip.slip_status in ("Pending", "Live"):
                for leg in slip.legs:
                    if leg.status in ("Pending", "Live"):
                        urls.add(leg.result_url)
        return urls

    def delete_slip(self, slip_id: int) -> None:
        """Delete a slip by id from the slips DB."""
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
        """Return aggregate slip statistics for the current filters."""
        slips = self.get_slips(profile, date_from, date_to)
        settled, won, pending = _partition_slips(slips)

        n_settled = len(settled)
        n_won = len(won)
        stakes = sum(s.units for s in settled)
        gross_return = sum(s.total_odds * s.units for s in won)
        net_profit = gross_return - stakes
        actual_win_rate = round((n_won / n_settled * 100) if n_settled else 0.0, 2)

        # ── New value metrics ────────────────────────────────────────────────
        avg_odds = round(sum(s.total_odds for s in settled) / n_settled, 3) if n_settled else 0.0
        implied_win_rate = round(
            (sum(1.0 / s.total_odds for s in settled if s.total_odds > 0) / n_settled * 100) if n_settled else 0.0,
            2,
        )

        # Calculate overall edge using the new unified function
        edge = calculate_overall_edge(settled)

        # ── Staking consistency ──────────────────────────────────────────────
        avg_units = round(sum(s.units for s in settled) / n_settled, 2) if n_settled else 0.0
        units_std = _units_std(settled, n_settled, avg_units)

        # ── Sharpe ratio (daily P&L) ─────────────────────────────────────────
        daily_pnl, sharpe_ratio = _daily_pnl_and_sharpe(settled)

        # Best and worst day P&L
        best_day_pnl = max(daily_pnl.values()) if daily_pnl else None
        worst_day_pnl = min(daily_pnl.values()) if daily_pnl else None

        kelly_rec = calculate_kelly_recommendation(n_won, n_settled, avg_odds, gross_return)
        edge_analysis = get_rolling_edge_trend(settled)

        # ── New advanced metrics ───────────────────────────────────────────────
        biggest_win_loss = calculate_biggest_win_loss(settled)
        biggest_win_units = biggest_win_loss["biggest_win_units"]
        biggest_loss_units = biggest_win_loss["biggest_loss_units"]

        # Calculate streak metrics + profit factor
        streak_metrics = calculate_streak_metrics(slips)  # Pass all slips, not just settled ones
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
            "current_streak": streak_metrics["current_streak"],
            "longest_win_streak": streak_metrics["longest_win_streak"],
            "longest_loss_streak": streak_metrics["longest_loss_streak"],
            "profit_factor": profit_factor,
        }

    # ── Analytics ─────────────────────────────────────────────────────────·[...]

    def daily_summary(
        self,
        profile: str | list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return daily P&L summary rows for analytics."""
        from core.analytics_utils import calculate_daily_summary

        slips = self.get_slips(profile or "all", date_from, date_to)
        return calculate_daily_summary(slips, profile, date_from, date_to)

    def market_accuracy(
        self,
        profile: str | list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return per-market accuracy breakdown for analytics."""
        from core.analytics_utils import calculate_market_accuracy

        slips = self.get_slips(profile or "all", date_from, date_to)
        return calculate_market_accuracy(slips)

    def correlation_data(
        self,
        profile: str | list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return source/market correlation data for analytics."""
        from core.analytics_utils import calculate_correlation_data

        slips = self.get_slips(profile or "all", date_from, date_to)
        settled = [s for s in slips if self._get_status_value(s.slip_status) in ("Won", "Lost")]
        return calculate_correlation_data(settled)

    # ── Builder ──────────────────────────────────────────────────────────[...]

    # build_preview is already defined above

    # ── Slips (with broadcast) ────────────────────────────────────────────────

    def validate_and_broadcast(self) -> Any:
        """Validate pending slips and broadcast live updates over WS."""
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
        """Generate slips for active profiles and broadcast over WS.

        This is the manual Generate button (POST /api/slips/generate) — it IS
        a generation, so it claims the once-per-day guard like the ticker.
        Distinct from building a slip manually on the Build page
        (POST /api/slips -> save_slip_and_broadcast), which never touches
        generation state.
        """
        profiles = self._get_active_profiles()
        result: dict = {}
        try:
            if profiles:
                result = self.generate_slips(profiles)
                self._claim_profile_runs(profiles, status="ok")
            self._broadcast_slips_updated()
            return result
        except Exception as exc:
            print(f"[Generator] manual ERROR: {exc}")
            self._claim_profile_runs(profiles, status="failed", error=str(exc))
            self._broadcast_slips_updated()
            raise

    def save_slip_and_broadcast(self, profile: str, legs: list, units: float) -> int:
        """Persist a manual slip and broadcast the update over WS."""
        slip_id = self.save_slip(profile, legs, units)
        self._broadcast_slips_updated()
        return slip_id

    def delete_slip_and_broadcast(self, slip_id: int) -> None:
        """Delete a slip and broadcast the update over WS."""
        self.delete_slip(slip_id)
        self._broadcast_slips_updated()

    def pull_and_broadcast(self) -> str:
        """Pull the upstream DB and broadcast refreshed matches over WS."""
        msg = self.pull_matches_db(self._matches_db_path)
        self._broadcast_matches_updated()
        return msg

    # ── Services ─────────────────────────────────────────────────────────··[...]

    def toggle_service(self, name: str) -> bool:
        """Enable or disable a named service and persist the setting."""
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

    # ── Helpers ──────────────────────────────────────────────────────────[...]

    def _get_active_profiles(self) -> dict[str, tuple]:
        """Active profiles as {name: (BetSlipConfig, units, count, target_payout)}.

        Ordering: explicit ``order`` ascending first, unordered profiles keep their
        settings-dict (insertion) order after them. A profile is active when
        ``auto_generate`` is set or it has a legacy truthy ``run_daily_count``;
        auto_generate-only profiles run once per day (count 1).
        """
        profiles_raw = self._settings.get("profiles") or {}
        active = {name: cfg for name, cfg in profiles_raw.items() if _profile_is_active(cfg)}
        ordered = sorted(
            (n for n, c in active.items() if c.get("order") is not None),
            key=lambda n: _order_sort_key(active[n]["order"]),
        )
        unordered = [n for n, c in active.items() if c.get("order") is None]

        def _active_stake(cfg: dict) -> tuple:
            """(units, target_payout) honouring persisted stake_mode (issue #95).

            stake_mode="payout" → payout is the active stake (units still
            passed through, generate_slips prefers payout when > 0).
            "units" (or legacy absent) → payout reported as None so the
            generator uses fixed units. Both values stay on disk; only the
            selection changes.
            """
            units = cfg.get("units", 1.0)
            payout = cfg.get("target_payout")
            if cfg.get("stake_mode") == "payout":
                return (units, payout)
            return (units, None)

        result = {}
        for name in ordered + unordered:
            cfg = active[name]
            units, payout = _active_stake(cfg)
            result[name] = (
                _yaml_to_config(cfg),
                units,
                cfg.get("run_daily_count") or (1 if cfg.get("auto_generate") else 0),
                payout,
            )
        return result
