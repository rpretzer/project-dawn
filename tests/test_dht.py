"""
Tests for DHT (Distributed Hash Table) implementation
"""

import pytest
from crypto import NodeIdentity
from p2p.dht import DHT, DHTNode, KBucket


class TestKBucket:
    """Tests for KBucket"""
    
    def test_add_node(self):
        """Test adding nodes to bucket"""
        bucket = KBucket(k=3)
        
        node1 = DHTNode("node1", "ws://node1:8000")
        node2 = DHTNode("node2", "ws://node2:8000")
        node3 = DHTNode("node3", "ws://node3:8000")
        
        assert bucket.add_node(node1) == True
        assert bucket.add_node(node2) == True
        assert bucket.add_node(node3) == True
        assert len(bucket.nodes) == 3
        
        # Adding 4th node should remove oldest
        node4 = DHTNode("node4", "ws://node4:8000")
        result = bucket.add_node(node4)
        assert len(bucket.nodes) == 3
        assert node4 in bucket.nodes
    
    def test_remove_node(self):
        """Test removing nodes from bucket"""
        bucket = KBucket()
        node1 = DHTNode("node1", "ws://node1:8000")
        node2 = DHTNode("node2", "ws://node2:8000")
        
        bucket.add_node(node1)
        bucket.add_node(node2)
        
        assert bucket.remove_node("node1") == True
        assert len(bucket.nodes) == 1
        assert bucket.nodes[0].node_id == "node2"
        
        assert bucket.remove_node("nonexistent") == False
    
    def test_update_last_seen(self):
        """Test updating last seen time"""
        import time
        bucket = KBucket()
        node1 = DHTNode("node1", "ws://node1:8000")
        node1.last_seen = 100.0
        
        bucket.add_node(node1)
        
        time.sleep(0.1)
        bucket.update_last_seen("node1")
        
        assert bucket.nodes[0].node_id == "node1"
        assert bucket.nodes[0].last_seen > 100.0


