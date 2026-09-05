from __future__ import annotations

from core.ws import ws_manager
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["system"])


def _get(request: Request):
    return request.app.state.app_logic


@router.post("/api/pull")
def pull_db(request: Request):
    app = _get(request)
    try:
        msg = app.pull_and_broadcast()
        return {
            "status": "ok",
            "message": msg,
            "timestamp": app.logic.last_pull_timestamp,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/api/status")
def get_status(request: Request):
    app = _get(request)
    df = app.logic.match_df
    return {
        "last_pull": app.logic.last_pull_timestamp,
        "matches_loaded": 0 if df is None or df.empty else len(df),
    }


@router.get("/api/config/sources")
def get_sources_config(request: Request):
    """Get all unique sources from RUNNER_SETS in scraper_config.yaml"""
    app = _get(request)
    settings = app.logic.settings
    scraper_cfg = settings.get("scraper_config") or {}
    runner_sets = scraper_cfg.get("RUNNER_SETS", {})

    # Get unique sources across all runner sets
    all_sources = set()
    for sources in runner_sets.values():
        all_sources.update(sources)

    return {"sources": sorted(all_sources)}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Simple keepalive protocol
            if data == "ping":
                await websocket.send_text('{"event":"pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
