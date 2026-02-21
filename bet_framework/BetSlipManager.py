import sqlite3
import math

import pandas as pd

class BetSlipManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
            """
            Returns a list of match names that MUST BE EXCLUDED from new slips.
            Rule 1: All settled matches (Won/Lost) are excluded forever.
            Rule 2: Pending matches are excluded ONLY IF their slip is still alive.
            """
            query = '''
                SELECT DISTINCT match_name
                FROM legs
                WHERE status IN ('Won', 'Lost')
                   OR (
                       status = 'Pending'
                       AND slip_id NOT IN (
                           SELECT slip_id
                           FROM legs
                           WHERE status = 'Lost'
                       )
                   )
            '''
            self.cursor.execute(query)
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching active matches: {e}")
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

    def _process_rows_to_slips(self, rows):
        """
        Helper to group raw SQL rows into a structured slip/legs dictionary.
        Logic:
        - Slip is 'Lost' if ANY leg is Lost.
        - Slip is 'Pending' if no legs are Lost but at least one is Pending.
        - Slip is 'Won' only if ALL legs are Won.
        """
        slips_data = {}

        for row in rows:
            # Match the order from your SELECT query:
            # s.slip_id, s.date_generated, s.risk_level, s.total_odds,
            # l.match_name, l.market, l.market_type, l.odds, l.status
            slip_id, date, risk, total_odds, match, market, market_type, odds, status = row

            if slip_id not in slips_data:
                slips_data[slip_id] = {
                    'slip_id': slip_id,
                    'date_generated': date,
                    'risk_level': risk,
                    'total_odds': total_odds,
                    'legs': [],
                    'slip_status': 'Won'  # Default to Won, will be downgraded by legs
                }

            # If the slip has a leg (LEFT JOIN might return null for legs)
            if match:
                slips_data[slip_id]['legs'].append({
                    'match_name': match,
                    'market': market,
                    'market_type': market_type,
                    'odds': odds,
                    'status': status
                })

                # Update Slip Status based on this leg
                # 1. If any leg is Lost, the entire slip is Lost (highest priority)
                if status == 'Lost':
                    slips_data[slip_id]['slip_status'] = 'Lost'

                # 2. If a leg is Pending, slip is Pending UNLESS another leg already marked it Lost
                elif status == 'Pending' and slips_data[slip_id]['slip_status'] != 'Lost':
                    slips_data[slip_id]['slip_status'] = 'Pending'

        return list(slips_data.values())

    def get_all_slips_with_legs(self, risk_filter=None):
        query = '''
            SELECT
                s.slip_id, s.date_generated, s.risk_level, s.total_odds,
                l.match_name, l.market, l.market_type, l.odds, l.status
            FROM slips s
            LEFT JOIN legs l ON s.slip_id = l.slip_id
        '''
        params = []
        if risk_filter and risk_filter != 'all':
            query += " WHERE s.risk_level = ?"
            params.append(risk_filter)

        query += " ORDER BY s.date_generated DESC, s.slip_id DESC"

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        # Use the helper to structure the data
        return self._process_rows_to_slips(rows)

    def get_historic_stats(self, risk_filter=None):
        """Calculates dynamic statistics including net totals (1 unit per bet)."""
        slips = self.get_all_slips_with_legs(risk_filter=risk_filter)

        total_settled = 0
        total_won_count = 0
        total_units_bet = len(slips)
        total_units_returned = 0 # Gross payout

        for slip in slips:
            if slip['slip_status'] in ['Won', 'Lost']:
                total_settled += 1

                if slip['slip_status'] == 'Won':
                    total_won_count += 1
                    total_units_returned += slip['total_odds']

        net_balance = total_units_returned - total_units_bet
        win_rate = (total_won_count / total_settled * 100) if total_settled > 0 else 0
        roi = (net_balance / total_units_bet * 100) if total_units_bet > 0 else 0

        return {
            'total_settled': total_settled,
            'total_won_count': total_won_count,
            'win_rate': round(win_rate, 2),
            'total_units_bet': total_units_bet,      # Total staked
            'total_units_won': round(total_units_returned, 2), # Gross Returns
            'net_balance': round(net_balance, 2),    # Final Profit/Loss
            'roi_percentage': round(roi, 2)
        }

    def close(self):
        self.conn.commit()
        self.conn.close()