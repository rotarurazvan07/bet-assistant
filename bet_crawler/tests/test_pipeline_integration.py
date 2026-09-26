"""Full pipeline integration tests (issue #68): prepare → scrape → merge →
generate → validate, with runner-set isolation and FT/LIVE/PENDING handling.

All HTTP is mocked: stub finders emit matches, and BetAssistant's result-page
scraper is patched to serve canned FT/LIVE/PENDING HTML per URL. Zero network.
"""

import json
from datetime import datetime
from unittest.mock import patch

import pytest
import yaml
import os

from bet_crawler.crawl_core.generate_slips import generate_slips
from bet_crawler.crawl_core.merge import merge
from bet_crawler.crawl_core.prepare_scrape import prepare_scrape
from bet_crawler.crawl_core.scrape import scrape
from bet_crawler.crawl_core.validate_slips import validate_slips
from bet_framework.BetAssistant import BetAssistant
from bet_framework.core.Slip import CandidateLeg
from bet_framework.core.type_defs import MarketLabel, MarketType

from .conftest import (
    StubCrawler,
    StubFactory,
    make_chunk_db,
    make_match,
    make_result_html_ft,
    make_result_html_live,
    make_result_html_pending,
)

DT = datetime(2026, 9, 25, 15, 0, 0)


def _sim_config():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(root, "config", "similarity_config.yaml")) as f:
        return yaml.safe_load(f)


SIM = _sim_config()

PROFILE = {
    "target_odds": 2.0,
    "target_legs": 1,
    "tolerance_factor": 0.30,
    "stop_threshold": 0.50,
    "consensus_floor": 40.0,
    "min_odds": 1.01,
}


def _consensus_match(home, away, url, source_prefix):
    from bet_framework.core.Match import Odds, Score

    return make_match(
        home=home,
        away=away,
        dt=DT,
        preds=[Score(source=f"{source_prefix}{i}", home=3, away=1) for i in range(3)],
        odds=Odds(home=1.9, draw=3.4, away=4.2),
        url=url,
    )


def _leg_statuses(slips_db):
    ba = BetAssistant(slips_db)
    try:
        rows = ba.fetch_rows("SELECT status, result_url FROM legs ORDER BY leg_id")
        return [(r["status"], r["result_url"]) for r in rows]
    finally:
        ba.close()


class TestFullPipelineP0:
    def test_full_pipeline_happy_path_settles_won(self, tmp_cwd, capsys):
        """prepare → scrape → merge → generate → validate with an FT result page."""
        match_a = _consensus_match("Pipeline FC", "United", "https://alpha.com/m/1", "a")
        match_b = _consensus_match("Jupiter FC", "Saturn", "https://beta.com/m/2", "b")
        urls = [f"https://alpha.com/x/{i}" for i in range(25)] + [f"https://beta.com/y/{i}" for i in range(25)]
        crawler_a = StubCrawler(urls[:25], matches=[match_a])
        crawler_b = StubCrawler(urls[25:], matches=[match_b])
        factory = StubFactory(
            {"actions": [crawler_a, crawler_b]},
            url_to_crawler={"alpha": crawler_a, "beta": crawler_b},
        )

        # 1. prepare
        prepare_scrape("actions", factory, {"actions": 2})
        tasks = json.loads(capsys.readouterr().out.strip())
        assert len(tasks) == 2  # 50 urls / max(20, ceil(50/2)=25) → 2 chunks of 25

        # 2. scrape each chunk (stubs emit matches; dupes expected across chunks)
        for task in tasks:
            scrape(task["db_path"], task["urls_file"], factory, SIM)

        # 3. merge all chunks into final db
        final_db = str(tmp_cwd / "final_matches.db")
        merge(final_db, str(tmp_cwd), SIM, {"alpha": {}, "beta": {}}, {"actions": ["alpha", "beta"]})

        # 4. generate slip
        slips_db = str(tmp_cwd / "slips.db")
        generate_slips(final_db, slips_db, "daily", dict(PROFILE))
        ba = BetAssistant(slips_db)
        slips = ba.get_slips()
        ba.close()
        assert len(slips) == 1
        assert len(slips[0].legs) == 1
        assert abs(slips[0].total_odds - 1.9) < 1e-9

        # 5. validate with mocked result pages (FT for every URL)
        def fake_scrape(urls, callback, **kwargs):
            for url in urls:
                callback(url, make_result_html_ft("3:1"))

        with patch("bet_framework.BetAssistant.scrape", side_effect=fake_scrape):
            validate_slips(slips_db)
        statuses = _leg_statuses(slips_db)
        assert statuses == [("Won", statuses[0][1])]
        assert statuses[0][1] in ("https://alpha.com/m/1", "https://beta.com/m/2")

    def test_ft_live_pending_mixed_results(self, tmp_path):
        """Three seeded legs: FT settles Won, LIVE stays Live, PENDING stays Pending."""
        slips_db = str(tmp_path / "slips.db")
        legs = [
            CandidateLeg(
                match_name="FT FC vs Opp",
                datetime=DT,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.9,
                result_url="https://r.com/ft",
                consensus=100.0,
                sources=3,
            ),
            CandidateLeg(
                match_name="Live FC vs Opp",
                datetime=DT,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.9,
                result_url="https://r.com/live",
                consensus=100.0,
                sources=3,
            ),
            CandidateLeg(
                match_name="Pend FC vs Opp",
                datetime=DT,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.9,
                result_url="https://r.com/pend",
                consensus=100.0,
                sources=3,
            ),
        ]
        ba = BetAssistant(slips_db)
        ba.save_slip("mixed", legs)
        ba.close()

        pages = {
            "https://r.com/ft": make_result_html_ft("2:0"),
            "https://r.com/live": make_result_html_live("63'", "1:0"),
            "https://r.com/pend": make_result_html_pending(),
        }

        def fake_scrape(urls, callback, **kwargs):
            for url in urls:
                callback(url, pages[url])

        with patch("bet_framework.BetAssistant.scrape", side_effect=fake_scrape):
            validate_slips(slips_db)
        statuses = {url: status for status, url in _leg_statuses(slips_db)}
        assert statuses["https://r.com/ft"] == "Won"
        assert statuses["https://r.com/live"] == "Live"
        assert statuses["https://r.com/pend"] == "Pending"


