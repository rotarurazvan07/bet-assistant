import argparse
from collections import defaultdict
from contextlib import redirect_stdout
import json
import math
import os
import sys
import time
import random
from urllib.parse import urlparse
from bet_crawler.ScorePredictorFinder import ScorePredictorFinder, SCOREPREDICTOR_NAME
from bet_crawler.SoccerVistaFinder import SoccerVistaFinder, SOCCERVISTA_NAME
from bet_crawler.WhoScoredFinder import WhoScoredFinder, WHOSCORED_NAME

from bet_crawler.WinDrawWinFinder import WinDrawWinFinder, WINDRAWWIN_NAME
from bet_crawler.ForebetFinder import ForebetFinder, FOREBET_NAME
from bet_crawler.VitibetFinder import VitibetFinder, VITIBET_NAME
from bet_crawler.PredictzFinder import PredictzFinder, PREDICTZ_NAME
from bet_crawler.FootballBettingTipsFinder import FootballBettingTipsFinder

from bet_framework.DatabaseManager import DatabaseManager
from bet_framework.SettingsManager import settings_manager

ACTION_RUNNERS = [
    # ForebetFinder,
    VitibetFinder,
    WinDrawWinFinder,
    ScorePredictorFinder,
    PredictzFinder,
    # WhoScoredFinder,
    SoccerVistaFinder,
]
LOCAL_RUNNERS = [
    ForebetFinder,
    WhoScoredFinder
]

MAX_GITHUB_RUNNERS = 200

def get_class_by_url(url):
    if SCOREPREDICTOR_NAME.lower() in url.lower():
        return ScorePredictorFinder
    if SOCCERVISTA_NAME.lower() in url.lower():
        return SoccerVistaFinder
    if WHOSCORED_NAME.lower() in url.lower():
        return WhoScoredFinder
    if WINDRAWWIN_NAME.lower() in url.lower():
        return WinDrawWinFinder
    if FOREBET_NAME.lower() in url.lower():
        return ForebetFinder
    if VITIBET_NAME.lower() in url.lower():
        return VitibetFinder
    if PREDICTZ_NAME.lower() in url.lower():
        return PredictzFinder

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Match Finder Scraper")
    parser.add_argument(
        "--mode",
        choices=["prepare-scrape", "scrape", "merge"],
        required=True,
        help="The phase of the workflow to execute"
    )
    parser.add_argument("--db_path", help="Path to the SQLite database file (e.g., matches.db)")
    parser.add_argument("--urls", help="Urls to scrape", default="")
    parser.add_argument("--chunks_dir", help="Where are the chunk stored", default=".")
    parser.add_argument("--runners", help="Which runner", choices=["actions", "local"], default="")

    args = parser.parse_args()
    settings_manager.load_settings("config")


    if args.mode == "prepare-scrape":
        finders = ACTION_RUNNERS if args.runners == "actions" else LOCAL_RUNNERS if args.runners == "local" else []
        urls = []
        with open(os.devnull, 'w') as f:
            with redirect_stdout(f):
                for match_finder in finders:
                    mf = match_finder(None)
                    try:
                        urls.append(mf.get_matches_urls())
                    except Exception:
                        pass
                    finally:
                        del mf
        urls = [item for sublist in urls for item in sublist]
        random.shuffle(urls)

        CHUNK_SIZE = max(20, math.ceil(len(urls) / MAX_GITHUB_RUNNERS))

        all_tasks = []
        for i in range(0, len(urls), CHUNK_SIZE):
            chunk = urls[i : i + CHUNK_SIZE]
            all_tasks.append({
                "db_path": f"{args.runners}-{i // CHUNK_SIZE + 1}.db",
                "urls": ",".join(chunk)
            })
        print(json.dumps(all_tasks))
    elif args.mode == "scrape":
        if not args.urls or not args.db_path:
            parser.error("requires --urls and --db_path")
            sys.exit(1)
        urls = [u.strip() for u in args.urls.split(',')]
        groups = defaultdict(list)
        for url in urls:
            domain = urlparse(url).netloc
            core_name = domain.split('.')[-2] if len(domain.split('.')) > 1 else domain
            groups[core_name].append(url)
        list_of_lists = list(groups.values())

        db_manager = DatabaseManager(args.db_path)
        db_manager.reset_matches_db()
        def _add_match_callback(match):
            db_manager.add_match(match)

        for i, group in enumerate(list_of_lists):
            print(f"Group {i+1} ({urlparse(group[0]).netloc}):")
            finder = get_class_by_url(group[0])(_add_match_callback)
            finder.get_matches(group)
            del finder

        db_manager.close()
    elif args.mode == "merge":
        if not args.chunks_dir or not args.db_path or not os.path.isdir(args.chunks_dir):
            print(f"❌ Error: {args.chunks_dir} is not a valid directory.")
            sys.exit(1)
        db_manager = DatabaseManager(args.db_path)
        db_manager.reset_matches_db()
        db_manager.merge_databases(args.chunks_dir)
        db_manager.close()
