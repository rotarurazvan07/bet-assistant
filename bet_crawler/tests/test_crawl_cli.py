"""CrawlerFactory + CLI wiring tests (issue #68, crawl.py wiring context).

Pins: runner-set resolution, URL→crawler-key matching, class loading,
real finder construction safety (offline ctor), skip-pattern injection,
load_runtime/load_profile config plumbing, argparse mode validation.
"""

import pytest
import yaml

from bet_crawler.crawl import CrawlerFactory, CrawlerRuntimeSettings, build_parser, load_profile, load_runtime

RUNNER_SETS = {
    "actions": ["alpha", "beta"],
    "local": ["gamma"],
    "test": ["delta"],
}
CRAWLER_KEYS = {
    "alpha": {"class": "FakeFinderA", "contributes_odds": False, "top_leagues_only": True},
    "beta": {"class": "FakeFinderB", "contributes_odds": True, "top_leagues_only": False},
    "gamma": {"class": "FakeFinderA", "contributes_odds": False, "top_leagues_only": True},
    "delta": {"class": "FakeFinderB", "contributes_odds": False, "top_leagues_only": True},
}


def _factory():
    rt = CrawlerRuntimeSettings(
        num_days_ahead=1,
        local_timezone="Europe/Bucharest",
        skip_patterns=((r"\bU\d{2}s?\b", "Youth team"),),
    )
    return CrawlerFactory(CRAWLER_KEYS, RUNNER_SETS, rt)


@pytest.fixture
def fake_finders(monkeypatch):
    """Redirect _load_class to offline stubs instead of real finder modules."""

    class FakeFinder:
        def __init__(
            self,
            on_match_callback,
            contributes_odds=False,
            top_leagues_only=False,
            num_days_ahead=1,
            local_timezone="UTC",
            skip_patterns=(),
        ):
            self.on_match_callback = on_match_callback
            self.contributes_odds = contributes_odds
            self.top_leagues_only = top_leagues_only
            self.num_days_ahead = num_days_ahead
            self.local_timezone = local_timezone
            self.skip_patterns = tuple(skip_patterns)
            self.received_callback = on_match_callback is not None

    monkeypatch.setattr("bet_crawler.crawl.CrawlerFactory._load_class", staticmethod(lambda name: FakeFinder))
    return FakeFinder


class TestCrawlerFactoryP1:
    def test_runner_keys_resolve_per_set(self):
        f = _factory()
        assert f.runner_keys("actions") == ["alpha", "beta"]
        assert f.runner_keys("local") == ["gamma"]
        assert f.runner_keys("test") == ["delta"]
        assert f.runner_keys("ghost") == []

    def test_normalise_adds_all_set_with_every_key(self):
        f = _factory()
        assert set(f.runner_sets["all"]) == set(CRAWLER_KEYS.keys())
        assert f.runner_names() == ["actions", "local", "test", "all"]

    def test_crawler_key_for_url_matches_by_substring(self):
        f = _factory()
        assert f._crawler_key_for_url("https://www.alpha.com/match/1") == "alpha"
        assert f._crawler_key_for_url("https://beta.io/x") == "beta"

    def test_crawler_key_for_unknown_url_raises(self):
        f = _factory()
        with pytest.raises(ValueError, match="No crawler registered"):
            f._crawler_key_for_url("https://nowhere.example/1")

    def test_create_injects_runtime_settings_and_callback(self, fake_finders):
        f = _factory()
        inst = f.create("alpha", on_match_callback=print)
        assert isinstance(inst, fake_finders)
        assert inst.received_callback
        assert inst.contributes_odds is False
        assert inst.top_leagues_only is True
        assert inst.num_days_ahead == 1
        assert inst.local_timezone == "Europe/Bucharest"
        assert inst.skip_patterns == ((r"\bU\d{2}s?\b", "Youth team"),)

    def test_create_defaults_flags_from_config(self, fake_finders):
        f = _factory()
        inst = f.create("beta")
        assert inst.contributes_odds is True
        assert inst.top_leagues_only is False
        assert inst.received_callback is False

    def test_create_for_url_resolves_and_creates(self, fake_finders):
        f = _factory()
        inst = f.create_for_url("https://www.gamma.com/m/1", on_match_callback=None)
        assert isinstance(inst, fake_finders)

    def test_create_for_runner_builds_whole_set(self, fake_finders):
        f = _factory()
        insts = f.create_for_runner("actions")
        assert len(insts) == 2