class TestRunnerSetIsolationP0:
    @pytest.mark.parametrize("runner", ["actions", "local", "test"])
    def test_prepare_writes_only_own_runner_prefix(self, runner, tmp_cwd, capsys):
        """Runner sets never mix: a run for X produces only X-prefixed chunk files."""
        mine = [f"https://{runner}src.com/m/{i}" for i in range(45)]
        other = [f"https://othersrc.com/m/{i}" for i in range(45)]
        factory = StubFactory(
            {
                "actions": [StubCrawler(mine if runner == "actions" else other)],
                "local": [StubCrawler(mine if runner == "local" else other)],
                "test": [StubCrawler(mine if runner == "test" else other)],
            }
        )
        prepare_scrape(runner, factory, {runner: 2})
        files = sorted(p.name for p in tmp_cwd.iterdir())
        assert all(f.startswith(f"{runner}-") for f in files)
        assert len(files) == 2  # 45 urls, chunk floor 20 → 2 chunks
        got = []
        for f in files:
            with open(tmp_cwd / f) as fh:
                got.extend(fh.read().split(","))
        assert sorted(got) == sorted(mine)

    def test_two_runners_sequential_never_share_files(self, tmp_cwd, capsys):
        """Running actions then local leaves both sets present and unmixed."""
        act_urls = [f"https://actsrc.com/m/{i}" for i in range(45)]
        loc_urls = [f"https://locsrc.com/m/{i}" for i in range(45)]
        factory = StubFactory(
            {
                "actions": [StubCrawler(act_urls)],
                "local": [StubCrawler(loc_urls)],
            }
        )
        prepare_scrape("actions", factory, {"actions": 2})
        capsys.readouterr()
        prepare_scrape("local", factory, {"local": 2})
        capsys.readouterr()
        act_files = sorted(p.name for p in tmp_cwd.glob("actions-*"))
        loc_files = sorted(p.name for p in tmp_cwd.glob("local-*"))
        assert len(act_files) == 2 and len(loc_files) == 2
        for f in act_files:
            with open(tmp_cwd / f) as fh:
                assert set(fh.read().split(",")) <= set(act_urls)
        for f in loc_files:
            with open(tmp_cwd / f) as fh:
                assert set(fh.read().split(",")) <= set(loc_urls)

    def test_cross_runner_duplicate_merges_to_one_row(self, tmp_path):
        """Same fixture listed under two runner chunks dedups; both runner sets validate."""
        from bet_framework.core.Match import Score

        chunks = tmp_path / "chunks"
        chunks.mkdir()
        m1 = make_match(home="Shared FC", away="Common", preds=None, url="https://alpha.com/1")
        m1.predictions = [Score(source="alpha", home=2, away=1)]
        m2 = make_match(home="Shared FC", away="Common", preds=None, url="https://beta.com/2")
        m2.predictions = [Score(source="beta", home=3, away=0)]
        make_chunk_db(chunks / "actions-1.db", [m1])
        make_chunk_db(chunks / "test-1.db", [m2])
        final = tmp_path / "final.db"
        merge(
            str(final),
            str(chunks),
            SIM,
            {"alpha": {}, "beta": {}},
            {"actions": ["alpha"], "test": ["beta"]},
        )
        from bet_framework.MatchesManager import MatchesManager

        mm = MatchesManager(str(final), similarity_config=SIM)
        df = mm.fetch_matches()
        mm.close()
        assert len(df) == 1
        assert {s["source"] for s in df.iloc[0]["scores"]} == {"alpha", "beta"}


class TestPipelineResilienceP1:
    def test_empty_pipeline_produces_no_artifacts(self, tmp_cwd, capsys):
        """Zero URLs → no chunks; empty merge; no slip; validate reports nothing checked."""
        crawler = StubCrawler([])
        factory = StubFactory({"actions": [crawler]})
        prepare_scrape("actions", factory, {"actions": 2})
        tasks = json.loads(capsys.readouterr().out.strip())
        assert tasks == []
        assert list(tmp_cwd.iterdir()) == []

        final_db = str(tmp_cwd / "final.db")
        merge(final_db, str(tmp_cwd), SIM, {}, {"actions": ["alpha"]})
        slips_db = str(tmp_cwd / "slips.db")
        generate_slips(final_db, slips_db, "daily", dict(PROFILE))
        ba = BetAssistant(slips_db)
        assert ba.get_slips() == []
        ba.close()

        def fake_scrape(urls, callback, **kwargs):
            assert urls == []

        with patch("bet_framework.BetAssistant.scrape", side_effect=fake_scrape):
            validate_slips(slips_db)
        assert _leg_statuses(slips_db) == []
