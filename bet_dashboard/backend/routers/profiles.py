"""Profiles API: list, save and delete builder profiles."""

from core.config_helpers import _config_to_yaml_dict
from core.schemas import ProfileIn
from fastapi import APIRouter, HTTPException, Request

from bet_framework.core.Slip import BetSlipConfig

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _get(request: Request):
    """Dependency: yield the shared AppLogic instance."""
    return request.app.state.app_logic


@router.get("")
def list_profiles(request: Request):
    """Return all saved builder profiles."""
    app = _get(request)
    profiles = app.settings.get("profiles") or {}
    return {"profiles": profiles}


@router.post("")
def save_profile(request: Request, body: ProfileIn):
    """Persist a named builder profile.

    Scheduling/ordering keys (run_daily_count, order, auto_generate,
    generate_hour, generate_minute) are tri-state in the payload: when the
    caller omits them, the values already persisted for this profile are
    carried over instead of being reset. That keeps a Smart Builder save from
    silently wiping a schedule configured on the Services page (review F1).
    """
    app = _get(request)
    name = "".join(c for c in body.name if c.isalnum() or c in ("_", "-")).lower()
    if not name:
        raise HTTPException(400, "Invalid profile name")

    existing = (app.settings.get("profiles") or {}).get(name, {})

    # Use shared helper to convert ProfileIn to YAML dict
    data = _config_to_yaml_dict(
        BetSlipConfig(
            target_odds=body.target_odds,
            target_legs=body.target_legs,
            max_legs_overflow=body.max_legs_overflow,
            consensus_floor=body.consensus_floor,
            min_odds=body.min_odds,
            tolerance_factor=body.tolerance_factor,
            stop_threshold=body.stop_threshold,
            min_legs_fill_ratio=body.min_legs_fill_ratio,
            quality_vs_balance=body.quality_vs_balance,
            consensus_vs_sources=body.consensus_vs_sources,
            included_markets=body.included_markets,
            included_leagues=body.included_leagues,
            excluded_sources=body.excluded_sources,
            # Advanced
            consensus_shrinkage_k=body.consensus_shrinkage_k,
            min_source_edge=body.min_source_edge,
            max_single_leg_odds=body.max_single_leg_odds,
            tol_lower=body.tol_lower,
            tol_upper=body.tol_upper,
            balance_decay=body.balance_decay,
            min_pick_quality=body.min_pick_quality,
            odds_movement_weight=body.odds_movement_weight,
            odds_movement_strength_min=body.odds_movement_strength_min,
        ),
        units=body.units,
        target_payout=body.target_payout,
        run_daily_count=body.run_daily_count,
        order=body.order,
        auto_generate=body.auto_generate,
        generate_hour=body.generate_hour,
        generate_minute=body.generate_minute,
    )
    # Omitted scheduling keys keep their persisted values; unknown keys on
    # disk are carried over so future additions are not dropped.
    for key in (
        "run_daily_count",
        "order",
        "auto_generate",
        "generate_hour",
        "generate_minute",
    ):
        if key not in data and key in existing:
            data[key] = existing[key]
    for key, value in existing.items():
        data.setdefault(key, value)
    app.settings.write(name, data, subpath="profiles")
    return {"name": name, "data": data}


@router.delete("/{name}")
def delete_profile(request: Request, name: str):
    """Delete a named builder profile."""
    _get(request).settings.delete(name, subpath="profiles")
    return {"deleted": name}
