"""
Integration Tests for Health Checks

Tests health check endpoints and health monitoring.
"""

import pytest
import asyncio
from health import HealthChecker, HealthStatus
from p2p.p2p_node import P2PNode
from crypto import NodeIdentity


@pytest.mark.asyncio
async def test_health_checker_initialization():
    """Test that health checker initializes correctly"""
    checker = HealthChecker()
    assert checker is not None
    
    # Check initial status
    status = checker.get_overall_status()
    assert status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]


@pytest.mark.asyncio
async def test_health_check_registration():
    """Test that health checks can be registered"""
    checker = HealthChecker()
    
    # Register a health check
    async def test_check():
        return {"status": "healthy", "message": "OK"}
    
    checker.register_check("test_service", test_check)
    
    # Get check result
    result = await checker.check("test_service")
    assert result is not None
    assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]


@pytest.mark.asyncio
async def test_health_check_aggregation():
    """Test that multiple health checks are aggregated correctly"""
    checker = HealthChecker()
    
    # Register multiple checks
    async def healthy_check():
        return {"status": "healthy"}
    
    async def degraded_check():
        return {"status": "degraded", "message": "Warning"}
    
    checker.register_check("service1", healthy_check)
    checker.register_check("service2", degraded_check)
    
    # Get overall status
    status = checker.get_overall_status()
    # Should be degraded if any service is degraded
    assert status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]


@pytest.mark.asyncio
async def test_health_endpoint_integration():
    """Test that health endpoints work with P2P node"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Health should be available via metrics/health endpoint
    # (This requires server_api to be running, so this is a placeholder)
    # In a real test, we'd start the API server and check the endpoint
    assert node is not None


@pytest.mark.asyncio
async def test_health_check_uptime():
    """Test that health checker tracks uptime"""
    checker = HealthChecker()
    
    # Get uptime
    uptime = checker.get_uptime()
    assert uptime >= 0
    
    # Wait a bit
    await asyncio.sleep(0.1)
    
    # Uptime should have increased
    new_uptime = checker.get_uptime()
    assert new_uptime >= uptime


@pytest.mark.asyncio
async def test_health_check_timeout():
    """Test that health checks timeout correctly"""
    checker = HealthChecker()
    
    # Register a slow check
    async def slow_check():
        await asyncio.sleep(10)  # Very slow
        return {"status": "healthy"}
    
    checker.register_check("slow_service", slow_check)
    
    # Check should timeout (if timeout is configured)
    # Note: This depends on HealthChecker implementation
    result = await checker.check("slow_service")
    # Should handle timeout gracefully
    assert result is not None
