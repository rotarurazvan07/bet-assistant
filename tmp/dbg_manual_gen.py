import sys, tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "/a0/usr/projects/bet_assistant/bet_dashboard/backend")

from _pytest.monkeypatch import MonkeyPatch
from tests.logic_test_helpers import build_app

mp = MonkeyPatch()
tmp = Path(tempfile.mkdtemp())

now = datetime.now()
profiles = {
    "p1": {
        "target_odds": 2.0,
        "target_legs": 1,
        "consensus_floor": 50.0,
        "min_leg_odds": 1.05,
        "tolerance_factor": 0.30,
        "stop_threshold": 0.50,
        "odds_movement_weight": 0.0,
        "odds_movement_strength_min": 0.2,
        "units": 1.0,
        "run_daily_count": 1,
        "generate_hour": now.hour,
        "generate_minute": 0,
    }
}

env = build_app(tmp, mp, profiles=profiles)
app = env.app
print("cfg on disk      :", app._profile_cfg("p1"))
print("local_now        :", app._local_now())
print("container now    :", now)
print("is_active        :", __import__("core.logic", fromlist=["_profile_is_active"])._profile_is_active(app._profile_cfg("p1")))
print("schedule_met     :", app._profile_schedule_met("p1"))
print("is_due           :", app._is_profile_due("p1"))
print("active_profiles  :", list(app._get_active_profiles()))
print("manual generate  :", app.generate_and_broadcast())
app._assistant.conn.close()
app._matches_manager.close()
