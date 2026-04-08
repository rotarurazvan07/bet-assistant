from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket


class ConnectionManager:
    """
    Manages WebSocket connections and provides thread-safe broadcasting.

    TickerService callbacks run in daemon threads. They call broadcast_sync()
    which uses run_coroutine_threadsafe() to safely schedule the async broadcast
    on the main event loop — zero polling, pure push.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called once from the FastAPI lifespan to store the running event loop."""
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, payload: dict) -> None:
        """Async broadcast to all connected clients. Dead connections are pruned."""
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_sync(self, payload: dict) -> None:
        """
        Thread-safe broadcast for use from sync daemon threads (TickerService).
        No-op if the event loop is not yet running or has been closed.
        """
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self._loop)


# Module-level singleton — imported by logic.py and system router
ws_manager = ConnectionManager()
