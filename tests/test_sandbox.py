"""
Tests for Code Execution Sandbox
"""

import pytest
import unittest.mock as mock
from security.sandbox import SandboxManager, DOCKER_AVAILABLE
from agents.code_agent import CodeAgent
from pathlib import Path

class TestSandbox:
    """Test suite for SandboxManager"""
    
    def test_sandbox_availability(self):
        """Test sandbox availability check"""
        manager = SandboxManager()
        # This will depend on the environment, but shouldn't crash
        available = manager.is_available()
        assert isinstance(available, bool)

    @mock.patch('security.sandbox.docker.from_env' if DOCKER_AVAILABLE else 'unittest.mock.MagicMock')
    def test_execute_python_mock(self, mock_docker):
        """Test python execution with mocked Docker"""
        if not DOCKER_AVAILABLE:
            pytest.skip("Docker library not available for mock test")
        # Setup mock
        mock_client = mock.MagicMock()
        mock_docker.return_value = mock_client
        mock_container = mock.MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_container.wait.return_value = {'StatusCode': 0}
        mock_container.logs.return_value = b"hello world"
        
        manager = SandboxManager()
        manager.client = mock_client
        
        result = manager.execute_code("print('hello world')", "python")
        
        assert result["success"] is True
        assert "hello world" in result["stdout"]
        mock_client.containers.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_code_agent_fallback(self):
        """Test CodeAgent fallback when sandbox is unavailable"""
        # Force sandbox unavailable
        with mock.patch.object(SandboxManager, 'is_available', return_value=False):
            agent = CodeAgent("test_agent")
            
            # This should use local subprocess execution
            result = await agent._code_execute("print('fallback')", "python")
            
            assert result["success"] is True
            assert "fallback" in result["stdout"].strip()

    @pytest.mark.asyncio
    async def test_code_agent_sandbox_integration(self):
        """Test CodeAgent calling sandbox when available"""
        with mock.patch.object(SandboxManager, 'is_available', return_value=True):
            with mock.patch.object(SandboxManager, 'execute_code') as mock_exec:
                mock_exec.return_value = {
                    "success": True,
                    "stdout": "sandboxed output",
                    "stderr": "",
                    "exit_code": 0
                }
                
                agent = CodeAgent("test_agent")
                result = await agent._code_execute("print('test')", "python")
                
                assert result["success"] is True
                assert result["stdout"] == "sandboxed output"
                mock_exec.assert_called_once()
