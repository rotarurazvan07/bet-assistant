from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

from bet_framework.core.Slip import CandidateLeg
from bet_framework.core.types import MarketLabel, MarketType
from bet_framework.core.utils import is_valid_url
from core.schemas import ManualLegIn, SlipIn

router = APIRouter(prefix="/api/slips", tags=["slips"])


def _get(request: Request):
    return request.app.state.app_logic


def _enum_or_str(val):
    """Extract value from enum or return string representation."""
    if hasattr(val, 'value'):
        return val.value
    return str(val)


ALLOWED_MARKETS = {"1", "X", "2", "Over 2.5", "Under 2.5", "BTTS Yes", "BTTS No"}


def validate_manual_leg(leg: dict, logic) -> dict:
    """
    Validate a single manual leg dict against the current match DataFrame.

    Parameters
    ----------
    leg : dict
        The leg data to validate.
    logic : AppLogic
        The application logic instance providing access to match data.

    Returns
    -------
    {"valid": True} on success or {"valid": False, "error": str} on failure.
    """
    # 1 — match existence (fuzzy search on home/away)
    match_name = leg.get("match_name", "")
    df = logic.match_df
    # Try to split by known separators to match both home and away precisely
    separator = None
    if " - " in match_name:
        separator = " - "
    elif " vs " in match_name:
        separator = " vs "
    
    if separator:
        home_part, away_part = match_name.split(separator, 1)
        match_row = df[
            (df["home"].str.contains(home_part.strip(), case=False, na=False))
            & (df["away"].str.contains(away_part.strip(), case=False, na=False))
        ]
    else:
        # Fallback: fuzzy search in either home or away
        match_row = df[
            (df["home"].str.contains(match_name, case=False, na=False))
            | (df["away"].str.contains(match_name, case=False, na=False))
        ]
    if match_row.empty:
        return {"valid": False, "error": f"Match not found: {match_name}"}

    # 2 — market allow-list
    market_raw = leg.get("market", "")
    market = market_raw.value if hasattr(market_raw, "value") else str(market_raw)
    if market not in ALLOWED_MARKETS:
        return {
            "valid": False,
            "error": f"Invalid market '{market}'. Allowed: {sorted(ALLOWED_MARKETS)}",
        }

    # 3 — odds sanity
    odds = leg.get("odds")
    try:
        odds_val = float(odds)
        if odds_val <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return {"valid": False, "error": f"Invalid odds: {odds}"}

    # 4 — optional URL format
    url = leg.get("result_url")
    if url and not is_valid_url(url):
        return {"valid": False, "error": f"Invalid result_url: {url}"}

    return {"valid": True}

def _leg_to_dict(leg) -> dict:
    return {
        "match_name": leg.match_name,
        "datetime": leg.datetime.isoformat()
            if hasattr(leg.datetime, "isoformat")
            else str(leg.datetime) if leg.datetime else None,
        "market": _enum_or_str(leg.market),
        "market_type": _enum_or_str(leg.market_type) if leg.market_type else None,
        "odds": leg.odds,
        "status": _enum_or_str(leg.status),
        "result_url": leg.result_url,
    }


def _slip_to_dict(slip) -> dict:
    # Handle slip_status as enum or string
    status_val = slip.slip_status
    if hasattr(status_val, 'value'):
        status_val = status_val.value
    else:
        status_val = str(status_val)

    return {
        "slip_id": slip.slip_id,
        "date_generated": slip.date_generated,
        "profile": slip.profile,
        "total_odds": slip.total_odds,
        "units": slip.units,
        "slip_status": status_val,
        "legs": [_leg_to_dict(leg) for leg in slip.legs],
    }


def _dict_to_candidate_leg(d: dict) -> CandidateLeg:
    market_str = d.get("market", "1")
    mtype_str = d.get("market_type", "result")
    try:
        market = MarketLabel(market_str)
    except ValueError:
        market = market_str
    try:
        market_type = MarketType(mtype_str)
    except ValueError:
        market_type = MarketType.RESULT

    return CandidateLeg(
        match_name=d["match_name"],
        datetime=d.get("datetime"),
        market=market,
        market_type=market_type,
        consensus=d.get("consensus", 0.0),
        odds=d["odds"],
        result_url=d.get("result_url"),
        sources=d.get("sources", 0),
        tier=d.get("tier", 1),
        score=d.get("score", 0.0),
    )


@router.post("")
def add_slip(request: Request, body: SlipIn):
    app = _get(request)
    logic = app.logic

    # Validate every leg
    for leg in body.legs:
        leg_dict = leg.dict()
        result = validate_manual_leg(leg_dict, logic)
        if not result["valid"]:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=result["error"])

    # Convert to CandidateLeg objects
    legs = [_dict_to_candidate_leg(leg.dict()) for leg in body.legs]

    # Default profile to "manual" if not provided (already defaulted in schema)
    profile = body.profile or "manual"

    slip_id = app.save_slip_and_broadcast(profile, legs, body.units)
    return {"slip_id": slip_id}


@router.get("")
def get_slips(
    request: Request,
    profile: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    hide_settled: str | None = None,
    live_only: str | None = None,
):
    app = _get(request)
    logic = app.logic
    prof = None if profile in (None, "all") else profile

    # Coerce query params to booleans
    def to_bool(val):
        if val is None:
            return False
        return str(val).lower() in ("true", "1", "yes", "on")

    hide_settled_bool = to_bool(hide_settled)
    live_only_bool = to_bool(live_only)

    slips = logic.get_slips(prof, date_from or None, date_to or None)

    # Helper to get status string from enum or string
    def status_str(val):
        if hasattr(val, 'value'):
            return val.value
        return str(val)

    if hide_settled_bool:
        slips = [s for s in slips if status_str(s.slip_status) not in ("Won", "Lost")]
    if live_only_bool:
        slips = [
            s for s in slips
            if any(status_str(leg.status) in ("Live") for leg in s.legs)
        ]

    stats = logic.stats(prof, date_from or None, date_to or None)
    profile_names = sorted(
        p.stem for p in Path(app.config_path + "/profiles").glob("*.yaml")
    )
    profile_names.append("manual")

    return {
        "slips": [_slip_to_dict(s) for s in slips],
        "stats": stats,
        "profiles": profile_names,
    }




@router.post("/validate_manual")
def validate_manual(request: Request, legs: list[ManualLegIn]):
    """
    Validate a list of manual leg payloads without creating a slip.
    Returns per-leg validation results and an overall `all_valid` flag.
    """
    logic = _get(request).logic
    results = []
    for leg in legs:
        leg_dict = leg.dict()
        result = validate_manual_leg(leg_dict, logic)
        results.append(result)

    all_valid = all(r["valid"] for r in results)
    return {"legs": results, "all_valid": all_valid}


@router.delete("/{slip_id}")
def delete_slip(request: Request, slip_id: int):
    _get(request).delete_slip_and_broadcast(slip_id)
    return {"deleted": slip_id}


@router.post("/validate")
def validate_slips(request: Request):
    result = _get(request).validate_and_broadcast()
    live = [
        {
            "match_name": item.match_name,
            "score": item.score,
            "minute": item.minute,
        }
        for item in result.live
    ]
    return {
        "checked": result.checked,
        "settled": len(result.settled),
        "live": len(result.live),
        "errors": result.errors,
        "live_data": live,
    }


@router.post("/generate")
def generate_slips(request: Request):
    result = _get(request).generate_and_broadcast()
    total = sum(len(v) for v in result.values())
    return {
        "generated": total,
        "by_profile": {k: len(v) for k, v in result.items()},
    }
