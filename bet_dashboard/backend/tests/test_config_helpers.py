"""Configuration / Profile tests for core.config_helpers (issue #62, cycle 6).

Scope (per issue #62 spec, testing-subissues-58-71.md):
- _yaml_to_config() parses ALL BetSlipConfig fields
- ensure_default_profiles() seeds built-in profiles into a fresh config dir
- Clamping boundaries for every clamped field (target_odds [1.10, 1000],
  target_legs [1, 100], consensus_floor, min_odds, tolerances, advanced ...)
- excluded_sources list preserved through the YAML -> config path
- Advanced fields parsed and preserved
- Profile YAML round-trip (save -> load -> verify) via SettingsManager

Spec/implementation divergence (documented, cycle-3 finding): the issue text
says ensure_default_profiles creates low/medium/high_risk, but PROFILES also
ships value_hunter, so every fresh config dir receives FOUR built-in profiles
(all with run_daily_count=0, i.e. inactive by default). Tests pin actual
behaviour.

Isolation: every test uses tmp_path config dirs; the repo-level config/ tree
is never touched (SettingsManager instances only ever see throwaway dirs).
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parents[1]
for _p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scrape_kit import SettingsManager  # noqa: E402

from bet_framework.core.Slip import PROFILES, BetSlipConfig  # noqa: E402

from core.config_helpers import (  # noqa: E402
    _config_to_yaml_dict,
    _yaml_to_config,
    ensure_default_profiles,
)


BUILTIN_PROFILE_NAMES = {"low_risk", "medium_risk", "high_risk", "value_hunter"}

# (field, lower bound, upper bound) for every clamped BetSlipConfig field.
CLAMP_BOUNDS = [
    ("target_odds", 1.10, 1000.0),
    ("target_legs", 1, 100),
    ("consensus_floor", 0.0, 100.0),
    ("min_odds", 1.01, 10.0),
    ("min_legs_fill_ratio", 0.50, 1.00),
    ("quality_vs_balance", 0.0, 1.0),
    ("consensus_vs_sources", 0.0, 1.0),
    ("tolerance_factor", 0.05, 0.80),
    ("stop_threshold", 0.50, 1.00),
    ("max_legs_overflow", 0, 5),
    ("consensus_shrinkage_k", 1.0, 10.0),
    ("min_source_edge", 0.0, 0.50),
    ("max_single_leg_odds", 1.0, 10.0),
    ("tol_lower", 0.01, 1.00),
    ("tol_upper", 0.01, 1.00),
    ("min_pick_quality", 0.0, 1.00),
    ("odds_movement_weight", 0.0, 0.30),
    ("odds_movement_strength_min", 0.05, 0.20),
]

# Deterministic case matrix: below-lo, lo, hi, above-hi for each field.
CLAMP_CASES: list[tuple[str, float | int, float | int]] = []
for _field, _lo, _hi in CLAMP_BOUNDS:
    CLAMP_CASES += [
        (_field, _lo - 1, _lo),
        (_field, _lo, _lo),
        (_field, _hi, _hi),
        (_field, _hi + 1, _hi),
    ]

# Clamped fields whose None default must survive construction untouched.
OPTIONAL_CLAMP_FIELDS = [
    "tolerance_factor",
    "stop_threshold",
    "max_legs_overflow",
    "consensus_shrinkage_k",
    "min_source_edge",
    "max_single_leg_odds",
    "tol_lower",
    "tol_upper",
    "min_pick_quality",
    "odds_movement_weight",
    "odds_movement_strength_min",
]


def make_full_profile_dict(**overrides) -> dict:
    """Every BetSlipConfig field with in-range values, plus noise keys.

    Includes runtime-only keys (date_from/date_to/excluded_urls), metadata
    keys (units/target_payout/run_daily_count) and one unknown key -- all of
    which _yaml_to_config must drop.
    """
    data = {
        "date_from": "2030-01-01",
        "date_to": "2030-01-02",
        "excluded_urls": ["https://example.com/x"],
        "excluded_sources": ["forebet", "windrawwin"],
        "included_markets": ["1", "X"],
        "included_leagues": ["La Liga"],
        "target_odds": 6.0,
        "target_legs": 4,
        "max_legs_overflow": 2,
        "consensus_floor": 60.0,
        "min_odds": 1.20,
        "tolerance_factor": 0.30,
        "stop_threshold": 0.85,
        "min_legs_fill_ratio": 0.75,
        "quality_vs_balance": 0.65,
        "consensus_vs_sources": 0.55,
        "consensus_shrinkage_k": 4.0,
        "min_source_edge": 0.06,
        "max_single_leg_odds": 3.50,
        "tol_lower": 0.35,
        "tol_upper": 0.20,
        "balance_decay": "linear",
        "min_pick_quality": 0.30,
        "odds_movement_weight": 0.15,
        "odds_movement_strength_min": 0.10,
        "units": 2.5,
        "target_payout": 25.0,
        "run_daily_count": 3,
        "totally_unknown_key": "ignored",
    }
    data.update(overrides)
    return data


class TestYamlToConfig:
    """[P1] _yaml_to_config: full-field YAML dict -> BetSlipConfig."""

    def test_parses_every_betslipconfig_field(self):
        """[P1] All 21 persisted BetSlipConfig fields survive the YAML ->
        config path. date_from/date_to/excluded_urls are fed in by the factory
        but are runtime-only and dropped (verified separately below)."""
        data = make_full_profile_dict()
        cfg = _yaml_to_config(data)
        assert isinstance(cfg, BetSlipConfig)
        assert cfg.excluded_sources == ["forebet", "windrawwin"]
        assert cfg.included_markets == ["1", "X"]
        assert cfg.included_leagues == ["La Liga"]
        assert cfg.target_odds == 6.0
        assert cfg.target_legs == 4
        assert cfg.max_legs_overflow == 2
        assert cfg.consensus_floor == 60.0
        assert cfg.min_odds == 1.20
        assert cfg.tolerance_factor == 0.30
        assert cfg.stop_threshold == 0.85
        assert cfg.min_legs_fill_ratio == 0.75
        assert cfg.quality_vs_balance == 0.65
        assert cfg.consensus_vs_sources == 0.55
        assert cfg.consensus_shrinkage_k == 4.0
        assert cfg.min_source_edge == 0.06
        assert cfg.max_single_leg_odds == 3.50
        assert cfg.tol_lower == 0.35
        assert cfg.tol_upper == 0.20
        assert cfg.balance_decay == "linear"
        assert cfg.min_pick_quality == 0.30
        assert cfg.odds_movement_weight == 0.15
        assert cfg.odds_movement_strength_min == 0.10

    def test_ignores_runtime_only_keys(self):
        """[P1] date_from/date_to/excluded_urls are dropped even though they
        are real BetSlipConfig fields -- _RUNTIME_ONLY explicitly excludes them."""
        cfg = _yaml_to_config(make_full_profile_dict())
        assert cfg.date_from is None
        assert cfg.date_to is None
        assert cfg.excluded_urls is None

    def test_ignores_metadata_and_unknown_keys(self):
        """[P2] units/target_payout/run_daily_count are profile-file metadata,
        not BetSlipConfig fields; unknown keys are silently dropped (pydantic-
        style extra=ignore semantics keep hand-edited YAML files loadable)."""
        data = make_full_profile_dict()
        cfg = _yaml_to_config(data)
        assert not hasattr(cfg, "units")
        assert not hasattr(cfg, "target_payout")
        assert not hasattr(cfg, "run_daily_count")
        assert not hasattr(cfg, "totally_unknown_key")

    def test_empty_dict_yields_defaults(self):
        """[P1] Empty YAML profile (or all-runtime keys) -> pure defaults."""
        cfg = _yaml_to_config({})
        assert cfg == BetSlipConfig()

    def test_partial_dict_overrides_only_given_fields(self):
        """[P1] Sparse YAML dict: only provided fields differ from defaults."""
        cfg = _yaml_to_config({"target_odds": 4.5, "target_legs": 5})
        defaults = BetSlipConfig()
        assert cfg.target_odds == 4.5
        assert cfg.target_legs == 5
        assert cfg.consensus_floor == defaults.consensus_floor
        assert cfg.min_odds == defaults.min_odds
        assert cfg.balance_decay == defaults.balance_decay

    def test_excluded_sources_list_preserved(self):
        """[P1] Issue #62: excluded_sources list must pass through intact."""
        sources = ["source_a", "source_b", "source_c"]
        cfg = _yaml_to_config({"excluded_sources": sources})
        assert cfg.excluded_sources == sources
        assert cfg.excluded_sources is sources or cfg.excluded_sources == sources

    def test_excluded_sources_none_default(self):
        """[P1] Absent excluded_sources stays None (no empty-list injection)."""
        assert _yaml_to_config({}).excluded_sources is None

    def test_balance_decay_invalid_falls_back_to_gaussian(self):
        """[P0] Invalid balance_decay string is normalised to 'gaussian' --
        a bad profile file must never crash the slip builder at runtime."""
        cfg = _yaml_to_config({"balance_decay": "exponential"})
        assert cfg.balance_decay == "gaussian"

    def test_balance_decay_valid_values_preserved(self):
        """[P1] Both documented decay modes survive parsing unchanged."""
        assert _yaml_to_config({"balance_decay": "linear"}).balance_decay == "linear"
        assert _yaml_to_config({"balance_decay": "gaussian"}).balance_decay == "gaussian"

    def test_optional_clamp_fields_none_survives(self):
        """[P0] None optionals stay None -- construction must NOT fabricate
        values for fields the engine auto-derives later."""
        cfg = _yaml_to_config(dict.fromkeys(OPTIONAL_CLAMP_FIELDS))
        for field in OPTIONAL_CLAMP_FIELDS:
            assert getattr(cfg, field) is None, field

    def test_clamping_applied_through_yaml_path(self):
        """[P0] Values outside bounds are clamped by BetSlipConfig.__post_init__
        when constructed through _yaml_to_config (end-to-end YAML -> clamp)."""
        cfg = _yaml_to_config({"target_odds": 5000.0, "target_legs": 999, "min_odds": 0.2})
        assert cfg.target_odds == 1000.0
        assert cfg.target_legs == 100
        assert cfg.min_odds == 1.01


