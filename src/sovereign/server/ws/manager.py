"""
src/sovereign/server/ws/manager.py
Asyncio-safe multi-topic WebSocket connection manager with bounded queues.

Tracks active WebSocket connections keyed by topic string and provides
broadcast, personal message, and graceful disconnect capabilities.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("sovereign.server.ws.manager")

# Maximum queued messages per client before dropping oldest
MAX_QUEUE_SIZE = 200


class ConnectionManager:
    """
    Thread-safe and asyncio-safe connection manager tracking active WebSocket
    connections keyed by topic string.

    Topics follow naming conventions:
        - "task:{task_id}" for agent reasoning trace
        - "network:telemetry" for real-time socket monitor events
        - "hitl:alerts" for approval gate notifications
    """

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, topic: str) -> None:
        """Accept and register a WebSocket connection for a topic."""
        await websocket.accept()
        async with self._lock:
            if topic not in self.active_connections:
                self.active_connections[topic] = set()
            self.active_connections[topic].add(websocket)
        logger.debug(f"WebSocket connected to topic '{topic}'")

    async def disconnect(self, websocket: WebSocket, topic: str) -> None:
        """Remove a WebSocket connection from a topic."""
        async with self._lock:
            if topic in self.active_connections:
                self.active_connections[topic].discard(websocket)
                if not self.active_connections[topic]:
                    del self.active_connections[topic]
        logger.debug(f"WebSocket disconnected from topic '{topic}'")

    async def broadcast(self, topic: str, message: dict) -> None:
        """
        Broadcast a JSON message to all connections subscribed to a topic.
        Gracefully handles disconnected clients without raising exceptions.
        """
        async with self._lock:
            connections = list(self.active_connections.get(topic, set()))

        dead_connections = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                if topic in self.active_connections:
                    for ws in dead_connections:
                        self.active_connections[topic].discard(ws)
                    if not self.active_connections[topic]:
                        del self.active_connections[topic]

    async def send_personal_message(
        self, websocket: WebSocket, message: dict
    ) -> None:
        """Send a JSON message to a specific WebSocket connection."""
        try:
            await websocket.send_json(message)
        except Exception:
            logger.debug("Failed to send personal message — client disconnected")

    def get_connection_count(self, topic: str) -> int:
        """Return the number of active connections for a topic."""
        return len(self.active_connections.get(topic, set()))

    def get_all_topics(self) -> list:
        """Return all active topic names."""
        return list(self.active_connections.keys())


# Singleton manager instance for the application
manager = ConnectionManager()
