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

from scrape_kit import get_logger

logger = get_logger(__name__)


def prepare_scrape(runner: str, crawler_factory, max_chunk_size: dict[str, int]) -> None:
    crawlers = crawler_factory.create_for_runner(runner)
    if not crawlers:
        logger.error("❌ No crawlers found for runner type.")
        sys.exit(1)

    urls = []
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        for crawler in crawlers:
            for attempt in range(3):
                try:
                    new_urls = crawler.get_matches_urls()
                    if new_urls:
                        urls.extend(new_urls)
                        break
                    logger.warning(f"⚠️  No URLs found for {crawler.__class__.__name__} (attempt {attempt + 1}/3)")
                except Exception as e:
                    logger.error(
                        f"❌ Error in {crawler.__class__.__name__}.get_matches_urls() (attempt {attempt + 1}/3): {e}"
                    )

                if attempt < 2:
                    import time

                    time.sleep(2)

    random.shuffle(urls)

    # Log unique domains
    unique_domains = sorted({urlparse(u).netloc for u in urls if u})
    logger.info(f"Collected {len(urls)} URLs across {len(unique_domains)} domains: {', '.join(unique_domains)}")

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