class TestConfigClamping:
    """[P0] Clamping boundaries for every clamped BetSlipConfig field,
    exercised through the _yaml_to_config path (issue #62: test ALL clamping
    boundaries; coverage target >= 95% for config_helpers.py)."""

    @pytest.mark.parametrize("field,value,expected", CLAMP_CASES)
    def test_clamp_boundary_matrix(self, field, value, expected):
        """[P0] below-lo clamps to lo; lo and hi pass through; above-hi
        clamps to hi. Covers all 18 clamped fields x 4 boundary cases."""
        cfg = _yaml_to_config({field: value})
        assert getattr(cfg, field) == expected

    def test_target_odds_spec_bounds(self):
        """[P0] Issue #62 explicit bounds: target_odds clamps into [1.1, 1000]."""
        assert _yaml_to_config({"target_odds": 0.5}).target_odds == pytest.approx(1.10)
        assert _yaml_to_config({"target_odds": 1.10}).target_odds == pytest.approx(1.10)
        assert _yaml_to_config({"target_odds": 1000.0}).target_odds == pytest.approx(1000.0)
        assert _yaml_to_config({"target_odds": 2000.0}).target_odds == pytest.approx(1000.0)

    def test_target_legs_spec_bounds(self):
        """[P0] Issue #62 explicit bounds: target_legs clamps into [1, 100]."""
        assert _yaml_to_config({"target_legs": -3}).target_legs == 1
        assert _yaml_to_config({"target_legs": 1}).target_legs == 1
        assert _yaml_to_config({"target_legs": 100}).target_legs == 100
        assert _yaml_to_config({"target_legs": 101}).target_legs == 100

    def test_extreme_out_of_range_pairs(self):
        """[P0] Simultaneous multi-field violation: each field clamps
        independently through one YAML dict."""
        cfg = _yaml_to_config(
            {
                "target_odds": 99.0,
                "target_legs": 0,
                "consensus_floor": 250.0,
                "min_odds": 42.0,
                "tolerance_factor": 5.0,
                "consensus_shrinkage_k": -1.0,
                "min_source_edge": 9.0,
                "max_single_leg_odds": 50.0,
                "tol_lower": 7.0,
                "tol_upper": 0.0,
                "min_pick_quality": 4.0,
                "odds_movement_weight": 3.0,
                "odds_movement_strength_min": 1.0,
            }
        )
        assert cfg.target_odds == 99.0
        assert cfg.target_legs == 1
        assert cfg.consensus_floor == 100.0
        assert cfg.min_odds == 10.0
        assert cfg.tolerance_factor == 0.80
        assert cfg.consensus_shrinkage_k == 1.0
        assert cfg.min_source_edge == 0.50
        assert cfg.max_single_leg_odds == 10.0
        assert cfg.tol_lower == 1.00
        assert cfg.tol_upper == 0.01
        assert cfg.min_pick_quality == 1.00
        assert cfg.odds_movement_weight == 0.30
        assert cfg.odds_movement_strength_min == 0.20


