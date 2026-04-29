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


def calc_consensus(scores: list) -> dict[str, dict[str, float]]:
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
    from scrape_kit import get_logger

    logger = get_logger(__name__)

    empty: dict[str, dict[str, float]] = {
        "result": {"home": 0.0, "draw": 0.0, "away": 0.0},
        "over_under_25": {"over": 0.0, "under": 0.0},
        "over_under_15": {"over": 0.0, "under": 0.0},
        "over_under_05": {"over": 0.0, "under": 0.0},
        "over_under_35": {"over": 0.0, "under": 0.0},
        "over_under_45": {"over": 0.0, "under": 0.0},
        "btts": {"yes": 0.0, "no": 0.0},
        "double_chance": {"1x": 0.0, "12": 0.0, "x2": 0.0},
    }
    if not scores:
        return empty

    total = len(scores)
    home_w = draw_w = away_w = 0
    over_25 = under_25 = 0
    over_15 = under_15 = 0
    over_05 = under_05 = 0
    over_35 = under_35 = 0
    over_45 = under_45 = 0
    btts_y = btts_n = 0
    dc_1x = dc_12 = dc_x2 = 0

    try:
        for s in scores:
            h = s.get("home", 0) or 0
            a = s.get("away", 0) or 0

            if h > a:
                home_w += 1
            elif h < a:
                away_w += 1
            else:
                draw_w += 1

            if h + a > 2.5:
                over_25 += 1
            else:
                under_25 += 1

            if h + a > 1.5:
                over_15 += 1
            else:
                under_15 += 1

            if h + a > 0.5:
                over_05 += 1
            else:
                under_05 += 1

            if h + a > 3.5:
                over_35 += 1
            else:
                under_35 += 1

            if h + a > 4.5:
                over_45 += 1
            else:
                under_45 += 1

            if h > 0 and a > 0:
                btts_y += 1
            else:
                btts_n += 1

            # Double chance calculations
            if h >= a:  # Home win or draw (1X)
                dc_1x += 1
            if h != a:  # Either team wins (12)
                dc_12 += 1
            if a >= h:  # Away win or draw (X2)
                dc_x2 += 1

    except Exception as e:
        logger.info(f"[consensus] Calculation error: {e}")
        return empty

    return {
        "result": {
            "home": to_pct(home_w, total),
            "draw": to_pct(draw_w, total),
            "away": to_pct(away_w, total),
        },
        "over_under_25": {
            "over": to_pct(over_25, total),
            "under": to_pct(under_25, total),
        },
        "over_under_15": {
            "over": to_pct(over_15, total),
            "under": to_pct(under_15, total),
        },
        "over_under_05": {
            "over": to_pct(over_05, total),
            "under": to_pct(under_05, total),
        },
        "over_under_35": {
            "over": to_pct(over_35, total),
            "under": to_pct(under_35, total),
        },
        "over_under_45": {
            "over": to_pct(over_45, total),
            "under": to_pct(under_45, total),
        },
        "btts": {
            "yes": to_pct(btts_y, total),
            "no": to_pct(btts_n, total),
        },
        "double_chance": {
            "1x": to_pct(dc_1x, total),
            "12": to_pct(dc_12, total),
            "x2": to_pct(dc_x2, total),
        },
    }
