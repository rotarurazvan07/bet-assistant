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
    order: int | None = None,
    auto_generate: bool | None = None,
    generate_hour: int | None = None,
    generate_minute: int | None = None,
) -> dict:
    """Convert a config object to a plain dict for YAML serialization."""
    d = asdict(cfg)
    # Runtime-only keys (date_from/date_to/excluded_urls) are Build-page
    # filters, never persisted to profile YAML — drop them entirely instead
    # of writing explicit nulls.
    for k in _RUNTIME_ONLY:
        d.pop(k, None)
    d["units"] = units
    d["target_payout"] = target_payout
    # run_daily_count is opt-in like the scheduling keys below: an omitted
    # (None) value keeps whatever is already persisted instead of resetting
    # a legacy auto-generation profile to 0.
    if run_daily_count is not None:
        d["run_daily_count"] = run_daily_count
    # scheduling/ordering keys are opt-in: only persisted when explicitly set
    if order is not None:
        d["order"] = order
    if auto_generate is not None:
        d["auto_generate"] = auto_generate
    if generate_hour is not None:
        d["generate_hour"] = generate_hour
    if generate_minute is not None:
        d["generate_minute"] = generate_minute
    return d


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
