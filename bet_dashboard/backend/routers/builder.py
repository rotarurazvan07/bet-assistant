from __future__ import annotations

import math

from core.schemas import BetSlipConfigIn, ExcludeUrlIn
from fastapi import APIRouter, Request

from bet_framework.core.Slip import BetSlipConfig

router = APIRouter(prefix="/api/builder", tags=["builder"])


def _get(request: Request):
    return request.app.state.app_logic


def _to_config(body: BetSlipConfigIn) -> BetSlipConfig:
    return BetSlipConfig(
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
        date_from=body.date_from,
        date_to=body.date_to,
        # Advanced
        consensus_shrinkage_k=body.consensus_shrinkage_k,
        min_source_edge=body.min_source_edge,
        max_single_leg_odds=body.max_single_leg_odds,
        tol_lower=body.tol_lower,
        tol_upper=body.tol_upper,
        balance_decay=body.balance_decay,
        min_pick_quality=body.min_pick_quality,
    )


@router.post("/preview")
def preview(request: Request, body: BetSlipConfigIn):
    app = _get(request)
    cfg = _to_config(body)
    legs = app.build_preview(cfg)
    total_odds = math.prod(leg.odds for leg in legs) if legs else 1.0
    pending_urls = list(app.logic.get_pending_urls())

    return {
        "total_odds": round(total_odds, 4),
        "pending_urls": pending_urls,
        "legs": [
            {
                "match_name": leg.match_name,
                "datetime": leg.datetime.isoformat()
                if hasattr(leg.datetime, "isoformat")
                else str(leg.datetime)
                if leg.datetime
                else None,
                "market": leg.market.value,
                "market_type": leg.market_type.value if hasattr(leg.market_type, "value") else str(leg.market_type),
                "consensus": leg.consensus,
                "odds": leg.odds,
                "result_url": leg.result_url,
                "sources": leg.sources,
                "tier": leg.tier,
                "score": round(leg.score, 4),
            }
            for leg in legs
        ],
    }


@router.get("/excluded")
def get_excluded(request: Request):
    return {"excluded": _get(request).get_manual_excluded()}


@router.get("/excluded/details")
def get_excluded_details(request: Request):
    """Get detailed info about manually excluded matches only."""
    app = _get(request)
    # Only return manually excluded URLs
    excluded_urls = app.get_manual_excluded()

    # Get match details from the matches database
    matches = app.logic.match_df
    details = []

    for url in excluded_urls:
        if url and not url.startswith("http"):
            continue
        match_row = matches[matches["result_url"] == url]
        if not match_row.empty:
            row = match_row.iloc[0]
            details.append(
                {
                    "url": url,
                    "match_name": f"{row['home']} vs {row['away']}",
                    "datetime": row["datetime"].isoformat() if hasattr(row["datetime"], "isoformat") else str(row["datetime"]),
                    "reason": "Manually excluded",
                }
            )
        else:
            details.append(
                {
                    "url": url,
                    "match_name": url.split("/")[-1] if url else "Unknown",
                    "datetime": None,
                    "reason": "Manually excluded",
                }
            )

    return {"excluded": details}


@router.post("/excluded")
def add_excluded(request: Request, body: ExcludeUrlIn):
    _get(request).add_excluded(body.url)
    return {"excluded": _get(request).get_manual_excluded()}


@router.post("/excluded/remove")
def remove_excluded(request: Request, body: ExcludeUrlIn):
    _get(request).remove_excluded(body.url)
    return {"excluded": _get(request).get_manual_excluded()}


@router.delete("/excluded")
def clear_excluded(request: Request):
    _get(request).clear_excluded()
    return {"excluded": []}
