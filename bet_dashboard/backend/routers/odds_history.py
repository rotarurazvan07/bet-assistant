from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from core.schemas import OddsHistoryOut, OddsMovementSummary, OddsSnapshotOut

router = APIRouter(prefix="/api/odds-history", tags=["odds-history"])


def _get(request: Request):
    return request.app.state.app_logic


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

    snapshots = [
        OddsSnapshotOut(timestamp=h["timestamp"], odds=h["odds"] or {})
        for h in history
    ]

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

    return OddsMovementSummary(
        home=movement.get("home"),
        draw=movement.get("draw"),
        away=movement.get("away"),
        over_25=movement.get("over_25"),
        under_25=movement.get("under_25"),
        btts_y=movement.get("btts_y"),
        btts_n=movement.get("btts_n"),
    )


@router.get("/movements/all")
def get_all_movements(request: Request) -> dict[int, OddsMovementSummary]:
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
            if movement:
                result[idx] = OddsMovementSummary(
                    home=movement.get("home"),
                    draw=movement.get("draw"),
                    away=movement.get("away"),
                    over_25=movement.get("over_25"),
                    under_25=movement.get("under_25"),
                    btts_y=movement.get("btts_y"),
                    btts_n=movement.get("btts_n"),
                )

    return result