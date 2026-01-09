"""
Privacy & Anonymity Enhancements

Implements privacy features for the decentralized network:
- Onion routing (multi-hop encryption)
- Message padding (traffic analysis prevention)
- Timing obfuscation (delay injection, batching)
"""

import asyncio
import json
import logging
import random
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import os

from crypto import NodeIdentity, MessageEncryptor, KeyExchange

logger = logging.getLogger(__name__)

# Privacy configuration
MIN_PADDING_SIZE = 64  # Minimum message size in bytes
MAX_PADDING_SIZE = 1024  # Maximum padding to add
MIN_DELAY_MS = 10  # Minimum delay in milliseconds
MAX_DELAY_MS = 100  # Maximum delay in milliseconds
ONION_HOPS = 3  # Default number of onion routing hops


@dataclass
class OnionLayer:
    """Single layer of onion encryption"""
    next_hop: str  # Node ID of next hop
    encrypted_payload: bytes  # Encrypted data for this layer
    nonce: bytes  # Nonce for this layer


class MessagePadder:
    """
    Message padding to prevent traffic analysis
    
    Adds random padding to messages to make them uniform in size,
    preventing analysis based on message length.
    """
    
    def __init__(self, min_size: int = MIN_PADDING_SIZE, max_padding: int = MAX_PADDING_SIZE):
        """
        Initialize message padder
        
        Args:
            min_size: Minimum message size (bytes)
            max_padding: Maximum padding to add (bytes)
        """
        self.min_size = min_size
        self.max_padding = max_padding
    
    def pad_message(self, message: bytes) -> bytes:
        """
        Add padding to message
        
        Args:
            message: Original message bytes
            
        Returns:
            Padded message bytes
        """
        current_size = len(message)
        
        if current_size >= self.min_size:
            # Already large enough, add random small padding
            padding_size = random.randint(0, min(self.max_padding, current_size // 10))
        else:
            # Need to pad to minimum size
            padding_size = self.min_size - current_size + random.randint(0, self.max_padding)
        
        # Generate random padding
        padding = os.urandom(padding_size)
        
        # Create padded message: [original_length][original][padding]
        padded = len(message).to_bytes(4, 'big') + message + padding
        
        return padded
    
    def unpad_message(self, padded_message: bytes) -> bytes:
        """
        Remove padding from message
        
        Args:
            padded_message: Padded message bytes
            
        Returns:
            Original message bytes
        """
        if len(padded_message) < 4:
            raise ValueError("Invalid padded message")
        
        # Extract original length
        original_length = int.from_bytes(padded_message[:4], 'big')
        
        if original_length > len(padded_message) - 4:
            raise ValueError("Invalid message length")
        
        # Extract original message
        return padded_message[4:4+original_length]


class TimingObfuscator:
    """
    Timing obfuscation to prevent traffic analysis
    
    Adds random delays and batches messages to obscure timing patterns.
    """
    
    def __init__(
        self,
        min_delay_ms: float = MIN_DELAY_MS,
        max_delay_ms: float = MAX_DELAY_MS,
        batch_window_ms: float = 50.0,
    ):
        """
        Initialize timing obfuscator
        
        Args:
            min_delay_ms: Minimum delay in milliseconds
            max_delay_ms: Maximum delay in milliseconds
            batch_window_ms: Time window for batching messages
        """
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.batch_window_ms = batch_window_ms
        self.message_queue: List[Tuple[bytes, str]] = []  # (message, target)
        self.batch_task: Optional[asyncio.Task] = None
    
    async def send_with_delay(self, message: bytes, target: str) -> None:
        """
        Send message with random delay
        
        Args:
            message: Message to send
            target: Target node ID
        """
        # Calculate random delay
        delay_ms = random.uniform(self.min_delay_ms, self.max_delay_ms)
        await asyncio.sleep(delay_ms / 1000.0)
        
        # Send message (would be handled by caller)
        logger.debug(f"Sent message to {target[:16]}... with {delay_ms:.1f}ms delay")
    
    async def batch_send(self, message: bytes, target: str, send_callback) -> None:
        """
        Batch message for sending (reduces timing patterns)
        
        Args:
            message: Message to send
            target: Target node ID
            send_callback: Callback to actually send the message
        """
        self.message_queue.append((message, target))
        
        # Start batch task if not running
        if not self.batch_task or self.batch_task.done():
            self.batch_task = asyncio.create_task(self._process_batch(send_callback))
    
    async def _process_batch(self, send_callback) -> None:
        """Process batched messages"""
        await asyncio.sleep(self.batch_window_ms / 1000.0)
        
        # Send all queued messages
        messages_to_send = self.message_queue.copy()
        self.message_queue.clear()
        
        # Shuffle to obscure order
        random.shuffle(messages_to_send)
        
        for message, target in messages_to_send:
            try:
                await send_callback(message, target)
            except Exception as e:
                logger.error(f"Error sending batched message: {e}")


class OnionRouter:
    """
    Onion routing for anonymous communication
    
    Implements multi-hop encryption where each hop only knows
    the next hop, not the final destination.
    """
    
    def __init__(self, identity: NodeIdentity, padder: Optional[MessagePadder] = None):
        """
        Initialize onion router
        
        Args:
            identity: Node identity for encryption
            padder: Optional message padder
        """
        self.identity = identity
        self.padder = padder or MessagePadder()
        self.routing_table: Dict[str, List[str]] = {}  # target -> [hop1, hop2, ...]
    
    def build_onion(
        self,
        message: bytes,
        path: List[str],
        target_node_id: str,
    ) -> bytes:
        """
        Build onion-encrypted message
        
        Args:
            message: Original message
            path: List of node IDs for routing path (excluding target)
            target_node_id: Final destination node ID
            
        Returns:
            Onion-encrypted message bytes
        """
        # Pad message first
        padded_message = self.padder.pad_message(message)
        
        # Build onion from inside out
        # Start with target node
        current_payload = padded_message
        full_path = path + [target_node_id]
        
        # Encrypt layer by layer (from target backwards)
        for i in range(len(full_path) - 1, -1, -1):
            current_node = full_path[i]
            next_node = full_path[i + 1] if i + 1 < len(full_path) else None
            
            # Create layer payload
            if next_node:
                layer_data = {
                    "next_hop": next_node,
                    "payload": current_payload.hex(),
                }
            else:
                # Final layer (target)
                layer_data = {
                    "payload": current_payload.hex(),
                }
            
            # Encrypt this layer
            # In production, would use shared secret with current_node
            # For now, use a simplified encryption
            layer_json = json.dumps(layer_data).encode('utf-8')
            
            # Use AES-GCM for layer encryption
            # In production, would derive key from node's public key
            key = os.urandom(32)  # Simplified - would use key exchange
            aesgcm = AESGCM(key)
            nonce = os.urandom(12)
            encrypted_layer = aesgcm.encrypt(nonce, layer_json, None)
            
            # Create layer structure
            current_payload = json.dumps({
                "encrypted": encrypted_layer.hex(),
                "nonce": nonce.hex(),
            }).encode('utf-8')
        
        return current_payload
    
    def peel_onion_layer(self, onion_message: bytes, sender_node_id: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Peel one layer of onion encryption
        
        Args:
            onion_message: Onion-encrypted message
            sender_node_id: Node ID of sender (for key derivation)
            
        Returns:
            Tuple of (decrypted_payload, next_hop_node_id)
            Returns (None, None) if this is the final destination
        """
        try:
            # Parse layer
            layer_data = json.loads(onion_message.decode('utf-8'))
            encrypted = bytes.fromhex(layer_data["encrypted"])
            nonce = bytes.fromhex(layer_data["nonce"])
            
            # Decrypt layer
            # In production, would derive key from sender's public key
            key = os.urandom(32)  # Simplified - would use key exchange
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(nonce, encrypted, None)
            
            # Parse decrypted layer
            layer_info = json.loads(decrypted.decode('utf-8'))
            
            next_hop = layer_info.get("next_hop")
            payload = bytes.fromhex(layer_info["payload"])
            
            # If no next_hop, this is the final destination
            if not next_hop:
                # Unpad and return
                try:
                    unpadded = self.padder.unpad_message(payload)
                    return (unpadded, None)
                except Exception as e:
                    logger.error(f"Error unpadding message: {e}")
                    return (payload, None)  # Return as-is if unpadding fails
            
            return (payload, next_hop)
        
        except Exception as e:
            logger.error(f"Error peeling onion layer: {e}", exc_info=True)
            return (None, None)
    
    def select_path(self, target_node_id: str, num_hops: int = ONION_HOPS) -> List[str]:
        """
        Select routing path for onion routing
        
        Args:
            target_node_id: Target node ID
            num_hops: Number of intermediate hops
            
        Returns:
            List of node IDs for routing path
        """
        # In production, would select random nodes from network
        # For now, return empty path (direct routing)
        # This would be enhanced with peer registry lookup
        return []
    
    def add_routing_path(self, target: str, path: List[str]) -> None:
        """
        Add a routing path to routing table
        
        Args:
            target: Target node ID
            path: List of intermediate node IDs
        """
        self.routing_table[target] = path
        logger.debug(f"Added routing path for {target[:16]}...: {len(path)} hops")


class PrivacyLayer:
    """
    Unified privacy layer
    
    Combines onion routing, message padding, and timing obfuscation.
    """
    
    def __init__(
        self,
        identity: NodeIdentity,
        enable_onion: bool = True,
        enable_padding: bool = True,
        enable_timing_obfuscation: bool = True,
    ):
        """
        Initialize privacy layer
        
        Args:
            identity: Node identity
            enable_onion: Enable onion routing
            enable_padding: Enable message padding
            enable_timing_obfuscation: Enable timing obfuscation
        """
        self.identity = identity
        self.enable_onion = enable_onion
        self.enable_padding = enable_padding
        self.enable_timing_obfuscation = enable_timing_obfuscation
        
        self.padder = MessagePadder() if enable_padding else None
        self.onion_router = OnionRouter(identity, self.padder) if enable_onion else None
        self.timing_obfuscator = TimingObfuscator() if enable_timing_obfuscation else None
    
    async def send_private_message(
        self,
        message: bytes,
        target_node_id: str,
        send_callback,
    ) -> None:
        """
        Send message with privacy protections
        
        Args:
            message: Message to send
            target_node_id: Target node ID
            send_callback: Callback to send message (message_bytes, target_node_id)
        """
        processed_message = message
        
        # Apply padding
        if self.enable_padding and self.padder:
            processed_message = self.padder.pad_message(processed_message)
        
        # Apply onion routing
        if self.enable_onion and self.onion_router:
            path = self.onion_router.select_path(target_node_id)
            processed_message = self.onion_router.build_onion(
                processed_message,
                path,
                target_node_id,
            )
        
        # Apply timing obfuscation
        if self.enable_timing_obfuscation and self.timing_obfuscator:
            await self.timing_obfuscator.batch_send(
                processed_message,
                target_node_id,
                send_callback,
            )
        else:
            # Send directly
            await send_callback(processed_message, target_node_id)
    
    async def receive_private_message(
        self,
        encrypted_message: bytes,
        sender_node_id: str,
    ) -> Optional[bytes]:
        """
        Receive and process private message
        
        Args:
            encrypted_message: Encrypted/onion message
            sender_node_id: Node ID of sender
            
        Returns:
            Decrypted message or None if error
        """
        current_message = encrypted_message
        
        # Peel onion layers if enabled
        if self.enable_onion and self.onion_router:
            payload, next_hop = self.onion_router.peel_onion_layer(
                current_message,
                sender_node_id,
            )
            
            if payload is None:
                logger.error("Failed to peel onion layer")
                return None
            
            # If there's a next hop, forward the message
            if next_hop:
                # In production, would forward to next_hop
                logger.debug(f"Onion message to forward to {next_hop[:16]}...")
                # For now, return None (forwarding would be handled by routing layer)
                return None
            
            current_message = payload
        
        # Remove padding
        if self.enable_padding and self.padder:
            try:
                current_message = self.padder.unpad_message(current_message)
            except Exception as e:
                logger.error(f"Error unpadding message: {e}")
                # Return as-is if unpadding fails
                pass
        
        return current_message
    
    def get_privacy_config(self) -> Dict[str, Any]:
        """Get current privacy configuration"""
        return {
            "onion_routing": self.enable_onion,
            "message_padding": self.enable_padding,
            "timing_obfuscation": self.enable_timing_obfuscation,
        }



