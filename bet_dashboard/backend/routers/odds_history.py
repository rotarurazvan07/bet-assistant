from __future__ import annotations

from core.schemas import OddsHistoryOut, OddsMovementSummary, OddsSnapshotOut
from fastapi import APIRouter, HTTPException, Request

from bet_dashboard.backend.core.market_config import MARKET_DEFINITIONS

router = APIRouter(prefix="/api/odds-history", tags=["odds-history"])


def _get(request: Request):
    return request.app.state.app_logic


# ── Bulk endpoint (MUST be before /{match_id} to avoid route conflict) ─────


@router.get("/movements/all")
def get_all_movements(request: Request) -> dict[str, OddsMovementSummary]:
    """Get movement summary for all future matches."""
    logic = _get(request).logic
    df = logic.match_df

    if df.empty:
        return {}

    from datetime import datetime

    now = datetime.utcnow()
    result = {}

    for idx, row in df.iterrows():
        match_dt = row.get("datetime")
        if match_dt and match_dt > now:
            movement = logic.get_odds_movement(idx)
            match_id = row.get("match_id", str(idx))
            if movement:
                # Build OddsMovementSummary dynamically from MARKET_DEFINITIONS
                summary_kwargs = {md.odds_key: movement.get(md.odds_key) for md in MARKET_DEFINITIONS}
                result[match_id] = OddsMovementSummary(**summary_kwargs)

    return result


# ── Single-match endpoints ─────────────────────────────────────────────────


@router.get("/{match_id}", response_model=OddsHistoryOut)
def get_match_odds_history(request: Request, match_id: int):
    """Get full odds history for a specific match."""
    logic = _get(request).logic

    # Get match info from the database
    df = logic.match_df
    if df.empty:
        raise HTTPException(status_code=404, detail="No matches available")

    # Find the match by ID (rowid in SQLite)
    # Note: match_id corresponds to the row index in the buffer
    if match_id < 0 or match_id >= len(df):
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    match_row = df.iloc[match_id]
    match_name = f"{match_row.get('home', '')} vs {match_row.get('away', '')}"
    match_datetime = match_row.get("datetime", "")
    if hasattr(match_datetime, "isoformat"):
        match_datetime = match_datetime.isoformat()

    # Get history and movement
    history = logic.get_odds_history(match_id)
    movement = logic.get_odds_movement(match_id)

    snapshots = [OddsSnapshotOut(timestamp=h["timestamp"], odds=h["odds"] or {}) for h in history]

    return OddsHistoryOut(
        match_id=match_id,
        match_name=match_name,
        datetime=str(match_datetime),
        snapshots=snapshots,
        movement=movement,
    )


@router.get("/{match_id}/movement", response_model=OddsMovementSummary)
def get_match_movement(request: Request, match_id: int):
    """Get just the movement summary for a match."""
    logic = _get(request).logic
    movement = logic.get_odds_movement(match_id)

    # Build OddsMovementSummary dynamically from MARKET_DEFINITIONS
    summary_kwargs = {md.odds_key: movement.get(md.odds_key) for md in MARKET_DEFINITIONS}
    return OddsMovementSummary(**summary_kwargs)
