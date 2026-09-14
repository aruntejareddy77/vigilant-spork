"""
src/sovereign/server/ws/trace.py
WebSocket endpoint /ws/tasks/{task_id} for agent reasoning trace streaming.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sovereign.server.ws.manager import manager

logger = logging.getLogger("sovereign.server.ws.trace")
router = APIRouter()


@router.websocket("/ws/tasks/{task_id}")
async def ws_task_trace(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for streaming agent reasoning steps for a specific task.

    Supports client ping/pong keepalives:
      - Client sends {"type": "ping"} → Server responds with {"type": "pong"}
      - Client sends {"type": "cancel"} → Server closes connection
    """
    topic = f"task:{task_id}"
    await manager.connect(websocket, topic)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "task_id": task_id,
                    "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                })
            elif msg_type == "cancel":
                await websocket.send_json({
                    "type": "CANCELLED",
                    "task_id": task_id,
                })
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket, topic)


async def emit_trace_step(task_id: str, step_data: dict) -> None:
    """
    Broadcast a reasoning trace step event to all connected clients
    watching the specified task.

    Args:
        task_id: The task identifier.
        step_data: Dict containing step details (node_name, thought, tool_calls, etc.)
    """
    message = {
        "type": "TRACE_STEP",
        "task_id": task_id,
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        **step_data,
    }
    await manager.broadcast(f"task:{task_id}", message)


async def emit_hitl_suspended(task_id: str, pending_approval: dict) -> None:
    """
    Broadcast a HITL suspension event to all connected clients watching the task.

    Args:
        task_id: The task identifier.
        pending_approval: Dict with approval gate details.
    """
    message = {
        "type": "HITL_SUSPENDED",
        "task_id": task_id,
        "pending_approval": pending_approval,
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast(f"task:{task_id}", message)
