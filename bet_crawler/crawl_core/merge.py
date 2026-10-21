"""
merge module for handling the merge mode logic
"""

import os
from collections import defaultdict
from urllib.parse import urlparse

import pandas as pd

from bet_crawler.crawler_logging import (
    get_event_totals,
    get_logger,
    log_event,
    reset_event_totals,
)

logger = get_logger(__name__)


def merge(
    db_path: str,
    chunks_dir: str,
    similarity_config: dict | None,
    crawler_keys: dict,
    runner_sets: dict[str, list[str]],
) -> None:
    """Merge multiple chunk databases into a single database and generate summary."""
    reset_event_totals(stage="merge")
    if not os.path.isdir(chunks_dir):
        log_event(
            logger,
            event="stage.failed",
            outcome="error",
            reason_code="chunk_directory_missing",
            level=40,
            message=f"Not a valid chunks directory: {chunks_dir}",
            stage="merge",
            url=chunks_dir,
        )
        raise SystemExit(1)

    try:
        matches_df = _perform_merge(db_path, chunks_dir, similarity_config)
        _generate_merge_summary(
            matches_df, chunks_dir, db_path, crawler_keys, runner_sets
        )
    except Exception as exc:
        logger.exception(
            "Merge stage failed for chunks directory %s",
            chunks_dir,
            extra={
                "event": "stage.failed",
                "outcome": "error",
                "reason_code": "merge_operation_failed",
                "stage": "merge",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise


def _perform_merge(
    db_path: str, chunks_dir: str, similarity_config: dict | None
) -> pd.DataFrame:
    """Perform the database merge operation. Returns the merged DataFrame."""
    from bet_framework.MatchesManager import MatchesManager

    matches_manager = MatchesManager(db_path, similarity_config=similarity_config)
    matches_manager.reset_matches_db()
    matches_manager.merge_databases(chunks_dir)
    matches_df = matches_manager.fetch_matches()
    matches_manager.close()
    return matches_df


def _generate_merge_summary(
    matches_df: pd.DataFrame,
    chunks_dir: str,
    db_path: str,
    crawler_keys: dict,
    runner_sets: dict[str, list[str]],
) -> None:
    """Generate and log a summary of the merge operation."""

    source_to_matches = _build_source_mapping(matches_df)
    matches_count = len(matches_df)
    chunk_files = [
        f
        for f in os.listdir(chunks_dir)
        if f.endswith(".db") and f != os.path.basename(db_path)
    ]

    _log_summary_header(matches_count, len(chunk_files))
    _log_source_details(source_to_matches)
    missing_crawlers = _log_missing_crawlers(source_to_matches, crawler_keys)
    missing_runner_sets = _validate_runner_sets(
        source_to_matches, chunk_files, runner_sets
    )
    _log_footer(db_path)
    event_totals = get_event_totals(stage="merge")
    has_missing_data = bool(
        missing_crawlers
        or missing_runner_sets
        or event_totals["warnings"]
        or event_totals["errors"]
    )
    log_event(
        logger,
        event="stage.completed",
        outcome="partial" if has_missing_data else "success",
        reason_code=(
            "runner_set_missing_data"
            if missing_runner_sets
            else "crawler_sources_missing"
            if missing_crawlers
            else None
        ),
        level=40
        if missing_runner_sets or event_totals["errors"]
        else 30
        if has_missing_data
        else 20,
        message="Merge stage completed",
        stage="merge",
        counts={
            "matches": matches_count,
            "chunks": len(chunk_files),
            "sources": len(source_to_matches),
            "crawlers_missing": len(missing_crawlers),
            "runner_sets_missing": len(missing_runner_sets),
            **event_totals,
        },
    )


def _build_source_mapping(matches_df: pd.DataFrame) -> dict[str, set]:
    """Build mapping of source names to match indices."""
    source_to_matches = defaultdict(set)

    for i, row in matches_df.iterrows():
        url = row.get("result_url")
        scores_list = row.get("scores")

        # Infer from URL
        if isinstance(url, str) and url.strip():
            try:
                domain = urlparse(url).netloc
            except Exception as exc:
                log_event(
                    logger,
                    event="merge.source_mapping.warning",
                    outcome="warning",
                    reason_code="result_url_parse_failed",
                    level=30,
                    message=f"Could not infer match source from result URL {url!r}: {exc}",
                    url=url,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                domain = ""
            if domain:
                core_name = domain.split(".")[-2] if "." in domain else domain
                source_to_matches[core_name.lower()].add(i)

        # Extract from predictions list
        if isinstance(scores_list, (list, tuple)):
            for p in scores_list:
                if not isinstance(p, dict):
                    continue
                src = p.get("source")
                if src:
                    source_to_matches[src.lower()].add(i)

    return source_to_matches


def _log_summary_header(matches_count: int, chunk_count: int) -> None:
    """Log the summary header section."""
    logger.info("  " + "=" * 26)
    logger.info("  " + "MERGE SUMMARY".center(26))
    logger.info("  " + "=" * 26)
    logger.info(f"  Unique Matches: {matches_count}")
    logger.info(f"  Chunks scanned: {chunk_count}")


def _log_source_details(source_to_matches: dict[str, set]) -> None:
    """Log detailed source statistics."""
    sorted_sources = sorted(
        [(s, len(ms)) for s, ms in source_to_matches.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    for k, v in sorted_sources:
        logger.info(f"    - {k}: {v} matches")


def _log_missing_crawlers(
    source_to_matches: dict[str, set], crawler_keys: dict
) -> set[str]:
    """Identify configured crawlers that did not contribute matches."""
    missing_crawlers = set()
    for crawler in sorted(crawler_keys.keys()):
        if crawler not in source_to_matches:
            missing_crawlers.add(crawler)
            logger.warning(f"    - {crawler}: 0 matches (MISSING)")
    return missing_crawlers


def _validate_runner_sets(
    source_to_matches: dict[str, set],
    chunk_files: list[str],
    runner_sets: dict[str, list[str]],
) -> set[str]:
    """Validate that all expected runner sets contributed data."""
    seen_runners = set()
    for source in source_to_matches:
        for runner_name, crawlers in runner_sets.items():
            if source in crawlers:
                seen_runners.add(runner_name)

    expected_runners = set()
    for cf in chunk_files:
        runner_name = cf.split("-")[0]
        if runner_name in runner_sets:
            expected_runners.add(runner_name)

    missing_runner_sets = expected_runners - seen_runners
    if missing_runner_sets:
        logger.error(f"  ❌ Full runner sets missing data: {missing_runner_sets}")
    return missing_runner_sets


def _log_footer(db_path: str) -> None:
    """Log the footer with output path."""
    logger.info("  " + "=" * 26)
    logger.info(f"✅ Merged into: {db_path}")
