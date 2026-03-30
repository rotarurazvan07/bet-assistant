"""
main.py — Bet Assistant CLI
────────────────────────────
Modes:
  prepare-scrape   Collect match URLs and split them into chunks for parallel scraping.
  scrape           Scrape a chunk of URLs into a local SQLite DB.
  merge            Merge all chunk DBs into a single final DB.
  generate-slips   Run all daily-enabled profiles and insert slips.
  validate-slips   Scrape match results and update pending leg outcomes.

Usage examples:
  python -m main --mode prepare-scrape --runners actions
  python -m main --mode scrape --matches_db_path chunk-1.db --urls "url1,url2,..."
  python -m main --mode merge --matches_db_path final.db --chunks_dir ./chunks
  python -m main --mode generate-slips --matches_db_path final.db --slips_db_path slips.db --config_path ./config
  python -m main --mode validate-slips --slips_db_path slips.db
"""

import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from contextlib import redirect_stdout
from urllib.parse import urlparse

from scrape_kit import SettingsManager, get_logger

logger = get_logger(__name__)

from bet_framework.MatchesManager import MatchesManager

# ─────────────────────────────────────────────────────────────────────────────
# Crawler registry
# ─────────────────────────────────────────────────────────────────────────────

_CRAWLER_KEYS = {
    "scorepredictor": lambda: _import("ScorePredictorFinder"),
    "soccervista": lambda: _import("SoccerVistaFinder"),
    "whoscored": lambda: _import("WhoScoredFinder"),
    "windrawwin": lambda: _import("WinDrawWinFinder"),
    "forebet": lambda: _import("ForebetFinder"),
    "vitibet": lambda: _import("VitibetFinder"),
    "predictz": lambda: _import("PredictzFinder"),
    "onemillionpredictions": lambda: _import("OneMillionPredictionsFinder"),
    "footballbettingtips": lambda: _import("FootballBettingTipsFinder"),
    "xgscore": lambda: _import("xGScoreFinder"),
}

_RUNNER_SETS = {
    "actions": [
        "vitibet",
        "scorepredictor",
        "predictz",
        "soccervista",
        "windrawwin",
        "onemillionpredictions",
        "xgscore",
    ],
    "local": ["whoscored", "forebet", "footballbettingtips"],
    "all": list(_CRAWLER_KEYS.keys()),
    "test": ["footballbettingtips"],
}

MAX_CHUNK_SIZE = {"actions": 100, "local": 1, "all": 1, "test": 1}


def _import(cls: str):
    from bet_crawler import finders

    return getattr(finders, cls)


def get_crawler_class(url: str):
    lower = url.lower()
    for key, loader in _CRAWLER_KEYS.items():
        if key in lower:
            return loader()
    raise ValueError(f"No crawler registered for URL: {url}")


def get_runner_classes(runner: str) -> list:
    keys = _RUNNER_SETS.get(runner, [])
    return [_CRAWLER_KEYS[k]() for k in keys]


# ─────────────────────────────────────────────────────────────────────────────
# Mode: prepare-scrape
# ─────────────────────────────────────────────────────────────────────────────


