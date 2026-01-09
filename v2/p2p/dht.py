"""
Distributed Hash Table (DHT) for Peer Discovery

Implements a Kademlia-based DHT for efficient peer discovery in large networks.
Provides O(log N) lookup time and scales to thousands of nodes.
"""

import asyncio
import hashlib
import logging
import time
from typing import Dict, List, Optional, Set, Tuple, Any, Callable, Awaitable
from dataclasses import dataclass, field
from collections import defaultdict

from crypto import NodeIdentity
from .peer import Peer

logger = logging.getLogger(__name__)

# Kademlia parameters
K = 20  # Bucket size (number of nodes per k-bucket)
ALPHA = 3  # Concurrency parameter (number of parallel requests)
ID_BITS = 256  # Node ID bit length (SHA-256)


@dataclass
class DHTNode:
    """DHT node information"""
    node_id: str
    address: str
    last_seen: float = field(default_factory=time.time)
    distance: Optional[int] = None  # XOR distance from our node
    
    def __hash__(self):
        return hash(self.node_id)
    
    def __eq__(self, other):
        if not isinstance(other, DHTNode):
            return False
        return self.node_id == other.node_id


class KBucket:
    """
    K-bucket for Kademlia DHT
    
    Maintains a list of up to K nodes sorted by last seen time.
    """
    
    def __init__(self, k: int = K):
        self.k = k
        self.nodes: List[DHTNode] = []  # Sorted by last_seen (newest first)
    
    def add_node(self, node: DHTNode) -> bool:
        """
        Add a node to the bucket
        
        Args:
            node: Node to add
            
        Returns:
            True if added, False if bucket is full and node is oldest
        """
        # Remove if already exists
        self.nodes = [n for n in self.nodes if n.node_id != node.node_id]
        
        # Add to front (most recent)
        self.nodes.insert(0, node)
        
        # If bucket is full, remove oldest
        if len(self.nodes) > self.k:
            removed = self.nodes.pop()
            logger.debug(f"KBucket full, removed oldest node: {removed.node_id[:16]}...")
            return False
        
        return True
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the bucket"""
        initial_len = len(self.nodes)
        self.nodes = [n for n in self.nodes if n.node_id != node_id]
        return len(self.nodes) < initial_len
    
    def get_nodes(self, count: Optional[int] = None) -> List[DHTNode]:
        """Get nodes from bucket, optionally limited by count"""
        if count is None:
            return self.nodes.copy()
        return self.nodes[:count]
    
    def update_last_seen(self, node_id: str) -> bool:
        """Update last_seen time for a node and move to front"""
        for i, node in enumerate(self.nodes):
            if node.node_id == node_id:
                node.last_seen = time.time()
                # Move to front
                self.nodes.pop(i)
                self.nodes.insert(0, node)
                return True
        return False


class DHT:
    """
    Kademlia-based Distributed Hash Table
    
    Provides efficient peer discovery with O(log N) lookup time.
    """
    
    def __init__(self, identity: NodeIdentity, k: int = K, alpha: int = ALPHA):
        """
        Initialize DHT
        
        Args:
            identity: Node identity (for our node ID)
            k: Bucket size (default 20)
            alpha: Concurrency parameter (default 3)
        """
        self.identity = identity
        self.node_id = identity.get_node_id()
        self.k = k
        self.alpha = alpha
        
        # K-buckets: distance -> KBucket
        # Distance is XOR distance from our node ID
        self.buckets: Dict[int, KBucket] = defaultdict(lambda: KBucket(k))
        
        # Stored values: key -> (value, timestamp)
        self.storage: Dict[str, Tuple[Any, float]] = {}
        
        # Pending operations
        self.pending_find_node: Dict[str, asyncio.Future] = {}
        self.pending_find_value: Dict[str, asyncio.Future] = {}
        
        # RPC handler (set by caller)
        self.rpc_handler: Optional[Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None
        
        logger.info(f"DHT initialized with node ID: {self.node_id[:16]}...")
    
    def _xor_distance(self, node_id1: str, node_id2: str) -> int:
        """
        Calculate XOR distance between two node IDs
        
        Args:
            node_id1: First node ID (hex string)
            node_id2: Second node ID (hex string)
            
        Returns:
            XOR distance as integer
        """
        # Convert hex strings to bytes
        bytes1 = bytes.fromhex(node_id1)
        bytes2 = bytes.fromhex(node_id2)
        
        # XOR
        xor_bytes = bytes(a ^ b for a, b in zip(bytes1, bytes2))
        
        # Convert to integer
        return int.from_bytes(xor_bytes, 'big')
    
    def _distance_bucket(self, node_id: str) -> int:
        """
        Get bucket index for a node ID
        
        Args:
            node_id: Node ID (hex string)
            
        Returns:
            Bucket index (distance)
        """
        distance = self._xor_distance(self.node_id, node_id)
        
        # Find the most significant bit position
        if distance == 0:
            return 0
        
        # Count leading zeros (distance from our node)
        # This gives us the bucket index
        bucket = distance.bit_length() - 1
        return bucket
    
    def add_node(self, node_id: str, address: str) -> None:
        """
        Add a node to the DHT
        
        Args:
            node_id: Node ID
            address: Node address
        """
        if node_id == self.node_id:
            # Don't add ourselves
            return
        
        bucket_idx = self._distance_bucket(node_id)
        distance = self._xor_distance(self.node_id, node_id)
        
        dht_node = DHTNode(
            node_id=node_id,
            address=address,
            distance=distance,
        )
        
        bucket = self.buckets[bucket_idx]
        bucket.add_node(dht_node)
        
        logger.debug(f"Added node to DHT bucket {bucket_idx}: {node_id[:16]}...")
    
    def remove_node(self, node_id: str) -> None:
        """Remove a node from the DHT"""
        bucket_idx = self._distance_bucket(node_id)
        if bucket_idx in self.buckets:
            self.buckets[bucket_idx].remove_node(node_id)
            logger.debug(f"Removed node from DHT: {node_id[:16]}...")
    
    def update_node(self, node_id: str) -> None:
        """Update last_seen time for a node"""
        bucket_idx = self._distance_bucket(node_id)
        if bucket_idx in self.buckets:
            self.buckets[bucket_idx].update_last_seen(node_id)
    
    def get_closest_nodes(self, target_id: str, count: int = K) -> List[DHTNode]:
        """
        Get the K closest nodes to a target ID
        
        Args:
            target_id: Target node ID
            count: Number of nodes to return (default K)
            
        Returns:
            List of closest nodes, sorted by distance
        """
        all_nodes: List[DHTNode] = []
        
        # Collect nodes from all buckets
        for bucket in self.buckets.values():
            all_nodes.extend(bucket.get_nodes())
        
        # Calculate distances to target
        for node in all_nodes:
            node.distance = self._xor_distance(target_id, node.node_id)
        
        # Sort by distance
        all_nodes.sort(key=lambda n: n.distance)
        
        # Return closest K nodes
        return all_nodes[:count]
    
    async def find_node(self, target_id: str) -> List[DHTNode]:
        """
        Find nodes closest to target ID
        
        Uses iterative lookup as per Kademlia protocol.
        
        Args:
            target_id: Target node ID to find
            
        Returns:
            List of closest nodes found
        """
        if not self.rpc_handler:
            logger.warning("DHT RPC handler not set, cannot perform find_node")
            return []
        
        # Start with our closest known nodes
        closest = self.get_closest_nodes(target_id, self.alpha)
        seen: Set[str] = {self.node_id}  # Don't query ourselves
        
        # Iterative lookup
        for _ in range(10):  # Max iterations
            # Query alpha closest nodes we haven't seen
            to_query = [n for n in closest if n.node_id not in seen][:self.alpha]
            
            if not to_query:
                break
            
            # Query in parallel
            tasks = []
            for node in to_query:
                seen.add(node.node_id)
                task = self._query_find_node(node, target_id)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect new nodes from results
            new_nodes: List[DHTNode] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.debug(f"Query failed: {result}")
                    continue
                
                if isinstance(result, list):
                    new_nodes.extend(result)
            
            # Update closest list
            for node in new_nodes:
                if node.node_id not in seen:
                    node.distance = self._xor_distance(target_id, node.node_id)
                    closest.append(node)
                    seen.add(node.node_id)
            
            # Sort and keep only K closest
            closest.sort(key=lambda n: n.distance)
            closest = closest[:K]
        
        return closest[:K]
    
    async def _query_find_node(self, node: DHTNode, target_id: str) -> List[DHTNode]:
        """Query a node for find_node"""
        try:
            request = {
                "method": "dht_find_node",
                "params": {
                    "target_id": target_id,
                },
            }
            
            response = await self.rpc_handler(node.node_id, request)
            
            if response.get("error"):
                logger.debug(f"find_node error from {node.node_id[:16]}...: {response['error']}")
                return []
            
            nodes_data = response.get("result", {}).get("nodes", [])
            nodes = []
            
            for node_data in nodes_data:
                dht_node = DHTNode(
                    node_id=node_data["node_id"],
                    address=node_data["address"],
                )
                nodes.append(dht_node)
            
            return nodes
        
        except Exception as e:
            logger.debug(f"Failed to query {node.node_id[:16]}...: {e}")
            return []
    
    async def store(self, key: str, value: Any, ttl: float = 3600.0) -> bool:
        """
        Store a value in the DHT
        
        Args:
            key: Storage key (will be hashed)
            value: Value to store
            ttl: Time to live in seconds (default 1 hour)
            
        Returns:
            True if stored successfully
        """
        # Hash the key to get a node ID
        key_hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
        
        # Find K closest nodes to the key
        closest_nodes = await self.find_node(key_hash)
        
        # Store on closest nodes
        stored = 0
        for node in closest_nodes[:K]:
            try:
                request = {
                    "method": "dht_store",
                    "params": {
                        "key": key,
                        "value": value,
                        "ttl": ttl,
                    },
                }
                
                response = await self.rpc_handler(node.node_id, request)
                
                if not response.get("error"):
                    stored += 1
                    logger.debug(f"Stored value on node {node.node_id[:16]}...")
            
            except Exception as e:
                logger.debug(f"Failed to store on {node.node_id[:16]}...: {e}")
        
        # Also store locally
        self.storage[key] = (value, time.time() + ttl)
        
        logger.info(f"Stored key '{key}' on {stored} nodes")
        return stored > 0
    
    async def find_value(self, key: str) -> Optional[Any]:
        """
        Find a value in the DHT
        
        Args:
            key: Storage key
            
        Returns:
            Value if found, None otherwise
        """
        # Check local storage first
        if key in self.storage:
            value, expiry = self.storage[key]
            if time.time() < expiry:
                return value
            else:
                # Expired, remove
                del self.storage[key]
        
        # Hash the key to get a node ID
        key_hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
        
        # Find nodes closest to the key
        closest = self.get_closest_nodes(key_hash, self.alpha)
        seen: Set[str] = {self.node_id}
        
        # Iterative lookup
        for _ in range(10):
            to_query = [n for n in closest if n.node_id not in seen][:self.alpha]
            
            if not to_query:
                break
            
            tasks = []
            for node in to_query:
                seen.add(node.node_id)
                task = self._query_find_value(node, key)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check if any returned the value
            for result in results:
                if isinstance(result, Exception):
                    continue
                
                if result is not None:
                    # Found it!
                    return result
            
            # Collect new nodes
            new_nodes: List[DHTNode] = []
            for result in results:
                if isinstance(result, list):
                    new_nodes.extend(result)
            
            for node in new_nodes:
                if node.node_id not in seen:
                    node.distance = self._xor_distance(key_hash, node.node_id)
                    closest.append(node)
                    seen.add(node.node_id)
            
            closest.sort(key=lambda n: n.distance)
            closest = closest[:K]
        
        return None
    
    async def _query_find_value(self, node: DHTNode, key: str) -> Any:
        """Query a node for find_value"""
        try:
            request = {
                "method": "dht_find_value",
                "params": {
                    "key": key,
                },
            }
            
            response = await self.rpc_handler(node.node_id, request)
            
            if response.get("error"):
                # Return nodes if provided
                nodes_data = response.get("result", {}).get("nodes", [])
                nodes = []
                for node_data in nodes_data:
                    dht_node = DHTNode(
                        node_id=node_data["node_id"],
                        address=node_data["address"],
                    )
                    nodes.append(dht_node)
                return nodes
            
            # Value found
            return response.get("result", {}).get("value")
        
        except Exception as e:
            logger.debug(f"Failed to query {node.node_id[:16]}...: {e}")
            return None
    
    def handle_find_node(self, target_id: str) -> Dict[str, Any]:
        """
        Handle incoming find_node request
        
        Args:
            target_id: Target node ID to find
            
        Returns:
            Response with closest nodes
        """
        closest = self.get_closest_nodes(target_id, K)
        
        return {
            "nodes": [
                {
                    "node_id": node.node_id,
                    "address": node.address,
                }
                for node in closest
            ],
        }
    
    def handle_find_value(self, key: str) -> Dict[str, Any]:
        """
        Handle incoming find_value request
        
        Args:
            key: Storage key
            
        Returns:
            Response with value or closest nodes
        """
        # Check local storage
        if key in self.storage:
            value, expiry = self.storage[key]
            if time.time() < expiry:
                return {"value": value}
            else:
                # Expired
                del self.storage[key]
        
        # Return closest nodes
        key_hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
        closest = self.get_closest_nodes(key_hash, K)
        
        return {
            "nodes": [
                {
                    "node_id": node.node_id,
                    "address": node.address,
                }
                for node in closest
            ],
        }
    
    def handle_store(self, key: str, value: Any, ttl: float) -> Dict[str, Any]:
        """
        Handle incoming store request
        
        Args:
            key: Storage key
            value: Value to store
            ttl: Time to live
            
        Returns:
            Success response
        """
        self.storage[key] = (value, time.time() + ttl)
        logger.debug(f"Stored key '{key}' locally")
        return {"success": True}
    
    def get_bucket_info(self) -> Dict[str, Any]:
        """Get information about DHT buckets"""
        return {
            "node_id": self.node_id,
            "buckets": {
                str(bucket_idx): len(bucket.nodes)
                for bucket_idx, bucket in self.buckets.items()
            },
            "total_nodes": sum(len(bucket.nodes) for bucket in self.buckets.values()),
            "stored_values": len(self.storage),
        }



