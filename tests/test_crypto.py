"""
Comprehensive tests for cryptographic components
"""

import pytest
from crypto import (
    NodeIdentity,
    MessageSigner,
    MessageEncryptor,
    KeyExchange,
    create_signed_message,
    verify_signed_message,
    create_encrypted_message,
    decrypt_message,
    perform_key_exchange,
    hash_bytes,
    hash_string,
    constant_time_compare,
)


class TestNodeIdentity:
    """Test NodeIdentity"""
    
    def test_generate_new_identity(self):
        """Test generating new identity"""
        identity = NodeIdentity()
        assert identity.can_sign()
        assert identity.get_node_id() is not None
        assert len(identity.get_node_id()) == 64  # 32 bytes = 64 hex chars
    
    def test_node_id_short(self):
        """Test short node ID"""
        identity = NodeIdentity()
        short_id = identity.get_node_id_short()
        assert len(short_id) == 16
        assert short_id == identity.get_node_id()[:16]
    
    def test_serialize_keys(self):
        """Test key serialization"""
        identity = NodeIdentity()
        
        private_bytes = identity.serialize_private_key()
        assert len(private_bytes) == 32
        
        public_bytes = identity.serialize_public_key()
        assert len(public_bytes) == 32
    
    def test_from_private_key_bytes(self):
        """Test creating identity from private key bytes"""
        identity1 = NodeIdentity()
        private_bytes = identity1.serialize_private_key()
        
        identity2 = NodeIdentity.from_private_key_bytes(private_bytes)
        assert identity2.get_node_id() == identity1.get_node_id()
        assert identity2.can_sign()
    
    def test_from_public_key_bytes(self):
        """Test creating read-only identity from public key"""
        identity1 = NodeIdentity()
        public_bytes = identity1.serialize_public_key()
        
        identity2 = NodeIdentity.from_public_key_bytes(public_bytes)
        assert identity2.get_node_id() == identity1.get_node_id()
        assert not identity2.can_sign()  # Read-only
    
    def test_unique_identities(self):
        """Test that each identity is unique"""
        identity1 = NodeIdentity()
        identity2 = NodeIdentity()
        
        assert identity1.get_node_id() != identity2.get_node_id()


class TestMessageSigner:
    """Test MessageSigner"""
    
    def test_sign_and_verify(self):
        """Test signing and verifying messages"""
        identity = NodeIdentity()
        signer = MessageSigner(identity)
        
        message = b"Hello, World!"
        signature = signer.sign(message)
        
        assert len(signature) == 64  # Ed25519 signature is 64 bytes
        assert signer.verify(message, signature)
    
    def test_sign_string(self):
        """Test signing string messages"""
        identity = NodeIdentity()
        signer = MessageSigner(identity)
        
        message = "Hello, World!"
        signature = signer.sign_string(message)
        
        assert signer.verify_string(message, signature)
    
    def test_verify_with_different_key_fails(self):
        """Test that verification fails with wrong key"""
        identity1 = NodeIdentity()
        identity2 = NodeIdentity()
        
        signer1 = MessageSigner(identity1)
        signer2 = MessageSigner(identity2)
        
        message = b"Hello, World!"
        signature = signer1.sign(message)
        
        # Should fail with different key
        assert not signer2.verify(message, signature)
    
    def test_verify_with_public_key_bytes(self):
        """Test verification with public key bytes"""
        identity = NodeIdentity()
        signer = MessageSigner(identity)
        
        message = b"Hello, World!"
        signature = signer.sign(message)
        public_key_bytes = identity.serialize_public_key()
        
        assert MessageSigner.verify_with_public_key_bytes(message, signature, public_key_bytes)
    
    def test_signed_message_envelope(self):
        """Test signed message envelope"""
        identity = NodeIdentity()
        signer = MessageSigner(identity)
        
        message = b"Hello, World!"
        envelope = create_signed_message(message, signer)
        
        assert "message" in envelope
        assert "signature" in envelope
        assert "sender" in envelope
        assert envelope["sender"] == identity.get_node_id()
        
        # Verify envelope
        public_key_bytes = identity.serialize_public_key()
        verified_message = verify_signed_message(envelope, public_key_bytes)
        assert verified_message == message
    
    def test_read_only_identity_cannot_sign(self):
        """Test that read-only identity cannot sign"""
        identity1 = NodeIdentity()
        public_bytes = identity1.serialize_public_key()
        identity2 = NodeIdentity.from_public_key_bytes(public_bytes)
        
        with pytest.raises(ValueError):
            MessageSigner(identity2)


