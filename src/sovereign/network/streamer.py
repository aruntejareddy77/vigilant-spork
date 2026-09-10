"""
src/sovereign/network/streamer.py
FastAPI WebSocket endpoint and broadcast hub for real-time telemetry streaming.
"""
import asyncio
import json
import logging
from typing import List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sovereign.network.models import NetworkEvent, TelemetrySnapshot
from sovereign.network.ring_buffer import ConnectionRingBuffer

logger = logging.getLogger("sovereign.network.streamer")


class TelemetryStreamer:
    """
    Manages active WebSocket connections and broadcasts real-time NetworkEvents
    to UI clients.
    """

    def __init__(self, ring_buffer: ConnectionRingBuffer):
        self.ring_buffer = ring_buffer
        self.active_connections: Set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        self._loop = asyncio.get_running_loop()
        # Immediately send recent snapshot to client upon connecting
        snap = self.ring_buffer.get_snapshot(limit=50)
        await websocket.send_text(snap.model_dump_json())

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(self, event: NetworkEvent) -> None:
        """Asynchronously sends an event to all connected WebSocket clients."""
        if not self.active_connections:
            return

        msg = event.model_dump_json()
        dead_connections = set()

        for conn in list(self.active_connections):
            try:
                await conn.send_text(msg)
            except Exception:
                dead_connections.add(conn)

        for dead in dead_connections:
            self.disconnect(dead)

    def broadcast_sync(self, event: NetworkEvent) -> None:
        """Thread-safe synchronous broadcast hook for background worker threads."""
        if self._loop and self._loop.is_running() and self.active_connections:
            asyncio.run_coroutine_threadsafe(self.broadcast(event), self._loop)


def create_telemetry_router(streamer: TelemetryStreamer) -> APIRouter:
    """Factory creating APIRouter bound to a specific TelemetryStreamer instance."""
    router = APIRouter(tags=["telemetry"])

    @router.websocket("/ws/network-telemetry")
    async def websocket_telemetry(websocket: WebSocket):
        await streamer.connect(websocket)
        try:
            while True:
                # Keep socket alive and respond to client heartbeats
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            streamer.disconnect(websocket)
        except Exception:
            streamer.disconnect(websocket)

    @router.get("/api/network/telemetry/snapshot", response_model=TelemetrySnapshot)
    async def get_snapshot(limit: int = 100):
        return streamer.ring_buffer.get_snapshot(limit=limit)

    return router
