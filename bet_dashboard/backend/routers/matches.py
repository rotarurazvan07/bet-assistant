from __future__ import annotations

import math

from core.market_config import CONSENSUS_COLUMNS, MARKET_DEFINITIONS
from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _get(request: Request):
    return request.app.state.app_logic


def _clean(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _row_to_dict(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = _clean(v)
    return out


@router.get("")
def get_matches(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=100),
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = Query("datetime"),
    sort_dir: str = Query("asc"),
    min_consensus: int | None = Query(None, ge=0, le=100),
    min_odds: float | None = Query(None, ge=1.0, le=50.0),
):
    logic = _get(request).logic
    df = logic.filter_matches(
        search_text=search or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )

    if df.empty:
        return {
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 1,
            "matches": [],
        }

    # Apply combined min_consensus + min_odds filter
    has_cons = min_consensus is not None and min_consensus > 0
    has_odds = min_odds is not None and min_odds > 1.0
    if has_cons or has_odds:
        import pandas as pd
        mask = pd.Series(False, index=df.index)
        for md in MARKET_DEFINITIONS:
            if md.cons_key not in df.columns:
                continue
            cell_ok = pd.Series(True, index=df.index)
            if has_cons:
                cell_ok &= df[md.cons_key].ge(min_consensus)
            if has_odds and md.odds_key in df.columns:
                cell_ok &= df[md.odds_key].ge(min_odds)
            elif has_odds:
                cell_ok = pd.Series(False, index=df.index)
            mask |= cell_ok
        df = df[mask]

    if df.empty:
        return {
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 1,
            "matches": [],
        }

    valid = {"datetime", "home", "away", "sources"} | set(CONSENSUS_COLUMNS)
    col = sort_by if sort_by in valid and sort_by in df.columns else "datetime"
    df = df.sort_values(col, ascending=(sort_dir != "desc"), na_position="last")

    total = len(df)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    rows = [_row_to_dict(r) for r in df.iloc[start : start + page_size].to_dict("records")]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "matches": rows,
    }