class TestDHT:
    """Tests for DHT"""
    
    def test_init(self):
        """Test DHT initialization"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        assert dht.node_id == identity.get_node_id()
        assert dht.k == 20
        assert dht.alpha == 3
    
    def test_xor_distance(self):
        """Test XOR distance calculation"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        # Same node should have distance 0
        distance = dht._xor_distance(dht.node_id, dht.node_id)
        assert distance == 0
        
        # Different nodes should have non-zero distance
        other_id = NodeIdentity().get_node_id()
        distance = dht._xor_distance(dht.node_id, other_id)
        assert distance > 0
    
    def test_add_node(self):
        """Test adding nodes to DHT"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        other_id = NodeIdentity().get_node_id()
        dht.add_node(other_id, "ws://other:8000")
        
        # Check that node was added to a bucket
        total_nodes = sum(len(bucket.nodes) for bucket in dht.buckets.values())
        assert total_nodes == 1
    
    def test_remove_node(self):
        """Test removing nodes from DHT"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        other_id = NodeIdentity().get_node_id()
        dht.add_node(other_id, "ws://other:8000")
        
        dht.remove_node(other_id)
        
        total_nodes = sum(len(bucket.nodes) for bucket in dht.buckets.values())
        assert total_nodes == 0
    
    def test_get_closest_nodes(self):
        """Test getting closest nodes"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        # Add some nodes
        for i in range(5):
            other_id = NodeIdentity().get_node_id()
            dht.add_node(other_id, f"ws://node{i}:8000")
        
        # Get closest nodes
        target_id = NodeIdentity().get_node_id()
        closest = dht.get_closest_nodes(target_id, count=3)
        
        assert len(closest) <= 3
        assert all(node.distance is not None for node in closest)
    
    def test_handle_find_node(self):
        """Test handling find_node request"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        # Add some nodes
        for i in range(5):
            other_id = NodeIdentity().get_node_id()
            dht.add_node(other_id, f"ws://node{i}:8000")
        
        target_id = NodeIdentity().get_node_id()
        result = dht.handle_find_node(target_id)
        
        assert "nodes" in result
        assert isinstance(result["nodes"], list)
        assert len(result["nodes"]) <= 20  # K value
    
    def test_handle_store_and_find_value(self):
        """Test storing and finding values"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        # Store a value
        result = dht.handle_store("test_key", "test_value", 3600.0)
        assert result["success"] == True
        
        # Find the value
        result = dht.handle_find_value("test_key")
        assert "value" in result
        assert result["value"] == "test_value"
        
        # Non-existent key should return nodes
        result = dht.handle_find_value("nonexistent")
        assert "nodes" in result
    
    @pytest.mark.asyncio
    async def test_find_node_async(self):
        """Test async find_node"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        # Create valid hex node IDs
        node1_id = NodeIdentity().get_node_id()
        node2_id = NodeIdentity().get_node_id()
        
        # Mock RPC handler
        async def mock_rpc(node_id, request):
            return {
                "result": {
                    "nodes": [
                        {"node_id": node1_id, "address": "ws://node1:8000"},
                        {"node_id": node2_id, "address": "ws://node2:8000"},
                    ]
                }
            }
        
        dht.rpc_handler = mock_rpc
        
        # Add initial nodes
        dht.add_node(node1_id, "ws://node1:8000")
        dht.add_node(node2_id, "ws://node2:8000")
        
        # Find nodes
        target_id = NodeIdentity().get_node_id()
        nodes = await dht.find_node(target_id)
        
        assert isinstance(nodes, list)
    
    @pytest.mark.asyncio
    async def test_store_and_find_value_async(self):
        """Test async store and find_value"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        # Mock RPC handler
        stored_values = {}
        
        async def mock_rpc(node_id, request):
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "dht_store":
                stored_values[params["key"]] = params["value"]
                return {"result": {"success": True}}
            elif method == "dht_find_value":
                key = params["key"]
                if key in stored_values:
                    return {"result": {"value": stored_values[key]}}
                else:
                    return {"result": {"nodes": []}}
            else:
                return {"result": {"nodes": []}}
        
        dht.rpc_handler = mock_rpc
        
        # Add some nodes
        for i in range(3):
            other_id = NodeIdentity().get_node_id()
            dht.add_node(other_id, f"ws://node{i}:8000")
        
        # Store value
        success = await dht.store("test_key", "test_value", 3600.0)
        assert success == True
        
        # Find value
        value = await dht.find_value("test_key")
        assert value == "test_value"
    
    def test_get_bucket_info(self):
        """Test getting bucket information"""
        identity = NodeIdentity()
        dht = DHT(identity)
        
        # Add some nodes
        for i in range(5):
            other_id = NodeIdentity().get_node_id()
            dht.add_node(other_id, f"ws://node{i}:8000")
        
        info = dht.get_bucket_info()
        
        assert "node_id" in info
        assert "buckets" in info
        assert "total_nodes" in info
        assert "stored_values" in info
        assert info["total_nodes"] == 5


class TestDHTIntegration:
    """Integration tests for DHT"""
    
    @pytest.mark.asyncio
    async def test_multiple_dht_nodes(self):
        """Test multiple DHT nodes interacting"""
        # Create two DHT nodes
        identity1 = NodeIdentity()
        dht1 = DHT(identity1)
        
        identity2 = NodeIdentity()
        dht2 = DHT(identity2)
        
        # Set up RPC handlers
        async def rpc1(node_id, request):
            return dht2.handle_find_node(request["params"]["target_id"])
        
        async def rpc2(node_id, request):
            return dht1.handle_find_node(request["params"]["target_id"])
        
        dht1.rpc_handler = rpc1
        dht2.rpc_handler = rpc2
        
        # Add nodes to each other
        dht1.add_node(identity2.get_node_id(), "ws://node2:8000")
        dht2.add_node(identity1.get_node_id(), "ws://node1:8000")
        
        # Find nodes
        target_id = NodeIdentity().get_node_id()
        nodes1 = await dht1.find_node(target_id)
        nodes2 = await dht2.find_node(target_id)
        
        assert isinstance(nodes1, list)
        assert isinstance(nodes2, list)

