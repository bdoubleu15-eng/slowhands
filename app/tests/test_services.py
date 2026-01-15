"""
Tests for service layer components.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.services import AgentService
from src.connection_manager import ConnectionManager, ConnectionInfo
from src.config import Config


class TestConnectionManager:
    """Test connection manager."""

    @pytest.fixture
    def manager(self):
        """Create a connection manager instance."""
        return ConnectionManager(message_queue_max_size=10)

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        websocket = AsyncMock()
        websocket.send_json = AsyncMock()
        return websocket

    @pytest.mark.asyncio
    async def test_connect(self, manager, mock_websocket):
        """Should accept connection and store it."""
        await manager.connect(mock_websocket)
        assert mock_websocket in manager.connections
        assert len(manager.connections) == 1
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, manager, mock_websocket):
        """Should remove connection on disconnect."""
        await manager.connect(mock_websocket)
        assert len(manager.connections) == 1
        await manager.disconnect(mock_websocket)
        assert len(manager.connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_with_connections(self, manager, mock_websocket):
        """Should send message to connected clients."""
        await manager.connect(mock_websocket)
        message = {"type": "test", "content": "hello"}
        await manager.broadcast(message)
        mock_websocket.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_without_connections(self, manager):
        """Should queue message when no connections."""
        message = {"type": "test", "content": "hello"}
        await manager.broadcast(message)
        assert manager.message_queue.size() == 1

    @pytest.mark.asyncio
    async def test_update_activity(self, manager, mock_websocket):
        """Should update last activity time."""
        await manager.connect(mock_websocket)
        initial_time = manager.connections[mock_websocket].last_activity
        manager.update_activity(mock_websocket)
        new_time = manager.connections[mock_websocket].last_activity
        assert new_time > initial_time

    def test_get_connection_stats(self, manager, mock_websocket):
        """Should return connection statistics."""
        # Need to run connect synchronously for test
        asyncio.run(manager.connect(mock_websocket))
        stats = manager.get_connection_stats()
        assert len(stats) == 1
        assert stats[0]["connection_id"] is not None


class TestAgentService:
    """Test agent service."""

    @pytest.fixture
    def mock_connection_manager(self):
        """Create a mock connection manager."""
        manager = AsyncMock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.fixture
    def service(self, mock_connection_manager):
        """Create an agent service instance."""
        return AgentService(mock_connection_manager)

    def test_initialization(self, service, mock_connection_manager):
        """Service should initialize with connection manager."""
        assert service.connection_manager == mock_connection_manager
        assert service.agent is None

    @patch("src.services.Agent")
    @patch("src.services.load_config")
    def test_initialize_agent_success(self, mock_load_config, mock_agent_class, service):
        """Should initialize agent successfully."""
        mock_config = MagicMock(spec=Config)
        mock_config.slow_mode = False
        mock_config.verbose = False
        mock_load_config.return_value = mock_config
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        result = service.initialize_agent()
        assert result is True
        assert service.agent == mock_agent

    @patch("src.services.load_config")
    def test_initialize_agent_failure(self, mock_load_config, service):
        """Should handle agent initialization failure."""
        mock_load_config.side_effect = Exception("Config error")
        result = service.initialize_agent()
        assert result is False
        assert service.agent is None

    def test_get_status_no_agent(self, service):
        """Should return None when agent not initialized."""
        assert service.get_status() is None

    def test_get_status_with_agent(self, service):
        """Should return agent status."""
        mock_agent = MagicMock()
        mock_agent.get_status.return_value = {"step": 0, "running": False}
        service.agent = mock_agent
        status = service.get_status()
        assert status == {"step": 0, "running": False}

    def test_reset_agent(self, service):
        """Should reset agent memory."""
        mock_agent = MagicMock()
        service.agent = mock_agent
        service.reset_agent()
        mock_agent.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_agent(self, service, mock_connection_manager):
        """Should stop agent and broadcast."""
        mock_agent = MagicMock()
        mock_agent.is_running = True
        mock_agent.current_step = 5
        service.agent = mock_agent

        correlation_id = await service.stop_agent()
        assert correlation_id is not None
        assert mock_agent.is_running is False
        mock_connection_manager.broadcast.assert_called_once()
        call_args = mock_connection_manager.broadcast.call_args[0][0]
        assert call_args["type"] == "stopped"

    def test_run_chat(self, service):
        """Should run synchronous chat."""
        mock_agent = MagicMock()
        mock_agent.run.return_value = "Test response"
        service.agent = mock_agent
        response = service.run_chat("Hello")
        assert response == "Test response"
        mock_agent.run.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_start_stream_chat(self, service):
        """Should start streaming chat in background."""
        with patch.object(service, '_stream_agent_response', AsyncMock()) as mock_stream:
            await service.start_stream_chat("Hello")
            mock_stream.assert_called_once_with("Hello", None)

    @pytest.mark.asyncio
    async def test_stream_agent_response_no_agent(self, service, mock_connection_manager):
        """Should broadcast error when agent not initialized."""
        service.agent = None
        await service._stream_agent_response("Hello")
        mock_connection_manager.broadcast.assert_called_once()
        call_args = mock_connection_manager.broadcast.call_args[0][0]
        assert call_args["type"] == "error"
        assert "Agent not initialized" in call_args["content"]