def mode_prepare_scrape(runner: str) -> None:
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
                    logger.warning(
                        f"⚠️  No URLs found for {cls.__name__} (attempt {attempt + 1}/3)"
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Error in {cls.__name__}.get_matches_urls() (attempt {attempt + 1}/3): {e}"
                    )

                if attempt < 2:
                    import time

                    time.sleep(2)
            del instance

    random.shuffle(urls)

    # Log unique domains
    unique_domains = sorted(list({urlparse(u).netloc for u in urls if u}))
    logger.info(
        f"Collected {len(urls)} URLs across {len(unique_domains)} domains: {', '.join(unique_domains)}"
    )

    max_runners = MAX_CHUNK_SIZE[runner]
    chunk_size = max(20, math.ceil(len(urls) / max_runners))

    tasks = [
        {
            "db_path": f"{runner}-{i // chunk_size + 1}.db",
            "urls": ",".join(urls[i : i + chunk_size]),
        }
        for i in range(0, len(urls), chunk_size)
    ]

    sys.stdout.write(json.dumps(tasks) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: scrape
# ─────────────────────────────────────────────────────────────────────────────


def mode_scrape(db_path: str, urls_str: str, config_dir: str) -> None:
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
    matches_manager = MatchesManager(
        db_path, similarity_config=sm.get("similarity_config")
    )
    matches_manager.reset_matches_db()

    def _on_match(match) -> None:
        matches_manager.add_match(match)

    for i, (domain_key, group_urls) in enumerate(groups.items()):
        logger.info(
            f"  [{i + 1}/{len(groups)}] Scraping {domain_key} ({len(group_urls)} URLs)..."
        )
        try:
            crawler = get_crawler_class(group_urls[0])(_on_match)
            crawler.get_matches(group_urls)
        except Exception as e:
            logger.error(f"    ⚠️ Error scraping {domain_key}: {e}")

    matches_manager.close()


# ─────────────────────────────────────────────────────────────────────────────
# Mode: merge
# ─────────────────────────────────────────────────────────────────────────────


def mode_merge(db_path: str, chunks_dir: str, config_dir: str) -> None:
    if not os.path.isdir(chunks_dir):
        logger.error(f"❌ Not a valid directory: {chunks_dir}")
        sys.exit(1)

    # Initialize SettingsManager locally
    sm = SettingsManager(config_dir)
    matches_manager = MatchesManager(
        db_path, similarity_config=sm.get("similarity_config")
    )
    matches_manager.reset_matches_db()
    matches_manager.merge_databases(chunks_dir)
    matches_df = matches_manager.fetch_matches()
    matches_manager.close()

    # Generate summary
    # Track unique match indices per source to prevent double counting
    source_to_matches = defaultdict(set)
    matches_count = len(matches_df)

    for i, row in matches_df.iterrows():
        url = row.get("result_url")
        scores_list = row.get("scores")

        # 1. Infer from URL
        if url:
            domain = urlparse(url).netloc
            core_name = domain.split(".")[-2] if "." in domain else domain
            source_to_matches[core_name.lower()].add(i)

        # 2. Extract from predictions list (already deserialized by fetch_matches)
        if scores_list:
            for p in scores_list:
                src = p.get("source")
                if src:
                    source_to_matches[src.lower()].add(i)

    logger.info("  " + "=" * 26)
    logger.info("  " + "MERGE SUMMARY".center(26))
    logger.info("  " + "=" * 26)
    logger.info(f"  Unique Matches: {matches_count}")
    chunk_files = [
        f
        for f in os.listdir(chunks_dir)
        if f.endswith(".db") and f != os.path.basename(db_path)
    ]
    logger.info(f"  Chunks scanned: {len(chunk_files)}")

    # Sort and print sorted sources
    sorted_sources = sorted(
        [(s, len(ms)) for s, ms in source_to_matches.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    for k, v in sorted_sources:
        logger.info(f"    - {k}: {v} matches")

    # Identify specific crawlers that were expected but had 0 matches
    for crawler in sorted(_CRAWLER_KEYS.keys()):
        if crawler not in source_to_matches:
            logger.warning(f"    - {crawler}: 0 matches (MISSING)")

    # Map sources back to runner sets to validate if all expected runners contributed
    seen_runners = set()
    for source in source_to_matches.keys():
        for runner_name, crawlers in _RUNNER_SETS.items():
            if source in crawlers:
                seen_runners.add(runner_name)

    expected_runners = set()
    for cf in chunk_files:
        runner_name = cf.split("-")[0]
        if runner_name in _RUNNER_SETS:
            expected_runners.add(runner_name)

    missing_runner_sets = expected_runners - seen_runners
    if missing_runner_sets:
        logger.error(f"  ❌ Full runner sets missing data: {missing_runner_sets}")
    logger.info("  " + "=" * 26)

    logger.info(f"✅ Merged into: {db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: generate-slips
# ─────────────────────────────────────────────────────────────────────────────


def mode_generate_slips(
    matches_db_path: str, slips_db_path: str, profile_path: str
) -> None:
    """
    Load matches and generate slips for the profile defined in the given YAML file.
    """
    from bet_framework.BetAssistant import BetAssistant, BetSlipConfig

    sm = SettingsManager(profile_path)
    # The profile name is the stem of the file
    name = os.path.basename(profile_path).split(".")[0]
    data = sm.get(name)

    if not data:
        logger.error(f"❌ No data found in profile file: {profile_path}")
        sys.exit(1)

    raw_df = MatchesManager(matches_db_path).fetch_matches()

    assistant = BetAssistant(slips_db_path)
    assistant.load_matches(raw_df)

    units = float(data.get("units", 1.0))

    cfg = BetSlipConfig(
        target_odds=data.get("target_odds"),
        target_legs=data.get("target_legs"),
        max_legs_overflow=data.get("max_legs_overflow"),
        consensus_floor=data.get("consensus_floor"),
        min_odds=data.get("min_odds"),
        tolerance_factor=data.get("tolerance_factor"),
        stop_threshold=data.get("stop_threshold"),
        min_legs_fill_ratio=data.get("min_legs_fill_ratio"),
        quality_vs_balance=data.get("quality_vs_balance"),
        consensus_vs_sources=data.get("consensus_vs_sources"),
        included_markets=data.get("included_markets"),
        date_from=data.get("date_from"),
        date_to=data.get("date_to"),
        excluded_urls=data.get("excluded_urls"),
    )

    logger.info(f"\n▶ Profile: {name.upper()}")

    legs = assistant.build_slip_auto_exclude(cfg)
    if not legs:
        logger.info("  ℹ️  No suitable matches found.")
    else:
        slip_id = assistant.save_slip(name, legs, units)
        total_odds = 1.0
        for leg in legs:
            logger.info(f"  ⚽ {leg['match']} ({leg['market']}) @ {leg['odds']:.2f}")
            total_odds *= leg.get("odds", 1.0)
        logger.info(
            f"  ✅ Slip #{slip_id} — {len(legs)} legs @ {total_odds:.2f} ({units}u)"
        )

    assistant.close()


# ─────────────────────────────────────────────────────────────────────────────
# Mode: validate-slips
# ─────────────────────────────────────────────────────────────────────────────


def mode_validate_slips(slips_db_path: str) -> None:
    """
    Delegate entirely to BetAssistant.validate_slips() — no duplicated
    scraping or outcome logic here.
    """
    from bet_framework.BetAssistant import BetAssistant

    assistant = BetAssistant(slips_db_path)
    result = assistant.validate_slips()
    assistant.close()

    logger.info(
        f"✅ Checked {result['checked']} · Settled {len(result['settled'])} · Live {len(result['live'])} · Errors {result['errors']}"
    )

    for item in result["live"]:
        logger.info(
            f"  🟡 {item['match_name']} ({item['market']})  {item['score']}  {item['minute']}"
        )

    for item in result["settled"]:
        icon = "✅" if item["outcome"] == "Won" else "❌"
        logger.info(
            f"  {icon} {item['match_name']} ({item['market']})  {item['score']}  → {item['outcome']}"
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
        if not args.runners:
            build_parser().error("--runners is required for prepare-scrape")
        mode_prepare_scrape(args.runners)

    elif args.mode == "scrape":
        if not args.urls or not args.matches_db_path or not args.config_dir:
            build_parser().error(
                "--urls, --matches_db_path, and --config_dir are required for scrape"
            )
        mode_scrape(args.matches_db_path, args.urls, args.config_dir)

    elif args.mode == "merge":
        if not args.matches_db_path or not args.chunks_dir or not args.config_dir:
            build_parser().error(
                "--matches_db_path, --chunks_dir, and --config_dir are required for merge"
            )
        mode_merge(args.matches_db_path, args.chunks_dir, args.config_dir)

    elif args.mode == "generate-slips":
        if not args.matches_db_path or not args.slips_db_path or not args.profile_path:
            build_parser().error(
                "--matches_db_path, --slips_db_path, and --profile_path are required for generate-slips"
            )
        mode_generate_slips(args.matches_db_path, args.slips_db_path, args.profile_path)

    elif args.mode == "validate-slips":
        if not args.slips_db_path:
            build_parser().error("--slips_db_path is required for validate-slips")
        mode_validate_slips(args.slips_db_path)
