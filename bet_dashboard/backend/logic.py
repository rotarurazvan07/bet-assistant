"""
logic.py — Application logic layer for the FastAPI backend.

Wraps the existing dashboard.logic.DashboardLogic without modification.
Adds:
  - Server-lifetime manual excluded URLs (_manual_excluded set)
  - Event broadcasting via WebSocket after every state-changing operation
  - TickerService wiring that broadcasts named events instead of bumping version counters
"""
from __future__ import annotations

import sys
from dataclasses import asdict, fields as dc_fields
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Repo root on sys.path ─────────────────────────────────────────────────────
# main.py is at bet_dashboard/backend/main.py
# Repo root is three levels up: backend/ → bet_dashboard/ → repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bet_framework.core.Slip import BetSlipConfig, CandidateLeg, PROFILES  # noqa: E402
from dashboard.logic import DashboardLogic  # noqa: E402
from dashboard.services import TickerService  # noqa: E402
from scrape_kit import SettingsManager, configure  # noqa: E402

from .ws import ws_manager  # noqa: E402

# ── BetSlipConfig field helpers ───────────────────────────────────────────────

_BETSLIP_FIELDS: set[str] = {f.name for f in dc_fields(BetSlipConfig)}
_RUNTIME_ONLY: set[str] = {"date_from", "date_to", "excluded_urls"}


def _yaml_to_config(data: dict) -> BetSlipConfig:
    """Convert a profile YAML dict to a BetSlipConfig, ignoring runtime-only keys."""
    kwargs = {
        k: v
        for k, v in data.items()
        if k in _BETSLIP_FIELDS and k not in _RUNTIME_ONLY
    }
    return BetSlipConfig(**kwargs)


def _config_to_yaml_dict(
    cfg: BetSlipConfig,
    units: float = 1.0,
    run_daily_count: int = 0,
) -> dict:
    d = asdict(cfg)
    for k in _RUNTIME_ONLY:
        d[k] = None
    d["units"] = units
    d["run_daily_count"] = run_daily_count
    return d


def _ensure_default_profiles(profiles_dir: str, settings: SettingsManager) -> None:
    """Write built-in profiles to disk the first time the app starts."""
    p = Path(profiles_dir)
    if p.is_dir() and any(p.glob("*.yaml")):
        return
    p.mkdir(parents=True, exist_ok=True)
    for name, cfg in PROFILES.items():
        data = _config_to_yaml_dict(cfg, units=1.0, run_daily_count=0)
        settings.write(name, data, subpath="profiles")


# ── AppLogic ──────────────────────────────────────────────────────────────────