class TestMessageEncryptor:
    """Test MessageEncryptor"""
    
    def test_encrypt_and_decrypt(self):
        """Test encryption and decryption"""
        encryptor = MessageEncryptor()
        
        plaintext = b"Hello, World!"
        nonce, ciphertext = encryptor.encrypt(plaintext)
        
        assert len(nonce) == 12  # GCM nonce is 12 bytes
        assert len(ciphertext) > len(plaintext)  # Includes tag
        
        decrypted = encryptor.decrypt(nonce, ciphertext)
        assert decrypted == plaintext
    
    def test_encrypt_string(self):
        """Test encrypting strings"""
        encryptor = MessageEncryptor()
        
        plaintext = "Hello, World!"
        nonce, ciphertext = encryptor.encrypt_string(plaintext)
        
        decrypted = encryptor.decrypt_string(nonce, ciphertext)
        assert decrypted == plaintext
    
    def test_associated_data(self):
        """Test encryption with associated data"""
        encryptor = MessageEncryptor()
        
        plaintext = b"Hello, World!"
        ad = b"metadata"
        
        nonce, ciphertext = encryptor.encrypt(plaintext, ad)
        
        # Decrypt with correct AD
        decrypted = encryptor.decrypt(nonce, ciphertext, ad)
        assert decrypted == plaintext
        
        # Decrypt with wrong AD should fail
        with pytest.raises(ValueError):
            encryptor.decrypt(nonce, ciphertext, b"wrong")
    
    def test_different_keys_dont_decrypt(self):
        """Test that wrong key cannot decrypt"""
        encryptor1 = MessageEncryptor()
        encryptor2 = MessageEncryptor()
        
        plaintext = b"Hello, World!"
        nonce, ciphertext = encryptor1.encrypt(plaintext)
        
        # Should fail with different key
        with pytest.raises(ValueError):
            encryptor2.decrypt(nonce, ciphertext)
    
    def test_encrypted_message_envelope(self):
        """Test encrypted message envelope"""
        encryptor = MessageEncryptor()
        
        plaintext = b"Hello, World!"
        envelope = create_encrypted_message(plaintext, encryptor)
        
        assert "nonce" in envelope
        assert "ciphertext" in envelope
        
        decrypted = decrypt_message(envelope, encryptor)
        assert decrypted == plaintext
    
    def test_same_key_different_encryption(self):
        """Test that same plaintext encrypts differently each time"""
        encryptor = MessageEncryptor()
        
        plaintext = b"Hello, World!"
        nonce1, ciphertext1 = encryptor.encrypt(plaintext)
        nonce2, ciphertext2 = encryptor.encrypt(plaintext)
        
        # Should be different (different nonces)
        assert nonce1 != nonce2 or ciphertext1 != ciphertext2


