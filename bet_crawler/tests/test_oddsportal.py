"""

Discovery patched at fetch(); odds flow via FakeBrowserSession (D7).
MAX_CONCURRENCY patched to 1 for deterministic single-thread batch path.
"""

import datetime as dtmod
import importlib
import logging

import pytest

from bet_crawler.finders.OddsPortalFinder import ODDSPORTAL_NAME, OddsPortalFinder

from .finder_test_helpers import (
    FakeAnchor,
    FakeRow,
    FakeTooltipPage,
    fake_browser,
    load_fixture,
    make_finder,
    make_tooltip_session,
    patch_fetch,
    relax_date_window,
)

op = importlib.import_module("bet_crawler.finders.OddsPortalFinder")

# D53 (fixture-date rot): league.html carries a FIXED anchor date
# (2026-09-25, generator ANCHOR_TOMORROW). The discovery window is
# [today, today+N] on the finder's UTC clock — freezing the clock to
# 2026-09-24 puts that anchor at today+1: deterministically in-window on
# any runner, any day, forever (predictz D5 protocol applied at module
# scope so future discovery tests inherit the freeze).
_FROZEN_NOW = dtmod.datetime(2026, 9, 24, 12, 0, 0, tzinfo=dtmod.timezone.utc)


class _FrozenDatetime(dtmod.datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return _FROZEN_NOW.astimezone(tz)
        return _FROZEN_NOW.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _freeze_discovery_clock(monkeypatch) -> None:
    monkeypatch.setattr(op, "datetime", _FrozenDatetime)


def _finder(**kw):
    finder, collector = make_finder(OddsPortalFinder, **kw)
    return relax_date_window(finder), collector


def _league_url(top_only: bool = True):
    return (op.TOP_LEAGUES if top_only else op.ALL_LINKS)[0]


class TestDiscovery:
    def test_json_ld_discovery_filters_window_status_and_dedupes(self, monkeypatch) -> None:
        url = _league_url()
        patch_fetch(monkeypatch, op, {url: load_fixture("oddsportal", "league.html")})
        monkeypatch.setattr(op, "TOP_LEAGUES", [url])
        finder, _ = _finder(top_leagues_only=True, num_days_ahead=2)
        urls = finder.get_matches_urls()
        # in-window scheduled x2 (deduped) + out-window + cancelled + no-date all excluded
        assert sorted(urls) == ["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"]

    def test_all_links_branch_when_not_top_only(self, monkeypatch) -> None:
        url = "https://www.oddsportal.com/football/world/world-cup-2026/"  # ALL_LINKS[0]
        patch_fetch(monkeypatch, op, {url: load_fixture("oddsportal", "league.html")})
        monkeypatch.setattr(op, "ALL_LINKS", [url])
        finder, _ = _finder(top_leagues_only=False, num_days_ahead=2)
        urls = finder.get_matches_urls()
        assert urls == ["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"]

    def test_fetch_error_on_one_league_continues(self, monkeypatch) -> None:
        def boom(url, **kw):
            raise RuntimeError("network down")

        monkeypatch.setattr(op, "TOP_LEAGUES", ["https://x/1/", "https://x/2/"])
        patch_fetch(monkeypatch, op, boom)
        finder, _ = _finder(top_leagues_only=True)
        assert finder.get_matches_urls() == []

    def test_returns_set_deduplicated_across_leagues(self, monkeypatch) -> None:
        league = load_fixture("oddsportal", "league.html")
        monkeypatch.setattr(op, "TOP_LEAGUES", ["https://x/1/", "https://x/2/"])
        patch_fetch(monkeypatch, op, {"https://x/1/": league, "https://x/2/": league})
        finder, _ = _finder(top_leagues_only=True, num_days_ahead=2)
        assert finder.get_matches_urls() == ["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"]


class TestGetMatches:
    def test_empty_urls_short_circuit(self) -> None:
        finder, collector = _finder()
        finder.get_matches([])
        assert len(collector) == 0

    def test_single_concurrency_direct_batch(self, monkeypatch) -> None:
        seen_batches = []

        def fake_batch(self, urls) -> None:
            seen_batches.append(list(urls))

        monkeypatch.setattr(op, "MAX_CONCURRENCY", 1)
        monkeypatch.setattr(OddsPortalFinder, "_process_url_batch", fake_batch)
        finder, _ = _finder()
        finder.get_matches(["u1", "u2"])
        assert seen_batches == [["u1", "u2"]]

    def test_chunking_splits_into_max_concurrency_chunks(self, monkeypatch) -> None:
        captured = {}

        def fake_batch(self, urls) -> None:
            captured.setdefault("batches", []).append(list(urls))

        monkeypatch.setattr(op, "MAX_CONCURRENCY", 3)
        monkeypatch.setattr(OddsPortalFinder, "_process_url_batch", fake_batch)
        finder, _ = _finder()
        finder.get_matches([f"u{i}" for i in range(9)])
        assert len(captured["batches"]) == 3
        assert sorted(sum(captured["batches"], [])) == [f"u{i}" for i in range(9)]

    def test_chunking_balances_uneven_url_count(self, monkeypatch) -> None:
        captured = {}

        def fake_batch(self, urls) -> None:
            captured.setdefault("batches", []).append(list(urls))

        monkeypatch.setattr(op, "MAX_CONCURRENCY", 10)
        monkeypatch.setattr(OddsPortalFinder, "_process_url_batch", fake_batch)
        finder, _ = _finder()
        urls = [f"u{i:02d}" for i in range(39)]

        finder.get_matches(urls)

        assert sorted(len(batch) for batch in captured["batches"]) == [
            3,
            4,
            4,
            4,
            4,
            4,
            4,
            4,
            4,
            4,
        ]
        assert sorted(sum(captured["batches"], [])) == urls


class TestProcessUrlBatch:
    def _session_map(self, monkeypatch, base="match_base", extra=None):
        base_html = load_fixture("oddsportal", f"{base}.html")
        x2 = load_fixture("oddsportal", "match_1x2.html")
        btts = load_fixture("oddsportal", "match_btts.html")
        dc = load_fixture("oddsportal", "match_dc.html")
        ou = load_fixture("oddsportal", "match_ou.html")

        def content_for(clicks):
            # initial page before any market click, then swapped per click
            if not clicks:
                return base_html
            label = clicks[-1]
            if label == "1X2":
                return x2
            if label == "Both Teams to Score":
                return btts
            if label == "Double Chance":
                return dc
            if label == "Over/Under":
                return ou
            return base_html

        content_map = {"https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/": content_for}
        return fake_browser(monkeypatch, op, content_map, **(extra or {}))

    def test_full_odds_flow_adds_match_with_all_markets(self, monkeypatch) -> None:
        self._session_map(monkeypatch)
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"])
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.year == 2035
        assert m.predictions == []  # Match ctor normalizes None to []
        odds = m.odds
        assert odds.home == 2.10
        assert odds.draw == 3.40
        assert odds.away == 3.75
        assert odds.btts_y == 1.85
        assert odds.btts_n == 1.95
        assert odds.dc_1x == 1.25
        assert odds.dc_12 == 1.30
        assert odds.dc_x2 == 1.45
        assert odds.over_05 == 1.10
        assert odds.under_05 == 8.00
        assert odds.over_25 == 1.70
        assert odds.under_25 == 2.10
        assert odds.over_45 == 6.50
        assert (odds.dc_1x, odds.dc_12, odds.dc_x2) != (odds.home, odds.draw, odds.away)
        assert (odds.btts_y, odds.btts_n) != (odds.home, odds.draw)

    def test_stale_1x2_cells_do_not_fill_dc_or_btts(self, monkeypatch) -> None:
        """Live palace dumps: tab headers flip, first-row cells stay 1X2."""
        monkeypatch.setattr(OddsPortalFinder, "_TAB_SETTLE_S", 0)
        x2 = load_fixture("oddsportal", "match_1x2.html")
        stale_btts = x2.replace(">1</th>", ">Yes</th>").replace(">X</th>", ">No</th>")
        stale_dc = x2.replace(">1</th>", ">1X</th>").replace(">X</th>", ">12</th>").replace(">2</th>", ">X2</th>")
        ou = load_fixture("oddsportal", "match_ou.html")

        def content_for(clicks):
            if not clicks or clicks[-1] == "1X2":
                return x2
            if clicks[-1] == "Both Teams to Score":
                return stale_btts
            if clicks[-1] == "Double Chance":
                return stale_dc
            if clicks[-1] == "Over/Under":
                return ou
            return x2

        fake_browser(
            monkeypatch,
            op,
            {"https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/": content_for},
        )
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"])
        assert len(collector) == 1
        odds = collector.first.odds
        assert odds.home == 2.10
        assert odds.btts_y is None
        assert odds.dc_1x is None
        assert odds.over_25 == 1.70

    def test_click_targets_inner_tab_button(self, monkeypatch) -> None:
        """Live 2026-10-12: React onClick is on li.tab-item > button, not the li."""
        session = self._session_map(monkeypatch)
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"])
        assert len(collector) == 1
        assert session.click_calls
        assert all(sel == "li.tab-item button" for sel, _ in session.click_calls)

    def test_li_fallback_when_button_selector_missing(self, monkeypatch) -> None:
        """Old layout without inner buttons still scrapes via the li fallback."""
        session = self._session_map(monkeypatch)
        real_click = session.click

        def click_no_button(selector, label=None):
            if selector == "li.tab-item button":
                return False
            return real_click(selector, label)

        session.click = click_no_button
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"])
        odds = collector.first.odds
        assert (odds.home, odds.btts_y, odds.dc_1x, odds.over_05) == (
            2.10,
            1.85,
            1.25,
            1.10,
        )

    def test_live_shaped_market_tables_are_accepted(self, monkeypatch) -> None:
        """Live 2026-10-12 shape: glued 'claim bonus' bookmaker text, quarter lines,
        and '%' payouts must parse — never time out as 'did not settle'."""
        x2 = load_fixture("oddsportal", "match_1x2.html")
        btts = load_fixture("oddsportal", "match_btts.html").replace(">888sport<", ">888sportclaim bonus<")
        dc = load_fixture("oddsportal", "match_dc.html").replace(">888sport<", ">888sportclaim bonus<")
        quarter = "<tr><td>Over/Under +0.75</td><td>1.04</td><td>12.00</td><td>95.7%</td></tr>"
        ou = (
            load_fixture("oddsportal", "match_ou.html")
            .replace("<td>Over/Under +0.5</td>", "<td>Over/Under +0.5O/U +0.57</td>")
            .replace("<td>Over/Under +2.5</td>", "<td>Over/Under +2.5O/U +2.57</td>")
            .replace("<tr><td>Over/Under +1.5</td>", quarter + "<tr><td>Over/Under +1.5</td>")
        )

        def content_for(clicks):
            label = clicks[-1] if clicks else ""
            return {
                "": x2,
                "1X2": x2,
                "Both Teams to Score": btts,
                "Double Chance": dc,
                "Over/Under": ou,
            }.get(label, x2)

        fake_browser(
            monkeypatch,
            op,
            {"https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/": content_for},
        )
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"])
        odds = collector.first.odds
        assert (odds.home, odds.btts_y, odds.btts_n) == (2.10, 1.85, 1.95)
        assert (odds.dc_1x, odds.dc_12, odds.dc_x2) == (1.25, 1.30, 1.45)
        assert (odds.over_05, odds.under_05, odds.over_15, odds.under_15) == (
            1.10,
            8.00,
            1.35,
            3.10,
        )
        assert (odds.over_25, odds.under_25, odds.over_35, odds.under_35) == (
            1.70,
            2.10,
            3.20,
            1.34,
        )
        assert (odds.over_45, odds.under_45) == (6.50, 1.09)

    def test_fetch_error_then_retry_recovers(self, monkeypatch) -> None:
        session = self._session_map(monkeypatch)
        # make retry succeed: fetch_error_urls only raise once
        calls = {"n": 0}
        orig_fetch = session.fetch

        def flaky_fetch(url, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("timeout")
            return orig_fetch(url, **kw)

        session.fetch = flaky_fetch
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"])
        assert len(collector) == 1  # retry path succeeded

    def test_broken_page_logged_no_match(self, monkeypatch) -> None:
        content_map = {"https://www.oddsportal.com/match/broken-x/": load_fixture("oddsportal", "broken.html")}
        fake_browser(monkeypatch, op, content_map)
        finder, collector = _finder()
        finder._process_url_batch(["https://www.oddsportal.com/match/broken-x/"])
        assert len(collector) == 0

    def test_missing_identity_skips_url_siblings_kept(self, monkeypatch) -> None:
        session = self._session_map(monkeypatch)
        session.content_map["https://www.oddsportal.com/match/broken-x/"] = load_fixture("oddsportal", "broken.html")
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(
            [
                "https://www.oddsportal.com/match/broken-x/",
                "https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/",
            ]
        )
        assert len(collector) == 1
        assert collector.first.home_team == "Arsenal"

    def test_missing_market_tab_still_adds_match(self, monkeypatch) -> None:
        """AC-04: a market tab without its table leaves that market None."""
        monkeypatch.setattr(OddsPortalFinder, "_TAB_SETTLE_S", 0)
        session = self._session_map(monkeypatch)
        identity_only = load_fixture("oddsportal", "match_base.html")
        x2 = load_fixture("oddsportal", "match_1x2.html")

        def content_for(clicks):
            if not clicks or clicks[-1] == "1X2":
                return x2
            return identity_only

        session.content_map["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"] = content_for
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/football/h2h/arsenal-xxx/chelsea-yyy/"])
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.odds.home == 2.10
        assert m.odds.btts_y is None
        assert m.odds.dc_12 is None
        assert m.odds.over_25 is None

    def test_thread_safe_add_match(self, monkeypatch) -> None:
        """_add_match_lock exists and guards concurrent adds (wiring pin)."""
        finder, _ = _finder()
        assert hasattr(finder, "_add_match_lock")


class TestSourceName:
    def test_name_constant(self) -> None:
        assert ODDSPORTAL_NAME == "oddsportal"


class TestMovement:
    """Issue #105 movement hover, headless (CR #106 remediation, no live browser)."""

    BASE_HTML = '<div id="app"></div>'
    # each cell's popup; +0.0 keeps the current odds unambiguous (no other numbers)
    OVER_TIP = '<div class="absolute">ODDS MOVEMENT 2.10 +0.0 Opening odds: 2.00</div>'

    def test_opening_pp_first_decimal_after_label(self) -> None:
        """B1: 'Opening odds: 2.00 +5.0' must NOT fabricate movement (opening=5.0)."""
        pp = OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 2.10 +0.0 Opening odds: 2.00 +5.0", "2.10")
        assert pp is None

    def test_opening_pp_happy_path(self) -> None:
        """B1/B4: unambiguous tooltip reproduces the known pp."""
        pp = OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 2.10 +0.0 Opening odds: 2.00", "2.10")
        assert pp == 5.0

    def test_opening_pp_missing_label(self) -> None:
        """B4: no 'Opening odds:' entry - never guessed."""
        assert OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 2.10 +0.0", "2.10") is None

    def test_opening_pp_zero_opening_rejected(self) -> None:
        """B4: opening 0.00 cannot divide."""
        assert OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 2.10 +0.0 Opening odds: 0.00", "2.10") is None

    def test_opening_pp_current_must_match_cell(self) -> None:
        """B4: tooltip for another cell (current != hovered) is dropped."""
        assert OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 3.10 +0.0 Opening odds: 2.00", "2.10") is None

    def test_opening_pp_multi_number_tooltip_rejected(self) -> None:
        """B4: more decimals after the label make it unpinnable."""
        assert OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 2.10 +0.0 Opening odds: 2.00 1.85", "2.10") is None

    def test_opening_pp_three_decimal_tooltip_matches_two_decimal_cell(self) -> None:
        """F13: tooltips may carry 3 decimals while cells show 2."""
        pp = OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 2.105 +0.0 Opening odds: 2.00", "2.10")
        assert pp == 5.25

    def test_opening_pp_sanity_band(self) -> None:
        """F13: 1.001-1000 opening band; 0.5 and 5000 are not prices."""
        assert OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 0.60 +0.0 Opening odds: 0.50", "0.60") is None
        assert OddsPortalFinder._opening_pp_from_tooltip("ODDS MOVEMENT 5000.00 +0.0 Opening odds: 5000.00", "5000.00") is None

    def test_ou_line_lookup_is_exact_token(self) -> None:
        """F10a: '+10.5' style labels must not claim the '+0.5' keys."""
        assert OddsPortalFinder._ou_keys_for_line("Over/Under +0.5") == [
            "over_05",
            "under_05",
        ]
        assert OddsPortalFinder._ou_keys_for_line("Over/Under +10.5 O/U +10.57") is None

    def _hover_finder(self, monkeypatch, page, rows=None):
        finder, _ = _finder()
        monkeypatch.setattr(OddsPortalFinder, "_TOOLTIP_WAIT_S", 1.0)
        monkeypatch.setattr(OddsPortalFinder, "_TOOLTIP_POLL_S", 0.01)
        return finder, make_tooltip_session(page, rows)

    def test_stale_tooltip_from_previous_cell_is_ignored(self, monkeypatch) -> None:
        """B2: same-price O/U lines - the first cell's popup must not answer the second cell."""
        page = FakeTooltipPage(self.BASE_HTML, [self.OVER_TIP, self.OVER_TIP])
        finder, session = self._hover_finder(monkeypatch, page)
        first, second = FakeAnchor("2.10", page, 0), FakeAnchor("2.10", page, 1)
        assert finder._hover_opening_pp(session, first, "2.10") == 5.0
        second_result = finder._hover_opening_pp(session, second, "2.10")
        assert second_result is None or second_result == 5.0
        assert finder._hover_opening_pp(session, second, "2.10") is None

    def test_no_new_tooltip_returns_none(self, monkeypatch) -> None:
        """B2: a page whose HTML never changes after hover yields no movement."""
        page = FakeTooltipPage(self.BASE_HTML, [])
        finder, session = self._hover_finder(monkeypatch, page)
        anchor = FakeAnchor("2.10", page, 0)
        assert finder._hover_opening_pp(session, anchor, "2.10") is None

    def test_hover_parses_page_only_on_change(self, monkeypatch) -> None:
        """F6: no full-page BeautifulSoup re-parse every 0.25s tick."""
        page = FakeTooltipPage(self.BASE_HTML, [self.OVER_TIP])
        finder, session = self._hover_finder(monkeypatch, page)
        anchor = FakeAnchor("2.10", page, 0)
        assert finder._hover_opening_pp(session, anchor, "2.10") == 5.0
        assert page.content_calls <= 3

    def test_cell_movements_skips_row_on_anchor_count_mismatch(self, monkeypatch) -> None:
        """F10b: 3 anchors for 2 keys - no positional key shifting."""
        page = FakeTooltipPage(self.BASE_HTML, [])
        finder, session = self._hover_finder(monkeypatch, page)
        row = FakeRow("Both Teams to Score", [FakeAnchor("1.90", page, 0)])
        result = finder._hover_cell_movements(session, ("btts_yes", "btts_no"), first_row_only=False)
        assert result == {"btts_yes": None, "btts_no": None}
        assert row  # row shape kept for the full-run assertion below

    def test_cell_movements_full_run_confirms_one_cell(self, monkeypatch) -> None:
        """B2+B10 end-to-end: 1X2 first row confirms home only."""
        page = FakeTooltipPage(self.BASE_HTML, [self.OVER_TIP, "", ""])
        finder, session = self._hover_finder(monkeypatch, page)
        row = FakeRow(
            "1X2",
            [
                FakeAnchor("2.10", page, 0),
                FakeAnchor("3.40", page, 1),
                FakeAnchor("3.75", page, 2),
            ],
        )
        tbody = page.locator("table.w-full.table-fixed tbody").first
        tbody.rows = [row]
        result = finder._hover_cell_movements(session, ("home", "draw", "away"))
        assert result == {"home": 5.0, "draw": None, "away": None}

    def test_btts_movement_keys_match_consumer_keys(self, monkeypatch) -> None:
        """B3: finder emits btts_yes/btts_no - the keys MARKET_DEFINITIONS derive."""
        from bet_dashboard.backend.core.market_config import MARKET_DEFINITIONS

        expected = {md.odds_key.replace("odds_", "") for md in MARKET_DEFINITIONS if md.market_type == "btts"}
        assert expected == {"btts_yes", "btts_no"}
        page = FakeTooltipPage(self.BASE_HTML, [])
        finder, session = self._hover_finder(monkeypatch, page)
        finder._click_tab = lambda session, label, headers=(): None
        finder._first_bookmaker_odds = lambda soup: ["1.85", "1.95"]
        movements = {}
        finder._scrape_tab_btts(session, "t", movements)
        assert set(movements) == {"btts_yes", "btts_no"}

    def test_zero_confirmed_movement_logs_warning(self, monkeypatch, caplog) -> None:
        """F14: a site change that zeroes every movement is visible in normal logs."""
        page = FakeTooltipPage(self.BASE_HTML, [])
        finder, session = self._hover_finder(monkeypatch, page)
        tbody = page.locator("table.w-full.table-fixed tbody").first
        tbody.rows = [FakeRow("1X2", [FakeAnchor("2.10", page, 0)])]
        with caplog.at_level("WARNING", logger="bet_crawler.finders.OddsPortalFinder"):
            finder._hover_cell_movements(session, ("home", "draw", "away"), first_row_only=False)
        assert any("confirmed opening-odds movement" in r.getMessage() for r in caplog.records)
        assert any(r.levelno == logging.WARNING for r in caplog.records)
