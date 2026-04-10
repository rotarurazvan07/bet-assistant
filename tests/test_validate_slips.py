from datetime import datetime
from unittest.mock import patch

import pytest

from bet_framework.BetAssistant import BetAssistant, _parse_match_result_html
from bet_framework.core.Slip import CandidateLeg
from bet_framework.core.types import MarketLabel, MarketType, MatchStatus, Outcome

# ── Mock Data ────────────────────────────────────────────────────────────────

SCORE_DIV = '<div class="text-base font-bold min-sm:text-xl text-center">2:1</div>'
STATUS_FINISHED = '<div id="status-container">FT</div>'
STATUS_LIVE = '<div id="status-container">LIVE 65\'</div>'
PARENT_DIV = '<div><div class="text-base font-bold min-sm:text-xl text-center">1:1</div><div>65\'</div></div>'


@pytest.fixture
def ba(tmp_path):
    assistant = BetAssistant(str(tmp_path / "validate.db"))
    yield assistant
    assistant.close()


# ── Tests for _parse_match_result_html ──────────────────────────────────────


def test_parse_normal_finished():
    """Verify FT result parsing with downloaded HTML."""
    html = f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"
    res = _parse_match_result_html(html, "http://test.url")
    assert res.status == MatchStatus.FT
    assert res.score == "2:1"


def test_parse_future_match_ignores_stats():
    """Verify that a future match (no status) ignores random X:Y patterns on the page."""
    html = '<html><body><span class="random-stat">4:3</span><div class="footer">Kickoff 20:00</div></body></html>'
    res = _parse_match_result_html(html, "http://test.future")
    assert res.status == MatchStatus.PENDING
    assert res.score == ""  # Should NOT pick up the 4:3


def test_parse_fuzzy_fallback():
    """Verify that score is found via fuzzy regex if class structure changes."""
    html = '<html><body><span class="random-new-class">3:2</span><div id="status-container">FT</div></body></html>'
    res = _parse_match_result_html(html, "http://test.url")
    assert res.status == MatchStatus.FT
    assert res.score == "3:2"


def test_parse_live():
    """Verify LIVE result parsing."""
    html = f"<html><body>{SCORE_DIV}{STATUS_LIVE}</body></html>"
    res = _parse_match_result_html(html, "http://test.url")
    assert res.status == MatchStatus.LIVE
    assert res.score == "2:1"


# ── Tests for validate_slips ───────────────────────────────────────────────


def test_validate_slips_integration(ba):
    """Full integration test for the validation loop."""
    # 1. Setup DB with a pending slip
    legs = [
        CandidateLeg(
            match_name="A vs B",
            datetime=datetime.now(),
            market=MarketLabel.HOME,
            market_type=MarketType.RESULT,
            odds=1.5,
            result_url="http://match1",
            consensus=80.0,
            sources=3,
        )
    ]
    ba.save_slip("test_profile", legs)

    # 2. Fake WebScraper scrape calling the callback
    html = f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"

    def fake_scrape(urls, callback, **kwargs):
        for url in urls:
            callback(url, html)

    with patch("bet_framework.BetAssistant.scrape", side_effect=fake_scrape):
        report = ba.validate_slips()

        assert report.checked == 1
        assert len(report.settled) == 1
        assert report.settled[0].outcome == Outcome.WON

        # Verify DB updated
        rows = ba.fetch_rows("SELECT status FROM legs")
        assert rows[0]["status"] == Outcome.WON


def test_validate_slips_skips_processed(ba):
    """Verify validate_slips only touches Pending/Live legs."""
    legs = [
        CandidateLeg(
            match_name="A vs B",
            datetime=datetime.now(),
            market=MarketLabel.HOME,
            market_type=MarketType.RESULT,
            odds=1.5,
            result_url="http://match1",
            consensus=80.0,
            sources=3,
        )
    ]
    # We have to manually insert to force status 'Won' for testing purposes or use update_leg
    ba.save_slip("test", legs)
    rows = ba.fetch_rows("SELECT leg_id FROM legs")
    ba.update_leg(rows[0]["leg_id"], Outcome.WON)

    with patch("bet_framework.BetAssistant.scrape") as mock_scrape:
        report = ba.validate_slips()
        assert report.checked == 0
        assert mock_scrape.call_count == 0
