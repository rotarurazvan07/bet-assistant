import sqlite3
import math

import pandas as pd

class BetSlipManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Create Slips Table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS slips (
                slip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_generated TEXT,
                risk_level TEXT,
                total_odds REAL
            )
        ''')

        # Create Legs Table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS legs (
                leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                slip_id INTEGER,
                match_name TEXT,
                market TEXT,
                market_type TEXT,
                odds REAL,
                result_url TEXT,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY(slip_id) REFERENCES slips(slip_id)
            )
        ''')
        self.conn.commit()

    def get_pending_match_names(self):
        try:
            """Returns a set of 'Home vs Away' strings for active matches."""
            self.cursor.execute("SELECT match_name FROM legs WHERE status = 'Pending'")
            # Returns a set like {'RB Leipzig vs Borussia Dortmund', 'Celtic vs Hibernian'}
            return [row[0] for row in self.cursor.fetchall()]
        except Exception:
            return []

    def insert_slip(self, risk_level, legs_list):
        """Inserts a parlay slip and all its individual legs."""
        # Calculate total odds (Product of all leg odds)
        total_odds = math.prod([leg['odds'] for leg in legs_list])
        date_today = pd.Timestamp.now().strftime('%Y-%m-%d')

        # Insert Slip
        self.cursor.execute(
            "INSERT INTO slips (date_generated, risk_level, total_odds) VALUES (?, ?, ?)",
            (date_today, risk_level, total_odds)
        )
        slip_id = self.cursor.lastrowid

        # Insert Legs
        for leg in legs_list:
            self.cursor.execute('''
                INSERT INTO legs (slip_id, match_name, market, market_type, odds, result_url)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (slip_id, leg['match'], leg['market'], leg['market_type'], leg['odds'], leg['result_url']))

        self.conn.commit()
        return slip_id

    def get_legs_to_validate(self):
        """Fetches all legs that are still pending for the validation loop."""
        self.cursor.execute("SELECT leg_id, result_url, market, market_type FROM legs WHERE status = 'Pending'")
        return self.cursor.fetchall()

    def update_leg_status(self, leg_id, status):
        """Updates a leg outcome."""
        self.cursor.execute("UPDATE legs SET status = ? WHERE leg_id = ?", (status, leg_id))
        self.conn.commit()

    def close(self):
        self.conn.close()