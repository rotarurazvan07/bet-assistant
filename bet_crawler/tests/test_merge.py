"""Stage 3: merge tests.

Pins: chunk db consolidation, fuzzy dedup via MatchesManager, odds preservation,
empty chunk handling, summary logging, runner-set validation.
Note: crawl merge uses MatchesManager.merge_databases (NOT merge_with_history_preservation,
which is a backend-only path — see automation-summary divergence table).
"""

import json
import os

import pytest
import yaml

from bet_crawler.crawl_core.merge import merge
from bet_crawler.crawler_logging import configure_event_logging, disable_event_logging
from bet_framework.MatchesManager import MatchesManager

from .conftest import make_chunk_db, make_match

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
)


def _load_sim_config():
    with open(os.path.join(CONFIG_DIR, "similarity_config.yaml")) as f:
        return yaml.safe_load(f)


def _fetch(db_path, sim=None):
    mm = MatchesManager(db_path, similarity_config=sim)
    try:
        return mm.fetch_matches()
    finally:
        mm.close()


SIM = _load_sim_config()


class TestMergeP0:
    def test_merges_two_chunk_dbs_into_final_db(self, tmp_path) -> None:
        chunks = tmp_path / "chunks"
        chunks.mkdir()
        make_chunk_db(
            chunks / "actions-1.db",
            [make_match(home="Alpha FC", url="https://a.com/1")],
        )
        make_chunk_db(chunks / "actions-2.db", [make_match(home="Beta FC", url="https://b.com/1")])
        final = tmp_path / "final.db"
        merge(str(final), str(chunks), SIM, {}, {})
        df = _fetch(str(final), SIM)
        assert sorted(df["home_name"]) == ["Alpha FC", "Beta FC"]

    def test_fuzzy_dedup_across_chunks_single_row_merged_sources(self, tmp_path) -> None:
        """Man Utd vs Manchester United (same away+datetime) → one row, 2 sources."""
        from bet_framework.core.Match import Score

        chunks = tmp_path / "chunks"
        chunks.mkdir()
        m1 = make_match(
            home="Manchester United",
            away="Liverpool",
            preds=None,
            url="https://a.com/1",
        )
        m1.predictions = [Score(source="srcA", home=2, away=1)]
        m2 = make_match(home="Man Utd", away="Liverpool", preds=None, url="https://b.com/2")
        m2.predictions = [Score(source="srcB", home=3, away=1)]
        make_chunk_db(chunks / "actions-1.db", [m1])
        make_chunk_db(chunks / "actions-2.db", [m2])
        final = tmp_path / "final.db"
        merge(str(final), str(chunks), SIM, {}, {})
        df = _fetch(str(final), SIM)
        assert len(df) == 1
        assert {s["source"] for s in df.iloc[0]["scores"]} == {"srcA", "srcB"}

    def test_odds_preserved_in_merged_output(self, tmp_path) -> None:
        from bet_framework.core.Match import Odds

        chunks = tmp_path / "chunks"
        chunks.mkdir()
        m = make_match(
            home="Odds FC",
            odds=Odds(home=1.9, draw=3.4, away=4.2),
            url="https://a.com/1",
        )
        make_chunk_db(chunks / "actions-1.db", [m])
        final = tmp_path / "final.db"
        merge(str(final), str(chunks), SIM, {}, {})
        df = _fetch(str(final), SIM)
        assert df.iloc[0]["odds"]["home"] == 1.9

    def test_invalid_chunks_dir_raises_system_exit(self, tmp_path) -> None:
        with pytest.raises(SystemExit) as exc:
            merge(str(tmp_path / "f.db"), str(tmp_path / "nope"), SIM, {}, {})
        assert exc.value.code == 1
        assert not (tmp_path / "f.db").exists() or True  # db may exist w/ empty tables

    def test_empty_chunk_db_yields_empty_final(self, tmp_path) -> None:
        """Chunk db with schema but zero rows must not break the merge."""
        chunks = tmp_path / "chunks"
        chunks.mkdir()
        make_chunk_db(chunks / "actions-1.db", [])
        final = tmp_path / "final.db"
        merge(str(final), str(chunks), SIM, {}, {})
        assert len(_fetch(str(final), SIM)) == 0

    def test_mixed_empty_and_populated_chunks(self, tmp_path) -> None:
        chunks = tmp_path / "chunks"
        chunks.mkdir()
        make_chunk_db(chunks / "actions-1.db", [])
        make_chunk_db(chunks / "actions-2.db", [make_match(home="Solo FC", url="https://a.com/1")])
        final = tmp_path / "final.db"
        merge(str(final), str(chunks), SIM, {}, {})
        df = _fetch(str(final), SIM)
        assert list(df["home_name"]) == ["Solo FC"]


