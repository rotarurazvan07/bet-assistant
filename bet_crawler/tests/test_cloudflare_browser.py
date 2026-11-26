"""Tests for the Cloudflare-aware browser helper and the finders that use it."""

import importlib

from bet_crawler.finders.ForebetFinder import ForebetFinder
from bet_crawler.finders.WinDrawWinFinder_per_league import WinDrawWinFinder_per_league
from bet_crawler.finders.WinDrawWinFinder_per_match import WinDrawWinFinder_per_match

from .finder_test_helpers import (
    fake_cf_browser,
    load_fixture,
    make_finder,
    relax_date_window,
)

fb = importlib.import_module("bet_crawler.finders.ForebetFinder")
wdw_pm = importlib.import_module("bet_crawler.finders.WinDrawWinFinder_per_match")
wdw_pl = importlib.import_module("bet_crawler.finders.WinDrawWinFinder_per_league")

# Every test asserts the finder opened a *headful* solving session and no longer
# relies on scrape(mode=STEALTH), whose hardcoded AsyncStealthySession ignores
# every anti-detection flag bet-assistant can pass.


class TestCfBrowserHelper:
    def test_cf_browser_forwards_antidetect_flags(self, monkeypatch) -> None:
        from bet_crawler.finders import _cloudflare_browser as cfb

        seen: dict = {}

        class _FakeCtx:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_browser(**kwargs):
            seen.update(kwargs)
            return _FakeCtx()

        monkeypatch.setattr(cfb, "browser", fake_browser)

        cfb.cf_browser(
            headless=False,
            solve_cloudflare=True,
            interactive=True,
            disable_resources=False,
        )

        assert seen["headless"] is False
        assert seen["solve_cloudflare"] is True
        # Anti-detection flags must reach the session.
        assert "--disable-blink-features=AutomationControlled" in seen["extra_flags"]
        assert seen["additional_args"]["hide_canvas"] is True
        assert seen["additional_args"]["block_webrtc"] is True
        assert seen["useragent"].startswith("Mozilla/5.0")

    def test_cf_browser_always_injects_antidetect(self, monkeypatch) -> None:
        """cf_browser always injects anti-detection flags regardless of domain;
        the caller (finder) decides when to use it.
        """
        from bet_crawler.finders import _cloudflare_browser as cfb

        seen: dict = {}

        class _FakeCtx:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_browser(**kwargs):
            seen.update(kwargs)
            return _FakeCtx()

        monkeypatch.setattr(cfb, "browser", fake_browser)

        cfb.cf_browser()

        # cf_browser unconditionally injects flags; finders that don't want them
        # simply don't call cf_browser.
        assert "--disable-blink-features=AutomationControlled" in seen["extra_flags"]
        assert seen["additional_args"]["hide_canvas"] is True
        assert seen["additional_args"]["block_webrtc"] is True
        assert seen["useragent"].startswith("Mozilla/5.0")
        assert seen["headless"] is True  # default preserved when caller passes True


class TestForebetHeadfulPath:
    def test_get_matches_opens_headful_session_and_parses(self, monkeypatch) -> None:
        html = load_fixture("forebet", "league.html")
        session, calls = fake_cf_browser(monkeypatch, fb, {"https://u/": html})
        finder, collector = make_finder(ForebetFinder, contributes_odds=True)
        relax_date_window(finder)

        finder.get_matches(["https://u/"])

        assert len(calls) == 1
        assert calls[0]["headless"] is False
        assert calls[0]["solve_cloudflare"] is True
        assert session.fetched == ["https://u/"]
        assert len(collector) == 1

    def test_fetch_failure_does_not_crash(self, monkeypatch) -> None:
        session, _calls = fake_cf_browser(
            monkeypatch, fb, {}, fetch_error_urls={"https://bad/"}
        )
        finder, collector = make_finder(ForebetFinder)

        finder.get_matches(["https://bad/"])

        assert session.fetched == ["https://bad/"]  # loop continued past the failure
        assert len(collector) == 0  # failed URL contributed no matches


class TestWinDrawWinHeadfulPath:
    def test_league_finder_uses_headful_browser(self, monkeypatch) -> None:
        html = load_fixture("windrawwin", "league.html")
        session, calls = fake_cf_browser(monkeypatch, wdw_pl, {"https://u/": html})
        finder, collector = make_finder(
            WinDrawWinFinder_per_league, contributes_odds=True
        )
        relax_date_window(finder)

        finder.get_matches(["https://u/"])

        assert calls and calls[0]["headless"] is False
        assert session.fetched == ["https://u/"]
        assert len(collector) == 2

    def test_match_finder_uses_headful_browser(self, monkeypatch) -> None:
        html = load_fixture("windrawwin", "match.html")
        session, calls = fake_cf_browser(monkeypatch, wdw_pm, {"https://u/": html})
        finder, collector = make_finder(
            WinDrawWinFinder_per_match, contributes_odds=True
        )
        relax_date_window(finder)

        finder.get_matches(["https://u/"])

        assert calls and calls[0]["headless"] is False
        assert session.fetched == ["https://u/"]
        assert len(collector) == 1

    def test_fetch_failure_does_not_crash(self, monkeypatch) -> None:
        session, _calls = fake_cf_browser(
            monkeypatch, wdw_pl, {}, fetch_error_urls={"https://bad/"}
        )
        finder, collector = make_finder(WinDrawWinFinder_per_league)

        finder.get_matches(["https://bad/"])

        assert len(collector) == 0
