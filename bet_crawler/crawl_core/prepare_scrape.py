"""
prepare_scrape module for handling the prepare-scrape mode logic
"""

import json
import math
import os
import random
import sys
from contextlib import redirect_stdout
from urllib.parse import urlparse

from bet_crawler.crawler_logging import (
    get_event_totals,
    get_logger,
    log_context,
    log_event,
    reset_event_totals,
    source_key_for,
)

logger = get_logger(__name__)


def prepare_scrape(runner: str, crawler_factory, max_chunk_size: dict[str, int]) -> None:
    """Prepare scraping by collecting URLs and creating chunk tasks.

    Args:
        runner: Runner type (actions, local, test).
        crawler_factory: Factory for creating crawler instances.
        max_chunk_size: Dict mapping runner to max chunk size.
    """
    crawlers = crawler_factory.create_for_runner(runner)
    reset_event_totals(stage="prepare-scrape")
    if not crawlers:
        log_event(
            logger,
            event="stage.failed",
            outcome="error",
            reason_code="no_crawlers_configured",
            level=40,
            message="No crawlers found for runner type",
            stage="prepare-scrape",
            runner=runner,
        )
        sys.exit(1)

    urls = []
    failed_sources = 0
    empty_sources = 0
    sources_with_warnings = set()
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        for crawler in crawlers:
            source_key = source_key_for(crawler, crawler_factory)
            with log_context(
                stage="prepare-scrape",
                runner=runner,
                source_key=source_key,
                finder=crawler.__class__.__name__,
            ):
                for attempt in range(3):
                    previous_totals = get_event_totals(stage="prepare-scrape")
                    try:
                        new_urls = crawler.get_matches_urls()
                        current_totals = get_event_totals(stage="prepare-scrape")
                        if current_totals["warnings"] > previous_totals["warnings"]:
                            sources_with_warnings.add(source_key)
                        if new_urls:
                            urls.extend(new_urls)
                            log_event(
                                logger,
                                event="source.discovery.completed",
                                outcome="success",
                                reason_code="urls_discovered",
                                message="Source URL discovery completed",
                                counts={"urls": len(new_urls)},
                            )
                            break
                        empty_sources += 1 if attempt == 2 else 0
                        log_event(
                            logger,
                            event="source.discovery.empty",
                            outcome="warning",
                            reason_code="no_urls_found",
                            level=30,
                            message=f"No URLs found for {crawler.__class__.__name__} (attempt {attempt + 1}/3)",
                            attempt=attempt + 1,
                            max_attempts=3,
                        )
                    except Exception as exc:
                        if attempt == 2:
                            failed_sources += 1
                            logger.exception(
                                "URL discovery exhausted retries for %s",
                                crawler.__class__.__name__,
                                extra={
                                    "event": "source.discovery.failed",
                                    "outcome": "error",
                                    "reason_code": "discovery_retries_exhausted",
                                    "attempt": attempt + 1,
                                    "max_attempts": 3,
                                    "error_type": type(exc).__name__,
                                    "error_message": str(exc),
                                },
                            )
                        else:
                            log_event(
                                logger,
                                event="source.discovery.retry",
                                outcome="warning",
                                reason_code="discovery_retry",
                                level=30,
                                message=(
                                    f"URL discovery failed for {crawler.__class__.__name__} "
                                    f"(attempt {attempt + 1}/3): {exc}"
                                ),
                                attempt=attempt + 1,
                                max_attempts=3,
                                error_type=type(exc).__name__,
                                error_message=str(exc),
                            )

                    if attempt < 2:
                        import time

                        time.sleep(2)

    random.shuffle(urls)

    # Log unique domains
    unique_domains = sorted({urlparse(u).netloc for u in urls if u})
    logger.info(f"Collected {len(urls)} URLs across {len(unique_domains)} domains: {', '.join(unique_domains)}")
    event_totals = get_event_totals(stage="prepare-scrape")
    partial = bool(
        failed_sources or empty_sources or event_totals["errors"] or sources_with_warnings
    )
    log_event(
        logger,
        event="stage.completed",
        outcome="partial" if partial else "success",
        reason_code=(
            "source_discovery_failures"
            if failed_sources
            else "sources_returned_no_urls"
            if empty_sources
            else "source_discovery_warnings"
            if sources_with_warnings
            else None
        ),
        level=(
            40
            if failed_sources or event_totals["errors"]
            else 30
            if partial
            else 20
        ),
        message="Prepare-scrape completed",
        stage="prepare-scrape",
        runner=runner,
        counts={
            "urls": len(urls),
            "sources_failed": failed_sources,
            "sources_empty": empty_sources,
            "sources_with_warnings": len(sources_with_warnings),
            **event_totals,
        },
    )

    max_runners = max_chunk_size.get(runner, 1)
    chunk_size = max(20, math.ceil(len(urls) / max_runners))

    tasks = [
        {
            "db_path": f"{runner}-{i // chunk_size + 1}.db",
            "urls_file": f"{runner}-{i // chunk_size + 1}-urls.txt",
        }
        for i in range(0, len(urls), chunk_size)
    ]

    # Create URL files for each task
    for i, task in enumerate(tasks):
        with open(task["urls_file"], "w") as f:
            start_idx = i * chunk_size
            end_idx = min((i + 1) * chunk_size, len(urls))
            f.write(",".join(urls[start_idx:end_idx]))

    sys.stdout.write(json.dumps(tasks) + "\n")
