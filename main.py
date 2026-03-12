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
  python -m main --mode scrape --db_path chunk-1.db --urls "url1,url2,..."
  python -m main --mode merge --db_path final.db --chunks_dir ./chunks
  python -m main --mode generate-slips --db_path final.db
  python -m main --mode validate-slips --db_path slips.db
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

from bet_framework.BettingAnalyzer import BetSlipConfig, BettingAnalyzer
from bet_framework.MatchesManager import MatchesManager
from bet_framework.SettingsManager import SettingsManager
from bet_framework.BetSlipManager import BetSlipManager

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

# Which crawlers run where
_RUNNER_SETS = {
    "actions": ["vitibet", "scorepredictor", "predictz", "soccervista", "windrawwin"],
    "local":   ["whoscored", "forebet"],
}

MAX_CHUNK_SIZE = {"actions": 100, "local": 1}


def _import(module: str, cls: str):
    import importlib
    return getattr(importlib.import_module(module), cls)


def get_crawler_class(url: str):
    """Return the crawler class whose key appears in the given URL."""
    lower = url.lower()
    for key, loader in _CRAWLER_KEYS.items():
        if key in lower:
            return loader()
    raise ValueError(f"No crawler registered for URL: {url}")


def get_runner_classes(runner: str) -> list:
    """Return instantiated crawler classes for the given runner type."""
    keys = _RUNNER_SETS.get(runner, [])
    return [_CRAWLER_KEYS[k]() for k in keys]


# ─────────────────────────────────────────────────────────────────────────────
# Profile helpers
# ─────────────────────────────────────────────────────────────────────────────

# BetSlipConfig fields that are always None at generation time (runtime-only)
_RUNTIME_FIELDS = {"date_from", "date_to", "excluded_urls"}

from dataclasses import fields as _dc_fields
_BETSLIP_FIELDS = {f.name for f in _dc_fields(BetSlipConfig)}


# def load_profiles(profiles_dir: str = "config/profiles") -> dict:
#     """Return all profiles that exist on disk as {name: raw_dict}."""
#     return {
#         name: cfg
#         for name, cfg in settings_manager.config.items()
#         if os.path.exists(os.path.join(profiles_dir, f"{name}.yaml"))
#     }


# def profile_to_config(data: dict, excluded_urls: list = None) -> BetSlipConfig:
#     """
#     Build a BetSlipConfig from a profile YAML dict.
#     - Ignores dashboard-only keys (units, run_daily).
#     - Injects excluded_urls at runtime (not stored in the profile).
#     """
#     kwargs = {
#         k: v for k, v in data.items()
#         if k in _BETSLIP_FIELDS and k not in _RUNTIME_FIELDS
#     }
#     kwargs["excluded_urls"] = excluded_urls or None
#     return BetSlipConfig(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Mode: prepare-scrape
# ─────────────────────────────────────────────────────────────────────────────

def mode_prepare_scrape(runner: str):
    """
    Collect all match URLs from the relevant crawlers, shuffle them,
    split into chunks sized for the runner type, and print JSON.
    Each chunk becomes one scrape job: {db_path, urls}.
    """
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
    """
    Scrape a comma-separated list of URLs into a fresh local DB.
    URLs are grouped by domain so each crawler runs in one batch.
    """
    urls = [u.strip() for u in urls_str.split(",") if u.strip()]

    # Group URLs by their core domain name → one crawler per group
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
    """Merge all chunk DBs found in chunks_dir into a single final DB."""
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

# def mode_generate_slips(db_path: str):
#     """
#     For every profile with run_daily=True, build a bet slip and persist it.
#     Matches already in pending slips are excluded to avoid duplication.
#     """
#     # Load match data
#     matches_manager = MatchesManager(db_path)
#     analyzer   = BettingAnalyzer(matches_manager)
#     analyzer.refresh_data()
#     matches_manager.close()

#     slips_path      = os.path.join(os.path.dirname(db_path), "slips.db")
#     slip_manager    = BetSlipManager(slips_path)
#     active_urls     = slip_manager.get_pending_result_urls()

#     profiles = load_profiles()
#     if not profiles:
#         print("⚠️  No profiles found in config/profiles/")
#         sys.exit(0)

#     for prof_name, prof_data in profiles.items():
#         if not prof_data.get("run_daily", False):
#             print(f"⏩ Skipping '{prof_name}' (run_daily is off)")
#             continue

#         print(f"\n▶ Running profile: {prof_name.upper()}")

#         cfg  = profile_to_config(prof_data, excluded_urls=active_urls)
#         legs = analyzer.build_bet_slip(cfg)

#         if not legs:
#             print(f"  ℹ️  No suitable matches found.")
#             continue

#         units   = float(prof_data.get("units", 1.0))
#         slip_id = slip_manager.insert_slip(prof_name, legs, units=units)

#         total_odds = 1.0
#         for leg in legs:
#             total_odds *= leg.get("odds", 1.0)

#         print(f"  ✅ Slip #{slip_id} — {len(legs)} legs @ {total_odds:.2f} ({units}u)")

