import sqlite3
import math
import os

import pandas as pd

class BetSlipManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._file_mtime = os.path.getmtime(self.db_path)

        # Create Slips Table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS slips (
                slip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_generated TEXT,
                profile TEXT,
                total_odds REAL,
                units REAL DEFAULT 1.0
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

    def get_pending_result_urls(self):
        self.reopen_if_changed()
        try:
            """
            Returns a list of URLs that MUST BE EXCLUDED from new slips.
            Rule 1: All settled matches (Won/Lost) are excluded forever.
            Rule 2: Pending matches are excluded ONLY IF their slip is still alive.
            """
            query = '''
                SELECT DISTINCT result_url
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
            return [row[0] for row in self.cursor.fetchall() if row[0] is not None]
        except Exception as e:
            print(f"Error fetching active URLs: {e}")
            return []

    def insert_slip(self, profile, legs_list, units=1.0):
        """Inserts a parlay slip and all its individual legs."""
        # Calculate total odds (Product of all leg odds)
        total_odds = math.prod([leg['odds'] for leg in legs_list])
        date_today = pd.Timestamp.now().strftime('%Y-%m-%d')

        # Insert Slip
        self.cursor.execute(
            "INSERT INTO slips (date_generated, profile, total_odds, units) VALUES (?, ?, ?, ?)",
            (date_today, profile, total_odds, units)
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
            # s.slip_id, s.date_generated, s.profile, s.total_odds, s.units,
            # l.match_name, l.market, l.market_type, l.odds, l.status
            slip_id, date, profile, total_odds, units, match, market, market_type, odds, status, result_url = row

            if slip_id not in slips_data:
                slips_data[slip_id] = {
                    'slip_id': slip_id,
                    'date_generated': date,
                    'profile': profile,
                    'total_odds': total_odds,
                    'units': units,
                    'legs': [],
                    'slip_status': 'Won',  # Default to Won, will be downgraded by legs
                }

            # If the slip has a leg (LEFT JOIN might return null for legs)
            if match:
                slips_data[slip_id]['legs'].append({
                    'match_name': match,
                    'market': market,
                    'market_type': market_type,
                    'odds': odds,
                    'status': status,
                    'result_url': result_url
                })

                # Update Slip Status based on this leg
                # 1. If any leg is Lost, the entire slip is Lost (highest priority)
                if status == 'Lost':
                    slips_data[slip_id]['slip_status'] = 'Lost'

                # 2. If a leg is Pending, slip is Pending UNLESS another leg already marked it Lost
                elif status == 'Pending' and slips_data[slip_id]['slip_status'] != 'Lost':
                    slips_data[slip_id]['slip_status'] = 'Pending'

        return list(slips_data.values())

    def get_all_slips_with_legs(self, profile_filter=None):
        query = '''
            SELECT
                s.slip_id, s.date_generated, s.profile, s.total_odds, s.units,
                l.match_name, l.market, l.market_type, l.odds, l.status, l.result_url
            FROM slips s
            LEFT JOIN legs l ON s.slip_id = l.slip_id
        '''
        params = []
        if profile_filter and profile_filter != 'all':
            query += " WHERE s.profile = ?"
            params.append(profile_filter)

        query += " ORDER BY s.date_generated DESC, s.slip_id DESC"

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        # Use the helper to structure the data
        return self._process_rows_to_slips(rows)

    def get_historic_stats(self, profile_filter=None):
        """
        Calculates betting statistics on SETTLED slips only.

        Definitions:
        stakes          — total units placed on settled slips
        gross_return    — total units returned on winning slips (odds × units)
        net_profit      — gross_return - stakes  (can be negative)
        roi             — net_profit / stakes × 100
        win_rate        — won / settled × 100
        """
        slips = self.get_all_slips_with_legs(profile_filter=profile_filter)

        settled_slips = [s for s in slips if s['slip_status'] in ('Won', 'Lost')]
        won_slips     = [s for s in settled_slips if s['slip_status'] == 'Won']

        total_settled   = len(settled_slips)
        total_won_count = len(won_slips)

        stakes       = sum(s['units'] for s in settled_slips)
        gross_return = sum(s['total_odds'] * s['units'] for s in won_slips)
        net_profit   = gross_return - stakes

        win_rate = (total_won_count / total_settled * 100) if total_settled > 0 else 0.0
        roi      = (net_profit / stakes * 100)             if stakes > 0         else 0.0

        return {
            'total_settled':    total_settled,
            'total_won_count':  total_won_count,
            'win_rate':         round(win_rate, 2),      # % of settled slips won
            'total_units_bet':  round(stakes, 2),        # staked on settled slips only
            'gross_return':     round(gross_return, 2),  # gross return from winning slips
            'net_profit':       round(net_profit, 2),    # profit / loss (+ or -)
            'roi_percentage':   round(roi, 2),           # net profit as % of stakes
        }

    def get_balance_history(self, profile_filter=None):
        where = "WHERE s.profile = ?" if (profile_filter and profile_filter != "all") else ""
        params = [profile_filter] if where else []

        query = f'''
            SELECT
                s.date_generated, s.profile, s.total_odds, s.units,
                CASE
                    WHEN SUM(CASE WHEN l.status = 'Lost'    THEN 1 ELSE 0 END) > 0 THEN 'Lost'
                    WHEN SUM(CASE WHEN l.status = 'Pending' THEN 1 ELSE 0 END) > 0 THEN 'Pending'
                    ELSE 'Won'
                END AS slip_status
            FROM slips s
            LEFT JOIN legs l ON s.slip_id = l.slip_id
            {where}
            GROUP BY s.slip_id
            HAVING slip_status IN ('Won', 'Lost')
            ORDER BY s.date_generated ASC
        '''
        self.cursor.execute(query, params)
        return [
            {"date": r[0], "profile": r[1], "total_odds": r[2],
             "units": r[3], "status": r[4]}
            for r in self.cursor.fetchall()
        ]

    def get_per_profile_stats(self):
        query = '''
            SELECT
                s.profile,
                s.total_odds, s.units,
                CASE
                    WHEN SUM(CASE WHEN l.status = 'Lost'    THEN 1 ELSE 0 END) > 0 THEN 'Lost'
                    WHEN SUM(CASE WHEN l.status = 'Pending' THEN 1 ELSE 0 END) > 0 THEN 'Pending'
                    ELSE 'Won'
                END AS slip_status
            FROM slips s
            LEFT JOIN legs l ON s.slip_id = l.slip_id
            GROUP BY s.slip_id
            HAVING slip_status IN ('Won', 'Lost')
        '''
        self.cursor.execute(query)

        from collections import defaultdict
        agg = defaultdict(lambda: {"settled": 0, "won": 0, "stakes": 0.0, "gross": 0.0})

        for profile, total_odds, units, status in self.cursor.fetchall():
            agg[profile]["settled"] += 1
            agg[profile]["stakes"]  += units
            if status == "Won":
                agg[profile]["won"]   += 1
                agg[profile]["gross"] += total_odds * units

        result = {}
        for name, d in agg.items():
            net = d["gross"] - d["stakes"]
            result[name] = {
                "profile":    name,
                "settled":    d["settled"],
                "won":        d["won"],
                "win_rate":   round(d["won"] / d["settled"] * 100, 1) if d["settled"] else 0.0,
                "stakes":     round(d["stakes"], 2),
                "net_profit": round(net, 2),
                "roi":        round(net / d["stakes"] * 100, 1) if d["stakes"] else 0.0,
            }
        return result

    def get_market_type_stats(self, profile_filter=None):
        where = "AND s.profile = ?" if (profile_filter and profile_filter != "all") else ""
        params = [profile_filter] if where else []

        query = f'''
            SELECT l.market_type, l.market, l.status, COUNT(*) AS cnt
            FROM legs l
            JOIN slips s ON l.slip_id = s.slip_id
            WHERE l.status IN ('Won', 'Lost')
            {where}
            GROUP BY l.market_type, l.market, l.status
        '''
        self.cursor.execute(query, params)
        return [
            {"market_type": r[0], "market": r[1], "status": r[2], "count": r[3]}
            for r in self.cursor.fetchall()
        ]

    def get_settled_legs_with_urls(self, profile_filter=None):
        where = "AND s.profile = ?" if (profile_filter and profile_filter != "all") else ""
        params = [profile_filter] if where else []

        query = f'''
            SELECT l.result_url, l.status
            FROM legs l
            JOIN slips s ON l.slip_id = s.slip_id
            WHERE l.status IN ('Won', 'Lost') AND l.result_url IS NOT NULL
            {where}
        '''
        self.cursor.execute(query, params)
        return [{"result_url": r[0], "status": r[1]} for r in self.cursor.fetchall()]

    # to be called by who uses this (dashboard, in a heartbeat thread or something!)
    def reopen_if_changed(self):
        """
        Check if the database file has been replaced on disk.
        If the mtime changed, close the old connection and open a fresh one.
        """
        try:
            current_mtime = os.path.getmtime(self.db_path)
        except OSError:
            return  # file temporarily unavailable, do nothing

        if current_mtime == self._file_mtime:
            return  # nothing changed

        print(f"[BetSlipManager] File change detected ({self.db_path}), reopening connection...")

        # Close the old connection
        try:
            self.conn.close()
        except Exception:
            pass

        # Open a new connection
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._file_mtime = current_mtime

        print("[BetSlipManager] Reopened successfully.")

    def close(self):
        self.conn.commit()
        self.conn.close()
