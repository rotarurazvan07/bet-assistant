"""Tests for the CI scraping-run log summary."""

import json
from pathlib import Path

from bet_crawler.summarize_scrape_logs import render_markdown, summarize


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(item) + "\n" for item in records), encoding="utf-8"
    )


def test_summary_groups_actionable_events_and_keeps_benign_info_out(tmp_path) -> None:
    artifacts = tmp_path / "logs-scrape-actions"
    artifacts.mkdir()
    _write_jsonl(
        artifacts / "crawler-events.jsonl",
        [
            {
                "severity": "INFO",
                "event": "match.skipped",
                "outcome": "info",
                "reason_code": "team_pattern_excluded",
                "source_key": "predictz",
                "message": "Youth team filtered",
            },
            {
                "severity": "WARNING",
                "event": "match.skipped",
                "outcome": "warning",
                "reason_code": "score_invalid",
                "source_key": "predictz",
                "url": "https://example.test/match",
                "message": "Invalid score data",
            },
            {
                "severity": "ERROR",
                "event": "source.scrape.failed",
                "outcome": "error",
                "reason_code": "fetch_failed",
                "source_key": "eaglepredict",
                "error_type": "TimeoutError",
                "message": "Source exhausted retries",
            },
            {
                "severity": "ERROR",
                "event": "stage.completed",
                "outcome": "partial",
                "stage": "scrape",
                "counts": {"errors": 1},
                "message": "Aggregate stage status, not a separate issue",
            },
        ],
    )
    summary = summarize(artifacts, {"scrape-actions": "success"})

    assert summary["issue_count"] == 2
    assert summary["severity_counts"] == {"WARNING": 1, "ERROR": 1}
    assert {(group["source"], group["reason_code"]) for group in summary["groups"]} == {
        ("predictz", "score_invalid"),
        ("eaglepredict", "fetch_failed"),
    }
    assert len(summary["stage_events"]) == 1
    markdown = render_markdown(summary)
    assert "2 total" in markdown
    assert "Youth team filtered" not in markdown
    assert "https://example.test/match" in markdown


def test_pipeline_health_aggregates_stage_results_and_omits_source_completions(
    tmp_path,
) -> None:
    artifacts = tmp_path / "logs-scrape-actions-actions-1.db"
    artifacts.mkdir()
    _write_jsonl(
        artifacts / "crawler-events.jsonl",
        [
            {
                "severity": "INFO",
                "event": "source.scrape.completed",
                "outcome": "success",
                "source_key": "predictz",
            },
            {
                "severity": "WARNING",
                "event": "stage.completed",
                "outcome": "partial",
                "reason_code": "source_scrape_warnings",
                "stage": "scrape",
                "counts": {
                    "groups_completed": 3,
                    "groups_total": 3,
                    "matches_added": 20,
                    "matches_skipped": 4,
                    "warnings": 2,
                },
            },
            {
                "severity": "INFO",
                "event": "stage.completed",
                "outcome": "success",
                "stage": "scrape",
                "counts": {
                    "groups_completed": 2,
                    "groups_total": 2,
                    "matches_added": 10,
                    "matches_skipped": 1,
                },
            },
        ],
    )

    summary = summarize(tmp_path)
    markdown = render_markdown(summary)

    assert len(summary["stage_events"]) == 2
    assert "## Pipeline health" in markdown
    assert "`scrape-actions`" in markdown
    assert "5/5 groups" in markdown
    assert "30 added, 5 skipped" in markdown
    assert "2 warnings" in markdown
    assert "## Incomplete or degraded work" in markdown
    assert "`source_scrape_warnings` (1)" in markdown
    assert "source.scrape.completed" not in markdown
    assert "## Stage outcomes" not in markdown


def test_summary_reads_legacy_non_crawler_errors_without_double_counting(
    tmp_path,
) -> None:
    artifact = tmp_path / "logs-prepare-actions"
    artifact.mkdir()
    _write_jsonl(
        artifact / "crawler-events.jsonl",
        [
            {
                "severity": "ERROR",
                "event": "source.discovery.failed",
                "outcome": "error",
                "reason_code": "discovery_failed",
                "logger": "bet_crawler.crawl_core.prepare_scrape",
                "message": "Discovery exhausted retries",
            }
        ],
    )
    (artifact / "job_log.txt").write_text(
        "2026-10-17 10:00:00 - bet_crawler.crawl_core.prepare_scrape -    ERROR - Discovery exhausted retries\n"
        "2026-10-17 10:00:01 - scrape_kit.fetcher - WARNING - Retrying request\n",
        encoding="utf-8",
    )
    summary = summarize(artifact)

    assert summary["issue_count"] == 2
    assert summary["severity_counts"] == {"ERROR": 1, "WARNING": 1}
    assert any(group["source"] == "scrape_kit.fetcher" for group in summary["groups"])


