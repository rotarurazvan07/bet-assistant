"""
scrape module for handling the scrape mode logic
"""

import os
from collections import defaultdict
from urllib.parse import urlparse

from scrape_kit import SettingsManager, configure, get_logger

from bet_crawler.crawl_registry import get_crawler_class
from bet_framework.MatchesManager import MatchesManager

logger = get_logger(__name__)


def scrape(db_path: str, urls_str: str, config_dir: str) -> None:
    configure(config_dir)

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

    # Initialize SettingsManager locally
    sm = SettingsManager(config_dir)
    matches_manager = MatchesManager(db_path, similarity_config=sm.get("similarity_config"))
    matches_manager.reset_matches_db()

    def _on_match(match) -> None:
        matches_manager.add_match(match)

    for i, (domain_key, group_urls) in enumerate(groups.items()):
        logger.info(f"  [{i + 1}/{len(groups)}] Scraping {domain_key} ({len(group_urls)} URLs)...")
        try:
            crawler, contributes_odds = get_crawler_class(group_urls[0], _on_match)
            crawler.contributes_odds = contributes_odds
            crawler.get_matches(group_urls)
        except Exception as e:
            logger.error(f"    ⚠️ Error scraping {domain_key}: {e}")

    matches_manager.close()
