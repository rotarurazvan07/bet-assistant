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
  score_consensus(consensus, cfg)                → float
  score_sources(sources, max_sources)            → float
  score_balance(odds, ideal, tolerance)          → float
  score_pick(opt, ideal_odds, max_sources, cfg)  → (int, float)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bet_framework.core.Slip import BetSlipConfig, CandidateLeg


# ── Config resolvers ──────────────────────────────────────────────────────────


def resolve_tolerance(cfg: BetSlipConfig) -> float:
    """
    Auto-derive the per-leg odds tolerance band from the target leg count.
    Wider for few legs, tighter for many.
    1 leg → 0.40 │ 2 → 0.28 │ 3 → 0.23 │ 5 → 0.18 │ 10 → 0.13
    """
    if cfg.tolerance_factor is not None:
        return cfg.tolerance_factor
    return round(0.40 / (cfg.target_legs**0.5), 4)


def resolve_stop_threshold(cfg: BetSlipConfig) -> float:
    """
    Auto-derive the early-stop threshold from the target leg count.
    Tight for singles, slightly looser for longer accas.
    1 leg → 0.98 │ 2 → 0.93 │ 3 → 0.91 │ 5 → 0.90 │ 10 → 0.89
    """
    if cfg.stop_threshold is not None:
        return cfg.stop_threshold
    return round(0.88 + (0.1 / cfg.target_legs), 4)


def resolve_max_legs(cfg: BetSlipConfig) -> int:
    """Return the hard cap on leg count (target + auto/manual overflow headroom)."""
    if cfg.max_legs_overflow is not None:
        return cfg.target_legs + cfg.max_legs_overflow
    if cfg.target_legs == 1:
        return 1
    if cfg.target_legs < 5:
        return cfg.target_legs + 1
    return cfg.target_legs + 2


# ── Individual scoring axes ───────────────────────────────────────────────────


def adjusted_consensus(consensus: float, sources: int, k: float = 3.0) -> float:
    """
    Apply source-weighted shrinkage to consensus.
    
    Formula: weight = sources / (sources + k)
    Returns: 50.0 + weight * (consensus - 50.0)
    
    This pulls low-source consensus toward 50% (no net edge) while
    high-source consensus remains closer to the raw value.
    """
    weight = sources / (sources + k)
    return 50.0 + weight * (consensus - 50.0)


def score_consensus(consensus: float, cfg: BetSlipConfig) -> float:
    """
    Normalise a consensus percentage to [0.0, 1.0].
    cfg.consensus_floor maps to 0.0; 100 % maps to 1.0.
    """
    span = 100.0 - cfg.consensus_floor
    return 1.0 if span <= 0 else max(0.0, min(1.0, (consensus - cfg.consensus_floor) / span))


def score_sources(sources: int, max_sources: int) -> float:
    """Normalise source count to [0.0, 1.0] relative to the pool maximum."""
    return 0.0 if max_sources <= 0 else min(1.0, sources / max_sources)


def score_balance(odds: float, ideal: float, tolerance: float, cfg: BetSlipConfig) -> float:
    """
    Score how close a pick's odds are to the ideal per-leg target.
    Perfect match → 1.0 ; at/beyond the tolerance edge → 0.0.
    
    Supports asymmetric tolerance (tol_lower, tol_upper) and Gaussian decay.
    """
    # Determine which tolerance to use based on direction
    if odds < ideal:
        tol = cfg.tol_lower if cfg.tol_lower is not None else tolerance
    else:
        tol = cfg.tol_upper if cfg.tol_upper is not None else tolerance
    
    deviation = abs(odds - ideal) / ideal
    
    if cfg.balance_decay == "gaussian":
        # Gaussian decay: exp(-0.5 * (deviation/tol)^2)
        # Never exactly 0, smoother falloff
        score = math.exp(-0.5 * (deviation / tol) ** 2)
        return min(1.0, score)
    else:
        # Linear decay: max(0.0, 1.0 - deviation/tol)
        return max(0.0, 1.0 - (deviation / tolerance))


# ── Composite scorer ──────────────────────────────────────────────────────────


def score_pick(
    opt: CandidateLeg,
    ideal_odds: float,
    max_sources: int,
    cfg: BetSlipConfig,
) -> tuple[int, float]:
    """
    Score a single candidate pick and assign it to Tier 1 or Tier 2.

    Tier 1 picks sit within the ±tolerance band around ideal_odds and always
    rank above Tier 2 picks in the selection loop.

    Returns
    -------
    (tier, final_score)  where tier ∈ {1, 2} and final_score ∈ [0.0, 1.0].
    
    Note: This function assumes the candidate has already passed hard filters
    (min_source_edge, max_single_leg_odds). It does not apply those filters itself.
    """
    tolerance = resolve_tolerance(cfg)
    
    # Apply consensus adjustment if k is set
    consensus = opt.consensus
    if cfg.consensus_shrinkage_k is not None:
        consensus = adjusted_consensus(consensus, opt.sources, cfg.consensus_shrinkage_k)
    
    # Check max_single_leg_odds filter (hard gate)
    if cfg.max_single_leg_odds is not None and opt.odds > cfg.max_single_leg_odds:
        # Return lowest possible score to effectively reject
        return 2, 0.0
    
    deviation = abs(opt.odds - ideal_odds) / ideal_odds
    tier = 1 if deviation <= tolerance else 2

    c_score = score_consensus(consensus, cfg)
    s_score = score_sources(opt.sources, max_sources)
    b_score = score_balance(opt.odds, ideal_odds, tolerance, cfg)

    quality = cfg.consensus_vs_sources * c_score + (1 - cfg.consensus_vs_sources) * s_score
    final = cfg.quality_vs_balance * quality + (1 - cfg.quality_vs_balance) * b_score
    return tier, round(final, 6)
