"""
scrape module for handling the scrape mode logic
"""

import os
from collections import defaultdict
from urllib.parse import urlparse

from bet_crawler.crawler_logging import (
    get_event_totals,
    get_logger,
    log_context,
    log_event,
    reset_event_totals,
    source_key_for,
)
from bet_framework.MatchesManager import MatchesManager

logger = get_logger(__name__)


def scrape(db_path: str, urls_str: str, crawler_factory, similarity_config: dict | None = None) -> None:
    """Scrape chunk URLs per domain with per-finder instances and write chunk SQLite DBs."""
    chunk_id = os.path.basename(db_path)
    reset_event_totals(stage="scrape", chunk_id=chunk_id)
    if os.path.isfile(urls_str):
        with open(urls_str) as f:
            urls = [u.strip() for u in f.read().split(",") if u.strip()]
    else:
        urls = [u.strip() for u in urls_str.split(",") if u.strip()]

    groups: dict = defaultdict(list)
    for url in urls:
        domain = urlparse(url).netloc
        core_name = domain.split(".")[-2] if "." in domain else domain
        groups[core_name].append(url)

    matches_manager = MatchesManager(db_path, similarity_config=similarity_config)
    matches_manager.reset_matches_db()

    def _on_match(match) -> None:
        """Persist one scraped match into the chunk DB via the manager."""
        matches_manager.add_match(match)

    failed_groups = 0
    completed_groups = 0
    match_counts = {"matches_added": 0, "matches_skipped": 0, "match_errors": 0}
    source_warning_counts: dict[str, int] = {}
    try:
        for i, (domain_key, group_urls) in enumerate(groups.items()):
            logger.info(f"  [{i + 1}/{len(groups)}] Scraping {domain_key} ({len(group_urls)} URLs)...")
            crawler = None
            try:
                crawler = crawler_factory.create_for_url(group_urls[0], _on_match)
                source_key = source_key_for(crawler, crawler_factory)
                crawler._log_chunk_id = os.path.basename(db_path)
                warnings_before = get_event_totals(stage="scrape", chunk_id=chunk_id)["warnings"]
                with log_context(
                    stage="scrape",
                    chunk_id=os.path.basename(db_path),
                    source_key=source_key,
                    finder=crawler.__class__.__name__,
                    url=group_urls[0],
                ):
                    crawler.get_matches(group_urls)
                for key in match_counts:
                    match_counts[key] += getattr(crawler, "log_counts", {}).get(key, 0)
                warnings_after = get_event_totals(stage="scrape", chunk_id=chunk_id)["warnings"]
                source_warning_counts[source_key] = warnings_after - warnings_before
                completed_groups += 1
                log_event(
                    logger,
                    event="source.scrape.completed",
                    outcome="success",
                    reason_code="source_scrape_completed",
                    message="Source scrape completed",
                    stage="scrape",
                    chunk_id=os.path.basename(db_path),
                    source_key=source_key,
                    finder=crawler.__class__.__name__,
                    counts={"urls": len(group_urls)},
                )
            except Exception as exc:
                failed_groups += 1
                for key in match_counts:
                    match_counts[key] += getattr(crawler, "log_counts", {}).get(key, 0)
                if crawler is not None:
                    warnings_after = get_event_totals(stage="scrape", chunk_id=chunk_id)["warnings"]
                    source_warning_counts[source_key] = warnings_after - warnings_before
                logger.exception(
                    "Error scraping URL group %s (%d URLs)",
                    domain_key,
                    len(group_urls),
                    extra={
                        "event": "source.scrape.failed",
                        "outcome": "error",
                        "reason_code": "source_scrape_exception",
                        "stage": "scrape",
                        "chunk_id": os.path.basename(db_path),
                        "source_key": domain_key,
                        "url": group_urls[0],
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "counts": {"urls": len(group_urls)},
                    },
                )
    finally:
        try:
            matches_manager.close()
        except Exception as exc:
            logger.exception(
                "Failed to close scraped matches database %s",
                db_path,
                extra={
                    "event": "stage.failed",
                    "outcome": "error",
                    "reason_code": "matches_database_close_failed",
                    "stage": "scrape",
                    "chunk_id": os.path.basename(db_path),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            raise

    event_totals = get_event_totals(stage="scrape", chunk_id=chunk_id)
    event_totals["sources_with_warnings"] = sum(count > 0 for count in source_warning_counts.values())
    event_totals["matches_added"] = match_counts["matches_added"]
    event_totals["matches_skipped"] = match_counts["matches_skipped"]
    partial = bool(
        failed_groups or match_counts["match_errors"] or event_totals["errors"] or event_totals["sources_with_warnings"]
    )
    log_event(
        logger,
        event="stage.completed",
        outcome="partial" if partial else "success",
        reason_code=(
            "source_scrape_failures"
            if failed_groups
            else "match_persistence_failures"
            if match_counts["match_errors"]
            else "source_scrape_warnings"
            if event_totals["sources_with_warnings"]
            else None
        ),
        level=(40 if failed_groups or match_counts["match_errors"] or event_totals["errors"] else 30 if partial else 20),
        message="Scrape stage completed",
        stage="scrape",
        chunk_id=os.path.basename(db_path),
        counts={
            "groups_total": len(groups),
            "groups_completed": completed_groups,
            "groups_failed": failed_groups,
            "match_errors": match_counts["match_errors"],
            **event_totals,
        },
    )
