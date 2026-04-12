from __future__ import annotations

from pydantic import BaseModel

# ── Builder ───────────────────────────────────────────────────────────────────


class BetSlipConfigIn(BaseModel):
    target_odds: float = 3.0
    target_legs: int = 3
    max_legs_overflow: int | None = None
    consensus_floor: float = 50.0
    min_odds: float = 1.05
    tolerance_factor: float | None = None
    stop_threshold: float | None = None
    min_legs_fill_ratio: float = 0.70
    quality_vs_balance: float = 0.5
    consensus_vs_sources: float = 0.5
    included_markets: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    # Advanced
    consensus_shrinkage_k: float | None = None
    min_source_edge: float = 0.0
    max_single_leg_odds: float | None = None
    tol_lower: float | None = None
    tol_upper: float | None = None
    balance_decay: str = "linear"
    min_pick_quality: float | None = None


class ExcludeUrlIn(BaseModel):
    url: str


class CandidateLegOut(BaseModel):
    match_name: str
    datetime: str | None = None
    market: str
    market_type: str  # Must match the market category (result, over_under_2.5, btts)
    consensus: float
    odds: float
    result_url: str | None = None
    sources: int
    tier: int = 1
    score: float = 0.0


class PreviewOut(BaseModel):
    legs: list[CandidateLegOut]
    total_odds: float
    pending_urls: list[str]


# ── Profiles ──────────────────────────────────────────────────────────────────


class ProfileIn(BaseModel):
    name: str
    target_odds: float = 3.0
    target_legs: int = 3
    max_legs_overflow: int | None = None
    consensus_floor: float = 50.0
    min_odds: float = 1.05
    tolerance_factor: float | None = None
    stop_threshold: float | None = None
    min_legs_fill_ratio: float = 0.70
    quality_vs_balance: float = 0.5
    consensus_vs_sources: float = 0.5
    included_markets: list[str] | None = None
    units: float = 1.0
    run_daily_count: int = 0
    # Advanced
    consensus_shrinkage_k: float | None = None
    min_source_edge: float = 0.0
    max_single_leg_odds: float | None = None
    tol_lower: float | None = None
    tol_upper: float | None = None
    balance_decay: str = "linear"
    min_pick_quality: float | None = None


# ── Slips ─────────────────────────────────────────────────────────────────────


class ManualLegIn(BaseModel):
    match_name: str
    market: str
    market_type: str
    odds: float
    result_url: str
    datetime: str  # ISO format datetime, required for filtering/sorting
    consensus: float  # 0-100 percentage, required for scoring
    sources: int  # number of sources, required for scoring


class SlipIn(BaseModel):
    profile: str = "manual"
    legs: list[ManualLegIn]
    units: float = 1.0


class BetLegOut(BaseModel):
    match_name: str
    datetime: str | None = None
    market: str
    market_type: str | None = None
    odds: float
    status: str
    result_url: str | None = None


class BetSlipOut(BaseModel):
    slip_id: int
    date_generated: str
    profile: str
    total_odds: float
    units: float
    legs: list[BetLegOut]
    slip_status: str


# ── Services ──────────────────────────────────────────────────────────────────


class ServicesSettingsIn(BaseModel):
    pull_hour: int
    generate_hour: int