class TestLoadRuntimeP1:
    def test_load_runtime_on_tmp_config_dir(self, tmp_path):
        scraper = {
            "num_days_ahead": 2,
            "local_timezone": "Europe/Berlin",
            "SKIP_PATTERNS": [{"pattern": "\\bW\\b", "description": "Women's team"}],
            "CRAWLER_KEYS": CRAWLER_KEYS,
            "RUNNER_SETS": RUNNER_SETS,
            "MAX_CHUNK_SIZE": {"actions": 5, "test": 1},
        }
        with open(tmp_path / "scraper_config.yaml", "w") as fh:
            yaml.safe_dump(scraper, fh)
        with open(tmp_path / "similarity_config.yaml", "w") as fh:
            yaml.safe_dump({"threshold": 65, "weights": {"token": 0.4}, "acronyms": {}, "synonyms": {}, "weak_tokens": []}, fh)
        rt = load_runtime(str(tmp_path))
        assert rt["max_chunk_size"] == {"actions": 5, "test": 1}
        assert rt["similarity_config"]["threshold"] == 65
        f = rt["factory"]
        assert f.runtime_settings.num_days_ahead == 2
        assert f.runtime_settings.local_timezone == "Europe/Berlin"
        assert f.runtime_settings.skip_patterns == (("\\bW\\b", "Women's team"),)
        assert f.runner_keys("test") == ["delta"]


class TestLoadProfileP1:
    def test_load_profile_reads_flat_profile_file(self, tmp_path):
        p = tmp_path / "aggressive.yaml"
        with open(p, "w") as fh:
            yaml.safe_dump({"target_odds": 4.0, "units": 2.5}, fh)
        name, data = load_profile(str(p))
        assert name == "aggressive"
        assert data == {"target_odds": 4.0, "units": 2.5}

    def test_load_profile_returns_file_body_even_with_foreign_top_key(self, tmp_path):
        """SettingsManager.get(stem) returns the whole file body: a profile file
        whose top-level key mismatches still yields its body (quirk pinned;
        generate_slips then degrades gracefully to BetSlipConfig defaults)."""
        p = tmp_path / "mystery.yaml"
        with open(p, "w") as fh:
            yaml.safe_dump({"something_else": {"x": 1}}, fh)
        name, data = load_profile(str(p))
        assert name == "mystery"
        assert data == {"something_else": {"x": 1}}

    def test_load_profile_empty_file_yields_empty_dict(self, tmp_path):
        """The `or {}` guard: empty profile body → empty dict (no crash)."""
        p = tmp_path / "hollow.yaml"
        p.write_text("")
        name, data = load_profile(str(p))
        assert name == "hollow"
        assert data == {}


class TestBuildParserP2:
    @pytest.mark.parametrize(
        "mode",
        ["prepare-scrape", "scrape", "merge", "generate-slips", "validate-slips"],
    )
    def test_all_five_modes_accepted(self, mode):
        args = build_parser().parse_args(["--mode", mode])
        assert args.mode == mode

    def test_unknown_mode_rejected(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--mode", "explode"])

    def test_missing_mode_rejected(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_optional_args_default_none(self):
        args = build_parser().parse_args(["--mode", "merge"])
        assert args.matches_db_path is None
        assert args.chunks_dir is None
        assert args.urls is None
