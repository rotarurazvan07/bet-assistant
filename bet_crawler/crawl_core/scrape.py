"""
scrape module for handling the scrape mode logic
"""

import os
from collections import defaultdict
from urllib.parse import urlparse

from scrape_kit import get_logger

from bet_framework.MatchesManager import MatchesManager

logger = get_logger(__name__)


def scrape(db_path: str, urls_str: str, crawler_factory, similarity_config: dict | None = None) -> None:
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
        matches_manager.add_match(match)

    for i, (domain_key, group_urls) in enumerate(groups.items()):
        logger.info(f"  [{i + 1}/{len(groups)}] Scraping {domain_key} ({len(group_urls)} URLs)...")
        try:
            # factory.create_for_url returns a crawler instance
            crawler = crawler_factory.create_for_url(group_urls[0], _on_match)
            # Use the new v2 scrape method
            crawler.scrape(group_urls)
        except Exception as e:
            logger.error(f"    ⚠️ Error scraping {domain_key}: {e}")

    matches_manager.close()
