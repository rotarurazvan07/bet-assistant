"""
bet_framework.core.scoring
───────────────────────────
Pure functions for scoring and ranking candidate picks against a BetSlipConfig.

No state, no database, no I/O — all inputs are plain Python values.

Public surface
──────────────
  resolve_tolerance(cfg)                         → float
  resolve_stop_threshold(cfg)                    → float
  resolve_max_legs(cfg)                          → int
  resolve_shrinkage_k(cfg)                       → float
  resolve_max_single_leg_odds(cfg)               → float
  resolve_min_pick_quality(cfg)                  → float
  resolve_min_source_edge(cfg)                   → float
  score_consensus(consensus, cfg)                → float
  score_sources(sources, max_sources)            → float
  score_balance(odds, ideal, tolerance, cfg)     → float
  score_pick(opt, ideal_odds, max_sources, cfg)  → (int, float, float)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bet_framework.core.Slip import BetSlipConfig, CandidateLeg

# ── Constants ──────────────────────────────────────────────────────────────────

TOLERANCE_EXCESS_LAMBDA = 8.0
_TOL_BASE = 0.15
_TOL_DAMPING = 0.25
_STOP_BASE = 0.88
_STOP_ADJUSTMENT = 0.10


# ── Config resolvers ──────────────────────────────────────────────────────────


def resolve_tolerance(cfg: BetSlipConfig) -> float:
    """Auto-derive per-leg odds tolerance. Formula: base × (1 + damping / legs)."""
    if cfg.tolerance_factor is not None:
        return cfg.tolerance_factor
    tolerance = _TOL_BASE * (1 + _TOL_DAMPING / cfg.target_legs)
    return round(max(0.10, min(0.50, tolerance)), 4)


def resolve_stop_threshold(cfg: BetSlipConfig) -> float:
    """Auto-derive early-stop threshold. Formula: BASE + ADJUSTMENT / legs."""
    if cfg.stop_threshold is not None:
        return cfg.stop_threshold
    threshold = _STOP_BASE + (_STOP_ADJUSTMENT / cfg.target_legs)
    return round(max(0.85, min(0.99, threshold)), 4)


def resolve_max_legs(cfg: BetSlipConfig) -> int:
    """Return the hard cap on leg count (target + overflow headroom)."""
    if cfg.max_legs_overflow is not None:
        return cfg.target_legs + cfg.max_legs_overflow
    if cfg.target_legs == 1:
        return 1
    if cfg.target_legs < 5:
        return cfg.target_legs + 1
    return cfg.target_legs + 2


def resolve_shrinkage_k(cfg: BetSlipConfig) -> float:
    """Return the consensus shrinkage factor. Auto = 3.0."""
    return cfg.consensus_shrinkage_k if cfg.consensus_shrinkage_k is not None else 3.0


def resolve_max_single_leg_odds(cfg: BetSlipConfig) -> float:
    """Return the maximum allowed odds for any single leg. Auto = 3.5."""
    return cfg.max_single_leg_odds if cfg.max_single_leg_odds is not None else 3.5


def resolve_min_pick_quality(cfg: BetSlipConfig) -> float:
    """Return the minimum quality score threshold. Auto = 0.20."""
    return cfg.min_pick_quality if cfg.min_pick_quality is not None else 0.20


def resolve_min_source_edge(cfg: BetSlipConfig) -> float:
    """Return the minimum edge floor. Auto = 0.0."""
    return cfg.min_source_edge if cfg.min_source_edge is not None else 0.0


def resolve_odds_movement_weight(cfg: BetSlipConfig) -> float:
    """Return odds movement weight. Auto = 0.05 (5%), capped at 0.30."""
    v = cfg.odds_movement_weight
    if v is None:
        return 0.05
    return min(v, 0.30)


def resolve_odds_movement_strength_min(cfg: BetSlipConfig) -> float:
    """Return minimum movement strength threshold. Auto = 0.05 (5%)."""
    return cfg.odds_movement_strength_min if cfg.odds_movement_strength_min is not None else 0.05


def classify_odds_movement(direction: str | None) -> str:
    """Classify movement direction into confirm/stable/infirm.

    For the *picked* market:
      - odds dropping ('down') → bookmaker confidence → 'confirm'
      - odds rising  ('up')   → bookmaker doubt     → 'infirm'
      - stable / missing      → neutral             → 'stable'
    """
    if direction is None:
        return "stable"
    d = direction.lower().strip()
    if d == "down":
        return "confirm"
    if d == "up":
        return "infirm"
    return "stable"


def odds_movement_factor(classification: str) -> float:
    """Return the blending factor: confirm=1.0, stable=0.5, infirm=0.0."""
    if classification == "confirm":
        return 1.0
    if classification == "infirm":
        return 0.0
    return 0.5


def apply_odds_movement_adjustment(
    base_score: float,
    direction: str | None,
    strength: float,
    cfg: BetSlipConfig,
) -> float:
    """Apply odds-movement post-adjustment to *base_score*.

    Formula:
        final = base_score × (1 − w) + w × factor

    Guard: if strength < odds_movement_strength_min → w forced to 0.
    """
    w = resolve_odds_movement_weight(cfg)
    if w <= 0.0:
        return base_score
    min_str = resolve_odds_movement_strength_min(cfg)
    if strength < min_str:
        return base_score
    cls = classify_odds_movement(direction)
    if cls == "stable":
        return base_score
    factor = odds_movement_factor(cls)
    return base_score * (1.0 - w) + w * factor


# ── Individual scoring axes ───────────────────────────────────────────────────


def adjusted_consensus(consensus: float, sources: int, k: float = 3.0) -> float:
    """Apply source-weighted Bayesian shrinkage toward 50%."""
    weight = sources / (sources + k)
    return 50.0 + weight * (consensus - 50.0)


def score_consensus(consensus: float, cfg: BetSlipConfig) -> float:
    """Normalise consensus to [0, 1]. Floor maps to 0; 100% maps to 1."""
    span = 100.0 - cfg.consensus_floor
    return 1.0 if span <= 0 else max(0.0, min(1.0, (consensus - cfg.consensus_floor) / span))


def score_sources(sources: int, max_sources: int) -> float:
    """Normalise source count to [0, 1] relative to pool maximum."""
    return 0.0 if max_sources <= 0 else min(1.0, sources / max_sources)


def score_balance(odds: float, ideal: float, tolerance: float, cfg: BetSlipConfig) -> float:
    """Score proximity to ideal per-leg odds. Supports asymmetric tolerance."""
    if odds < ideal:
        tol = cfg.tol_lower if cfg.tol_lower is not None else tolerance
    else:
        tol = cfg.tol_upper if cfg.tol_upper is not None else (tolerance * 0.6)
    deviation = abs(odds - ideal) / ideal
    if cfg.balance_decay == "linear":
        return max(0.0, 1.0 - (deviation / tol))
    score = math.exp(-0.5 * (deviation / tol) ** 2)
    return min(1.0, score)


# ── Composite scorer ──────────────────────────────────────────────────────────


def score_pick(
    opt: CandidateLeg,
    ideal_odds: float,
    max_sources: int,
    cfg: BetSlipConfig,
    use_preadjusted: bool = False,
) -> tuple[int, float, float]:
    """
    Score a candidate pick. Returns (tier, final_score, quality_score).

    tier: 1 if within tolerance, 2 if outside.
    final_score: continuous score with penalty for out-of-tolerance picks.
    quality_score: raw quality component before balance blending.
    """
    tolerance = resolve_tolerance(cfg)
    shrinkage_k = resolve_shrinkage_k(cfg)
    max_leg_odds = resolve_max_single_leg_odds(cfg)
    # Consensus: use pre-adjusted if available, else compute
    if use_preadjusted and opt._adjusted_consensus > 0:
        consensus = opt._adjusted_consensus
    else:
        consensus = adjusted_consensus(opt.consensus, opt.sources, shrinkage_k)
    # Hard gate: max single leg odds
    if opt.odds > max_leg_odds:
        return 2, 0.0, 0.0
    deviation_signed = (opt.odds - ideal_odds) / ideal_odds
    # Resolve active tolerance
    if deviation_signed < 0:
        active_tol = cfg.tol_lower if cfg.tol_lower is not None else tolerance
    else:
        active_tol = cfg.tol_upper if cfg.tol_upper is not None else (tolerance * 0.6)
    abs_deviation = abs(deviation_signed)
    tier = 1 if abs_deviation <= active_tol else 2
    # Component scores
    c_score = score_consensus(consensus, cfg)
    s_score = score_sources(opt.sources, max_sources)
    b_score = score_balance(opt.odds, ideal_odds, tolerance, cfg)
    quality = cfg.consensus_vs_sources * c_score + (1 - cfg.consensus_vs_sources) * s_score
    base_score = cfg.quality_vs_balance * quality + (1 - cfg.quality_vs_balance) * b_score
    # Continuous penalty for out-of-tolerance picks
    if abs_deviation > active_tol:
        excess = abs_deviation - active_tol
        penalty = math.exp(-TOLERANCE_EXCESS_LAMBDA * excess)
        final_score = base_score * penalty
    else:
        final_score = base_score
    # Post-base odds movement adjustment
    final_score = apply_odds_movement_adjustment(
        final_score,
        opt.odds_movement_direction,
        opt.odds_movement_strength,
        cfg,
    )
    return tier, round(final_score, 6), round(quality, 6)
