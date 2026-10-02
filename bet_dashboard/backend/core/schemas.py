"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel

# ── Builder ───────────────────────────────────────────────────────────────────


class BetSlipConfigIn(BaseModel):
    """Builder config payload for preview requests."""

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
    included_leagues: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    excluded_sources: list[str] | None = None
    # Advanced
    consensus_shrinkage_k: float | None = None
    min_source_edge: float | None = None
    max_single_leg_odds: float | None = None
    tol_lower: float | None = None
    tol_upper: float | None = None
    balance_decay: str = "linear"
    min_pick_quality: float | None = None
    odds_movement_weight: float | None = None
    odds_movement_strength_min: float | None = None


class ExcludeUrlIn(BaseModel):
    """URL payload for exclusion endpoints."""

    url: str


class CandidateLegOut(BaseModel):
    """Response model for one builder candidate leg."""

    match_name: str
    datetime: str | None = None
    market: str
    market_type: str  # Must match the market category (result, over_under_2.5, btts)
    consensus: float
    odds: float
    result_url: str | None = None
    league: str | None = None
    sources: int
    tier: int = 1
    score: float = 0.0
    odds_movement_direction: str | None = None
    odds_movement_strength: float = 0.0
    predictions: list[dict] = []


class PreviewOut(BaseModel):
    """Response model for the builder preview result."""

    legs: list[CandidateLegOut]
    total_odds: float
    pending_urls: list[str]


# ── Profiles ──────────────────────────────────────────────────────────────────


class ProfileIn(BaseModel):
    """Payload for saving a named builder profile."""

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
    included_leagues: list[str] | None = None
    excluded_sources: list[str] | None = None
    units: float = 1.0
    target_payout: float | None = None
    run_daily_count: int = 0
    # Advanced
    consensus_shrinkage_k: float | None = None
    min_source_edge: float | None = None
    max_single_leg_odds: float | None = None
    tol_lower: float | None = None
    tol_upper: float | None = None
    balance_decay: str = "linear"
    min_pick_quality: float | None = None
    odds_movement_weight: float | None = None
    odds_movement_strength_min: float | None = None


# ── Slips ─────────────────────────────────────────────────────────────────────


class ManualLegIn(BaseModel):
    """One manually-built leg in an add-slip payload."""

    match_name: str
    market: str
    market_type: str
    odds: float
    result_url: str
    datetime: str  # ISO format datetime, required for filtering/sorting
    consensus: float  # 0-100 percentage, required for scoring
    sources: int  # number of sources, required for scoring
    league: str | None = None
    predictions: list[dict] | None = None  # Per-source predictions for source reliability tracking


class SlipIn(BaseModel):
    """Payload for adding a slip (profile, legs, units)."""

    profile: str = "manual"
    legs: list[ManualLegIn]
    units: float = 1.0


class BetLegOut(BaseModel):
    """Response model for one slip leg."""

    match_name: str
    datetime: str | None = None
    market: str
    market_type: str | None = None
    odds: float
    status: str
    result_url: str | None = None
    league: str | None = None
    predictions: list[dict] = []


class BetSlipOut(BaseModel):
    """Response model for one slip with its legs."""

    slip_id: int
    date_generated: str
    profile: str
    total_odds: float
    units: float
    legs: list[BetLegOut]
    slip_status: str


# ── Services ──────────────────────────────────────────────────────────────────


class ServicesSettingsIn(BaseModel):
    """Payload for service scheduler settings."""

    generate_hour: int
    generate_minute: int = 0


# ── Odds History ──────────────────────────────────────────────────────────────


class OddsSnapshotOut(BaseModel):
    """Response model for an odds snapshot."""

    timestamp: str  # ISO datetime when snapshot was captured
    odds: dict  # Full odds object {home, draw, away, over_25, under_25, ...}


class OddsHistoryOut(BaseModel):
    """Response model for odds history rows."""

    match_id: int
    match_name: str
    datetime: str
    snapshots: list[OddsSnapshotOut]
    movement: dict  # {market: "up"|"down"|"stable"} for each odds field


class OddsMovementSummary(BaseModel):
    """Per-market odds movement directions and strengths."""

    home: str | None = None  # "up", "down", "stable", or None
    draw: str | None = None
    away: str | None = None
    over_05: str | None = None
    under_05: str | None = None
    over_15: str | None = None
    under_15: str | None = None
    over_25: str | None = None
    under_25: str | None = None
    over_35: str | None = None
    under_35: str | None = None
    over_45: str | None = None
    under_45: str | None = None
    btts_yes: str | None = None
    btts_no: str | None = None
    dc_1x: str | None = None
    dc_12: str | None = None
    dc_x2: str | None = None
