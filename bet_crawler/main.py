"""
Bet assistant, 2022
"""
from bet_crawler.tippers.Tipper import Tipper
from bet_framework.DatabaseManager import DatabaseManager
from bet_framework.SettingsManager import settings_manager
from value_finder.ValueFinder import ValueFinder

if __name__ == "__main__":
    settings_manager.load_settings("config/config.yaml")
    db_manager = DatabaseManager()

    #db_manager.reset_matches_db()

    #value_finder = ValueFinder(db_manager)
    #value_finder.get_value_matches()

    tipper = Tipper(db_manager)
    tipper.get_tips()