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

from bs4 import BeautifulSoup
from bet_crawler.ScorePredictorFinder import ScorePredictorFinder, SCOREPREDICTOR_NAME
from bet_crawler.SoccerVistaFinder import SoccerVistaFinder, SOCCERVISTA_NAME
from bet_crawler.WhoScoredFinder import WhoScoredFinder, WHOSCORED_NAME

from bet_crawler.WinDrawWinFinder import WinDrawWinFinder, WINDRAWWIN_NAME
from bet_crawler.ForebetFinder import ForebetFinder, FOREBET_NAME
from bet_crawler.VitibetFinder import VitibetFinder, VITIBET_NAME
from bet_crawler.PredictzFinder import PredictzFinder, PREDICTZ_NAME
from bet_crawler.FootballBettingTipsFinder import FootballBettingTipsFinder

from bet_framework.BettingAnalyzer import BettingAnalyzer
from bet_framework.DatabaseManager import DatabaseManager
from bet_framework.SettingsManager import settings_manager
from bet_framework.BetSlipManager import BetSlipManager
from bet_framework.WebScraper import WebScraper

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
        choices=["prepare-scrape", "scrape", "merge", "generate-slips", "validate-slips"],
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
    elif args.mode == "generate-slips":
        db_manager = DatabaseManager(args.db_path)
        analyzer = BettingAnalyzer(db_manager)
        analyzer.refresh_data()
        db_manager.close()

        bet_slip_manager = BetSlipManager(os.path.join(os.path.dirname(args.db_path), "slips.db"))
        active_matches = bet_slip_manager.get_pending_match_names()
        low_slip = analyzer.generate_bet_slip_low_risk(exclude_matches=active_matches)
        med_slip = analyzer.generate_bet_slip_medium_risk(exclude_matches=active_matches)
        high_slip = analyzer.generate_bet_slip_high_risk(exclude_matches=active_matches)
        for label, slip in [("Low", low_slip), ("Medium", med_slip), ("High", high_slip)]:
            if slip:
                print(slip)
                bet_slip_manager.insert_slip(label, slip)
                print(f"Successfully saved {label} risk slip.")
    elif args.mode == "validate-slips":
        bet_slip_manager = BetSlipManager(args.db_path)
        pending_legs = bet_slip_manager.get_legs_to_validate()

        if not pending_legs:
            print("No pending matches to validate.")
        else:
            print(f"Validating {len(pending_legs)} matches...")

            for leg_id, url, market, market_type in pending_legs:
                scraper = WebScraper()
                html = scraper.fast_http_request(url)
                soup = BeautifulSoup(html, 'html.parser')

                def get_final_score(soup):
                    status_container = soup.find(id="status-container")
                    if "FT" in status_container.get_text(strip=True):
                        score_div = soup.find('div', class_='text-base font-bold min-sm:text-xl text-center')
                        if score_div:
                            return score_div.get_text(strip=True)
                    return None

                final_score = get_final_score(soup)
                outcome = "Pending"
                if final_score is not None:
                    home = int(final_score.split(":")[0])
                    away = int(final_score.split(":")[1])
                    if market_type == "result":
                        if market == "1"   and home > away: outcome = "Won"
                        elif market == "2" and away > home: outcome = "Won"
                        elif market == "X" and away == home: outcome = "Won"
                        else: outcome = "Lost"
                    elif market_type == "btts":
                        if market == "BTTS Yes"  and (home > 0 and away > 0): outcome = "Won"
                        elif market == "BTTS No" and (home == 0 or away == 0): outcome = "Won"
                        else: outcome = "Lost"
                    elif market_type == "over_under_2.5":
                        if market == "Over 2.5"    and home + away >= 3: outcome = "Won"
                        elif market == "Under 2.5" and home + away < 3: outcome = "Won"
                        else: outcome = "Lost"

                if outcome != "Pending":
                    bet_slip_manager.update_leg_status(leg_id, outcome)
                    print(f"Updated Leg {leg_id} to {outcome}")
                else:
                    print(f"Match at {url} still in progress or result not found.")

        bet_slip_manager.close()