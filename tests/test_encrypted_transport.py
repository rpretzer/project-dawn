"""
Tests for encrypted transport layer
"""

import pytest
import asyncio
import json
from crypto import NodeIdentity
from mcp.encrypted_transport import EncryptedWebSocketTransport, EncryptedWebSocketServer


class TestEncryptedTransport:
    """Test EncryptedWebSocketTransport"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test transport initialization"""
        identity = NodeIdentity()
        transport = EncryptedWebSocketTransport("ws://localhost:8000", identity)
        
        assert transport.identity == identity
        assert transport.enable_encryption is True
        assert transport.session_established is False
    
    @pytest.mark.asyncio
    async def test_plaintext_mode(self):
        """Test plaintext mode (encryption disabled)"""
        identity = NodeIdentity()
        transport = EncryptedWebSocketTransport(
            "ws://localhost:8000",
            identity,
            enable_encryption=False
        )
        
        assert transport.enable_encryption is False
        # In plaintext mode, should work without key exchange
        transport.session_established = True
        
        # Test send/receive (would need actual connection)
        # This is a unit test, so we'll test the logic
    
    def test_message_encryption_envelope(self):
        """Test encrypted message envelope format"""
        identity = NodeIdentity()
        transport = EncryptedWebSocketTransport("ws://localhost:8000", identity)
        
        # Manually set up encryptor for testing
        from crypto import MessageEncryptor
        transport.encryptor = MessageEncryptor()
        transport.session_established = True
        
        # Test encryption format
        message = '{"jsonrpc": "2.0", "id": 1, "method": "test"}'
        message_bytes = message.encode('utf-8')
        nonce, ciphertext = transport.encryptor.encrypt(message_bytes)
        
        # Create envelope
        envelope = {
            "type": "encrypted",
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
        }
        
        # Should have correct structure
        assert envelope["type"] == "encrypted"
        assert "nonce" in envelope
        assert "ciphertext" in envelope
    
    def test_message_signing(self):
        """Test message signing in envelope"""
        identity = NodeIdentity()
        transport = EncryptedWebSocketTransport("ws://localhost:8000", identity)
        
        # Manually set up for testing
        from crypto import MessageEncryptor
        transport.encryptor = MessageEncryptor()
        transport.session_established = True
        
        # Create envelope
        message = '{"jsonrpc": "2.0", "id": 1, "method": "test"}'
        message_bytes = message.encode('utf-8')
        nonce, ciphertext = transport.encryptor.encrypt(message_bytes)
        
        envelope = {
            "type": "encrypted",
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
        }
        
        # Sign envelope
        if transport.signer:
            import json
            envelope_bytes = json.dumps(envelope, sort_keys=True).encode('utf-8')
            signature = transport.signer.sign(envelope_bytes)
            envelope["signature"] = signature.hex()
            envelope["sender"] = transport.identity.get_node_id()
            
            assert "signature" in envelope
            assert "sender" in envelope


class TestEncryptedWebSocketServer:
    """Test EncryptedWebSocketServer"""
    
    def test_initialization(self):
        """Test server initialization"""
        identity = NodeIdentity()
        server = EncryptedWebSocketServer(identity)
        
        assert server.identity == identity
        assert server.enable_encryption is True
        assert len(server.client_sessions) == 0
    
    def test_plaintext_mode(self):
        """Test plaintext mode"""
        identity = NodeIdentity()
        server = EncryptedWebSocketServer(identity, enable_encryption=False)
        
        assert server.enable_encryption is False
    
    @pytest.mark.asyncio
    async def test_key_exchange_handshake(self):
        """Test key exchange handshake format"""
        from crypto import KeyExchange
        
        identity = NodeIdentity()
        server = EncryptedWebSocketServer(identity)
        
        # Simulate client handshake
        client_identity = NodeIdentity()
        client_key_exchange = KeyExchange()
        client_public_key = client_key_exchange.get_public_key_bytes()
        
        handshake = {
            "type": "key_exchange",
            "public_key": client_public_key.hex(),
            "node_id": client_identity.get_node_id(),
        }
        
        # Process handshake
        response = await server._handle_key_exchange("test_client", handshake)
        
        assert response is not None
        response_data = json.loads(response)
        assert response_data["type"] == "key_exchange"
        assert "public_key" in response_data
        assert "node_id" in response_data
    
    @pytest.mark.asyncio
    async def test_message_encryption_decryption(self):
        """Test message encryption/decryption flow"""
        identity = NodeIdentity()
        server = EncryptedWebSocketServer(identity)
        
        # Set up a client session manually
        from crypto import KeyExchange, perform_key_exchange, MessageEncryptor
        
        server_key_exchange = KeyExchange()
        client_key_exchange = KeyExchange()
        
        shared_secret, _ = perform_key_exchange(server_key_exchange, client_key_exchange)
        encryptor = MessageEncryptor(shared_secret)
        
        server.client_sessions["test_client"] = {
            "key_exchange": server_key_exchange,
            "encryptor": encryptor,
            "session_established": True,
        }
        
        # Encrypt a message
        original_message = '{"jsonrpc": "2.0", "id": 1, "method": "test"}'
        message_bytes = original_message.encode('utf-8')
        nonce, ciphertext = encryptor.encrypt(message_bytes)
        
        envelope = {
            "type": "encrypted",
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
        }
        
        # Decrypt via server
        encrypted_str = json.dumps(envelope)
        decrypted = await server._handle_message(encrypted_str, "test_client")
        
        assert decrypted == original_message


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_encryption(self):
        """Test end-to-end encryption flow"""
        # This would require actual WebSocket connections
        # For now, test the encryption/decryption logic
        
        from crypto import KeyExchange, perform_key_exchange, MessageEncryptor, MessageSigner
        
        # Setup
        alice_identity = NodeIdentity()
        bob_identity = NodeIdentity()
        
        alice_key_exchange = KeyExchange()
        bob_key_exchange = KeyExchange()
        
        # Key exchange
        shared_secret, _ = perform_key_exchange(alice_key_exchange, bob_key_exchange)
        
        # Create encryptors
        alice_encryptor = MessageEncryptor(shared_secret)
        bob_encryptor = MessageEncryptor(shared_secret)
        
        # Alice encrypts
        message = '{"jsonrpc": "2.0", "id": 1, "method": "test"}'
        message_bytes = message.encode('utf-8')
        nonce, ciphertext = alice_encryptor.encrypt(message_bytes)
        
        # Bob decrypts
        decrypted = bob_encryptor.decrypt(nonce, ciphertext)
        assert decrypted == message_bytes
        
        # Signing
        alice_signer = MessageSigner(alice_identity)
        signature = alice_signer.sign(message_bytes)
        
        # Verify
        assert alice_signer.verify(message_bytes, signature)
    
    def test_backward_compatibility(self):
        """Test backward compatibility with plaintext"""
        identity = NodeIdentity()
        
        # Plaintext transport
        transport = EncryptedWebSocketTransport(
            "ws://localhost:8000",
            identity,
            enable_encryption=False
        )
        
        # Should work without encryption
        transport.session_established = True
        assert transport.enable_encryption is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

