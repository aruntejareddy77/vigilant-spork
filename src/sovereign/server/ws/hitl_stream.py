"""
src/sovereign/server/ws/hitl_stream.py
WebSocket endpoint /ws/hitl for Human-in-the-Loop approval gate alerts.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sovereign.server.ws.manager import manager

logger = logging.getLogger("sovereign.server.ws.hitl_stream")
router = APIRouter()


@router.websocket("/ws/hitl")
async def ws_hitl_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for broadcasting pending HITL approval gate alerts
    to connected operators.
    """
    topic = "hitl:alerts"
    await manager.connect(websocket, topic)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "channel": "hitl",
                    "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket, topic)


async def emit_hitl_alert(task_id: str, gate_info: dict) -> None:
    """
    Broadcast a pending HITL approval request to all connected operators.

    Args:
        task_id: The task identifier awaiting approval.
        gate_info: Dict with gate details (action, deliverable_type, summary, etc.)
    """
    message = {
        "type": "HITL_ALERT",
        "task_id": task_id,
        "gate_info": gate_info,
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast("hitl:alerts", message)