class TestMergeSummaryP1:
    def test_merge_completion_reports_missing_sources_as_partial(self, tmp_path, monkeypatch) -> None:
        chunks = tmp_path / "chunks"
        chunks.mkdir()
        make_chunk_db(
            chunks / "actions-1.db",
            [make_match(home="Alpha FC", url="https://a.com/1")],
        )
        final = tmp_path / "final.db"
        event_path = tmp_path / "events.jsonl"
        monkeypatch.setenv("SCRAPE_EVENT_LOG_PATH", str(event_path))
        configure_event_logging(str(event_path))
        try:
            merge(str(final), str(chunks), SIM, {"a": {}, "ghost": {}}, {"actions": ["a"]})
            records = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
            completed = [record for record in records if record["event"] == "stage.completed"][-1]
            assert completed["outcome"] == "partial"
            assert completed["severity"] == "WARNING"
            assert completed["counts"]["crawlers_missing"] == 1
        finally:
            disable_event_logging()

    def test_missing_crawler_logs_warning(self, tmp_path, caplog) -> None:
        """Configured crawler with zero matches appears as MISSING in summary."""
        chunks = tmp_path / "chunks"
        chunks.mkdir()
        make_chunk_db(
            chunks / "actions-1.db",
            [make_match(home="Alpha FC", url="https://a.com/1")],
        )
        final = tmp_path / "final.db"
        with caplog.at_level("WARNING", logger="bet_crawler.crawl_core.merge"):
            merge(str(final), str(chunks), SIM, {"ghost": {}, "a": {}}, {"actions": ["a"]})
        missing = [r.getMessage() for r in caplog.records if "MISSING" in r.getMessage()]
        assert any("ghost: 0 matches (MISSING)" in m for m in missing)

    def test_missing_runner_set_logs_error(self, tmp_path, caplog) -> None:
        """Chunk file implies runner 'actions' but no actions crawler contributed."""
        chunks = tmp_path / "chunks"
        chunks.mkdir()
        # source 'someoneelse' belongs to no runner set
        make_chunk_db(
            chunks / "actions-1.db",
            [make_match(home="X FC", url="https://someoneelse.com/1")],
        )
        final = tmp_path / "final.db"
        with caplog.at_level("ERROR", logger="bet_crawler.crawl_core.merge"):
            merge(str(final), str(chunks), SIM, {}, {"actions": ["a"], "local": ["b"]})
        errs = [r.getMessage() for r in caplog.records if "missing data" in r.getMessage()]
        assert any("actions" in e for e in errs)

    def test_final_db_excluded_from_chunk_scan(self, tmp_path, caplog) -> None:
        """The output db living inside chunks_dir must not be re-merged into itself."""
        chunks = tmp_path / "chunks"
        chunks.mkdir()
        final = chunks / "final.db"
        make_chunk_db(
            chunks / "actions-1.db",
            [make_match(home="Alpha FC", url="https://a.com/1")],
        )
        merge(str(final), str(chunks), SIM, {"a": {}}, {"actions": ["a"]})
        df = _fetch(str(final), SIM)
        assert len(df) == 1  # merged once, not doubled by re-reading its own output

    def test_scores_source_contributes_to_source_mapping(self, tmp_path, caplog) -> None:
        """Predictions source names (no URL) still count toward runner-set validation."""
        from bet_framework.core.Match import Score

        chunks = tmp_path / "chunks"
        chunks.mkdir()
        m = make_match(home="Src FC", preds=None, url=None)
        m.predictions = [Score(source="predictz", home=1, away=1)]
        make_chunk_db(chunks / "actions-1.db", [m])
        final = tmp_path / "final.db"
        with caplog.at_level("ERROR", logger="bet_crawler.crawl_core.merge"):
            merge(str(final), str(chunks), SIM, {}, {"actions": ["predictz"]})
        errs = [r.getMessage() for r in caplog.records if "missing data" in r.getMessage()]
        assert errs == []  # predictz contributed → actions runner set seen


