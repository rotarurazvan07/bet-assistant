"""
Bet assistant, 2022
"""

from bet_framework.DatabaseManager import DatabaseManager
from tippers.Tipper import Tipper

if __name__ == "__main__":
    db_manager = DatabaseManager()
    # TODO - clean database with older entries
    db_manager.reset_db()
    tipper = Tipper(db_manager)
    tipper.get_tips()
