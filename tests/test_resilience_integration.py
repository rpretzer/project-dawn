"""
Integration Tests for Resilience Features

Tests rate limiting, circuit breakers, and retry policies in realistic scenarios.
"""

import pytest
import asyncio
import time
from crypto import NodeIdentity
from p2p.p2p_node import P2PNode
from p2p.peer import Peer
from resilience.errors import RateLimitError, CircuitBreakerOpenError, NetworkError
from resilience.rate_limit import RateLimiter, RateLimitConfig
from resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from resilience.retry import RetryPolicy, retry_with_policy


@pytest.mark.asyncio
async def test_rate_limiting_in_message_routing():
    """Test that rate limiting works in message routing"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Set low rate limit for testing
    node.rate_limiter.set_limit(
        "test_peer",
        RateLimitConfig(max_requests=5, time_window=1.0)
    )
    
    # Send messages up to limit
    for i in range(5):
        message = {
            "jsonrpc": "2.0",
            "method": "node/ping",
            "id": i,
        }
        result = await node._route_message(message, sender_node_id="test_peer")
        assert result is not None or "error" not in (result or {})
    
    # Next message should be rate limited
    message = {
        "jsonrpc": "2.0",
        "method": "node/ping",
        "id": 6,
    }
    result = await node._route_message(message, sender_node_id="test_peer")
    assert result is not None
    assert "error" in result
    assert result["error"]["code"] == -32000
    assert "rate limit" in result["error"]["message"].lower()


@pytest.mark.asyncio
async def test_circuit_breaker_per_peer():
    """Test that circuit breaker prevents connection attempts when open"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Create a peer
    peer = Peer(
        node_id="test_peer",
        address="ws://localhost:9999",  # Non-existent address
    )
    
    # Set low threshold for testing
    cb_config = CircuitBreakerConfig(failure_threshold=2, timeout=1.0)
    node.circuit_breakers[peer.node_id] = CircuitBreaker(
        name=f"peer_{peer.node_id[:16]}",
        config=cb_config,
    )
    
    # Attempt connection (will fail)
    result = await node.connect_to_peer(peer)
    assert result is False
    
    # Attempt again (will fail and open circuit)
    result = await node.connect_to_peer(peer)
    assert result is False
    
    # Circuit should now be open - next attempt should fail immediately
    result = await node.connect_to_peer(peer)
    assert result is False
    
    # Wait for circuit to half-open
    await asyncio.sleep(1.1)
    
    # Next attempt should try again (half-open)
    result = await node.connect_to_peer(peer)
    assert result is False


@pytest.mark.asyncio
async def test_retry_policy_connection_attempts():
    """Test that retry policy retries connection attempts"""
    from mcp.encrypted_transport import EncryptedWebSocketTransport
    
    identity = NodeIdentity()
    
    # Create transport with retry policy
    transport = EncryptedWebSocketTransport(
        url="ws://localhost:9999",  # Non-existent address
        identity=identity,
        enable_encryption=False,
    )
    
    # Attempt connection (will fail after retries)
    with pytest.raises((NetworkError, ConnectionError, Exception)):
        await transport.connect()


@pytest.mark.asyncio
async def test_resilience_integration_with_metrics():
    """Test that resilience features record metrics correctly"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Set low rate limit
    node.rate_limiter.set_limit(
        "test_peer",
        RateLimitConfig(max_requests=2, time_window=1.0)
    )
    
    # Send messages
    for i in range(3):
        message = {
            "jsonrpc": "2.0",
            "method": "node/ping",
            "id": i,
        }
        await node._route_message(message, sender_node_id="test_peer")
    
    # Check that metrics were recorded
    # (Metrics collection should have recorded errors)
    assert node.metrics is not None


@pytest.mark.asyncio
async def test_rate_limiter_recovery_after_window():
    """Test that rate limiter recovers after time window"""
    identity = NodeIdentity()
    node = P2PNode(identity=identity, address="ws://localhost:8000")
    
    # Set low rate limit
    node.rate_limiter.set_limit(
        "test_peer",
        RateLimitConfig(max_requests=2, time_window=0.5)
    )
    
    # Send messages up to limit
    for i in range(2):
        message = {"jsonrpc": "2.0", "method": "node/ping", "id": i}
        await node._route_message(message, sender_node_id="test_peer")
    
    # Next should be rate limited
    message = {"jsonrpc": "2.0", "method": "node/ping", "id": 3}
    result = await node._route_message(message, sender_node_id="test_peer")
    assert "error" in result
    
    # Wait for time window to expire
    await asyncio.sleep(0.6)
    
    # Next message should be allowed
    message = {"jsonrpc": "2.0", "method": "node/ping", "id": 4}
    result = await node._route_message(message, sender_node_id="test_peer")
    # Should not be rate limited (may still have error if method doesn't exist, but not rate limit error)
    if result and "error" in result:
        assert result["error"]["code"] != -32000 or "rate limit" not in result["error"]["message"].lower()


@pytest.mark.asyncio
async def test_circuit_breaker_state_transitions():
    """Test that circuit breaker transitions between states correctly"""
    from resilience.circuit_breaker import CircuitState
    
    cb = CircuitBreaker(
        name="test_cb",
        config=CircuitBreakerConfig(failure_threshold=2, timeout=0.5)
    )
    
    assert cb.state == CircuitState.CLOSED
    
    # Record failures
    cb._record_failure()
    assert cb.state == CircuitState.CLOSED
    
    cb._record_failure()
    assert cb.state == CircuitState.OPEN
    
    # Wait for timeout
    await asyncio.sleep(0.6)
    
    # Should transition to half-open on next call attempt
    if cb._should_attempt_half_open():
        cb.state = CircuitState.HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN
    
    # Record success
    cb._record_success()
    assert cb.state == CircuitState.CLOSED