class AppLogic:
    """
    Singleton owned by FastAPI's app.state.

    Lifecycle:
        1. Created at startup → starts TickerService daemon threads
        2. Lifespan sets event loop on ws_manager so broadcast_sync works
        3. TickerServices call _do_pull / _do_generate / _do_verify → broadcast events
        4. API routes call delegating methods that broadcast after state changes
    """

    def __init__(
        self,
        matches_db_path: str,
        slips_db_path: str,
        config_path: str,
    ) -> None:
        self._matches_db_path = matches_db_path
        self._config_path = config_path

        configure(config_path)
        self._settings = SettingsManager(config_path)
        _ensure_default_profiles(config_path + "/profiles", self._settings)

        self._logic = DashboardLogic(matches_db_path, slips_db_path)
        self._manual_excluded: set[str] = set()

        svc_cfg = self._settings.get("services") or {}
        self._services: dict[str, TickerService] = {
            "puller": TickerService(
                "puller", self._do_pull,
                hour=int(svc_cfg.get("pull_hour", 6)),
            ),
            "generator": TickerService(
                "generator", self._do_generate,
                hour=int(svc_cfg.get("generate_hour", 8)),
            ),
            "verifier": TickerService(
                "verifier", self._do_verify,
                interval=60,
            ),
        }

        # Apply any saved toggle states
        toggles = svc_cfg.get("toggles", {})
        for name, enabled in toggles.items():
            svc = self._services.get(name)
            if svc and hasattr(svc, "set_enabled"):
                svc.set_enabled(enabled)

    # ── TickerService callbacks ───────────────────────────────────────────────

    def _do_pull(self) -> None:
        try:
            self._logic.pull_matches_db(self._matches_db_path)
            ws_manager.broadcast_sync({
                "event": "matches_updated",
                "timestamp": self._logic.last_pull_timestamp,
            })
        except Exception as exc:
            print(f"[Puller] ERROR: {exc}")

    def _do_generate(self) -> None:
        try:
            profiles_raw = self._settings.get("profiles") or {}
            profiles = {
                name: (_yaml_to_config(cfg), cfg.get("units", 1.0), cfg.get("run_daily_count", 1))
                for name, cfg in profiles_raw.items()
                if cfg.get("run_daily_count")
            }
            if profiles:
                self._logic.generate_slips(profiles)
            ws_manager.broadcast_sync({
                "event": "slips_updated",
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as exc:
            print(f"[Generator] ERROR: {exc}")

    def _do_verify(self) -> None:
        try:
            result = self._logic.validate_slips()
            # Include live data in the broadcast
            live_data = {
                item.match_name: {
                    "score": item.score,
                    "minute": item.minute,
                }
                for item in result.live
            }
            ws_manager.broadcast_sync({
                "event": "slips_updated",
                "timestamp": datetime.now().isoformat(),
                "live_data": live_data,
            })
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
        return list(self._manual_excluded | set(self._logic.get_excluded_urls()))

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def logic(self) -> DashboardLogic:
        return self._logic

    @property
    def services(self) -> dict[str, TickerService]:
        return self._services

    @property
    def settings(self) -> SettingsManager:
        return self._settings

    @property
    def config_path(self) -> str:
        return self._config_path

    # ── Builder ───────────────────────────────────────────────────────────────

    def build_preview(self, cfg: BetSlipConfig) -> list[CandidateLeg]:
        # Only use manual exclusions for preview - pending slip matches should show with warning
        return self._logic.build_slip(cfg, extra_excluded_urls=list(self._manual_excluded))

    # ── Slips (with broadcast) ────────────────────────────────────────────────

    def validate_and_broadcast(self) -> Any:
        result = self._logic.validate_slips()
        ws_manager.broadcast_sync({
            "event": "slips_updated",
            "timestamp": datetime.now().isoformat(),
        })
        return result

    def generate_and_broadcast(self) -> dict:
        profiles_raw = self._settings.get("profiles") or {}
        profiles = {
            name: (_yaml_to_config(cfg), cfg.get("units", 1.0), cfg.get("run_daily_count", 1))
            for name, cfg in profiles_raw.items()
            if cfg.get("run_daily_count")
        }
        result: dict = {}
        if profiles:
            result = self._logic.generate_slips(profiles)
        ws_manager.broadcast_sync({
            "event": "slips_updated",
            "timestamp": datetime.now().isoformat(),
        })
        return result

    def save_slip_and_broadcast(self, profile: str, legs: list, units: float) -> int:
        slip_id = self._logic.save_slip(profile, legs, units)
        ws_manager.broadcast_sync({
            "event": "slips_updated",
            "timestamp": datetime.now().isoformat(),
        })
        return slip_id

    def delete_slip_and_broadcast(self, slip_id: int) -> None:
        self._logic.delete_slip(slip_id)
        ws_manager.broadcast_sync({
            "event": "slips_updated",
            "timestamp": datetime.now().isoformat(),
        })

    def pull_and_broadcast(self) -> str:
        msg = self._logic.pull_matches_db(self._matches_db_path)
        ws_manager.broadcast_sync({
            "event": "matches_updated",
            "timestamp": self._logic.last_pull_timestamp,
        })
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
        ws_manager.broadcast_sync({
            "event": "service_toggled",
            "name": name,
            "enabled": new_state,
            "timestamp": datetime.now().isoformat(),
        })
        return new_state

    def save_service_settings(self, pull_hour: int, generate_hour: int) -> None:
        cfg = self._settings.get("services") or {}
        cfg["pull_hour"] = pull_hour
        cfg["generate_hour"] = generate_hour
        self._settings.write("services", cfg)
        self._services["puller"].update_config(hour=pull_hour, trigger_now=False)
        self._services["generator"].update_config(hour=generate_hour, trigger_now=False)
