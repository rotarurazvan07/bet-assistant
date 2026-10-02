"""
bet_framework.core.consensus
─────────────────────────────
Pure functions for aggregating multiple predicted scores into consensus
percentages across result, over/under, and BTTS markets.

No state, no database, no configuration.

Public surface
──────────────
  to_pct(n, total)       → float
  calc_consensus(scores) → dict
"""

from __future__ import annotations


def to_pct(n: int, total: int) -> float:
    """Convert a count *n* to a percentage of *total*, rounded to 1 d.p.

    >>> to_pct(2, 4)
    50.0
    >>> to_pct(0, 0)
    0.0
    """
    return round((n / total) * 100, 1) if total else 0.0


def calc_consensus(scores: list[dict]) -> dict[str, dict[str, float]]:
    """
    Derive result / over-under / BTTS consensus percentages from a list of
    historical predicted score dicts.

    Each dict in *scores* must have 'home' and 'away' keys (int or float).
    An optional 'source' key is used externally for source counting.

    Returns
    -------
    {
        "result":         {"home": float, "draw": float, "away": float},
        "over_under_25": {"over": float, "under": float},
        "over_under_15": {"over": float, "under": float},
        "btts":           {"yes": float, "no": float},
    }
    All values are percentages in the range [0.0, 100.0].
    """
    counts = _count_votes(scores)
    if counts is None:
        return _empty_consensus()
    return _pct_map(counts, len(scores))


def _empty_consensus() -> dict[str, dict[str, float]]:
    """Return the zeroed consensus skeleton for all markets."""
    return {
        "result": {"home": 0.0, "draw": 0.0, "away": 0.0},
        "over_under_25": {"over": 0.0, "under": 0.0},
        "over_under_15": {"over": 0.0, "under": 0.0},
        "over_under_05": {"over": 0.0, "under": 0.0},
        "over_under_35": {"over": 0.0, "under": 0.0},
        "over_under_45": {"over": 0.0, "under": 0.0},
        "btts": {"yes": 0.0, "no": 0.0},
        "double_chance": {"1x": 0.0, "12": 0.0, "x2": 0.0},
    }


def _tally_double_chance(h, a, counts: dict) -> None:
    """Increment the double-chance vote counters for one score pair."""
    if h >= a:
        counts["dc_1x"] += 1
    if h != a:
        counts["dc_12"] += 1
    if a >= h:
        counts["dc_x2"] += 1


def _count_votes(scores: list[dict]):
    """Tally per-market votes across all scores; None signals malformed input."""
    from scrape_kit import get_logger

    logger = get_logger(__name__)
    counts = {
        "home_w": 0,
        "draw_w": 0,
        "away_w": 0,
        "over_25": 0,
        "under_25": 0,
        "over_15": 0,
        "under_15": 0,
        "over_05": 0,
        "under_05": 0,
        "over_35": 0,
        "under_35": 0,
        "over_45": 0,
        "under_45": 0,
        "btts_y": 0,
        "btts_n": 0,
        "dc_1x": 0,
        "dc_12": 0,
        "dc_x2": 0,
    }
    try:
        for s in scores:
            h = s.get("home", 0) or 0
            a = s.get("away", 0) or 0

            if h > a:
                counts["home_w"] += 1
            elif h < a:
                counts["away_w"] += 1
            else:
                counts["draw_w"] += 1

            for key, threshold in (
                ("over_25", 2.5),
                ("over_15", 1.5),
                ("over_05", 0.5),
                ("over_35", 3.5),
                ("over_45", 4.5),
            ):
                if h + a > threshold:
                    counts[key] += 1
                else:
                    counts["under_" + key.split("_")[1]] += 1

            if h > 0 and a > 0:
                counts["btts_y"] += 1
            else:
                counts["btts_n"] += 1

            _tally_double_chance(h, a, counts)
    except Exception as e:
        logger.info(f"[consensus] Calculation error: {e}")
        return None
    return counts


def _pct_map(counts: dict, total: int) -> dict[str, dict[str, float]]:
    """Build the consensus percentage map from raw vote counts."""
    return {
        "result": {
            "home": to_pct(counts["home_w"], total),
            "draw": to_pct(counts["draw_w"], total),
            "away": to_pct(counts["away_w"], total),
        },
        "over_under_25": {
            "over": to_pct(counts["over_25"], total),
            "under": to_pct(counts["under_25"], total),
        },
        "over_under_15": {
            "over": to_pct(counts["over_15"], total),
            "under": to_pct(counts["under_15"], total),
        },
        "over_under_05": {
            "over": to_pct(counts["over_05"], total),
            "under": to_pct(counts["under_05"], total),
        },
        "over_under_35": {
            "over": to_pct(counts["over_35"], total),
            "under": to_pct(counts["under_35"], total),
        },
        "over_under_45": {
            "over": to_pct(counts["over_45"], total),
            "under": to_pct(counts["under_45"], total),
        },
        "btts": {
            "yes": to_pct(counts["btts_y"], total),
            "no": to_pct(counts["btts_n"], total),
        },
        "double_chance": {
            "1x": to_pct(counts["dc_1x"], total),
            "12": to_pct(counts["dc_12"], total),
            "x2": to_pct(counts["dc_x2"], total),
        },
    }
