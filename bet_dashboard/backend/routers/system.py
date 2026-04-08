from __future__ import annotations

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from ..ws import ws_manager

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


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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
