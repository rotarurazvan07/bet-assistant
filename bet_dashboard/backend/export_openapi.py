"""Export the dashboard OpenAPI schema without importing main.py.

main.py instantiates AppLogic (SQLite) at import time; the schema dump only
needs route declarations, so the routers are mounted on a bare app. Routers
pull the shared logic lazily via request.app.state, so importing is DB-free.

Usage: PYTHONPATH=<repo root> python bet_dashboard/backend/export_openapi.py <out.json>
"""

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
REPO_ROOT = BACKEND.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND))

from fastapi import FastAPI
from routers import (
    analytics,
    builder,
    matches,
    odds_history,
    profiles,
    services,
    slips,
    system,
)

from bet_framework.markets.enums import MarketKey, MarketType

MODULES = (matches, builder, slips, profiles, analytics, services, odds_history, system)


def build_schema() -> dict:
    """Build the OpenAPI schema for the bet-assistant API.

    Creates a bare FastAPI app with all routers mounted, generates the OpenAPI
    schema, and injects the canonical MarketKey and MarketType enums as
    schema-only components so frontend types are generated from Python.

    Returns:
        OpenAPI schema dictionary.
    """
    app = FastAPI(title="bet-assistant")
    for module in MODULES:
        app.include_router(module.router)
    schema = app.openapi()
    # Endpoints return hand-built dicts (no response_model), so the canonical
    # market enums would otherwise never reach the OpenAPI document. Inject
    # them as schema-only components (single source: bet_framework.markets)
    # so frontend types are generated from Python, not hand-mirrored.
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components["MarketKey"] = {
        "type": "string",
        "enum": [member.value for member in MarketKey],
        "title": "MarketKey",
        "description": "Canonical market identity keys (frozen values).",
    }
    components["MarketType"] = {
        "type": "string",
        "enum": [member.value for member in MarketType],
        "title": "MarketType",
        "description": "Canonical market category routing keys (frozen values).",
    }
    return schema


def main() -> None:
    """CLI entry point to export the OpenAPI schema to a JSON file.

    Args:
        sys.argv[1]: Optional output file path. Defaults to
            bet_dashboard/backend/openapi.generated.json.
    """
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else BACKEND / "openapi.generated.json"
    out.write_text(json.dumps(build_schema(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
