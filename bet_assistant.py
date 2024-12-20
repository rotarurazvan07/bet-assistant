"""
Bet assistant, 2022
"""
import asyncio

from src.DatabaseManager import DatabaseManager
from src.Tipper import Tipper

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    db_manager = DatabaseManager()
    # TODO - clean database with older entries
    db_manager.reset_db()
    tipper = Tipper(db_manager)
    tipper.get_tips()
