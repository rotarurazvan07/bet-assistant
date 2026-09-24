"""

Fixture uses TODAY+1 dates (closest-year search is +-1y bounded — decision D5);
regenerate fixtures if the committed file ages past ~1 year.
"""

import importlib

import datetime as dtmod

from bet_crawler.finders.PredictzFinder import PREDICTZ_NAME, PredictzFinder
from .finder_test_helpers import load_fixture, make_finder, patch_fetch, relax_date_window

pz = importlib.import_module("bet_crawler.finders.PredictzFinder")


def _finder(**kw):
    finder, collector = make_finder(PredictzFinder, **kw)
    return relax_date_window(finder), collector


class TestPredictz:
    def test_top_leagues_urls(self):
        finder, _ = _finder(top_leagues_only=True)
        assert finder.get_matches_urls() == list(pz.TOP_LEAGUES.keys())

    def test_non_top_optgroup_branch(self, monkeypatch):
        hub = '<html><body><div class="dd nav-select"><optgroup><option value="a"/></optgroup><optgroup><option value="b"/></optgroup><optgroup><option value="x"/></optgroup><optgroup><option value="y"/></optgroup><optgroup><option value="z"/></optgroup></div></body></html>'
        patch_fetch(monkeypatch, pz, {pz.PREDICTZ_URL: hub})
        finder, _ = _finder(top_leagues_only=False)
        urls = finder.get_matches_urls()
        assert urls == ["y", "z"]  # optgroups [3:] -> last two of five

    def test_parse_page_extracts_rows_with_odds(self):
        finder, collector = _finder(contributes_odds=True)
        url = next(iter(pz.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("predictz", "league.html"))
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.predictions[0].source == PREDICTZ_NAME
        assert m.predictions[0].home == 2
        assert m.predictions[0].away == 1
        assert m.odds.home == 1.9
        assert m.odds.draw == 3.5
        assert m.odds.away == 4.2

    def test_closest_year_resolution(self, monkeypatch):
        # Date-independent pin (cycle-8 D5 protocol): the fixture h2 carries a
        # fixed weekday+date ('Friday, September 25'). Originally expected was
        # TODAY+1 — which broke at midnight (fixture static, expected moving).
        # Freeze the finder's clock (datetime.now) to a date BEFORE the fixture
        # date so closest-year resolution is deterministic: Sep 25 2026 (Friday).
        frozen = dtmod.datetime(2026, 9, 10, 12, 0, 0)

        class _FrozenDatetime(dtmod.datetime):
            @classmethod
            def now(cls, tz=None):
                return frozen

        import bet_crawler.finders.PredictzFinder as _  # noqa: F401 — ensure module loaded
        monkeypatch.setattr(pz, "datetime", _FrozenDatetime)

        finder, collector = _finder()
        url = next(iter(pz.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("predictz", "league.html"))
        assert collector.first.datetime.date() == dtmod.date(2026, 9, 25)

    def test_no_matches_guard(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("predictz", "broken.html"))
        assert len(collector) == 0

    def test_missing_odds_fall_back_to_none(self):
        html = load_fixture("predictz", "league.html").replace('class="odds"', 'class="oddsx"')
        finder, collector = _finder(contributes_odds=True)
        url = next(iter(pz.TOP_LEAGUES))
        finder._parse_page(url, html)
        assert len(collector) == 1
        assert collector.first.odds is None

    def test_broken_structure_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", "<html><body><p>nothing</p></body></html>")
        assert len(collector) == 0