class TestEnsureDefaultProfiles:
    """[P1] ensure_default_profiles: built-in profile seeding into a fresh
    config dir (tmp_path isolation mandatory -- config/ is never touched)."""

    def test_seeds_all_builtin_profiles(self, tmp_path):
        """[P1] Fresh dir receives low/medium/high_risk PLUS value_hunter
        (spec names 3; implementation ships 4 -- actual behaviour pinned)."""
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        names = {p.stem for p in (config_dir / "profiles").glob("*.yaml")}
        assert names == BUILTIN_PROFILE_NAMES

    def test_writes_into_profiles_subpath(self, tmp_path):
        """[P1] Files land at <config>/profiles/<name>.yaml exactly as
        logic.py:62 expects (profiles_dir arg + subpath='profiles' write)."""
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        for name in BUILTIN_PROFILE_NAMES:
            assert (config_dir / "profiles" / f"{name}.yaml").is_file(), name

    def test_seeded_files_match_builtin_configs(self, tmp_path):
        """[P0] Each seeded YAML file parses back into the exact built-in
        BetSlipConfig (end-to-end: seed -> disk -> _yaml_to_config)."""
        import yaml

        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        for name, builtin in PROFILES.items():
            raw = yaml.safe_load((config_dir / "profiles" / f"{name}.yaml").read_text())
            assert asdict(_yaml_to_config(raw)) == asdict(builtin), name

    def test_metadata_stamped_on_every_profile(self, tmp_path):
        """[P1] Every seeded file carries units=1.0, target_payout=None,
        run_daily_count=0 -- run_daily_count=0 keeps built-ins INACTIVE by
        default (cycle-3 documented behaviour: the daily generator ignores
        them until a user raises the count)."""
        import yaml

        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        for name in BUILTIN_PROFILE_NAMES:
            raw = yaml.safe_load((config_dir / "profiles" / f"{name}.yaml").read_text())
            assert raw["units"] == 1.0, name
            assert raw["target_payout"] is None, name
            assert raw["run_daily_count"] == 0, name

    def test_runtime_only_keys_nulled_on_disk(self, tmp_path):
        """[P1] date_from/date_to/excluded_urls are stored as explicit None
        so profile files round-trip without dragging stale window state."""
        import yaml

        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        raw = yaml.safe_load((config_dir / "profiles" / "low_risk.yaml").read_text())
        assert raw["date_from"] is None
        assert raw["date_to"] is None
        assert raw["excluded_urls"] is None

    def test_idempotent_when_profiles_exist(self, tmp_path):
        """[P1] Second run is a no-op: pre-existing profile yaml files
        short-circuit the glob check, user edits are never overwritten."""
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        target = config_dir / "profiles" / "low_risk.yaml"
        target.write_text("target_odds: 99.9\n")  # simulate user hand-edit
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        assert "99.9" in target.read_text()

    def test_seeds_when_dir_has_only_non_yaml_files(self, tmp_path):
        """[P2] A dir holding only .txt files still counts as fresh:
        the guard is any(*.yaml), not a plain emptiness check."""
        config_dir = tmp_path / "cfg"
        profiles_dir = config_dir / "profiles"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "notes.txt").write_text("scratch")
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(profiles_dir), settings)
        assert {p.stem for p in profiles_dir.glob("*.yaml")} == BUILTIN_PROFILE_NAMES

    def test_creates_missing_parent_dirs(self, tmp_path):
        """[P2] Fully absent config tree is created via mkdir(parents=True)
        -- first app start against an empty volume works."""
        config_dir = tmp_path / "deep" / "nested" / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        assert (config_dir / "profiles" / "high_risk.yaml").is_file()

    def test_seeded_profiles_visible_via_settings_get(self, tmp_path):
        """[P1] SettingsManager DFS fallback surfaces seeded profiles by
        bare name -- the read path logic.py:741 relies on."""
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        raw = settings.get("low_risk")
        assert isinstance(raw, dict)
        assert asdict(_yaml_to_config(raw)) == asdict(PROFILES["low_risk"])