def test_malformed_jsonl_and_failed_ci_job_are_reported(tmp_path) -> None:
    artifact = tmp_path / "logs-prepare-local"
    artifact.mkdir()
    (artifact / "crawler-events.jsonl").write_text(
        '{"severity":"ERROR"\n', encoding="utf-8"
    )
    summary = summarize(
        artifact, {"prepare-local": "failure", "scrape-local": "skipped"}
    )

    assert summary["issue_count"] == 1
    assert summary["malformed_event_lines"]
    assert summary["failed_jobs"] == {"prepare-local": "failure"}
    markdown = render_markdown(summary)
    assert "malformed_jsonl_event" in json.dumps(summary)
    assert "prepare-local" in markdown
    assert "failure" in markdown


def test_warnings_are_not_reinterpreted_as_failures(tmp_path) -> None:
    artifact = tmp_path / "logs-scrape-actions"
    artifact.mkdir()
    _write_jsonl(
        artifact / "crawler-events.jsonl",
        [
            {
                "severity": "WARNING",
                "event": "source.discovery.retry",
                "outcome": "warning",
                "reason_code": "fetch_retry",
                "source_key": "predictz",
                "message": "Recovered after retry",
            }
        ],
    )
    summary = summarize(artifact, {"scrape-actions": "success"})

    assert summary["issue_count"] == 1
    assert summary["severity_counts"] == {"WARNING": 1}
    assert summary["failed_jobs"] == {}


def test_empty_artifact_directory_still_summarizes_job_conclusions(tmp_path) -> None:
    summary = summarize(tmp_path / "missing", {"merge": "skipped"})
    markdown = render_markdown(summary)

    assert summary["issue_count"] == 0
    assert "merge" in markdown
    assert "skipped" in markdown
    assert "No warning/error log events" in markdown


def test_legacy_crawler_logs_are_kept_when_that_job_has_no_jsonl_sidecar(
    tmp_path,
) -> None:
    artifact = tmp_path / "logs-prepare-actions"
    artifact.mkdir()
    (artifact / "job_log.txt").write_text(
        "2026-10-17 10:00:00 - bet_crawler.crawl_core.prepare_scrape -    ERROR - Python import failed\n",
        encoding="utf-8",
    )
    summary = summarize(tmp_path)

    assert summary["issue_count"] == 1
    assert summary["groups"][0]["reason_code"] == "legacy_error"
    assert "Python import failed" in summary["groups"][0]["samples"][0]["message"]


# -- Near-miss reports in the CI step summary -------------------------------------------------


def _write_near_miss_legacy_log(artifact: Path) -> None:
    """Write a job_log.txt containing a realistic NEAR-MISS REPORT block."""
    (artifact / "job_log.txt").write_text(
        "=== Job: merge started at 2026-10-29 10:00:00 ===\n"
        "2026-10-29 10:00:01 - bet_framework.MatchesManager - WARNING - === NEAR-MISS REPORT: 2 pairs (score 40-65) ===\n"
        "2026-10-29 10:00:01 - bet_framework.MatchesManager - WARNING -   [62] Arsenal vs Chelsea <-> Arsenal FC vs Chelsea FC\n"
        "2026-10-29 10:00:01 - bet_framework.MatchesManager - WARNING -   [45] Real Madrid vs Barcelona <-> Real Madrid CF vs FC Barcelona\n"
        "2026-10-29 10:00:01 - bet_framework.MatchesManager - WARNING - === END NEAR-MISS REPORT ===\n"
        "2026-10-29 10:00:02 - scrape_kit.fetcher - WARNING - Retrying request\n",
        encoding="utf-8",
    )


def test_near_misses_extracted_from_legacy_merge_log(tmp_path) -> None:
    artifact = tmp_path / "logs-merge"
    artifact.mkdir()
    _write_near_miss_legacy_log(artifact)

    summary = summarize(artifact, {"merge": "success"})

    assert summary["schema_version"] == 2
    assert len(summary["near_misses"]) == 2
    first = summary["near_misses"][0]
    assert first["score"] == 62.0
    assert first["home_a"] == "Arsenal"
    assert first["away_a"] == "Chelsea"
    assert first["home_b"] == "Arsenal FC"
    assert first["away_b"] == "Chelsea FC"
    # Near-miss lines must not inflate issue/severity counts
    assert summary["issue_count"] == 1  # only the scrape_kit.fetcher warning remains
    assert summary["severity_counts"] == {"WARNING": 1}


