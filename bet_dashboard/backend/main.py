"""
Bet Assistant — FastAPI Backend
================================
Run from bet_dashboard/backend/:

    export MATCHES_DB_PATH=../../final_matches.db
    export SLIPS_DB_PATH=../../slips.db
    export CONFIG_PATH=../../config
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# ── Repo root ─────────────────────────────────────────────────────────────────
# This file lives at bet_dashboard/backend/main.py
# Repo root is three levels up so bet_framework / dashboard / scrape_kit are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from bet_dashboard.backend.logic import AppLogic  # noqa: E402
from bet_dashboard.backend.ws import ws_manager  # noqa: E402
from bet_dashboard.backend.routers import matches, builder, profiles, slips, analytics, services, system  # noqa: E402

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hand the running event loop to ws_manager so TickerService daemon threads
    # can call broadcast_sync() safely via run_coroutine_threadsafe.
    ws_manager.set_loop(asyncio.get_event_loop())
    yield
    # TickerService threads are daemons — they die with the process automatically.


def create_app() -> FastAPI:
    matches_db = os.getenv("MATCHES_DB_PATH", "final_matches.db")
    slips_db   = os.getenv("SLIPS_DB_PATH",   "slips.db")
    config_dir = os.getenv("CONFIG_PATH",      "config")

    app = FastAPI(
        title="Bet Assistant API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Single shared logic instance — owns DashboardLogic + TickerServices
    app.state.app_logic = AppLogic(matches_db, slips_db, config_dir)

    for router in [
        matches.router,
        builder.router,
        profiles.router,
        slips.router,
        analytics.router,
        services.router,
        system.router,
    ]:
        app.include_router(router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bet_dashboard.backend.main:app", host="0.0.0.0", port=8000, reload=False)
