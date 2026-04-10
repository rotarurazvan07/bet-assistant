from __future__ import annotations

import math

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

    # Apply min_consensus filter if provided
    if min_consensus is not None and min_consensus > 0:
        consensus_cols = ["cons_home", "cons_draw", "cons_away", "cons_over", "cons_under", "cons_btts_yes", "cons_btts_no"]
        available_cols = [c for c in consensus_cols if c in df.columns]
        if available_cols:
            # Keep rows where at least one consensus column meets the threshold
            mask = df[available_cols].ge(min_consensus).any(axis=1)
            df = df[mask]

    if df.empty:
        return {
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 1,
            "matches": [],
        }

    valid = {
        "datetime",
        "home",
        "away",
        "sources",
        "cons_home",
        "cons_draw",
        "cons_away",
        "cons_over",
        "cons_under",
        "cons_btts_yes",
    }
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