def test_near_misses_extracted_from_jsonl_events_when_present(tmp_path) -> None:
    artifact = tmp_path / "logs-merge"
    artifact.mkdir()
    _write_jsonl(
        artifact / "crawler-events.jsonl",
        [
            {
                "severity": "WARNING",
                "event": "application.warning",
                "outcome": "warning",
                "reason_code": "unclassified_warning",
                "logger": "bet_framework.MatchesManager",
                "message": "=== NEAR-MISS REPORT: 1 pairs (score 40-65) ===",
            },
            {
                "severity": "WARNING",
                "event": "application.warning",
                "outcome": "warning",
                "reason_code": "unclassified_warning",
                "logger": "bet_framework.MatchesManager",
                "message": "  [58] Liverpool vs Everton <-> Liverpool FC vs Everton FC",
            },
            {
                "severity": "WARNING",
                "event": "application.warning",
                "outcome": "warning",
                "reason_code": "unclassified_warning",
                "logger": "bet_framework.MatchesManager",
                "message": "=== END NEAR-MISS REPORT ===",
            },
        ],
    )

    summary = summarize(artifact, {"merge": "success"})

    assert len(summary["near_misses"]) == 1
    assert summary["near_misses"][0]["score"] == 58.0
    assert summary["near_misses"][0]["home_a"] == "Liverpool"
    assert summary["near_misses"][0]["away_b"] == "Everton FC"
    assert summary["issue_count"] == 0  # near-miss events excluded from issues


def test_render_markdown_includes_near_miss_section(tmp_path) -> None:
    artifact = tmp_path / "logs-merge"
    artifact.mkdir()
    _write_near_miss_legacy_log(artifact)

    summary = summarize(artifact, {"merge": "success"})
    markdown = render_markdown(summary)

    assert "## Near-miss reports" in markdown
    assert "| Score | Match A | Match B |" in markdown
    assert "62" in markdown
    assert "Arsenal vs Chelsea" in markdown
    assert "Arsenal FC vs Chelsea FC" in markdown
    # Section must come after the problems table area (or before pipeline health)
    problems_idx = markdown.find("## Problems by source and reason")
    near_idx = markdown.find("## Near-miss reports")
    health_idx = markdown.find("## Pipeline health")
    assert near_idx > -1
    if problems_idx > -1:
        assert near_idx > problems_idx
    if health_idx > -1:
        assert near_idx < health_idx


def test_render_markdown_omits_near_miss_section_when_empty(tmp_path) -> None:
    artifact = tmp_path / "logs-merge"
    artifact.mkdir()
    (artifact / "job_log.txt").write_text(
        "=== Job: merge started ===\nall good\n", encoding="utf-8"
    )

    summary = summarize(artifact, {"merge": "success"})
    markdown = render_markdown(summary)

    assert summary["near_misses"] == []
    assert "## Near-miss reports" not in markdown


def test_json_output_includes_near_misses_array(tmp_path) -> None:
    artifact = tmp_path / "logs-merge"
    artifact.mkdir()
    _write_near_miss_legacy_log(artifact)

    summary = summarize(artifact, {"merge": "success"})
    payload = json.dumps(summary)

    assert '"schema_version": 2' in payload
    assert '"near_misses"' in payload
    parsed = json.loads(payload)
    assert parsed["schema_version"] == 2
    assert isinstance(parsed["near_misses"], list)
    assert len(parsed["near_misses"]) == 2
    assert set(parsed["near_misses"][0].keys()) >= {
        "score",
        "home_a",
        "away_a",
        "home_b",
        "away_b",
    }


def test_near_miss_block_without_pairs_yields_empty_list(tmp_path) -> None:
    artifact = tmp_path / "logs-merge"
    artifact.mkdir()
    (artifact / "job_log.txt").write_text(
        "2026-10-29 10:00:01 - bet_framework.MatchesManager - WARNING - === NEAR-MISS REPORT: 0 pairs (score 40-65) ===\n"
        "2026-10-29 10:00:01 - bet_framework.MatchesManager - WARNING - === END NEAR-MISS REPORT ===\n",
        encoding="utf-8",
    )

    summary = summarize(artifact)
    assert summary["near_misses"] == []
    assert "## Near-miss reports" not in render_markdown(summary)
