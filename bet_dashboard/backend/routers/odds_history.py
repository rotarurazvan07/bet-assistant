"""Odds movement API (issue #105: sourced from movement_change_pp)."""

from core.schemas import OddsMovementSummary
from fastapi import APIRouter, Request

from bet_dashboard.backend.core.market_config import MARKET_DEFINITIONS

router = APIRouter(prefix="/api/odds-history", tags=["odds-history"])


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
                summary_kwargs = {
                    md.odds_key.replace("odds_", ""): movement.get(md.odds_key.replace("odds_", ""))
                    for md in MARKET_DEFINITIONS
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
    from datetime import datetime

    now = datetime.utcnow()
    result = {}
    for idx, row in df.iterrows():
        match_dt = row.get("datetime")
        if match_dt and match_dt > now:
            strength = logic.get_odds_movement_with_strength(idx)
            if not strength:
                continue
            sig_count = sum(1 for v in strength.values() if isinstance(v, dict) and v.get("significant"))
            if sig_count == 0:
                continue
            match_id = row.get("match_id", str(idx))
            result[match_id] = strength
    return result


# ── Single-match movement endpoint ─────────────────────────────────────────


@router.get("/{match_id}/movement", response_model=OddsMovementSummary)
def get_match_movement(request: Request, match_id: int):
    """Get just the movement summary for a match."""
    logic = _get(request).logic
    movement = logic.get_odds_movement(match_id)

    # Build OddsMovementSummary dynamically from MARKET_DEFINITIONS
    summary_kwargs = {
        md.odds_key.replace("odds_", ""): movement.get(md.odds_key.replace("odds_", "")) for md in MARKET_DEFINITIONS
    }
    return OddsMovementSummary(**summary_kwargs)
