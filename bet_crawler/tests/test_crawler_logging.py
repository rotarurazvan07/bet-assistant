"""Tests for structured crawler event logging."""

import json
import logging

from bet_crawler.crawler_logging import (
    configure_event_logging,
    disable_event_logging,
    get_failed_sources,
    get_logger,
    log_context,
    log_event,
    reset_event_totals,
)


def test_jsonl_event_schema_context_and_exception_details(tmp_path, monkeypatch) -> None:
    event_path = tmp_path / "crawler-events.jsonl"
    monkeypatch.setenv("SCRAPE_EVENT_LOG_PATH", str(event_path))
    configure_event_logging(str(event_path))
    logger = get_logger("bet_crawler.tests.structured_logging")

    try:
        with log_context(
            stage="scrape",
            runner="actions",
            source_key="sample",
            chunk_id="actions-1.db",
        ):
            log_event(
                logger,
                event="match.skipped",
                outcome="warning",
                reason_code="invalid_score",
                level=logging.WARNING,
                message="Match candidate skipped",
                url="https://example.test/match/1",
            )
            try:
                raise ValueError("bad score payload")
            except ValueError:
                logger.exception(
                    "Match parse failed",
                    extra={
                        "event": "match.parse.failed",
                        "outcome": "error",
                        "reason_code": "parse_error",
                    },
                )

        records = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
        assert len(records) == 2
        warning, error = records
        assert warning["schema_version"] == 1
        assert warning["severity"] == "WARNING"
        assert warning["event"] == "match.skipped"
        assert warning["outcome"] == "warning"
        assert warning["reason_code"] == "invalid_score"
        assert warning["stage"] == "scrape"
        assert warning["runner"] == "actions"
        assert warning["source_key"] == "sample"
        assert warning["chunk_id"] == "actions-1.db"
        assert warning["url"] == "https://example.test/match/1"
        assert error["severity"] == "ERROR"
        assert error["error_type"] == "ValueError"
        assert "bad score payload" in error["exception"]
        assert error["event"] == "match.parse.failed"
        assert error["source_key"] == "sample"
        assert error["chunk_id"] == "actions-1.db"
        assert error["severity"] == "ERROR"
        assert "bad score payload" in error["exception"]
    finally:
        disable_event_logging()


def test_get_failed_sources_tracks_error_level_source_events(tmp_path, monkeypatch) -> None:
    """Error-level source.* events register their source_key for the stage/chunk."""
    event_path = tmp_path / "failed-sources.jsonl"
    monkeypatch.setenv("SCRAPE_EVENT_LOG_PATH", str(event_path))
    configure_event_logging(str(event_path))
    logger = get_logger("bet_crawler.tests.failed_sources")

    try:
        with log_context(stage="scrape", chunk_id="local-1.db", source_key="windrawwin"):
            reset_event_totals(stage="scrape", chunk_id="local-1.db")
            log_event(
                logger,
                event="source.fetch.retry",
                outcome="error",
                reason_code="fetch_retry_failed",
                level=logging.ERROR,
                message="still blocked",
                source_key="windrawwin",
            )
            log_event(
                logger,
                event="match.skipped",
                outcome="warning",
                level=logging.WARNING,
                message="benign skip",
                source_key="windrawwin",
            )
        assert get_failed_sources(stage="scrape", chunk_id="local-1.db") == {"windrawwin"}
        assert get_failed_sources(stage="scrape") == {"windrawwin"}
        assert get_failed_sources(stage="merge") == set()
        reset_event_totals(stage="scrape", chunk_id="local-1.db")
        assert get_failed_sources(stage="scrape", chunk_id="local-1.db") == set()
    finally:
        disable_event_logging()


def test_legacy_warning_and_error_get_fallback_classification(tmp_path, monkeypatch) -> None:
    event_path = tmp_path / "legacy-events.jsonl"
    monkeypatch.setenv("SCRAPE_EVENT_LOG_PATH", str(event_path))
    configure_event_logging(str(event_path))
    logger = get_logger("bet_crawler.tests.legacy_logging")

    try:
        logger.warning("Existing warning call")
        try:
            raise RuntimeError("network timed out")
        except RuntimeError:
            logger.error("Existing caught-error call")

        records = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
        assert records[0]["event"] == "application.warning"
        assert records[0]["reason_code"] == "unclassified_warning"
        assert records[1]["event"] == "application.error"
        assert records[1]["reason_code"] == "unclassified_error"
        assert records[1]["error_type"] == "RuntimeError"
        assert "network timed out" in records[1]["exception"]
    finally:
        disable_event_logging()
