"""Helpers for reading and converting scraper/profile config files."""

from dataclasses import asdict
from dataclasses import fields as dc_fields

from scrape_kit import SettingsManager

from bet_framework.core.Slip import PROFILES, BetSlipConfig

_BETSLIP_FIELDS: set[str] = {f.name for f in dc_fields(BetSlipConfig)}
_RUNTIME_ONLY: set[str] = {"date_from", "date_to", "excluded_urls"}


def _yaml_to_config(data: dict) -> BetSlipConfig:
    """Convert a profile YAML dict to a BetSlipConfig, ignoring runtime-only keys."""
    kwargs = {k: v for k, v in data.items() if k in _BETSLIP_FIELDS and k not in _RUNTIME_ONLY}
    return BetSlipConfig(**kwargs)


def _config_to_yaml_dict(
    cfg: BetSlipConfig,
    units: float = 1.0,
    target_payout: float | None = None,
    run_daily_count: int = 0,
    schedule: dict | None = None,
) -> dict:
    """Convert a config object to a plain dict for YAML serialization.

    An optional ``schedule`` block is round-tripped verbatim; when it is absent
    (``None``) no ``schedule`` key is fabricated.
    """
    d = asdict(cfg)
    for k in _RUNTIME_ONLY:
        d[k] = None
    d["units"] = units
    d["target_payout"] = target_payout
    d["run_daily_count"] = run_daily_count
    if schedule is not None:
        d["schedule"] = dict(schedule)
    return d


def parse_schedule_block(raw: object) -> dict | None:
    """Normalize an optional profile ``schedule`` block; ``None`` when absent or invalid.

    Expected keys: ``enabled``, ``hour``, ``minute``, ``units``, ``target_payout``.
    Absent ``units``/``target_payout`` stay ``None`` so the profile's own values
    apply; out-of-range times or non-numeric values invalidate the block.
    """
    if not isinstance(raw, dict):
        return None
    try:
        # Same documented 08:00 default as the legacy global mode
        # (routers/services.py) so both modes never disagree on "unset".
        hour = int(raw.get("hour", 8))
        minute = int(raw.get("minute", 0))
        units = float(raw["units"]) if raw.get("units") is not None else None
        payout = float(raw["target_payout"]) if raw.get("target_payout") is not None else None
    except (TypeError, ValueError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    if units is not None and units <= 0:
        units = None
    return {
        "enabled": bool(raw.get("enabled", False)),
        "hour": hour,
        "minute": minute,
        "units": units,
        "target_payout": payout,
    }


def ensure_default_profiles(profiles_dir: str, settings: SettingsManager) -> None:
    """Write built-in profiles to disk the first time the app starts."""
    from pathlib import Path

    p = Path(profiles_dir)
    if p.is_dir() and any(p.glob("*.yaml")):
        return
    p.mkdir(parents=True, exist_ok=True)
    for name, cfg in PROFILES.items():
        data = _config_to_yaml_dict(cfg, units=1.0, run_daily_count=0)
        settings.write(name, data, subpath="profiles")
