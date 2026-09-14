"""
src/sovereign/server/ws/network_stream.py
WebSocket endpoint /ws/network for real-time socket monitor telemetry streaming.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sovereign.server.ws.manager import manager

logger = logging.getLogger("sovereign.server.ws.network_stream")
router = APIRouter()


@router.websocket("/ws/network")
async def ws_network_telemetry(websocket: WebSocket):
    """
    WebSocket endpoint for streaming live NetworkEvent objects from the
    NetworkMonitor callback.

    Events are tagged as NETWORK_EVENT for allowed connections and
    EGRESS_ALERT for denied egress attempts.
    """
    topic = "network:telemetry"
    await manager.connect(websocket, topic)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "channel": "network",
                    "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket, topic)


async def emit_network_event(event_data: dict) -> None:
    """
    Push a network event to all connected WebSocket clients.

    The event_type is determined by the verdict field:
      - "ALLOW" -> NETWORK_EVENT
      - "DENY" -> EGRESS_ALERT

    Args:
        event_data: Dict representation of a NetworkEvent.
    """
    verdict = event_data.get("verdict", "ALLOW")
    event_type = "EGRESS_ALERT" if verdict == "DENY" else "NETWORK_EVENT"

    message = {
        "type": event_type,
        "event": event_data,
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast("network:telemetry", message)


def bind_network_monitor(monitor) -> None:
    """
    Attach a callback to the NetworkMonitor that pushes events
    to the WebSocket manager.

    Note: Since the monitor runs in a sync thread and the manager
    is async, we schedule the broadcast on the event loop.

    Args:
        monitor: NetworkMonitor instance from sovereign.network.monitor.
    """
    import asyncio

    def _on_network_event(event):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(emit_network_event(event.model_dump()))
        except Exception:
            pass

    monitor.event_callback = _on_network_event
