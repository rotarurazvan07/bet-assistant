"""
bet_framework.core.Slip
────────────────────────
Data models for bet slips, legs, and match result information.

This module contains only dataclasses, named profiles, and the profile
accessor. No I/O, no database, no scraping.

Public surface
──────────────
  CandidateLeg        — raw candidate pick before selection
  MatchResultInfo     — parsed HTML scrape result
  LegOutcomeInfo      — evaluation record after settling
  BetLeg              — stored leg record with ID and status
  BetSlip             — stored slip aggregate with nested legs
  BetSlipConfig       — slip-builder configuration
  PROFILES            — built-in named risk profiles
  get_profile(name)   → BetSlipConfig
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from bet_framework.core.types import MarketLabel, MarketType, MatchStatus, Outcome

# ── Candidate / Match / Leg data models ───────────────────────────────────────


@dataclass
class CandidateLeg:
    """
    A single candidate pick before scoring and selection.
    """

    match_name: str
    datetime: Any  # pandas.Timestamp or datetime
    market: MarketLabel
    market_type: MarketType
    consensus: float  # Must be provided, no default
    odds: float
    result_url: str
    sources: int  # Must be provided, no default
    tier: int = 1  # UI only: 1=balanced, 2=drift
    score: float = 0.0  # UI only: quality score


@dataclass
class MatchResultInfo:
    """
    Standardized representation of a parsed live or full-time match result.
    """

    status: MatchStatus
    score: str = ""
    minute: str = ""


@dataclass
class LegOutcomeInfo:
    """
    Details about a leg after outcome evaluation.
    """

    leg_id: int
    match_name: str
    market: MarketLabel
    score: str
    minute: str = ""
    outcome: Outcome | str = ""


@dataclass
class ValidationReport:
    """
    Summary of a validation run, containing checked count, settled legs, live legs, and error count.
    """

    checked: int
    settled: list[LegOutcomeInfo]
    live: list[LegOutcomeInfo]
    errors: int


@dataclass
class BetLeg:
    """
    Representation of a leg that has been saved to the database.
    """

    match_name: str
    datetime: Any  # ISO format or datetime
    market: MarketLabel
    market_type: MarketType
    odds: float
    status: Outcome
    result_url: str


@dataclass
class BetSlip:
    """
    A completed bet slip containing one or more legs.
    """

    slip_id: int
    date_generated: str
    profile: str
    total_odds: float
    units: float
    legs: list[BetLeg] = field(default_factory=list)
    slip_status: Outcome = Outcome.PENDING


# ── Slip configuration ────────────────────────────────────────────────────────


@dataclass
class BetSlipConfig:
    """
    Full configuration for the slip builder.

    ┌─ SCOPE ──────────────────────────────────────────────────────────────────┐
    │ date_from / date_to        ISO 'YYYY-MM-DD' window. None = no limit.     │
    │ excluded_urls              result_urls to skip entirely.                 │
    │ included_markets           None = all; or list of labels (1, X, 2, etc). │
    ├─ SHAPE ──────────────────────────────────────────────────────────────────┤
    │ target_odds      [1.10–1000]  Desired cumulative odds.                   │
    │ target_legs      [1–10]       Desired number of legs.                    │
    │ max_legs_overflow[0–5]        Extra legs allowed beyond target.          │
    ├─ QUALITY GATE ───────────────────────────────────────────────────────────┤
    │ consensus_floor    [0–100]   Minimum source agreement percentage.        │
    │ min_odds           [1.01–10] Minimum bookmaker odds (filters near-certs).│
    ├─ ODDS TOLERANCE ─────────────────────────────────────────────────────────┤
    │ tolerance_factor   [0.05–0.80] ±band around ideal per-leg odds.          │
    │                              None = auto-derived.                        │
    ├─ STOP CONDITION ─────────────────────────────────────────────────────────┤
    │ stop_threshold     [0.50–1.00] Stop when odds ≥ target × this.          │
    │                                None = auto-derived.                      │
    │ min_legs_fill_ratio[0.50–1.00] Min fraction of legs before early stop.  │
    ├─ SCORING ────────────────────────────────────────────────────────────────┤
    │ quality_vs_balance [0–1]  0 = balance only, 1 = quality only.           │
    │ consensus_vs_sources [0–1]  Within quality: 0 = sources, 1 = consensus. │
    ├─ ADVANCED ────────────────────────────────────────────────────────────────┤
    │ consensus_shrinkage_k [1.0–10.0] Source-weighted consensus adjustment.    │
    │                              None = auto (3.0).                          │
    │ min_source_edge       [0.0–0.50] Minimum edge over implied probability.  │
    │ max_single_leg_odds   [1.0–10.0] Maximum odds for any single leg.        │
    │                              None = auto (3.5).                          │
    │ tol_lower             [0.01–1.00] Lower tolerance band (below ideal).    │
    │ tol_upper             [0.01–1.00] Upper tolerance band (above ideal).    │
    │                              None = auto (tol_lower=tol, tol_upper=tol*0.6)│
    │ balance_decay         ["linear", "gaussian"] Decay function for balance. │
    │ min_pick_quality      [0.0–1.00] Minimum quality score to accept a pick. │
    │                              None = auto (0.20).                         │
    └──────────────────────────────────────────────────────────────────────────┘
    """

    # Scope
    date_from: str | None = None
    date_to: str | None = None
    excluded_urls: list[str] | None = None
    included_markets: list[str] | None = None

    # Shape
    target_odds: float = 3.0
    target_legs: int = 3
    max_legs_overflow: int | None = None

    # Quality gate
    consensus_floor: float = 50.0
    min_odds: float = 1.05

    # Odds tolerance
    tolerance_factor: float | None = None

    # Stop condition
    stop_threshold: float | None = None
    min_legs_fill_ratio: float = 0.70

    # Scoring weights
    quality_vs_balance: float = 0.5
    consensus_vs_sources: float = 0.5

    # Advanced
    consensus_shrinkage_k: float | None = None
    min_source_edge: float = 0.0
    max_single_leg_odds: float | None = None
    tol_lower: float | None = None
    tol_upper: float | None = None
    balance_decay: str = "linear"
    min_pick_quality: float | None = None

    def __post_init__(self) -> None:
        self.target_odds = max(1.10, min(1000.0, self.target_odds))
        self.target_legs = max(1, min(100, self.target_legs))
        self.consensus_floor = max(0.0, min(100.0, self.consensus_floor))
        self.min_odds = max(1.01, min(10.0, self.min_odds))
        self.min_legs_fill_ratio = max(0.50, min(1.00, self.min_legs_fill_ratio))
        self.quality_vs_balance = max(0.0, min(1.0, self.quality_vs_balance))
        self.consensus_vs_sources = max(0.0, min(1.0, self.consensus_vs_sources))

        if self.tolerance_factor is not None:
            self.tolerance_factor = max(0.05, min(0.80, self.tolerance_factor))
        if self.stop_threshold is not None:
            self.stop_threshold = max(0.50, min(1.00, self.stop_threshold))
        if self.max_legs_overflow is not None:
            self.max_legs_overflow = max(0, min(5, self.max_legs_overflow))

        # Advanced validation
        if self.consensus_shrinkage_k is not None:
            self.consensus_shrinkage_k = max(1.0, min(10.0, self.consensus_shrinkage_k))
        self.min_source_edge = max(0.0, min(0.50, self.min_source_edge))
        if self.max_single_leg_odds is not None:
            self.max_single_leg_odds = max(1.0, min(10.0, self.max_single_leg_odds))
        if self.tol_lower is not None:
            self.tol_lower = max(0.01, min(1.00, self.tol_lower))
        if self.tol_upper is not None:
            self.tol_upper = max(0.01, min(1.00, self.tol_upper))
        if self.balance_decay not in ("linear", "gaussian"):
            self.balance_decay = "linear"
        if self.min_pick_quality is not None:
            self.min_pick_quality = max(0.0, min(1.00, self.min_pick_quality))


# ── Built-in risk profiles ────────────────────────────────────────────────────

PROFILES: dict[str, BetSlipConfig] = {
    # Short-odds doubles — tight balance, high confidence
    "low_risk": BetSlipConfig(
        target_odds=2.0,
        target_legs=2,
        consensus_floor=65.0,
        min_odds=1.10,
        quality_vs_balance=0.35,
        consensus_vs_sources=0.60,
        tolerance_factor=0.20,
        stop_threshold=0.95,
        min_legs_fill_ratio=0.80,
        included_markets=["1", "2", "X", "BTTS Yes", "BTTS No"],
    ),
    # Balanced 3-leg accumulator
    "medium_risk": BetSlipConfig(
        target_odds=5.0,
        target_legs=3,
        consensus_floor=50.0,
        quality_vs_balance=0.50,
        consensus_vs_sources=0.50,
    ),
    # Longer accumulator, quality over odds precision
    "high_risk": BetSlipConfig(
        target_odds=15.0,
        target_legs=5,
        consensus_floor=50.0,
        quality_vs_balance=0.70,
        consensus_vs_sources=0.50,
        min_legs_fill_ratio=0.60,
    ),
    # Well-sourced picks with a minimum price floor
    "value_hunter": BetSlipConfig(
        target_odds=8.0,
        target_legs=4,
        consensus_floor=52.0,
        min_odds=1.30,
        quality_vs_balance=0.65,
        consensus_vs_sources=0.30,
        min_legs_fill_ratio=0.65,
    ),
}


def get_profile(name: str) -> BetSlipConfig:
    """Return a deep copy of a named built-in profile.

    Raises ValueError for unknown profile names.
    """
    if name not in PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Available: {list(PROFILES)}")
    return copy.deepcopy(PROFILES[name])
