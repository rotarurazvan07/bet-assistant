"""Canonical contract snapshot emitter for frontend parity tests.

Emits {market: {label, market_type, cons_key, odds_key}} as JSON. The frontend
contract test asserts its column config against this snapshot, so a `btts_yes`
class divergence fails CI instead of shipping.
"""

import json
import sys
from pathlib import Path

from bet_framework.markets.catalog import MARKET_CATALOG


def snapshot() -> dict[str, dict[str, str]]:
    """Canonical JSON snapshot of the market catalog."""
    return {
        spec.key: {
            "label": spec.label,
            "market_type": spec.market_type,
            "cons_key": spec.cons_key,
            "odds_key": spec.odds_key,
        }
        for spec in MARKET_CATALOG
    }


def emit(path: str | Path) -> dict[str, dict[str, str]]:
    """Write the canonical snapshot to ``path`` and return it."""
    data = snapshot()
    Path(path).write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return data


if (
    __name__ == "__main__"
):  # python -m bet_framework.markets.contract [path] -> refresh snapshot
    target = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).with_name("contract.snapshot.json")
    )
    emit(target)
