import sqlite3
import sys

db = sys.argv[1]
batch = sys.argv[2]  # 'legacy' | 'unknown'
conn = sqlite3.connect(db)
conn.executescript(
    """
CREATE TABLE IF NOT EXISTS slips (slip_id INTEGER PRIMARY KEY AUTOINCREMENT);
CREATE TABLE IF NOT EXISTS legs (
    leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    slip_id INTEGER, match_name TEXT, match_datetime TEXT,
    market TEXT, market_type TEXT, odds REAL, result_url TEXT,
    status TEXT DEFAULT 'Pending', league TEXT, predictions TEXT, final_score TEXT
);
"""
)
if batch == 'legacy':
    rows = [
        ('BTTS Yes', 'btts', 2.10),
        ('Over 2.5', 'over_under_25', 1.95),
        ('1', 'result', 1.50),
        ('X2', 'double_chance', 2.02),
        ('12', 'double_chance', 1.35),
        ('btts_no', 'btts', 3.10),
        ('dc_1x', 'double_chance', 1.25),
        ('home', 'result', 1.44),
    ]
else:
    rows = [('1', 'result', 1.5), ('WEIRD-MARKET', 'btts', 9.99)]
conn.executemany('INSERT INTO legs (market, market_type, odds) VALUES (?,?,?)', rows)
conn.commit()
conn.close()
print(f'seeded {len(rows)} rows ({batch})')
