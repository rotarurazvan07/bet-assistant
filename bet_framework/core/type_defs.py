"""
bet_framework.core.type_defs — DEPRECATED FACADE.

Canonical enums now live in ``bet_framework.markets.enums`` (single source of
truth, StrEnum with frozen values). The legacy ``(str, Enum)`` spellings and
the hand-synchronized duplicate catalogs are exactly the divergence this
refactor eliminates. All names below are re-exported for existing importers
during the burn-down and are deleted on the zero-reference gate.
"""

from bet_framework.markets.enums import (
    MarketKey,
    MarketLabel,
    MarketType,
    MatchStatus,
    Outcome,
)

__all__ = ["MarketKey", "MarketLabel", "MarketType", "MatchStatus", "Outcome"]