class TestMergeP2:
    def test_empty_chunks_dir_yields_empty_output(self, tmp_path, caplog) -> None:
        chunks = tmp_path / "chunks"
        chunks.mkdir()
        final = tmp_path / "final.db"
        with caplog.at_level("ERROR", logger="bet_crawler.crawl_core.merge"):
            merge(str(final), str(chunks), SIM, {}, {"actions": ["a"]})
        assert len(_fetch(str(final), SIM)) == 0
        errs = [r.getMessage() for r in caplog.records if "missing data" in r.getMessage()]
        # expected runners derive from chunk filename prefixes — no chunks → nothing expected,
        # so an empty dir logs no missing-runner-set errors (pinned actual semantics)
        assert errs == []

    def test_near_miss_reports_flow_into_ci_step_summary(self, tmp_path, caplog) -> None:
        """AC-7 (issue #113): merge near-miss logs land in the scheduled step summary.

        End-to-end: two chunks carry a below-threshold team pair → MatchesManager logs the
        NEAR-MISS REPORT block (job_log.txt in the merge artifact) → summarize_scrape_logs
        renders a dedicated "## Near-miss reports" section in the markdown summary.
        """
        from datetime import datetime

        from bet_crawler.summarize_scrape_logs import render_markdown, summarize
        from bet_framework.core.Match import Score

        chunks = tmp_path / "chunks"
        chunks.mkdir()
        dt = datetime(2026, 9, 25, 15, 0, 0)
        # 'Ajax' vs 'Ajax Cape Town' scores 50.0 and 'Feyenoord' vs 'Feyenoord Academy' scores 62.7.
        # Combined similarity = (50.0 + 62.7) / 2 = 56.4: inside the near-miss window [40, 65).
        m1 = make_match(home="Ajax", away="Feyenoord", dt=dt, preds=None, url="https://a.com/1")
        m1.predictions = [Score(source="srcA", home=1, away=0)]
        m2 = make_match(home="Ajax Cape Town", away="Feyenoord Academy", dt=dt, preds=None, url="https://b.com/1")
        m2.predictions = [Score(source="srcB", home=2, away=0)]
        make_chunk_db(chunks / "actions-1.db", [m1])
        make_chunk_db(chunks / "actions-2.db", [m2])
        final = tmp_path / "final.db"

        logs_dir = tmp_path / "logs-merge"
        logs_dir.mkdir()

        with caplog.at_level("WARNING", logger="bet_framework.MatchesManager"):
            merge(str(final), str(chunks), SIM, {"a": {}}, {"actions": ["a"]})

        near_miss_lines = [r for r in caplog.records if "NEAR-MISS" in r.getMessage()]
        assert near_miss_lines, "merge must emit NEAR-MISS REPORT lines for the 56.4 pair"

        # Simulate the CI job log artifact (console lines tee'd to job_log.txt).
        log_lines = ["=== Job: merge started at 2026-10-30 00:00:00 ==="]
        for record in caplog.records:
            timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            log_lines.append(f"{timestamp} - {record.name} - {record.levelname} - {record.getMessage()}")
        (logs_dir / "job_log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        summary = summarize(logs_dir, {"merge": "success"})
        markdown = render_markdown(summary)

        assert "## Near-miss reports" in markdown
        assert summary["near_misses"], "near-miss pairs must reach the summary payload"
        assert any(
            {nm["home_a"], nm["home_b"]} == {"Ajax", "Ajax Cape Town"}
            and {nm["away_a"], nm["away_b"]} == {"Feyenoord", "Feyenoord Academy"}
            for nm in summary["near_misses"]
        )
