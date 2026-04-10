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
    run_daily_count: int = 0,
) -> dict:
    d = asdict(cfg)
    for k in _RUNTIME_ONLY:
        d[k] = None
    d["units"] = units
    d["run_daily_count"] = run_daily_count
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
