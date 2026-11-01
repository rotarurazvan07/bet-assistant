"""Structured crawler logging alongside scrape-kit console output.

Set ``SCRAPE_EVENT_LOG_PATH`` to write one versioned JSON event per line.
The JSONL stream is intentionally separate from stdout, which is reserved for
prepare-scrape's task-matrix JSON contract.
"""

import contextvars
import json
import logging
import os
import re
import sys
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scrape_kit import get_logger as _get_logger

SCHEMA_VERSION = 1
_LOCAL_RUN_ID = os.environ.get("SCRAPE_RUN_ID") or os.environ.get("GITHUB_RUN_ID") or str(uuid.uuid4())
_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("crawler_log_context", default=None)
_HANDLER_LOCK = threading.Lock()
_EVENT_HANDLERS: dict[str, logging.Handler] = {}
_EVENT_COUNTS: dict[tuple[str, str, str], dict[str, int]] = {}


class ExceptionContextFilter(logging.Filter):
    """Retain traceback/type when legacy error logs are emitted inside except blocks."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR and record.exc_info is None:
            exc = sys.exc_info()
            if exc[0] is not None:
                record.exc_info = exc
                record.error_type = exc[0].__name__
                record.error_message = str(exc[1])
        return True


class JsonEventFormatter(logging.Formatter):
    """Serialize each crawler log record as a single JSONL event."""

    def format(self, record: logging.LogRecord) -> str:
        context = _CONTEXT.get() or {}
        message = record.getMessage()
        inferred_finder, inferred_source_key = _infer_finder(record.name)
        event = getattr(record, "event", None)
        if event is None:
            event = _default_event(record.levelno)
        outcome = getattr(record, "outcome", None) or _default_outcome(record.levelno)
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": (
                datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            ),
            "severity": record.levelname,
            "event": event,
            "outcome": outcome,
            "reason_code": getattr(record, "reason_code", None)
            or (
                "unclassified_error"
                if record.levelno >= logging.ERROR
                else "unclassified_warning"
                if record.levelno >= logging.WARNING
                else None
            ),
            "logger": record.name,
            "message": message,
            "run_id": context.get("run_id", _LOCAL_RUN_ID),
            "run_attempt": context.get("run_attempt", os.environ.get("GITHUB_RUN_ATTEMPT")),
            "job": context.get("job", os.environ.get("GITHUB_JOB")),
            "runner": getattr(record, "runner", context.get("runner", os.environ.get("RUNNER_NAME"))),
            "stage": getattr(record, "stage", context.get("stage")),
            "chunk_id": getattr(record, "chunk_id", context.get("chunk_id")),
            "source_key": getattr(record, "source_key", context.get("source_key", inferred_source_key)),
            "finder": getattr(record, "finder", context.get("finder", inferred_finder)),
            "url": getattr(record, "url", context.get("url")),
            "match_id": getattr(record, "match_id", context.get("match_id")),
        }
        count_key = (
            str(payload["run_id"]),
            str(payload["stage"] or "unknown"),
            str(payload["chunk_id"] or ""),
        )
        with _HANDLER_LOCK:
            totals = _EVENT_COUNTS.setdefault(
                count_key,
                {"warnings": 0, "errors": 0, "matches_added": 0, "matches_skipped": 0},
            )
            if record.levelno >= logging.ERROR:
                totals["errors"] += 1
            elif record.levelno >= logging.WARNING:
                totals["warnings"] += 1
            if event == "match.added" and payload["logger"] == "bet_crawler.finders.BaseMatchFinder":
                totals["matches_added"] += 1
            elif (
                event in ("match.skipped", "match.parse.failed") and payload["logger"] == "bet_crawler.finders.BaseMatchFinder"
            ):
                totals["matches_skipped"] += 1
        for key in (
            "attempt",
            "max_attempts",
            "error_type",
            "error_message",
            "duration_ms",
            "counts",
            "worker",
            "candidate",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if "candidate" not in payload and hasattr(record, "candidate"):
            payload["candidate"] = record.candidate
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, default=str)


def _infer_finder(logger_name: str) -> tuple[str | None, str | None]:
    """Infer finder class and source key from a finder module logger name.

    Args:
        logger_name: The logger name to parse (e.g., "bet_crawler.finders.PredictzFinder").

    Returns:
        Tuple of (source_key, snake_case_finder_name) or (None, None) if not a finder logger.
    """
    source = logger_name.removeprefix("bet_crawler.finders.").split(".", maxsplit=1)[0]
    if source == logger_name:
        return None, None
    name = re.sub(r"_per_(league|match)$", "", source)
    name = re.sub(r"Finder$", "", name)
    snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return source, re.sub(r"[^a-z0-9_]", "", snake_name)


def _default_event(level: int) -> str:
    """Map legacy log levels to broad machine-readable event names.

    Args:
        level: The logging level integer.

    Returns:
        Event name string for the given level.
    """
    if level >= logging.ERROR:
        return "application.error"
    if level >= logging.WARNING:
        return "application.warning"
    return "log_message"


def _default_outcome(level: int) -> str:
    """Map legacy log levels to default event outcomes.

    Args:
        level: The logging level integer.

    Returns:
        Outcome string for the given level.
    """
    if level >= logging.ERROR:
        return "error"
    if level >= logging.WARNING:
        return "warning"
    return "info"


def _json_handler(path: str) -> logging.Handler:
    """Get or create a JSONL file handler for the given path.

    Args:
        path: Path to the JSONL event log file.

    Returns:
        Configured logging.Handler for JSONL output.
    """
    resolved = str(Path(path).expanduser().resolve())
    with _HANDLER_LOCK:
        handler = _EVENT_HANDLERS.get(resolved)
        if handler is None:
            Path(resolved).parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(resolved, encoding="utf-8")
            handler.setFormatter(JsonEventFormatter())
            _EVENT_HANDLERS[resolved] = handler
        return handler


def get_logger(name: str) -> logging.Logger:
    """Return the familiar scrape-kit logger, with optional JSONL event output.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured logger instance.
    """
    return _configure_logger(_get_logger(name))


def _configure_logger(logger: logging.Logger) -> logging.Logger:
    """Add crawler-specific filters and the currently selected JSONL handler.

    Args:
        logger: The logger instance to configure.

    Returns:
        The configured logger instance.
    """
    if not any(isinstance(item, ExceptionContextFilter) for item in logger.filters):
        logger.addFilter(ExceptionContextFilter())
    event_path = os.environ.get("SCRAPE_EVENT_LOG_PATH")
    if event_path:
        handler = _json_handler(event_path)
        if handler not in logger.handlers:
            logger.addHandler(handler)
    return logger


def configure_event_logging(path: str | None = None) -> None:
    """Attach the JSONL sidecar to already-created crawler loggers.

    Primarily useful for embedding the crawler or testing; command-line runs
    should set SCRAPE_EVENT_LOG_PATH before importing the crawler modules.
    """
    if path is not None:
        os.environ["SCRAPE_EVENT_LOG_PATH"] = path
    event_path = os.environ.get("SCRAPE_EVENT_LOG_PATH")
    if not event_path:
        return
    handler = _json_handler(event_path)
    for name, candidate in logging.Logger.manager.loggerDict.items():
        if name.startswith("bet_crawler.") and isinstance(candidate, logging.Logger):
            for existing in tuple(candidate.handlers):
                if isinstance(existing.formatter, JsonEventFormatter) and existing is not handler:
                    candidate.removeHandler(existing)
            _configure_logger(candidate)


def disable_event_logging() -> None:
    """Detach and close JSONL handlers (mainly for isolated tests).

    Removes JsonEventFormatter handlers from all bet_crawler loggers
    and closes the underlying file handles.
    """
    for name, candidate in logging.Logger.manager.loggerDict.items():
        if name.startswith("bet_crawler.") and isinstance(candidate, logging.Logger):
            for handler in tuple(candidate.handlers):
                if isinstance(handler.formatter, JsonEventFormatter):
                    candidate.removeHandler(handler)
    with _HANDLER_LOCK:
        for handler in tuple(_EVENT_HANDLERS.values()):
            handler.flush()
            handler.close()
        _EVENT_HANDLERS.clear()
    os.environ.pop("SCRAPE_EVENT_LOG_PATH", None)


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    """Attach run/stage/source identifiers to logs in this execution context."""
    merged = {
        **(_CONTEXT.get() or {}),
        **{key: value for key, value in fields.items() if value is not None},
    }
    token = _CONTEXT.set(merged)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def set_log_context(**fields: Any) -> None:
    """Set process-level context for a CLI invocation or long-lived task."""
    _CONTEXT.set(
        {
            **(_CONTEXT.get() or {}),
            **{key: value for key, value in fields.items() if value is not None},
        }
    )


def get_event_totals(*, stage: str, chunk_id: str | None = None) -> dict[str, int]:
    """Return warning/error totals emitted so far for this process stage/chunk."""
    run_id = _CONTEXT.get()
    run_id = (run_id or {}).get("run_id", _LOCAL_RUN_ID)
    target_chunk = str(chunk_id or "")
    result = {"warnings": 0, "errors": 0, "matches_added": 0, "matches_skipped": 0}
    with _HANDLER_LOCK:
        for (event_run, event_stage, event_chunk), counts in _EVENT_COUNTS.items():
            if event_run == str(run_id) and event_stage == stage and (chunk_id is None or event_chunk == target_chunk):
                result["warnings"] += counts["warnings"]
                result["errors"] += counts["errors"]
                result["matches_added"] += counts["matches_added"]
                result["matches_skipped"] += counts["matches_skipped"]
    return result


def reset_event_totals(*, stage: str, chunk_id: str | None = None) -> None:
    """Start fresh counters for a stage invocation in the current run."""
    context = _CONTEXT.get() or {}
    run_id = str(context.get("run_id", _LOCAL_RUN_ID))
    target_chunk = str(chunk_id or "")
    with _HANDLER_LOCK:
        for key in tuple(_EVENT_COUNTS):
            event_run, event_stage, event_chunk = key
            if event_run == run_id and event_stage == stage and (chunk_id is None or event_chunk == target_chunk):
                del _EVENT_COUNTS[key]


def log_event(
    logger: logging.Logger,
    *,
    event: str,
    outcome: str,
    reason_code: str | None = None,
    level: int = logging.INFO,
    message: str,
    **fields: Any,
) -> None:
    """Emit an explicitly classified event while retaining the console message."""
    logger.log(
        level,
        message,
        extra={
            "event": event,
            "outcome": outcome,
            "reason_code": reason_code,
            **fields,
        },
    )


def exception_event(
    logger: logging.Logger,
    *,
    event: str,
    reason_code: str,
    message: str,
    **fields: Any,
) -> None:
    """Emit an ERROR event with exception type and traceback attached."""
    exc = sys.exc_info()[1]
    logger.error(
        message,
        exc_info=True,
        extra={
            "event": event,
            "outcome": "error",
            "reason_code": reason_code,
            "error_type": type(exc).__name__ if exc else None,
            "error_message": str(exc) if exc else message,
            **fields,
        },
    )


def source_key_for(crawler: Any, factory: Any = None) -> str:
    """Return the configured crawler key where available, otherwise a stable class key."""
    configured_key = getattr(crawler, "_log_source_key", None)
    if configured_key:
        return configured_key
    class_name = crawler.__class__.__name__
    crawler_keys = getattr(factory, "crawler_keys", {})
    for key, config in crawler_keys.items():
        if config.get("class") == class_name:
            return key
    name = re.sub(r"_per_(league|match)$", "", class_name)
    name = re.sub(r"Finder$", "", name)
    aliases = {
        "eagle_predict": "eaglepredict",
        "football_betting_tips": "footballbettingtips",
        "football_predictions": "footballpredictions",
        "score_predictor": "scorepredictor",
        "one_million_predictions": "onemillionpredictions",
        "win_draw_win": "windrawwin",
        "x_g_score": "xgscore",
    }
    source_key = re.sub(r"[^a-z0-9_]", "", re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())
    return aliases.get(source_key, source_key)
