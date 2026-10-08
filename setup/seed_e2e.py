"""Seed the CI e2e stack's matches.db with the demo matches (PR #94).

Runs ONLY as the one-shot ``e2e-seed`` service in setup/compose.e2e.yaml,
against that compose project's throwaway named volume — never against a real
workspace (workspace/data/*.db stays a pipeline output per AGENTS.md).

Why: the E2E specs skip installDemoApi when E2E_BASE_URL is set, so the CI
stack itself must serve the demo rows. Two jobs:

1. Insert the 3 demo matches from
   bet_dashboard/frontend/e2e/fixtures/demo-data.ts. The real stack derives
   consensus by voting (bet_framework.core.consensus.calc_consensus), so
   prediction scores are crafted to reproduce the spec-asserted cells:
     Arsenal   75% home @1.90 — 3/4 home votes, 4 sources
     Liverpool 42/28/30 @2.40/3.20/2.90 — 21/14/15 of 50 votes, 5 sources
     Barcelona 38/26/36 @2.70/3.30/2.50 — 19/13/18 of 50 votes, 6 sources
2. Park the puller/generator/verifier daemons via services.yaml so the seeded
   rows survive the whole playwright run — the puller would otherwise merge
   the upstream prod DB on its first 5-minute tick and evict the past-dated
   Arsenal row mid-run.

Rows are written with plain sqlite3 into the ``matches`` table that
MatchesManager creates. The read path (MatchesManager.fetch_matches →
BetAssistant → calc_consensus) is exactly what the app serves, and it is the
only path the dashboard uses; ``add_match()`` is crawler-only and its
scrape-kit signature moved between versions, so the seed deliberately avoids
it rather than coupling to a crawler-only API.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

# Container: /app (image WORKDIR). Local runs: repo root next to setup/.
_APP_ROOT = os.environ.get("E2E_SEED_APP_ROOT", "/app")
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(
    0, _APP_ROOT if Path(_APP_ROOT, "bet_framework").is_dir() else _REPO_ROOT
)

from bet_framework.core.Match import Odds, Score
from bet_framework.MatchesManager import MatchesManager

MATCHES_DB = os.environ.get("MATCHES_DB_PATH", "/app/workspace/data/matches.db")
CONFIG_DIR = Path(os.environ.get("CONFIG_PATH", "/app/workspace/config"))
_SRC_CONFIG = (
    Path(_APP_ROOT, "config")
    if Path(_APP_ROOT, "config").is_dir()
    else Path(_REPO_ROOT, "config")
)

# Demo prediction sources — real finder names so the Sources filter and
# /api/config/sources stay coherent on the seeded stack.
_S5 = ["forebet", "predictz", "scorepredictor", "vitibet", "windrawwin"]
_S6 = _S5 + ["eaglepredict"]


def _votes(score: tuple[int, int], count: int, sources: list[str]) -> list[Score]:
    """Build ``count`` predictions of one score pair, round-robin over sources."""
    return [
        Score(source=sources[i % len(sources)], home=score[0], away=score[1])
        for i in range(count)
    ]


def _odds(**overrides) -> dict:
    """Odds mirroring the Vitest makeMatch() defaults plus spec overrides."""
    base = {
        "home": 1.9,
        "draw": 3.4,
        "away": 4.2,
        "over_05": 1.1,
        "under_05": 8.0,
        "over_15": 1.3,
        "under_15": 3.2,
        "over_25": 1.8,
        "under_25": 2.0,
        "over_35": 2.8,
        "under_35": 1.4,
        "over_45": 5.5,
        "under_45": 1.1,
        "btts_y": 1.9,
        "btts_n": 1.9,
        "dc_1x": 1.2,
        "dc_12": 1.3,
        "dc_x2": 1.5,
    }
    base.update(overrides)
    return asdict(Odds(**base))


# (home, away, datetime, predictions, odds, result_url, league)
DEMO_MATCHES = [
    (
        "Arsenal",
        "Chelsea",
        "2026-09-25T15:00:00",
        [
            Score("forebet", 2, 1),
            Score("predictz", 2, 0),
            Score("scorepredictor", 3, 1),
            Score("vitibet", 1, 1),
        ],
        _odds(),
        "https://example.com/match/1",
        "England",
    ),
    (
        "Liverpool",
        "Man City",
        "2026-10-07T18:00:00",
        _votes((2, 1), 21, _S5) + _votes((1, 1), 14, _S5) + _votes((1, 2), 15, _S5),
        _odds(home=2.4, draw=3.2, away=2.9),
        "https://example.com/match/2",
        "England",
    ),
    (
        "Barcelona",
        "Real Madrid",
        "2026-10-08T20:45:00",
        _votes((2, 1), 19, _S6) + _votes((1, 1), 13, _S6) + _votes((1, 2), 18, _S6),
        _odds(home=2.7, draw=3.3, away=2.5),
        "https://example.com/match/3",
        "Spain",
    ),
]

# All three daemons parked: puller would merge the upstream DB (evicting the
# past-dated Arsenal row), generator/verifier would touch slips mid-run.
_SERVICES_YAML = (
    "services:\n"
    "  generate_hour: 9\n"
    "  generate_minute: 0\n"
    "  toggles:\n"
    "    puller: false\n"
    "    generator: false\n"
    "    verifier: false\n"
)

_INSERT = (
    "INSERT INTO matches "
    "(home_team_name, away_team_name, datetime, predictions_scores, odds, result_url, league) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)


def main() -> None:
    """Seed matches.db + park daemons, then self-check the exact spec values."""
    Path(MATCHES_DB).parent.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # First boot of a fresh volume: lay down the pristine config the main
    # container normally copies (start-dashboard.sh re-copies at boot; `cp`
    # never prunes, so services.yaml below survives that copy).
    if not any(CONFIG_DIR.iterdir()):
        shutil.copytree(_SRC_CONFIG, CONFIG_DIR, dirs_exist_ok=True)
    (CONFIG_DIR / "services.yaml").write_text(_SERVICES_YAML, encoding="utf-8")

    # MatchesManager creates the `matches` schema on init; then write rows.
    MatchesManager(MATCHES_DB)
    conn = sqlite3.connect(MATCHES_DB)
    try:
        conn.execute("DELETE FROM matches")
        for home, away, dt, preds, odds, url, league in DEMO_MATCHES:
            scores = json.dumps(
                [{"source": s.source, "home": s.home, "away": s.away} for s in preds]
            )
            conn.execute(
                _INSERT, (home, away, dt, scores, json.dumps(odds), url, league)
            )
        conn.commit()
    finally:
        conn.close()

    # Self-check through a FRESH manager (proves persistence) plus the same
    # consensus the app computes — fails the compose service loudly on drift.
    from bet_framework.core.consensus import calc_consensus

    df = MatchesManager(MATCHES_DB).fetch_matches()
    assert len(df) == 3, f"expected 3 seeded matches, got {len(df)}"
    by_home = {row["home_name"]: row for _, row in df.iterrows()}
    assert by_home["Arsenal"]["odds"]["home"] == 1.9
    assert by_home["Liverpool"]["odds"]["home"] == 2.4
    assert by_home["Barcelona"]["odds"]["home"] == 2.7
    for name, expected in (("Arsenal", 75.0), ("Liverpool", 42.0), ("Barcelona", 38.0)):
        cons = calc_consensus(by_home[name]["scores"])
        assert cons["result"]["home"] == expected, (
            f"{name}: cons_home {cons['result']['home']} != {expected}"
        )
    print(
        f"e2e seed OK: 3 demo matches in {MATCHES_DB}; daemons parked in {CONFIG_DIR / 'services.yaml'}"
    )


if __name__ == "__main__":
    main()
