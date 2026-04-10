from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from bet_framework.core.Slip import BetSlipConfig
from core.schemas import ProfileIn
from core.config_helpers import _config_to_yaml_dict

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _get(request: Request):
    return request.app.state.app_logic


@router.get("")
def list_profiles(request: Request):
    app = _get(request)
    profiles = app.settings.get("profiles") or {}
    return {"profiles": profiles}


@router.post("")
def save_profile(request: Request, body: ProfileIn):
    app = _get(request)
    name = "".join(c for c in body.name if c.isalnum() or c in ("_", "-")).lower()
    if not name:
        raise HTTPException(400, "Invalid profile name")

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
        ),
        units=body.units,
        run_daily_count=body.run_daily_count,
    )
    app.settings.write(name, data, subpath="profiles")
    return {"name": name, "data": data}


@router.delete("/{name}")
def delete_profile(request: Request, name: str):
    _get(request).settings.delete(name, subpath="profiles")
    return {"deleted": name}
