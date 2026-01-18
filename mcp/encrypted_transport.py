"""
Encrypted WebSocket Transport

Wraps WebSocket transport with end-to-end encryption and message signing.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Callable, Awaitable
from .transport import WebSocketServer, ConnectionState
from crypto import (
    NodeIdentity,
    MessageSigner,
    MessageEncryptor,
    KeyExchange,
    perform_key_exchange,
)

# Try to import websockets
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets library not available. Encrypted transport disabled.")

# Try to import resilience components for retry policies
try:
    from resilience import RetryPolicy, retry_async
    from resilience.errors import NetworkError, RetryExhaustedError
    RESILIENCE_AVAILABLE = True
except ImportError:
    RESILIENCE_AVAILABLE = False

logger = logging.getLogger(__name__)


class EncryptedWebSocketTransport:
    """
    Encrypted WebSocket transport wrapper
    
    Provides end-to-end encryption and message signing for WebSocket connections.
    """
    
    def __init__(
        self,
        url: str,
        identity: NodeIdentity,
        peer_public_key: Optional[bytes] = None,
        enable_encryption: bool = True,
        message_handler: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        """
        Initialize encrypted transport
        
        Args:
            url: WebSocket URL
            identity: Node identity for signing
            peer_public_key: Optional peer's public key (for pre-shared key)
            enable_encryption: Enable encryption (can disable for testing)
            message_handler: Optional callback for handling received messages
        """
        self.url = url
        self.identity = identity
        self.enable_encryption = enable_encryption
        self.message_handler = message_handler
        
        # Underlying WebSocket transport
        # We'll use websockets directly for client connections
        self.websocket = None
        self._receive_task = None
        
        # Encryption state
        self.encryptor: Optional[MessageEncryptor] = None
        self.signer = MessageSigner(identity) if identity.can_sign() else None
        self.key_exchange: Optional[KeyExchange] = None
        self.peer_key_exchange: Optional[KeyExchange] = None
        self.peer_public_key = peer_public_key
        
        # Session state
        self.session_established = False
        self.connection_state = ConnectionState.DISCONNECTED
        
        logger.debug(f"EncryptedWebSocketTransport initialized (encryption: {enable_encryption})")
    
    async def connect(self) -> None:
        """Connect and establish encrypted session"""
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets library not available")
        
        self.connection_state = ConnectionState.CONNECTING
        logger.info(f"Connecting to {self.url}...")
        
        try:
            # Use retry policy if available
            if RESILIENCE_AVAILABLE:
                retry_policy = RetryPolicy(
                    max_attempts=3,
                    initial_delay=1.0,
                    max_delay=10.0,
                    retryable_errors=(ConnectionError, TimeoutError, OSError),
                )
                
                async def _do_connect():
                    self.websocket = await websockets.connect(self.url)
                    self.connection_state = ConnectionState.CONNECTED
                    logger.info(f"Connected to {self.url}")
                
                try:
                    await retry_async(
                        _do_connect,
                        retry_policy,
                        operation_name="connect",
                    )
                except RetryExhaustedError as e:
                    self.connection_state = ConnectionState.ERROR
                    raise NetworkError(
                        f"Connection failed after {retry_policy.max_attempts} attempts",
                        original_error=e,
                    ) from e
            else:
                # Fallback without retry policy
                self.websocket = await websockets.connect(self.url)
                self.connection_state = ConnectionState.CONNECTED
                logger.info(f"Connected to {self.url}")
            
            if self.enable_encryption:
                await self._establish_session()
            else:
                self.session_established = True
                logger.debug("Connected in plaintext mode")
            
            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())
        
        except NetworkError:
            # Re-raise network errors
            raise
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.connection_state = ConnectionState.ERROR
            raise
    
    async def _receive_loop(self) -> None:
        """Receive messages from WebSocket"""
        try:
            async for message in self.websocket:
                if isinstance(message, str):
                    await self._handle_received_message(message)
                elif isinstance(message, bytes):
                    try:
                        text_message = message.decode('utf-8')
                        await self._handle_received_message(text_message)
                    except UnicodeDecodeError:
                        logger.error("Failed to decode message")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            self.connection_state = ConnectionState.ERROR
    
    async def _handle_received_message(self, message: str) -> None:
        """
        Handle received message (for client mode)
        
        Decrypts and processes incoming messages, routing them to the message handler.
        """
        try:
            # Check if message is encrypted
            if self.enable_encryption and self.encryptor:
                try:
                    # Parse envelope
                    envelope = json.loads(message)
                    if envelope.get("type") == "encrypted":
                        # Decrypt message
                        nonce = bytes.fromhex(envelope["nonce"])
                        ciphertext = bytes.fromhex(envelope["ciphertext"])
                        plaintext = self.encryptor.decrypt(nonce, ciphertext)
                        decrypted_message = plaintext.decode('utf-8')
                        
                        # Verify signature if present
                        if "signature" in envelope and "sender" in envelope:
                            sender = envelope.get("sender", "unknown")
                            signature = bytes.fromhex(envelope["signature"])
                            
                            if self.peer_public_key:
                                # Reconstruct the message that was signed
                                envelope_for_signing = {
                                    "type": envelope["type"],
                                    "nonce": envelope["nonce"],
                                    "ciphertext": envelope["ciphertext"],
                                }
                                envelope_bytes = json.dumps(envelope_for_signing, sort_keys=True).encode('utf-8')

                                # Verify the signature
                                if MessageSigner.verify_with_public_key_bytes(envelope_bytes, signature, self.peer_public_key):
                                    logger.debug(f"Verified signed message from server {sender[:16]}...")
                                else:
                                    logger.warning(f"INVALID signature in message from server {sender[:16]}")
                                    return  # Drop the message
                            else:
                                logger.warning(f"Received signed message from server {sender[:16]} but have no public key to verify.")
                        
                        message = decrypted_message
                        logger.debug("Decrypted message from server")
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Not encrypted or invalid format, use as-is
                    pass
                except Exception as e:
                    logger.error(f"Error decrypting message: {e}")
                    return
            
            # Route to message handler if provided
            if self.message_handler:
                try:
                    await self.message_handler(message)
                except Exception as e:
                    logger.error(f"Error in message handler: {e}", exc_info=True)
            else:
                # No handler, just log
                logger.debug(f"Received message (no handler): {message[:100]}")
        
        except Exception as e:
            logger.error(f"Error handling received message: {e}", exc_info=True)
    
    async def _establish_session(self) -> None:
        """
        Establish encrypted session with peer
        
        Performs key exchange to establish shared secret.
        """
        try:
            # Initialize key exchange
            self.key_exchange = KeyExchange()
            
            # Send our public key
            our_public_key = self.key_exchange.get_public_key_bytes()
            our_node_id = self.identity.get_node_id()
            
            # Create handshake message
            handshake = {
                "type": "key_exchange",
                "public_key": our_public_key.hex(),
                "node_id": our_node_id,
            }
            
            # Sign handshake
            if self.signer:
                handshake_bytes = json.dumps(handshake, sort_keys=True).encode('utf-8')
                signature = self.signer.sign(handshake_bytes)
                handshake["signature"] = signature.hex()
            
            # Send handshake
            await self.websocket.send(json.dumps(handshake))
            logger.debug("Sent key exchange handshake")
            
            # Wait for peer's handshake
            response_str = await self.websocket.recv()
            if not response_str:
                raise ConnectionError("No response to key exchange")
            
            response = json.loads(response_str)
            
            if response.get("type") != "key_exchange":
                raise ValueError("Invalid key exchange response")
            
            # Verify peer's signature if present
            peer_public_key_bytes = bytes.fromhex(response["public_key"])
            peer_node_id = response["node_id"]
            
            if "signature" in response:
                signature = bytes.fromhex(response["signature"])
                handshake_bytes = json.dumps({
                    "type": response["type"],
                    "public_key": response["public_key"],
                    "node_id": response["node_id"],
                }, sort_keys=True).encode('utf-8')
                
                # Note: The handshake uses X25519 public key for key exchange,
                # but the signature is with Ed25519. In a production system, you'd
                # need to either:
                # 1. Include the Ed25519 public key in the handshake
                # 2. Look up the peer's Ed25519 public key from a registry
                # 3. Use the same keypair for both (X25519 and Ed25519 can share keys)
                
                # For now, we'll log that we received a signature but can't verify it
                # without the peer's Ed25519 public key
                logger.debug(f"Received signed handshake from {peer_node_id[:16]} (signature present but not verified - need Ed25519 public key)")
            
            # Derive shared secret
            self.peer_key_exchange = KeyExchange.from_public_key_bytes(peer_public_key_bytes)
            shared_secret, _ = perform_key_exchange(self.key_exchange, self.peer_key_exchange)
            
            # Create encryptor with shared secret
            self.encryptor = MessageEncryptor(shared_secret)
            self.session_established = True
            
            logger.info(f"Encrypted session established with {peer_node_id[:16]}")
        
        except Exception as e:
            logger.error(f"Failed to establish encrypted session: {e}", exc_info=True)
            raise
    
    async def send(self, message: str) -> None:
        """
        Send encrypted and signed message
        
        Args:
            message: JSON-RPC message as string
        """
        if not self.session_established:
            raise RuntimeError("Session not established")
        
        if self.enable_encryption and self.encryptor:
            # Encrypt message
            message_bytes = message.encode('utf-8')
            nonce, ciphertext = self.encryptor.encrypt(message_bytes)
            
            # Create encrypted envelope
            envelope = {
                "type": "encrypted",
                "nonce": nonce.hex(),
                "ciphertext": ciphertext.hex(),
            }
            
            # Sign envelope if we have a signer
            if self.signer:
                envelope_bytes = json.dumps(envelope, sort_keys=True).encode('utf-8')
                signature = self.signer.sign(envelope_bytes)
                envelope["signature"] = signature.hex()
                envelope["sender"] = self.identity.get_node_id()
            
            # Send encrypted envelope
            await self.websocket.send(json.dumps(envelope))
            logger.debug("Sent encrypted message")
        else:
            # Plaintext mode
            await self.websocket.send(message)
            logger.debug("Sent plaintext message")
    
    async def receive(self) -> Optional[str]:
        """
        Receive and decrypt message
        
        Returns:
            Decrypted JSON-RPC message or None
        """
        if not self.websocket:
            return None
        
        try:
            raw_message = await self.websocket.recv()
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None
        
        if not raw_message:
            return None
        
        if self.enable_encryption and self.encryptor:
            try:
                # Parse envelope
                envelope = json.loads(raw_message)
                
                if envelope.get("type") != "encrypted":
                    # Not encrypted, return as-is (backward compatibility)
                    return raw_message
                
                # Verify signature if present
                if "signature" in envelope and "sender" in envelope:
                    # In production, verify against known peer identities
                    # For now, just log
                    sender = envelope.get("sender", "unknown")
                    logger.debug(f"Received signed message from {sender[:16]}")
                
                # Decrypt
                nonce = bytes.fromhex(envelope["nonce"])
                ciphertext = bytes.fromhex(envelope["ciphertext"])
                plaintext = self.encryptor.decrypt(nonce, ciphertext)
                
                message = plaintext.decode('utf-8')
                logger.debug("Received and decrypted message")
                return message
            
            except Exception as e:
                logger.error(f"Failed to decrypt message: {e}", exc_info=True)
                return None
        else:
            # Plaintext mode
            return raw_message
    
    async def disconnect(self) -> None:
        """Disconnect"""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        
        self.connection_state = ConnectionState.DISCONNECTED
        self.session_established = False
        self.encryptor = None
        self.websocket = None
        logger.debug("Disconnected encrypted transport")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return (self.connection_state == ConnectionState.CONNECTED and 
                self.websocket is not None and 
                self.session_established)


class EncryptedWebSocketServer:
    """
    Encrypted WebSocket server
    
    Handles encrypted connections from multiple clients.
    """
    
    def __init__(
        self,
        identity: NodeIdentity,
        message_handler: Optional[Callable[[str, Any], Awaitable[Optional[str]]]] = None,
        on_connect: Optional[Callable[[Any], Awaitable[None]]] = None,
        on_disconnect: Optional[Callable[[Any], Awaitable[None]]] = None,
        enable_encryption: bool = True,
        peer_registry: Optional[Any] = None,
        trust_manager: Optional[Any] = None,
        peer_validator: Optional[Any] = None,
    ):
        """
        Initialize encrypted WebSocket server
        
        Args:
            identity: Server node identity
            message_handler: Handler for incoming messages
            on_connect: Callback on client connect
            on_disconnect: Callback on client disconnect
            enable_encryption: Enable encryption
            peer_registry: Optional peer registry for signature verification
            trust_manager: Optional trust manager for peer trust management
            peer_validator: Optional peer validator for signature verification
        """
        self.identity = identity
        self.enable_encryption = enable_encryption
        self.signer = MessageSigner(identity) if identity.can_sign() else None
        self.message_handler = message_handler
        self.peer_registry = peer_registry
        self.trust_manager = trust_manager
        self.peer_validator = peer_validator
        
        # Client sessions: client_id -> (encryptor, key_exchange, peer_node_id, peer_public_key)
        self.client_sessions: Dict[Any, Dict[str, Any]] = {}
        
        # Underlying WebSocket server
        self.server = WebSocketServer(
            message_handler=self._handle_message,
            on_connect=self._on_client_connect,
            on_disconnect=self._on_client_disconnect,
        )
        
        logger.debug(f"EncryptedWebSocketServer initialized (encryption: {enable_encryption})")
    
    async def _on_client_connect(self, client_id: Any) -> None:
        """Handle client connection"""
        self.client_sessions[client_id] = {
            "key_exchange": None,
            "encryptor": None,
            "session_established": False,
            "peer_node_id": None,
            "peer_public_key": None,
        }
        
        logger.debug(f"Client {client_id} connected, waiting for key exchange")
    
    async def _on_client_disconnect(self, client_id: Any) -> None:
        """Handle client disconnection"""
        if client_id in self.client_sessions:
            del self.client_sessions[client_id]
        logger.debug(f"Client {client_id} disconnected")
    
    async def _handle_key_exchange(self, client_id: Any, message: Dict[str, Any]) -> Optional[str]:
        """Handle key exchange handshake"""
        try:
            # Get client's public key
            client_public_key_bytes = bytes.fromhex(message["public_key"])
            client_node_id = message.get("node_id", "unknown")
            
            # Verify signature if present
            peer_public_key_bytes = None
            signature_verified = False
            
            if "signature" in message:
                signature = bytes.fromhex(message["signature"])
                handshake_bytes = json.dumps({
                    "type": message["type"],
                    "public_key": message["public_key"],
                    "node_id": message["node_id"],
                }, sort_keys=True).encode('utf-8')
                
                # Try to get peer's public key from registry
                if self.peer_registry:
                    peer = self.peer_registry.get_peer(client_node_id)
                    if peer and peer.public_key:
                        peer_public_key_bytes = peer.public_key
                
                # Try to get public key from trust manager if available
                if not peer_public_key_bytes and hasattr(self, 'trust_manager'):
                    trust_record = self.trust_manager.get_trust_record(client_node_id)
                    if trust_record and trust_record.public_key:
                        try:
                            peer_public_key_bytes = bytes.fromhex(trust_record.public_key)
                        except ValueError:
                            pass
                
                # Verify signature using peer validator if available (handles new peers)
                if self.peer_validator:
                    if self.peer_validator.validate_peer_signature(
                        client_node_id,
                        handshake_bytes,
                        signature,
                        peer_public_key_bytes,
                    ):
                        signature_verified = True
                        logger.debug(f"Verified signed handshake from {client_node_id[:16]}... (via validator)")
                    elif peer_public_key_bytes:
                        # Fallback: direct verification
                        if MessageSigner.verify_with_public_key_bytes(handshake_bytes, signature, peer_public_key_bytes):
                            signature_verified = True
                            logger.debug(f"Verified signed handshake from {client_node_id[:16]}... (direct)")
                            # Record verification
                            if self.trust_manager:
                                self.trust_manager.record_verification(client_node_id, peer_public_key_bytes.hex())
                        else:
                            logger.error(f"Invalid signature in handshake from {client_node_id[:16]}...")
                            return None
                    else:
                        logger.warning(f"Cannot verify signature for {client_node_id[:16]}... (no public key)")
                elif peer_public_key_bytes:
                    # Direct verification if no validator
                    if MessageSigner.verify_with_public_key_bytes(handshake_bytes, signature, peer_public_key_bytes):
                        signature_verified = True
                        logger.debug(f"Verified signed handshake from {client_node_id[:16]}...")
                        # Record verification
                        if self.trust_manager:
                            self.trust_manager.record_verification(client_node_id, peer_public_key_bytes.hex())
                    else:
                        logger.error(f"Invalid signature in handshake from {client_node_id[:16]}...")
                        return None
                else:
                    logger.warning(f"Peer {client_node_id[:16]}... not in registry, cannot verify signature")
                
                logger.debug(f"Received signed handshake from {client_node_id[:16]}... (verified: {signature_verified})")
            
            # Initialize our key exchange
            our_key_exchange = KeyExchange()
            
            # Derive shared secret using client's public key
            shared_secret = our_key_exchange.derive_shared_secret_from_bytes(client_public_key_bytes)
            
            # Create encryptor
            encryptor = MessageEncryptor(shared_secret)
            
            # Store session with peer information
            self.client_sessions[client_id] = {
                "key_exchange": our_key_exchange,
                "encryptor": encryptor,
                "session_established": True,
                "peer_node_id": client_node_id,
                "peer_public_key": peer_public_key_bytes if 'peer_public_key_bytes' in locals() else None,
            }
            
            # Send our public key in response
            our_public_key = our_key_exchange.get_public_key_bytes()
            our_node_id = self.identity.get_node_id()
            
            response = {
                "type": "key_exchange",
                "public_key": our_public_key.hex(),
                "node_id": our_node_id,
            }
            
            # Sign response
            if self.signer:
                response_bytes = json.dumps(response, sort_keys=True).encode('utf-8')
                signature = self.signer.sign(response_bytes)
                response["signature"] = signature.hex()
            
            logger.info(f"Key exchange complete with {client_node_id[:16]}")
            return json.dumps(response)
        
        except Exception as e:
            logger.error(f"Key exchange failed: {e}", exc_info=True)
            return None
    
    async def _handle_message(self, message: str, client_id: Any) -> Optional[str]:
        """
        Handle incoming message
        
        Decrypts and verifies, then routes to handler.
        """
        try:
            # Check if it's a key exchange message
            try:
                parsed = json.loads(message)
                if parsed.get("type") == "key_exchange":
                    return await self._handle_key_exchange(client_id, parsed)
            except (json.JSONDecodeError, KeyError):
                pass
            
            # Get client session
            session = self.client_sessions.get(client_id)
            if not session or not session.get("session_established"):
                # No session, return as-is (backward compatibility)
                return message
            
            encryptor = session.get("encryptor")
            if not encryptor:
                return message
            
            # Decrypt message
            try:
                envelope = json.loads(message)
                if envelope.get("type") != "encrypted":
                    # Not encrypted, return as-is
                    return message
                
                # Verify signature if present
                if "signature" in envelope and "sender" in envelope:
                    sender = envelope.get("sender", "unknown")
                    signature = bytes.fromhex(envelope["signature"])
                    
                    # Get sender's public key
                    sender_public_key = None
                    if self.peer_registry:
                        peer = self.peer_registry.get_peer(sender)
                        if peer and peer.public_key:
                            sender_public_key = peer.public_key
                    
                    # Also check if it's the same peer as this session
                    session = self.client_sessions.get(client_id, {})
                    if not sender_public_key and session.get("peer_public_key"):
                        sender_public_key = session.get("peer_public_key")
                    
                    if sender_public_key:
                        # Verify signature
                        envelope_for_signing = {
                            "type": envelope["type"],
                            "nonce": envelope["nonce"],
                            "ciphertext": envelope["ciphertext"],
                        }
                        envelope_bytes = json.dumps(envelope_for_signing, sort_keys=True).encode('utf-8')
                        
                        if MessageSigner.verify_with_public_key_bytes(envelope_bytes, signature, sender_public_key):
                            logger.debug(f"Verified signed message from {sender[:16]}")
                        else:
                            logger.warning(f"Invalid signature in message from {sender[:16]}")
                            return None
                    else:
                        logger.debug(f"Received signed message from {sender[:16]} (signature not verified - peer not in registry)")
                
                # Decrypt
                nonce = bytes.fromhex(envelope["nonce"])
                ciphertext = bytes.fromhex(envelope["ciphertext"])
                plaintext = encryptor.decrypt(nonce, ciphertext)
                
                decrypted_message = plaintext.decode('utf-8')
                logger.debug(f"Decrypted message from client {client_id}")
                
                # Route to message handler
                if self.message_handler:
                    try:
                        response = await self.message_handler(decrypted_message, client_id)
                        return response
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}", exc_info=True)
                        return None
                else:
                    # No handler, return decrypted message
                    return decrypted_message
            
            except Exception as e:
                logger.error(f"Failed to decrypt message: {e}", exc_info=True)
                return None
        
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return None
    
    async def send_to_client(self, client_id: Any, message: str) -> None:
        """Send encrypted message to specific client"""
        session = self.client_sessions.get(client_id)
        if not session or not session.get("session_established"):
            # No session, send plaintext
            await self.server.send_to_client(client_id, message)
            return
        
        encryptor = session.get("encryptor")
        if not encryptor:
            await self.server.send_to_client(client_id, message)
            return
        
        # Encrypt message
        message_bytes = message.encode('utf-8')
        nonce, ciphertext = encryptor.encrypt(message_bytes)
        
        envelope = {
            "type": "encrypted",
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
        }
        
        # Sign if we have a signer
        if self.signer:
            envelope_bytes = json.dumps(envelope, sort_keys=True).encode('utf-8')
            signature = self.signer.sign(envelope_bytes)
            envelope["signature"] = signature.hex()
            envelope["sender"] = self.identity.get_node_id()
        
        await self.server.send_to_client(client_id, json.dumps(envelope))
    
    async def start(self, host: str = "localhost", port: int = 8000) -> None:
        """Start encrypted WebSocket server"""
        logger.info(f"Encrypted WebSocket server started on {host}:{port}")
        await self.server.start(host, port)
    
    async def stop(self) -> None:
        """Stop server"""
        await self.server.stop()
        self.client_sessions.clear()
        logger.info("Encrypted WebSocket server stopped")
