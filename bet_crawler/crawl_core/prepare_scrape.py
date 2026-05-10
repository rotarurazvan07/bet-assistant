"""
prepare_scrape module for handling the prepare-scrape mode logic
"""
import json
import math
import os
import random
import sys
from contextlib import redirect_stdout

from scrape_kit import configure, get_logger
from urllib.parse import urlparse

from bet_crawler.crawl_registry import get_runner_classes, MAX_CHUNK_SIZE

logger = get_logger(__name__)


def prepare_scrape(runner: str, config_dir: str) -> None:
    configure(config_dir)
    crawler_classes = get_runner_classes(runner)
    if not crawler_classes:
        logger.error("❌ No crawlers found for runner type.")
        sys.exit(1)

    urls = []
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        for cls in crawler_classes:
            instance = cls(None)
            for attempt in range(3):
                try:
                    new_urls = instance.get_matches_urls()
                    if new_urls:
                        urls.extend(new_urls)
                        break
                    logger.warning(f"⚠️  No URLs found for {cls.__name__} (attempt {attempt + 1}/3)")
                except Exception as e:
                    logger.error(f"❌ Error in {cls.__name__}.get_matches_urls() (attempt {attempt + 1}/3): {e}")

                if attempt < 2:
                    import time

                    time.sleep(2)
            del instance

    random.shuffle(urls)

    # Log unique domains
    unique_domains = sorted({urlparse(u).netloc for u in urls if u})
    logger.info(f"Collected {len(urls)} URLs across {len(unique_domains)} domains: {', '.join(unique_domains)}")

    max_runners = MAX_CHUNK_SIZE[runner]
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