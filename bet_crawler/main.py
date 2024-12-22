"""
Bet assistant, 2022
"""
from bet_framework.DatabaseManager import DatabaseManager
from value_finder.ValueFinder import ValueFinder

if __name__ == "__main__":
    db_manager = DatabaseManager()
    # # TODO - clean database with older entries
    # db_manager.reset_tips_db()
    # tipper = Tipper(db_manager)
    # tipper.get_tips()
    #
    db_manager.reset_value_matches_db()
    value_finder = ValueFinder(db_manager)
    value_finder.find_value_matches()