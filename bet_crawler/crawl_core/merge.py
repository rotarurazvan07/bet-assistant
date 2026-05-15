"""
merge module for handling the merge mode logic
"""

import os
from collections import defaultdict
from urllib.parse import urlparse

import pandas as pd
from scrape_kit import get_logger

logger = get_logger(__name__)


def merge(
    db_path: str,
    chunks_dir: str,
    similarity_config: dict | None,
    crawler_keys: dict,
    runner_sets: dict[str, list[str]],
) -> None:
    """Merge multiple chunk databases into a single database and generate summary."""
    if not os.path.isdir(chunks_dir):
        logger.error(f"❌ Not a valid directory: {chunks_dir}")
        raise SystemExit(1)

    matches_df = _perform_merge(db_path, chunks_dir, similarity_config)
    _generate_merge_summary(matches_df, chunks_dir, db_path, crawler_keys, runner_sets)


def _perform_merge(db_path: str, chunks_dir: str, similarity_config: dict | None) -> pd.DataFrame:
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
    chunk_files = [f for f in os.listdir(chunks_dir) if f.endswith(".db") and f != os.path.basename(db_path)]

    _log_summary_header(matches_count, len(chunk_files))
    _log_source_details(source_to_matches)
    _log_missing_crawlers(source_to_matches, crawler_keys)
    _validate_runner_sets(source_to_matches, chunk_files, runner_sets)
    _log_footer(db_path)


def _build_source_mapping(matches_df: pd.DataFrame) -> dict[str, set]:
    """Build mapping of source names to match indices."""
    source_to_matches = defaultdict(set)

    for i, row in matches_df.iterrows():
        url = row.get("result_url")
        scores_list = row.get("scores")

        # Infer from URL
        if url and isinstance(url, str):
            domain = urlparse(url).netloc
            core_name = domain.split(".")[-2] if "." in domain else domain
            source_to_matches[core_name.lower()].add(i)

        # Extract from predictions list
        if scores_list and isinstance(scores_list, list):
            for p in scores_list:
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


def _log_missing_crawlers(source_to_matches: dict[str, set], crawler_keys: dict) -> None:
    """Identify configured crawlers that did not contribute matches."""
    for crawler in sorted(crawler_keys.keys()):
        if crawler not in source_to_matches:
            logger.warning(f"    - {crawler}: 0 matches (MISSING)")


def _validate_runner_sets(
    source_to_matches: dict[str, set],
    chunk_files: list[str],
    runner_sets: dict[str, list[str]],
) -> None:
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


def _log_footer(db_path: str) -> None:
    """Log the footer with output path."""
    logger.info("  " + "=" * 26)
    logger.info(f"✅ Merged into: {db_path}")
