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
from dataclasses import fields as _dc_fields
from urllib.parse import urlparse

from bet_framework.BetAssistant import BetAssistant, BetSlipConfig
from bet_framework.MatchesManager import MatchesManager
from bet_framework.SettingsManager import SettingsManager

# ─────────────────────────────────────────────────────────────────────────────
# Crawler registry
# ─────────────────────────────────────────────────────────────────────────────

_CRAWLER_KEYS = {
    "scorepredictor": lambda: _import("bet_crawler.ScorePredictorFinder", "ScorePredictorFinder"),
    "soccervista":    lambda: _import("bet_crawler.SoccerVistaFinder",    "SoccerVistaFinder"),
    "whoscored":      lambda: _import("bet_crawler.WhoScoredFinder",      "WhoScoredFinder"),
    "windrawwin":     lambda: _import("bet_crawler.WinDrawWinFinder",     "WinDrawWinFinder"),
    "forebet":        lambda: _import("bet_crawler.ForebetFinder",        "ForebetFinder"),
    "vitibet":        lambda: _import("bet_crawler.VitibetFinder",        "VitibetFinder"),
    "predictz":       lambda: _import("bet_crawler.PredictzFinder",       "PredictzFinder"),
}

_RUNNER_SETS = {
    "actions": ["vitibet", "scorepredictor", "predictz", "soccervista", "windrawwin"],
    "local":   ["whoscored", "forebet"],
}

MAX_CHUNK_SIZE = {"actions": 100, "local": 1}

_BETSLIP_FIELDS  = {f.name for f in _dc_fields(BetSlipConfig)}
_RUNTIME_FIELDS  = {"date_from", "date_to", "excluded_urls"}


def _import(module: str, cls: str):
    import importlib
    return getattr(importlib.import_module(module), cls)


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

def mode_prepare_scrape(runner: str):
    crawler_classes = get_runner_classes(runner)
    if not crawler_classes:
        print("❌ No crawlers found for runner type.", file=sys.stderr)
        sys.exit(1)

    urls = []
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        for cls in crawler_classes:
            instance = cls(None)
            try:
                urls.extend(instance.get_matches_urls())
            except Exception:
                pass
            finally:
                del instance

    random.shuffle(urls)

    max_runners = MAX_CHUNK_SIZE[runner]
    chunk_size  = max(20, math.ceil(len(urls) / max_runners))

    tasks = [
        {
            "db_path": f"{runner}-{i // chunk_size + 1}.db",
            "urls":    ",".join(urls[i : i + chunk_size]),
        }
        for i in range(0, len(urls), chunk_size)
    ]

    print(json.dumps(tasks))


# ─────────────────────────────────────────────────────────────────────────────
# Mode: scrape
# ─────────────────────────────────────────────────────────────────────────────

def mode_scrape(db_path: str, urls_str: str):
    urls = [u.strip() for u in urls_str.split(",") if u.strip()]

    groups: dict = defaultdict(list)
    for url in urls:
        domain    = urlparse(url).netloc
        core_name = domain.split(".")[-2] if "." in domain else domain
        groups[core_name].append(url)

    matches_manager = MatchesManager(db_path, similarity_config=settings_manager.get("similarity_config"))
    matches_manager.reset_matches_db()

    def _on_match(match):
        matches_manager.add_match(match)

    for i, (domain_key, group_urls) in enumerate(groups.items()):
        print(f"  [{i+1}/{len(groups)}] Scraping {domain_key} ({len(group_urls)} URLs)...")
        try:
            crawler = get_crawler_class(group_urls[0])(_on_match)
            crawler.get_matches(group_urls)
        except Exception as e:
            print(f"    ⚠️ Error scraping {domain_key}: {e}", file=sys.stderr)
        finally:
            del crawler

    matches_manager.close()


# ─────────────────────────────────────────────────────────────────────────────
# Mode: merge
# ─────────────────────────────────────────────────────────────────────────────

