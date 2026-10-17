"""Contract test for the e2e seed config layout (two-track binding rule).

The Services scheduler derives its per-profile rows from GET /api/services and
``_get_active_profiles``. Both read ``settings.get("services")`` resolved through
scrape_kit's ``SettingsManager(CONFIG_PATH)``, which exposes each file's TOP-LEVEL
keys as that file's section. A seed that wraps the block in a redundant
``services:`` mapping resolves to ``{"services": {...}}`` instead, so every toggle
and schedule row silently disappears (the PR #104 E2E root cause).
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "bet_dashboard" / "backend"
for _p in (_REPO_ROOT, _BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _seed_config(tmp_path: Path) -> tuple[Path, Path]:
    """Run setup/seed_e2e.py against an isolated config+data dir; return both."""
    cfg = tmp_path / "workspace" / "config"
    data = tmp_path / "workspace" / "data"
    cfg.mkdir(parents=True)
    data.mkdir(parents=True)
    for name in ("scraper_config.yaml", "similarity_config.yaml"):
        src = _REPO_ROOT / "config" / name
        if src.exists():
            (cfg / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    env = {
        "CONFIG_PATH": str(cfg),
        "MATCHES_DB_PATH": str(data / "matches.db"),
        "SLIPS_DB_PATH": str(data / "slips.db"),
        "PYTHONPATH": f"{_REPO_ROOT}:{_BACKEND}",
        "PATH": os.environ.get("PATH", ""),
    }
    proc = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "setup" / "seed_e2e.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, f"seed failed: {proc.stderr[-2000:]}"
    return cfg, data


def test_seeded_services_yaml_is_not_double_nested(tmp_path: Path) -> None:
    """services.yaml must carry the flat block the app itself writes (logic.py)."""
    cfg, _ = _seed_config(tmp_path)
    raw = yaml.safe_load((cfg / "services.yaml").read_text(encoding="utf-8"))
    assert "services" not in raw, "services.yaml wrapped in a 'services:' key - app reads None for every toggle/schedule row"
    assert raw["generate_hour"] == 9
    assert raw["generate_minute"] == 0
    assert raw["toggles"] == {"puller": False, "generator": False, "verifier": False}


def test_seeded_services_resolve_through_settings_manager(tmp_path: Path) -> None:
    """SettingsManager(CONFIG_PATH).get('services') must expose the seeded rows."""
    cfg, _ = _seed_config(tmp_path)
    from scrape_kit import SettingsManager

    settings = SettingsManager(str(cfg))
    svc = settings.get("services") or {}
    assert svc.get("generate_hour") == 9
    sched = svc.get("profiles_schedule") or {}
    assert set(sched) == {"low", "medium", "high_risk"}
    low = sched["low"]
    assert low["enabled"] is True
    assert low["hour"] == 9
    assert low["minute"] == 30
    assert low["units"] == 2.5
    assert low["target_payout"] == 100
    assert sched["medium"]["enabled"] is False


def test_seeded_profiles_and_schedule_agree_with_services_spec(tmp_path: Path) -> None:
    """Rows must key off seeded profiles; e2e-services-scheduler.spec asserts them."""
    cfg, data = _seed_config(tmp_path)
    from scrape_kit import SettingsManager

    settings = SettingsManager(str(cfg))
    profiles = set(settings.get("profiles") or {})
    svc = settings.get("services") or {}
    schedule = set(svc.get("profiles_schedule") or {})
    assert profiles == {"low", "medium", "high_risk"}
    assert schedule <= profiles, "schedule rows without a matching seeded profile never render"

    from core.logic import AppLogic

    from tests.logic_test_helpers import FakeTicker

    FakeTicker.instances.clear()
    with patch("core.logic.TickerService", FakeTicker):
        logic = AppLogic(str(data / "matches.db"), str(data / "slips.db"), str(cfg))
    resolved = logic.settings.get("services") or {}
    assert (resolved.get("profiles_schedule") or {}).get("low", {}).get("units") == 2.5
    active = logic._get_active_profiles(due_only=False)
    assert set(active) >= {"low"}, "enabled seeded row must be active without due filter"
