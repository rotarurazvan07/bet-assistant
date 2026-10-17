"""Tests for the CI scraping-run log summary."""

import json
from pathlib import Path

from bet_crawler.summarize_scrape_logs import render_markdown, summarize


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")


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
    (artifact / "crawler-events.jsonl").write_text('{"severity":"ERROR"\n', encoding="utf-8")
    summary = summarize(artifact, {"prepare-local": "failure", "scrape-local": "skipped"})

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


def test_legacy_crawler_logs_are_kept_when_that_job_has_no_jsonl_sidecar(tmp_path) -> None:
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