class TestKeyExchange:
    """Test KeyExchange"""
    
    def test_generate_keypair(self):
        """Test generating keypair"""
        exchange = KeyExchange()
        assert exchange.public_key is not None
        assert exchange.private_key is not None
    
    def test_public_key_bytes(self):
        """Test public key serialization"""
        exchange = KeyExchange()
        public_bytes = exchange.get_public_key_bytes()
        assert len(public_bytes) == 32
    
    def test_derive_shared_secret(self):
        """Test deriving shared secret"""
        alice = KeyExchange()
        bob = KeyExchange()
        
        alice_secret = alice.derive_shared_secret(bob.public_key)
        bob_secret = bob.derive_shared_secret(alice.public_key)
        
        assert alice_secret == bob_secret
        assert len(alice_secret) == 32
    
    def test_derive_from_bytes(self):
        """Test deriving secret from public key bytes"""
        alice = KeyExchange()
        bob = KeyExchange()
        
        bob_public_bytes = bob.get_public_key_bytes()
        alice_secret = alice.derive_shared_secret_from_bytes(bob_public_bytes)
        
        bob_secret = bob.derive_shared_secret(alice.public_key)
        assert alice_secret == bob_secret
    
    def test_perform_key_exchange(self):
        """Test key exchange function"""
        alice = KeyExchange()
        bob = KeyExchange()
        
        alice_secret, bob_secret = perform_key_exchange(alice, bob)
        
        assert alice_secret == bob_secret
        assert len(alice_secret) == 32
    
    def test_key_exchange_with_salt_and_info(self):
        """Test key exchange with salt and info"""
        alice = KeyExchange()
        bob = KeyExchange()
        
        salt = b"test-salt"
        info = b"test-info"
        
        alice_secret = alice.derive_shared_secret(bob.public_key, salt, info)
        bob_secret = bob.derive_shared_secret(alice.public_key, salt, info)
        
        assert alice_secret == bob_secret
    
    def test_from_private_key_bytes(self):
        """Test creating KeyExchange from private key bytes"""
        exchange1 = KeyExchange()
        private_bytes = exchange1.get_private_key_bytes()
        
        exchange2 = KeyExchange.from_private_key_bytes(private_bytes)
        assert exchange2.get_public_key_bytes() == exchange1.get_public_key_bytes()


class TestUtilities:
    """Test utility functions"""
    
    def test_generate_random_bytes(self):
        """Test random byte generation"""
        from crypto.utils import generate_random_bytes
        
        bytes1 = generate_random_bytes(32)
        bytes2 = generate_random_bytes(32)
        
        assert len(bytes1) == 32
        assert len(bytes2) == 32
        assert bytes1 != bytes2  # Should be different
    
    def test_hash_bytes(self):
        """Test byte hashing"""
        data = b"Hello, World!"
        hash1 = hash_bytes(data, "sha256")
        hash2 = hash_bytes(data, "sha256")
        
        assert len(hash1) == 32  # SHA256 is 32 bytes
        assert hash1 == hash2  # Same input = same hash
    
    def test_hash_string(self):
        """Test string hashing"""
        data = "Hello, World!"
        hash1 = hash_string(data)
        hash2 = hash_string(data)
        
        assert len(hash1) == 64  # SHA256 hex is 64 chars
        assert hash1 == hash2
    
    def test_constant_time_compare(self):
        """Test constant-time comparison"""
        a = b"test"
        b = b"test"
        c = b"different"
        
        assert constant_time_compare(a, b)
        assert not constant_time_compare(a, c)
        assert not constant_time_compare(a, b"test1")  # Different length


class TestIntegration:
    """Integration tests"""
    
    def test_sign_and_encrypt_flow(self):
        """Test signing then encrypting a message"""
        # Setup
        identity = NodeIdentity()
        signer = MessageSigner(identity)
        encryptor = MessageEncryptor()
        
        # Original message
        message = b"Hello, World!"
        
        # Sign
        signature = signer.sign(message)
        
        # Encrypt message + signature
        combined = message + b":" + signature
        nonce, ciphertext = encryptor.encrypt(combined)
        
        # Decrypt
        decrypted = encryptor.decrypt(nonce, ciphertext)
        message2, signature2 = decrypted.split(b":", 1)
        
        # Verify
        assert message2 == message
        assert signer.verify(message2, signature2)
    
    def test_key_exchange_then_encrypt(self):
        """Test key exchange then using shared secret for encryption"""
        # Setup key exchange
        alice = KeyExchange()
        bob = KeyExchange()
        
        alice_secret, bob_secret = perform_key_exchange(alice, bob)
        assert alice_secret == bob_secret
        
        # Use shared secret for encryption
        alice_encryptor = MessageEncryptor(alice_secret)
        bob_encryptor = MessageEncryptor(bob_secret)
        
        # Alice encrypts
        message = b"Hello, Bob!"
        nonce, ciphertext = alice_encryptor.encrypt(message)
        
        # Bob decrypts
        decrypted = bob_encryptor.decrypt(nonce, ciphertext)
        assert decrypted == message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