class TestProfileRoundTrip:
    """[P1] Issue #62: profile YAML round-trip (save -> load -> verify)."""

    def test_custom_config_round_trip(self, tmp_path):
        """[P0] _config_to_yaml_dict -> disk -> _yaml_to_config returns the
        original BetSlipConfig for every field (runtime-only keys excluded)."""
        original = BetSlipConfig(
            target_odds=7.5,
            target_legs=4,
            max_legs_overflow=1,
            consensus_floor=65.0,
            min_odds=1.25,
            tolerance_factor=0.28,
            stop_threshold=0.90,
            min_legs_fill_ratio=0.80,
            quality_vs_balance=0.60,
            consensus_vs_sources=0.40,
            consensus_shrinkage_k=2.5,
            min_source_edge=0.04,
            max_single_leg_odds=3.80,
            tol_lower=0.30,
            tol_upper=0.15,
            balance_decay="linear",
            min_pick_quality=0.28,
            odds_movement_weight=0.10,
            odds_movement_strength_min=0.12,
            excluded_sources=["forebet"],
            included_markets=["1", "2"],
            included_leagues=["Serie A"],
        )
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        settings.write("my_profile", _config_to_yaml_dict(original, units=2.0), subpath="profiles")
        raw = settings.get("my_profile")
        assert asdict(_yaml_to_config(raw)) == asdict(original)

    def test_all_builtin_profiles_round_trip(self, tmp_path):
        """[P1] Every PROFILES entry survives the full disk round-trip."""
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        for name, builtin in PROFILES.items():
            settings.write(name, _config_to_yaml_dict(builtin), subpath="profiles")
        for name, builtin in PROFILES.items():
            raw = settings.get(name)
            assert asdict(_yaml_to_config(raw)) == asdict(builtin), name

    def test_round_trip_preserves_metadata(self, tmp_path):
        """[P2] units/target_payout/run_daily_count ride along in the YAML
        dict and survive disk -- they are profile-file metadata consumed by
        logic.py:741, not BetSlipConfig fields."""
        cfg = BetSlipConfig(target_odds=3.0)
        data = _config_to_yaml_dict(cfg, units=3.5, target_payout=42.0, run_daily_count=2)
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        settings.write("meta_profile", data, subpath="profiles")
        raw = settings.get("meta_profile")
        assert raw["units"] == 3.5
        assert raw["target_payout"] == 42.0
        assert raw["run_daily_count"] == 2

    def test_round_trip_with_out_of_range_source(self, tmp_path):
        """[P2] A hand-edited out-of-range YAML clamps on load -- saved disk
        state stays raw; the config object is always in-bounds."""
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        settings.write(
            "bad_edit",
            {"target_odds": 9000.0, "target_legs": -5, "units": 1.0},
            subpath="profiles",
        )
        cfg = _yaml_to_config(settings.get("bad_edit"))
        assert cfg.target_odds == 1000.0
        assert cfg.target_legs == 1

    def test_excluded_sources_survive_round_trip(self, tmp_path):
        """[P1] Issue #62: excluded_sources list must survive a full
        save -> load cycle unchanged."""
        sources = ["soccer_vista", "vitibet", "legit_predict"]
        cfg = BetSlipConfig(excluded_sources=sources)
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        settings.write("filtered", _config_to_yaml_dict(cfg), subpath="profiles")
        loaded = _yaml_to_config(settings.get("filtered"))
        assert loaded.excluded_sources == sources

    def test_user_profile_coexists_with_builtins(self, tmp_path):
        """[P1] First app start seeds built-ins, then a user-saved custom
        profile coexists on disk -- the ensure guard leaves it untouched on
        the next construction (the real logic.py startup sequence)."""
        config_dir = tmp_path / "cfg"
        settings = SettingsManager(str(config_dir))
        ensure_default_profiles(str(config_dir / "profiles"), settings)
        custom = _config_to_yaml_dict(BetSlipConfig(target_odds=12.0, target_legs=6), units=1.5)
        settings.write("user_custom", custom, subpath="profiles")
        ensure_default_profiles(str(config_dir / "profiles"), settings)  # app restart
        raw = settings.get("user_custom")
        assert raw["units"] == 1.5
        assert asdict(_yaml_to_config(raw)) == asdict(BetSlipConfig(target_odds=12.0, target_legs=6))
        assert {p.stem for p in (config_dir / "profiles").glob("*.yaml")} == BUILTIN_PROFILE_NAMES | {"user_custom"}

    def test_default_metadata_on_yaml_dict(self):
        """[P2] _config_to_yaml_dict defaults: units=1.0, target_payout=None,
        run_daily_count=0, runtime-only keys nulled."""
        data = _config_to_yaml_dict(BetSlipConfig())
        assert data["units"] == 1.0
        assert data["target_payout"] is None
        assert data["run_daily_count"] == 0
        for key in ("date_from", "date_to", "excluded_urls"):
            assert data[key] is None

    def test_yaml_dict_contains_every_config_field(self):
        """[P0] asdict-based serialization must cover the full field set --
        guards against a field added to BetSlipConfig without making it
        into profile files (silent default on round-trip would follow)."""
        data = _config_to_yaml_dict(BetSlipConfig())
        for field_name in BetSlipConfig.__dataclass_fields__:
            assert field_name in data, field_name
        assert set(data) == set(BetSlipConfig.__dataclass_fields__) | {
            "units",
            "target_payout",
            "run_daily_count",
        }
