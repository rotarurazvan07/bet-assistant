import time
from unittest.mock import patch, MagicMock
from bet_framework.BetAssistant import BetAssistant, _check_match_result, BetSlipConfig
import pytest
from datetime import datetime

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

# ── Tests for _check_match_result ───────────────────────────────────────────

def test_check_result_normal_finished():
    """Verify FT result parsing with single fetch."""
    html = f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"
    with patch("bet_framework.WebScraper.WebScraper.fetch", return_value=html) as mock_fetch:
        res = _check_match_result("http://test.url", "1", "result")
        assert res["status"] == "FT"
        assert res["score"] == "2:1"
        assert res["outcome"] == "Won"
        assert mock_fetch.call_count == 1

def test_check_result_retry_success():
    """Verify that it retries if score_div is missing on first fetch but status is present."""
    # Match is active (FT) but score hasn't loaded in the first fetch
    html_no_score = f"<html><body>{STATUS_FINISHED}</body></html>"
    html_with_score = f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"
    
    with patch("bet_framework.WebScraper.WebScraper.fetch") as mock_fetch:
        mock_fetch.side_effect = [html_no_score, html_with_score]
        with patch("time.sleep"):
            res = _check_match_result("http://test.url", "1", "result")
            assert res["status"] == "FT"
            assert res["score"] == "2:1"
            assert mock_fetch.call_count == 2

def test_check_result_still_pending_after_retries():
    """Verify it remains PENDING if score_div is never found even if match is full time."""
    html_no_score = f"<html><body>{STATUS_FINISHED}</body></html>"
    with patch("bet_framework.WebScraper.WebScraper.fetch", return_value=html_no_score) as mock_fetch:
        with patch("time.sleep"):
            res = _check_match_result("http://test.url", "1", "result")
            assert res["status"] == "PENDING"
            assert mock_fetch.call_count == 2

def test_check_result_future_match_ignores_stats():
    """Verify that a future match (no status) ignores random X:Y patterns on the page."""
    # This simulates a Soccervista page with H2H or predictions ("4:3") but no "FT" or live clock
    html = '<html><body><span class="random-stat">4:3</span><div class="footer">Kickoff 20:00</div></body></html>'
    with patch("bet_framework.WebScraper.WebScraper.fetch", return_value=html) as mock_fetch:
        res = _check_match_result("http://test.future", "1", "result")
        assert res["status"] == "PENDING"
        assert res["score"] == "" # Should NOT pick up the 4:3
        assert mock_fetch.call_count == 1

def test_check_result_fuzzy_fallback():
    """Verify that score is found via fuzzy regex if class structure changes."""
    # Class is totally different than expected
    html = '<html><body><span class="random-new-class">3:2</span><div id="status-container">FT</div></body></html>'
    with patch("bet_framework.WebScraper.WebScraper.fetch", return_value=html):
        res = _check_match_result("http://test.url", "1", "result")
        assert res["status"] == "FT"
        assert res["score"] == "3:2"
        # Since it's 3:2 and market is '1', outcome should be 'Won'
        assert res["outcome"] == "Won"

def test_check_match_result_live():
    """Verify LIVE result parsing."""
    html = f"<html><body>{SCORE_DIV}{STATUS_LIVE}</body></html>"
    with patch("bet_framework.WebScraper.WebScraper.fetch", return_value=html):
        res = _check_match_result("http://test.url", "1", "result")
        assert res["status"] == "LIVE"
        assert res["score"] == "2:1"

# ── Tests for validate_slips ───────────────────────────────────────────────

def test_validate_slips_integration(ba):
    """Full integration test for the validation loop."""
    # 1. Setup DB with a pending slip
    legs = [{
        "match": "A vs B",
        "datetime": datetime.now(),
        "market": "1",
        "market_type": "result",
        "odds": 1.5,
        "result_url": "http://match1",
        "consensus": 80.0,
        "sources": 3
    }]
    ba.save_slip("test_profile", legs)
    
    # 2. Mock result: The match finished 2:1 (Home win for market '1')
    html = f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"
    
    with patch("bet_framework.BetAssistant._check_match_result") as mock_check:
        mock_check.return_value = {"status": "FT", "score": "2:1", "outcome": "Won"}
        
        report = ba.validate_slips()
        
        assert report["checked"] == 1
        assert len(report["settled"]) == 1
        assert report["settled"][0]["outcome"] == "Won"
        
        # Verify DB updated
        rows = ba.fetch_rows("SELECT status FROM legs")
        assert rows[0]["status"] == "Won"

def test_validate_slips_skips_processed(ba):
    """Verify validate_slips only touches Pending/Live legs."""
    legs = [{
        "match": "A vs B",
        "datetime": datetime.now(),
        "market": "1",
        "market_type": "result",
        "odds": 1.5,
        "result_url": "http://match1",
        "status": "Won" # ALREADY SETTLED
    }]
    # We have to manually insert to force status 'Won' for testing purposes or use update_leg
    ba.save_slip("test", legs)
    rows = ba.fetch_rows("SELECT leg_id FROM legs")
    ba.update_leg(rows[0]["leg_id"], "Won")
    
    with patch("bet_framework.BetAssistant._check_match_result") as mock_check:
        report = ba.validate_slips()
        assert report["checked"] == 0
        assert mock_check.call_count == 0
