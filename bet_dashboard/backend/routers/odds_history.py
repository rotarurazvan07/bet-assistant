"""Odds history API: snapshots and movements per match."""

from datetime import datetime
import logging

from core.schemas import OddsHistoryOut, OddsMovementSummary, OddsSnapshotOut
from fastapi import APIRouter, HTTPException, Request

from bet_framework.markets.catalog import MARKET_CATALOG
from bet_framework.markets.keys import stripped_key

router = APIRouter(prefix="/api/odds-history", tags=["odds-history"])
logger = logging.getLogger(__name__)


def _get(request: Request):
    """Dependency: yield the shared AppLogic instance."""
    return request.app.state.app_logic


# ── Bulk endpoint (MUST be before /{match_id} to avoid route conflict) ─────


@router.get("/movements/all")
def get_all_movements(request: Request) -> dict[str, OddsMovementSummary]:
    """Get movement summary for all future matches."""
    logic = _get(request).logic
    df = logic.match_df

    if df.empty:
        return {}

    # Compute 'now' in the configured local timezone as naive datetime
    # to match DB storage (naive wall-clock in config local_timezone)
    tz = logic._local_tz()
    now = datetime.now(tz).replace(tzinfo=None)

    result = {}
    for pos, row in enumerate(df.itertuples(index=False)):
        match_dt = getattr(row, "datetime", None)
        if match_dt and match_dt > now:
            movement = logic.get_odds_movement(pos)
            match_id = getattr(row, "match_id", None)
            if not match_id:
                logger.warning(
                    f"Skipping row at position {pos}: missing match_id"
                )
                continue
            if movement:
                summary_kwargs = {
                    stripped_key(md.odds_key): movement.get(stripped_key(md.odds_key))
                    for md in MARKET_CATALOG
                }
                result[match_id] = OddsMovementSummary(**summary_kwargs)

    return result


@router.get("/movements/significant")
def get_significant_movements(request: Request) -> dict:
    """Movement data with strength metrics, filtered to significant only."""
    logic = _get(request).logic
    df = logic.match_df
    if df.empty:
        return {}

    tz = logic._local_tz()
    now = datetime.now(tz).replace(tzinfo=None)

    result = {}
    for pos, row in enumerate(df.itertuples(index=False)):
        match_dt = getattr(row, "datetime", None)
        if match_dt and match_dt > now:
            strength = logic.get_odds_movement_with_strength(pos)
            if not strength:
                continue
            sig_count = sum(
                1
                for v in strength.values()
                if isinstance(v, dict) and v.get("significant")
            )
            if sig_count == 0:
                continue
            match_id = getattr(row, "match_id", None)
            if not match_id:
                logger.warning(
                    f"Skipping row at position {pos}: missing match_id"
                )
                continue
            result[match_id] = strength
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

    snapshots = [
        OddsSnapshotOut(timestamp=h["timestamp"], odds=h["odds"] or {}) for h in history
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

    # Build OddsMovementSummary dynamically from MARKET_CATALOG
    summary_kwargs = {
        stripped_key(md.odds_key): movement.get(stripped_key(md.odds_key))
        for md in MARKET_CATALOG
    }
    return OddsMovementSummary(**summary_kwargs)