#         # Prevent the same matches being reused across profiles in the same run
#         active_urls.extend(leg["result_url"] for leg in legs)

#     slip_manager.close()


# ─────────────────────────────────────────────────────────────────────────────
# Mode: validate-slips
# ─────────────────────────────────────────────────────────────────────────────

def _parse_score(raw: str) -> tuple[int, int]:
    """Parse 'H:A' score string into (home_goals, away_goals)."""
    parts = raw.split(":")
    return int(parts[0]), int(parts[1])


def _fetch_final_score(soup) -> str | None:
    """
    Extract the full-time score from a BeautifulSoup-parsed result page.
    Returns 'H:A' string if the match is finished, None if still pending.
    """
    status = soup.find(id="status-container")
    if not (status and "FT" in status.get_text(strip=True)):
        return None
    score_div = soup.find(
        "div",
        class_="text-base font-bold min-sm:text-xl text-center"
    )
    return score_div.get_text(strip=True) if score_div else None


def _determine_outcome(home: int, away: int, market: str, market_type: str) -> str:
    """Return 'Won', 'Lost', or 'Pending' for a single leg given the final score."""
    if market_type == "result":
        if   market == "1" and home > away:  return "Won"
        elif market == "2" and away > home:  return "Won"
        elif market == "X" and home == away: return "Won"
        return "Lost"

    if market_type == "btts":
        scored = home > 0 and away > 0
        if   market == "BTTS Yes" and scored:  return "Won"
        elif market == "BTTS No"  and not scored: return "Won"
        return "Lost"

    if market_type == "over_under_2.5":
        total = home + away
        if   market == "Over 2.5"  and total >= 3: return "Won"
        elif market == "Under 2.5" and total <  3: return "Won"
        return "Lost"

    return "Pending"


def mode_validate_slips(db_path: str):
    """
    Fetch result pages for all pending legs and update their outcome.
    Requires scraping dependencies (requirements-scrape.txt).
    """
    try:
        from bs4 import BeautifulSoup
        from bet_framework.WebScraper import WebScraper
    except ImportError:
        print(
            "❌ Scraping dependencies missing. "
            "Install requirements-scrape.txt to use validate-slips.",
            file=sys.stderr,
        )
        sys.exit(1)

    slip_manager  = BetSlipManager(db_path)
    pending_legs  = slip_manager.get_legs_to_validate()

    if not pending_legs:
        print("✅ No pending legs to validate.")
        slip_manager.close()
        return

    print(f"🔍 Validating {len(pending_legs)} pending legs...")

    resolved = skipped = 0

    for leg_id, url, market, market_type in pending_legs:
        try:
            html  = WebScraper.fetch(url)
            soup  = BeautifulSoup(html, "html.parser")
            score = _fetch_final_score(soup)

            if score is None:
                print(f"  ⏳ Leg {leg_id}: match still in progress or result not found.")
                skipped += 1
                continue

            home, away = _parse_score(score)
            outcome    = _determine_outcome(home, away, market, market_type)

            slip_manager.update_leg_status(leg_id, outcome)
            print(f"  {'✅' if outcome == 'Won' else '❌'} Leg {leg_id}: {market} → {outcome}  ({home}:{away})")
            resolved += 1

        except (ValueError, IndexError) as e:
            print(f"  ⚠️  Leg {leg_id}: could not parse score — {e}", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️  Leg {leg_id}: unexpected error — {e}", file=sys.stderr)

    print(f"\nDone. Resolved: {resolved}, Still pending: {skipped}")
    slip_manager.close()


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
        choices=["prepare-scrape", "scrape", "merge", "generate-slips", "validate-slips"],
        help="Workflow phase to execute",
    )
    p.add_argument("--db_path",    help="Path to the SQLite database file")
    p.add_argument("--urls",       help="Comma-separated URLs to scrape", default="")
    p.add_argument("--chunks_dir", help="Directory containing chunk DBs",  default=".")
    p.add_argument("--config_path", help="Directory containing config files",  default=".")
    p.add_argument(
        "--runners",
        choices=["actions", "local"],
        default="",
        help="Which crawler set to use (prepare-scrape only)",
    )
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()

    settings_manager = SettingsManager(args.config_path)

    if args.mode == "prepare-scrape":
        if not args.runners:
            build_parser().error("--runners is required for prepare-scrape")
        mode_prepare_scrape(args.runners)

    elif args.mode == "scrape":
        if not args.urls or not args.db_path:
            build_parser().error("--urls and --db_path are required for scrape")
        mode_scrape(args.db_path, args.urls)

    elif args.mode == "merge":
        if not args.db_path:
            build_parser().error("--db_path is required for merge")
        mode_merge(args.db_path, args.chunks_dir)

    elif args.mode == "generate-slips":
        if not args.db_path:
            build_parser().error("--db_path is required for generate-slips")
        mode_generate_slips(args.db_path)

    elif args.mode == "validate-slips":
        if not args.db_path:
            build_parser().error("--db_path is required for validate-slips")
        mode_validate_slips(args.db_path)