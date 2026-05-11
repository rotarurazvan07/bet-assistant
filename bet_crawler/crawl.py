"""
main.py - Bet Assistant CLI
----------------------------
Modes:
  prepare-scrape       Collect match URLs and split them into chunks for parallel scraping.
  scrape               Scrape a chunk of URLs into a local SQLite DB.
  merge                Merge all chunk DBs into a single final DB.
  generate-slips       Run all daily-enabled profiles and insert slips.
  validate-slips       Scrape match results and update pending leg outcomes.

Usage examples:
  python -m main --mode prepare-scrape --runners actions
  python -m main --mode scrape --matches_db_path chunk-1.db --urls "url1,url2,..."
  python -m main --mode merge --matches_db_path final.db --chunks_dir ./chunks
  python -m main --mode generate-slips --matches_db_path final.db --slips_db_path slips.db --config_path ./config
  python -m main --mode validate-slips --slips_db_path slips.db
"""

import argparse
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scrape_kit import SettingsManager, configure, get_logger

from bet_crawler.crawl_core.generate_slips import generate_slips
from bet_crawler.crawl_core.merge import merge
from bet_crawler.crawl_core.prepare_scrape import prepare_scrape
from bet_crawler.crawl_core.scrape import scrape
from bet_crawler.crawl_core.validate_slips import validate_slips

logger = get_logger(__name__)


@dataclass(frozen=True)
class CrawlerRuntimeSettings:
    num_days_ahead: int
    local_timezone: str
    skip_patterns: tuple[tuple[str, str], ...]


class CrawlerFactory:
    def __init__(
        self,
        crawler_keys: dict[str, dict[str, Any]],
        runner_sets: dict[str, list[str]],
        runtime_settings: CrawlerRuntimeSettings,
    ) -> None:
        self.crawler_keys = crawler_keys
        self.runner_sets = self._normalise_runner_sets(runner_sets)
        self.runtime_settings = runtime_settings

    def create_for_url(self, url: str, on_match_callback: Callable | None = None):
        crawler_key = self._crawler_key_for_url(url)
        return self.create(crawler_key, on_match_callback)

    def create(self, crawler_key: str, on_match_callback: Callable | None = None):
        crawler_config = self.crawler_keys[crawler_key]
        crawler_class = self._load_class(crawler_config["class"])
        return crawler_class(
            on_match_callback,
            contributes_odds=bool(crawler_config.get("contributes_odds")),
            num_days_ahead=self.runtime_settings.num_days_ahead,
            local_timezone=self.runtime_settings.local_timezone,
            skip_patterns=self.runtime_settings.skip_patterns,
        )

    def create_for_runner(self, runner: str, on_match_callback: Callable | None = None):
        return [self.create(key, on_match_callback) for key in self.runner_keys(runner)]

    def runner_keys(self, runner: str) -> list[str]:
        return self.runner_sets.get(runner, [])

    def runner_names(self) -> list[str]:
        return list(self.runner_sets.keys())

    def _crawler_key_for_url(self, url: str) -> str:
        lower_url = url.lower()
        for crawler_key in self.crawler_keys:
            if crawler_key in lower_url:
                return crawler_key
        raise ValueError(f"No crawler registered for URL: {url}")

    def _normalise_runner_sets(self, runner_sets: dict[str, list[str]]) -> dict[str, list[str]]:
        normalised = {name: list(crawler_keys) for name, crawler_keys in runner_sets.items()}
        normalised.setdefault("all", list(self.crawler_keys.keys()))
        return normalised

    @staticmethod
    def _load_class(class_name: str):
        from bet_crawler import finders

        return getattr(finders, class_name)


def load_runtime(config_dir: str):
    configure(config_dir)
    settings = SettingsManager(config_dir)
    scraper_config = settings.get("scraper_config")

    crawler_keys = scraper_config.get("CRAWLER_KEYS")
    runner_sets = scraper_config.get("RUNNER_SETS")
    max_chunk_size = scraper_config.get("MAX_CHUNK_SIZE")
    skip_patterns = tuple((item["pattern"], item["description"]) for item in scraper_config.get("SKIP_PATTERNS"))
    runtime_settings = CrawlerRuntimeSettings(
        num_days_ahead=int(scraper_config.get("num_days_ahead")),
        local_timezone=str(scraper_config.get("local_timezone")),
        skip_patterns=skip_patterns,
    )

    factory = CrawlerFactory(crawler_keys, runner_sets, runtime_settings)
    return {
        "factory": factory,
        "max_chunk_size": max_chunk_size,
        "similarity_config": settings.get("similarity_config"),
    }


def load_profile(profile_path: str) -> tuple[str, dict[str, Any]]:
    settings = SettingsManager(profile_path)
    profile_name = os.path.basename(profile_path).split(".")[0]
    profile_data = settings.get(profile_name)
    return profile_name, profile_data or {}


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Bet Assistant CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--mode",
        required=True,
        choices=[
            "prepare-scrape",
            "scrape",
            "merge",
            "generate-slips",
            "validate-slips",
        ],
    )
    p.add_argument("--matches_db_path", help="Path to the matches SQLite DB")
    p.add_argument("--slips_db_path", help="Path to the slips SQLite DB")
    p.add_argument(
        "--urls",
        help="Comma-separated URLs to scrape or .txt file with them",
    )
    p.add_argument("--chunks_dir", help="Directory containing chunk DBs")
    p.add_argument("--config_dir", help="Directory containing config files")
    p.add_argument("--profile_path", help="Path to a specific YAML profile file")
    p.add_argument("--runners")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()

    if args.mode == "prepare-scrape":
        if not args.runners or not args.config_dir:
            build_parser().error("--runners and --config_dir are required for prepare-scrape")
        runtime = load_runtime(args.config_dir)
        prepare_scrape(args.runners, runtime["factory"], runtime["max_chunk_size"])

    elif args.mode == "scrape":
        if not args.urls or not args.matches_db_path or not args.config_dir:
            build_parser().error("--urls, --matches_db_path, and --config_dir are required for scrape")
        runtime = load_runtime(args.config_dir)
        scrape(args.matches_db_path, args.urls, runtime["factory"], runtime["similarity_config"])

    elif args.mode == "merge":
        if not args.matches_db_path or not args.chunks_dir or not args.config_dir:
            build_parser().error("--matches_db_path, --chunks_dir, and --config_dir are required for merge")
        runtime = load_runtime(args.config_dir)
        merge(
            args.matches_db_path,
            args.chunks_dir,
            runtime["similarity_config"],
            runtime["factory"].crawler_keys,
            runtime["factory"].runner_sets,
        )

    elif args.mode == "generate-slips":
        if not args.matches_db_path or not args.slips_db_path or not args.profile_path:
            build_parser().error("--matches_db_path, --slips_db_path, and --profile_path are required for generate-slips")
        profile_name, profile_data = load_profile(args.profile_path)
        generate_slips(args.matches_db_path, args.slips_db_path, profile_name, profile_data)

    elif args.mode == "validate-slips":
        if not args.slips_db_path:
            build_parser().error("--slips_db_path is required for validate-slips")
        validate_slips(args.slips_db_path)
