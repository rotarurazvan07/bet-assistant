"""Tests for structured crawler event logging."""

import json
import logging

from bet_crawler.crawler_logging import (
    configure_event_logging,
    disable_event_logging,
    get_logger,
    log_context,
    log_event,
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
