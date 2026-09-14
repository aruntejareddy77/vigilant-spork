"""
tests/test_server/test_websocket_streams.py
Tests for multi-channel WebSocket streaming (trace, network, hitl).
"""
import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sovereign.server.ws.manager import ConnectionManager, manager
from sovereign.server.ws.trace import router as trace_router, emit_trace_step
from sovereign.server.ws.network_stream import router as network_router, emit_network_event
from sovereign.server.ws.hitl_stream import router as hitl_router, emit_hitl_alert


def _create_ws_app():
    """Create a FastAPI app with all WebSocket routes."""
    app = FastAPI()
    app.include_router(trace_router)
    app.include_router(network_router)
    app.include_router(hitl_router)
    return app


# =============================================================================
# ConnectionManager Tests
# =============================================================================


class TestConnectionManager:
    """Tests for the WebSocket ConnectionManager."""

    def test_manager_initializes_empty(self):
        """Fresh manager should have no connections."""
        mgr = ConnectionManager()
        assert mgr.get_all_topics() == []

    def test_get_connection_count_empty(self):
        """Connection count for non-existent topic should be 0."""
        mgr = ConnectionManager()
        assert mgr.get_connection_count("task:test-123") == 0


# =============================================================================
# Task Trace WebSocket Tests
# =============================================================================


class TestTraceWebSocket:
    """Tests for /ws/tasks/{task_id} trace endpoint."""

    def test_connect_and_ping_pong(self):
        """Client should receive pong in response to ping."""
        app = _create_ws_app()
        client = TestClient(app)
        with client.websocket_connect("/ws/tasks/test-task-001") as ws:
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"
            assert response["task_id"] == "test-task-001"
            assert "timestamp_iso" in response

    def test_broadcast_trace_event_received(self):
        """Broadcast trace event from backend should be received by connected client."""
        app = _create_ws_app()
        client = TestClient(app)

        with client.websocket_connect("/ws/tasks/task-broadcast-01") as ws:
            # Broadcast a trace event from the server side
            async def _broadcast():
                await emit_trace_step("task-broadcast-01", {
                    "step_index": 1,
                    "node_name": "extract_findings",
                    "status": "RUNNING",
                    "thought": "Extracting inspection findings...",
                })

            # Run the broadcast in the event loop
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_broadcast())
            loop.close()

            response = ws.receive_json()
            assert response["type"] == "TRACE_STEP"
            assert response["task_id"] == "task-broadcast-01"
            assert response["step_index"] == 1
            assert response["node_name"] == "extract_findings"
            assert "timestamp_iso" in response


# =============================================================================
# Network Telemetry WebSocket Tests
# =============================================================================


class TestNetworkWebSocket:
    """Tests for /ws/network telemetry endpoint."""

    def test_connect_and_ping_pong(self):
        """Network WS should respond to ping with pong."""
        app = _create_ws_app()
        client = TestClient(app)
        with client.websocket_connect("/ws/network") as ws:
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"
            assert response["channel"] == "network"

    def test_network_event_broadcast(self):
        """Simulated network event should be broadcast as NETWORK_EVENT."""
        app = _create_ws_app()
        client = TestClient(app)

        with client.websocket_connect("/ws/network") as ws:
            async def _broadcast():
                await emit_network_event({
                    "timestamp_iso": "2026-09-14T16:20:12.450Z",
                    "protocol": "tcp",
                    "local_address": "127.0.0.1:8000",
                    "remote_address": "127.0.0.1:54321",
                    "pid": 4812,
                    "process_name": "python.exe",
                    "verdict": "ALLOW",
                    "reason": "loopback_allowed",
                })

            loop = asyncio.new_event_loop()
            loop.run_until_complete(_broadcast())
            loop.close()

            response = ws.receive_json()
            assert response["type"] == "NETWORK_EVENT"
            assert response["event"]["verdict"] == "ALLOW"
            assert response["event"]["protocol"] == "tcp"

    def test_egress_alert_broadcast(self):
        """Denied network event should be broadcast as EGRESS_ALERT."""
        app = _create_ws_app()
        client = TestClient(app)

        with client.websocket_connect("/ws/network") as ws:
            async def _broadcast():
                await emit_network_event({
                    "timestamp_iso": "2026-09-14T16:20:15.100Z",
                    "protocol": "udp",
                    "local_address": "192.168.1.50:61234",
                    "remote_address": "8.8.8.8:53",
                    "pid": 9102,
                    "process_name": "curl.exe",
                    "verdict": "DENY",
                    "reason": "port_53_strictly_denied",
                })

            loop = asyncio.new_event_loop()
            loop.run_until_complete(_broadcast())
            loop.close()

            response = ws.receive_json()
            assert response["type"] == "EGRESS_ALERT"
            assert response["event"]["verdict"] == "DENY"


# =============================================================================
# HITL WebSocket Tests
# =============================================================================


class TestHITLWebSocket:
    """Tests for /ws/hitl approval gate alerts endpoint."""

    def test_connect_and_ping_pong(self):
        """HITL WS should respond to ping with pong."""
        app = _create_ws_app()
        client = TestClient(app)
        with client.websocket_connect("/ws/hitl") as ws:
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"
            assert response["channel"] == "hitl"

    def test_hitl_alert_broadcast(self):
        """HITL alert should be received by connected client."""
        app = _create_ws_app()
        client = TestClient(app)

        with client.websocket_connect("/ws/hitl") as ws:
            async def _broadcast():
                await emit_hitl_alert("task-hitl-01", {
                    "action": "deliverable_signoff",
                    "deliverable_type": "docx",
                    "summary": "Refinery Vessel V-301 Inspection Approval Note",
                    "confidence_score": 0.94,
                })

            loop = asyncio.new_event_loop()
            loop.run_until_complete(_broadcast())
            loop.close()

            response = ws.receive_json()
            assert response["type"] == "HITL_ALERT"
            assert response["task_id"] == "task-hitl-01"
            assert response["gate_info"]["action"] == "deliverable_signoff"
            assert response["gate_info"]["confidence_score"] == 0.94


# =============================================================================
# Graceful Disconnect Tests
# =============================================================================


class TestGracefulDisconnect:
    """Tests for graceful WebSocket disconnect handling."""

    def test_disconnect_cleans_up_connections(self):
        """After disconnect, manager should clean up the connection entry."""
        app = _create_ws_app()
        client = TestClient(app)

        # Connect and then disconnect
        with client.websocket_connect("/ws/tasks/cleanup-test") as ws:
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"

        # After context manager exit, the connection should be cleaned up
        # (the manager cleans up in the finally block)
        # Give a brief moment for cleanup
        assert manager.get_connection_count("task:cleanup-test") == 0
