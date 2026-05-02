"""
main.py — Bet Assistant CLI
────────────────────────────
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
import sys

from scrape_kit import configure, get_logger

logger = get_logger(__name__)

# Import mode handlers from crawl_core
from bet_crawler.crawl_core.prepare_scrape import prepare_scrape
from bet_crawler.crawl_core.scrape import scrape
from bet_crawler.crawl_core.merge import merge
from bet_crawler.crawl_core.generate_slips import generate_slips
from bet_crawler.crawl_core.validate_slips import validate_slips

# Import crawler registry from the new shared module
from bet_crawler.crawl_registry import (
    _CRAWLER_KEYS,
    _RUNNER_SETS,
    MAX_CHUNK_SIZE,
    get_runner_classes,
)

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


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
    p.add_argument("--runners", choices=list(_RUNNER_SETS.keys()))
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()

    if args.mode == "prepare-scrape":
        if not args.runners or not args.config_dir:
            build_parser().error("--runners and --config_dir are required for prepare-scrape")
        prepare_scrape(args.runners, args.config_dir)

    elif args.mode == "scrape":
        if not args.urls or not args.matches_db_path or not args.config_dir:
            build_parser().error("--urls, --matches_db_path, and --config_dir are required for scrape")
        scrape(args.matches_db_path, args.urls, args.config_dir)

    elif args.mode == "merge":
        if not args.matches_db_path or not args.chunks_dir or not args.config_dir:
            build_parser().error("--matches_db_path, --chunks_dir, and --config_dir are required for merge")
        merge(args.matches_db_path, args.chunks_dir, args.config_dir)

    elif args.mode == "generate-slips":
        if not args.matches_db_path or not args.slips_db_path or not args.profile_path:
            build_parser().error("--matches_db_path, --slips_db_path, and --profile_path are required for generate-slips")
        generate_slips(args.matches_db_path, args.slips_db_path, args.profile_path)

    elif args.mode == "validate-slips":
        if not args.slips_db_path:
            build_parser().error("--slips_db_path is required for validate-slips")
        validate_slips(args.slips_db_path)