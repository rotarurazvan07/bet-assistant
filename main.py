import argparse
import sys

from bet_crawler.ScorePredictorFinder import ScorePredictorFinder
from bet_crawler.SoccerVistaFinder import SoccerVistaFinder
from bet_crawler.WhoScoredFinder import WhoScoredFinder
from bet_framework.DatabaseManager import DatabaseManager
from bet_framework.SettingsManager import settings_manager

from bet_crawler.WinDrawWinFinder import WinDrawWinFinder
from bet_crawler.ForebetFinder import ForebetFinder
from bet_crawler.VitibetFinder import VitibetFinder
from bet_crawler.PredictzFinder import PredictzFinder
from bet_crawler.FootballBettingTipsFinder import FootballBettingTipsFinder

class MatchFinder:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def _add_match_callback(self, match):
        self.db_manager.add_match(match)

    def get_matches(self):
        match_finders = [
            # More comprehensive websites first - db_manager doesnt update everything
            ForebetFinder(self._add_match_callback),
            VitibetFinder(self._add_match_callback),
            WinDrawWinFinder(self._add_match_callback),
            # Strictly for tips, below (lacks a lot of data)
            ScorePredictorFinder(self._add_match_callback),
            PredictzFinder(self._add_match_callback),
            # FootballBettingTipsFinder(self._add_match_callback), # TODO Cloudflare problems
            WhoScoredFinder(self._add_match_callback),
            SoccerVistaFinder(self._add_match_callback), # TODO - this has a lot more matches
        ]

        for match_finder in match_finders:
            match_finder.get_matches()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Match Finder Scraper")
    parser.add_argument("db_path", help="Path to the SQLite database file (e.g., matches.db)")
    args = parser.parse_args()
    settings_manager.load_settings("config")

    db_manager = DatabaseManager(args.db_path)

    db_manager.reset_matches_db()

    match_finder = MatchFinder(db_manager)
    match_finder.get_matches()

    db_manager.close()

    print(f"✅ Scrape complete. Database saved to: {args.db_path}")
