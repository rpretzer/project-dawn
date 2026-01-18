"""
Integration Tests for Security Features

Tests trust management, authorization, and security defaults in realistic scenarios.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from crypto import NodeIdentity
from p2p.p2p_node import P2PNode
from p2p.peer import Peer
from security import TrustManager, PeerValidator, AuthManager, TrustLevel, Permission, AuditLogger


@pytest.mark.asyncio
async def test_trust_policy_reject_unknown():
    """Test that reject_unknown policy rejects unknown peers"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        identity = NodeIdentity()
        trust_manager = TrustManager(data_dir=temp_dir)
        audit_logger = AuditLogger()
        
        # Create validator with reject_unknown=True
        validator = PeerValidator(
            trust_manager=trust_manager,
            local_identity=identity,
            audit_logger=audit_logger,
            config={"reject_unknown": True}
        )
        
        # Unknown peer should be rejected
        can_connect = validator.can_connect("unknown_peer")
        assert can_connect is False
        
        # Trusted peer should be allowed
        trust_manager.add_trusted_peer(
            node_id="trusted_peer",
            public_key=NodeIdentity().serialize_public_key().hex(),
            trust_level=TrustLevel.TRUSTED
        )
        can_connect = validator.can_connect("trusted_peer")
        assert can_connect is True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_trust_policy_allow_unknown():
    """Test that reject_unknown=False allows unknown peers"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        identity = NodeIdentity()
        trust_manager = TrustManager(data_dir=temp_dir)
        audit_logger = AuditLogger()
        
        # Create validator with reject_unknown=False (default)
        validator = PeerValidator(
            trust_manager=trust_manager,
            local_identity=identity,
            audit_logger=audit_logger,
            config={"reject_unknown": False}
        )
        
        # Unknown peer should be allowed
        can_connect = validator.can_connect("unknown_peer")
        assert can_connect is True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_authorization_in_message_routing():
    """Test that authorization checks work in message routing"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        identity = NodeIdentity()
        # Create node with temp data dir
        node = P2PNode(identity=identity, address="ws://localhost:8000")
        node.trust_manager.data_dir = temp_dir
        node.trust_manager.trust_path = temp_dir / "trust.json"
        node.trust_manager.trust_records.clear()
        
        # Create untrusted peer
        peer = Peer(node_id="untrusted_peer", address="ws://localhost:9999")
        node.trust_manager.add_trusted_peer(node_id="untrusted_peer", trust_level=TrustLevel.UNTRUSTED)
        node.peer_registry.add_peer(peer)
        
        # Message from untrusted peer should be rejected
        message = {
            "jsonrpc": "2.0",
            "method": "node/ping",
            "id": 1,
        }
        result = await node._route_message(message, sender_node_id="untrusted_peer")
        assert result is not None
        assert "error" in result
        assert result["error"]["code"] == -32001
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_trust_level_escalation():
    """Test that trust levels can be escalated"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        trust_manager = TrustManager(data_dir=temp_dir)
        
        # Start with unknown
        level = trust_manager.get_trust_level("test_peer")
        assert level == TrustLevel.UNKNOWN
        
        # Add as verified
        trust_manager.add_trusted_peer(
            node_id="test_peer",
            public_key=NodeIdentity().serialize_public_key().hex(),
            trust_level=TrustLevel.VERIFIED
        )
        
        level = trust_manager.get_trust_level("test_peer")
        assert level == TrustLevel.VERIFIED
        
        # Escalate to trusted
        trust_manager.add_trusted_peer(
            node_id="test_peer",
            public_key=NodeIdentity().serialize_public_key().hex(),
            trust_level=TrustLevel.TRUSTED
        )
        
        level = trust_manager.get_trust_level("test_peer")
        assert level == TrustLevel.TRUSTED
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_audit_logging():
    """Test that security events are logged"""
    audit_logger = AuditLogger()
    
    # Log an event
    audit_logger.log_event(
        event_type="AUTHORIZATION",
        node_id="test_node",
        peer_node_id="test_peer",
        success=False,
        error="Permission denied",
    )


@pytest.mark.asyncio
async def test_permission_grants():
    """Test that permissions can be granted and checked"""
    auth_manager = AuthManager()
    node_id = "test_peer"
    
    # Grant permission
    auth_manager.grant_permission(node_id, Permission.AGENT_EXECUTE)
    
    # Check permission
    has_permission = auth_manager.has_permission(node_id, Permission.AGENT_EXECUTE)
    assert has_permission is True
    
    # Check other permission
    has_permission = auth_manager.has_permission(node_id, Permission.AGENT_WRITE)
    assert has_permission is False


@pytest.mark.asyncio
async def test_peer_validator_with_config():
    """Test that PeerValidator respects configuration"""
    identity = NodeIdentity()
    trust_manager = TrustManager()
    audit_logger = AuditLogger()
    
    # Test with reject_unknown=True
    validator1 = PeerValidator(
        trust_manager=trust_manager,
        local_identity=identity,
        audit_logger=audit_logger,
        config={"reject_unknown": True}
    )
    assert validator1.reject_unknown is True
    
    # Test with reject_unknown=False
    validator2 = PeerValidator(
        trust_manager=trust_manager,
        local_identity=identity,
        audit_logger=audit_logger,
        config={"reject_unknown": False}
    )
    assert validator2.reject_unknown is False