def mode_merge(db_path: str, chunks_dir: str):
    if not os.path.isdir(chunks_dir):
        print(f"❌ Not a valid directory: {chunks_dir}", file=sys.stderr)
        sys.exit(1)

    matches_manager = MatchesManager(db_path, settings_manager.get("similarity_config"))
    matches_manager.reset_matches_db()
    matches_manager.merge_databases(chunks_dir)
    matches_manager.close()
    print(f"✅ Merged into {db_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Mode: generate-slips
# ─────────────────────────────────────────────────────────────────────────────

def mode_generate_slips(matches_db_path: str, slips_db_path: str, config_path: str):
    """
    Load matches, then for every profile with run_daily_count > 0
    build and persist that many slips via BetAssistant.
    """
    raw_df = MatchesManager(matches_db_path).fetch_matches()

    assistant = BetAssistant(slips_db_path)
    assistant.load_matches(raw_df)

    profiles = settings_manager.get("profiles") or {}
    if not profiles:
        print("⚠️  No profiles found in config.")
        return

    for name, data in profiles.items():
        count = int(data.get("run_daily_count", 0))
        if not count:
            print(f"⏩ Skipping '{name}' (run_daily_count is 0)")
            continue

        kwargs = {k: v for k, v in data.items()
                  if k in _BETSLIP_FIELDS and k not in _RUNTIME_FIELDS}
        cfg    = BetSlipConfig(**kwargs)
        units  = float(data.get("units", 1.0))

        print(f"\n▶ Profile: {name.upper()} — generating {count} slip(s)")

        for i in range(count):
            legs = assistant.build_slip_auto_exclude(cfg)
            if not legs:
                print(f"  ℹ️  [{i+1}/{count}] No suitable matches found.")
                continue

            slip_id    = assistant.save_slip(name, legs, units)
            total_odds = 1.0
            for leg in legs:
                total_odds *= leg.get("odds", 1.0)
            print(f"  ✅ [{i+1}/{count}] Slip #{slip_id} — {len(legs)} legs @ {total_odds:.2f} ({units}u)")

    assistant.close()


# ─────────────────────────────────────────────────────────────────────────────
# Mode: validate-slips
# ─────────────────────────────────────────────────────────────────────────────

def mode_validate_slips(slips_db_path: str):
    """
    Delegate entirely to BetAssistant.validate_slips() — no duplicated
    scraping or outcome logic here.
    """
    assistant = BetAssistant(slips_db_path)
    result    = assistant.validate_slips()
    assistant.close()

    print(f"✅ Checked {result['checked']} · Settled {result['settled']} · "
          f"Live {len(result['live'])} · Errors {result['errors']}")

    for item in result["live"]:
        print(f"  🟡 {item['match_name']}  {item['score']}  {item['minute']}")

    for item in result["finished"]:
        icon = "✅" if item["outcome"] == "Won" else "❌"
        print(f"  {icon} {item['match_name']}  {item['score']}  → {item['outcome']}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Bet Assistant CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--mode", required=True,
                   choices=["prepare-scrape", "scrape", "merge", "generate-slips", "validate-slips"])
    p.add_argument("--matches_db_path", help="Path to the matches SQLite DB",   default="")
    p.add_argument("--slips_db_path",   help="Path to the slips SQLite DB",     default="")
    p.add_argument("--urls",            help="Comma-separated URLs to scrape",  default="")
    p.add_argument("--chunks_dir",      help="Directory containing chunk DBs",  default=".")
    p.add_argument("--config_path",     help="Directory containing config files", default=".")
    p.add_argument("--runners", choices=["actions", "local"], default="")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()

    settings_manager = SettingsManager(args.config_path)

    if args.mode == "prepare-scrape":
        if not args.runners:
            build_parser().error("--runners is required for prepare-scrape")
        mode_prepare_scrape(args.runners)

    elif args.mode == "scrape":
        if not args.urls or not args.matches_db_path:
            build_parser().error("--urls and --matches_db_path are required for scrape")
        mode_scrape(args.matches_db_path, args.urls)

    elif args.mode == "merge":
        if not args.matches_db_path:
            build_parser().error("--matches_db_path is required for merge")
        mode_merge(args.matches_db_path, args.chunks_dir)

    elif args.mode == "generate-slips":
        if not args.matches_db_path or not args.slips_db_path:
            build_parser().error("--matches_db_path and --slips_db_path are required for generate-slips")
        mode_generate_slips(args.matches_db_path, args.slips_db_path, args.config_path)

    elif args.mode == "validate-slips":
        if not args.slips_db_path:
            build_parser().error("--slips_db_path is required for validate-slips")
        mode_validate_slips(args.slips_db_path)