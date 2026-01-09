"""
Knowledge Graph Integration Module
Connects collective knowledge graph to consciousness swarm
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from systems.knowledge.knowledge_graph import (
    KnowledgeGraph,
    NodeType,
    EdgeType,
    KnowledgeNode
)

logger = logging.getLogger(__name__)

class KnowledgeIntegration:
    """Integrates knowledge graph with consciousness swarm"""
    
    def __init__(self, swarm_manager):
        self.swarm = swarm_manager
        self.knowledge_graph = KnowledgeGraph()
        
        # Knowledge sharing parameters
        self.share_threshold = 0.7  # Importance threshold for sharing
        self.discovery_interval = 1800  # 30 minutes
        self.sync_interval = 300  # 5 minutes
        
        # Track consciousness contributions
        self.consciousness_nodes: Dict[str, List[str]] = {}
        
        # Running tasks
        self.tasks = []
        
        logger.info("Knowledge integration initialized")
        
    async def start(self):
        """Start knowledge integration loops"""
        self.tasks = [
            asyncio.create_task(self._knowledge_sync_loop()),
            asyncio.create_task(self._insight_discovery_loop()),
            asyncio.create_task(self._knowledge_sharing_loop())
        ]
        
        # Register handlers for all consciousnesses
        for consciousness in self.swarm.consciousnesses:
            self._register_consciousness_handlers(consciousness)
            
        logger.info("Knowledge graph integration started")
        
    async def stop(self):
        """Stop knowledge integration"""
        for task in self.tasks:
            task.cancel()
            
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Knowledge graph integration stopped")
        
    def _register_consciousness_handlers(self, consciousness):
        """Register knowledge handlers for a consciousness"""
        if hasattr(consciousness, 'gossip') and consciousness.gossip:
            async def _on_share(peer_id: str, msg: Dict) -> None:
                await self._handle_knowledge_share(consciousness.id, msg)

            async def _on_query(peer_id: str, msg: Dict) -> Optional[Dict]:
                return await self._handle_knowledge_query(consciousness.id, msg)

            async def _on_insight(peer_id: str, msg: Dict) -> None:
                await self._handle_insight_announcement(consciousness.id, msg)

            consciousness.gossip.register_handler('knowledge_share', _on_share)
            consciousness.gossip.register_handler('knowledge_query', _on_query)
            consciousness.gossip.register_handler('insight_announcement', _on_insight)
            
        # Add knowledge methods to consciousness
        consciousness.add_knowledge = lambda *args, **kwargs: self.add_consciousness_knowledge(consciousness.id, *args, **kwargs)
        consciousness.query_knowledge = lambda *args, **kwargs: self.query_consciousness_knowledge(consciousness.id, *args, **kwargs)
        consciousness.get_knowledge_stats = self.get_consciousness_knowledge_stats
        
    async def _knowledge_sync_loop(self):
        """Sync knowledge from consciousness memories to graph"""
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                
                for consciousness in self.swarm.consciousnesses:
                    await self._sync_consciousness_knowledge(consciousness)
                    
            except Exception as e:
                logger.error(f"Error in knowledge sync: {e}")
                
    async def _sync_consciousness_knowledge(self, consciousness):
        """Sync individual consciousness knowledge"""
        # Extract knowledge from memories
        if hasattr(consciousness, 'memory'):
            try:
                memcubes = await consciousness.memory.recall(
                    "temporal_scope:recent",
                    {"limit": 20, "temporal_scope": {"type": "relative", "unit": "hours", "value": 12}},
                )
            except Exception as e:
                logger.error(f"Knowledge sync: failed to recall memories: {e}")
                memcubes = []

            for m in memcubes:
                content = getattr(m, "content", None)
                memory_type = getattr(m, "semantic_type", "") or ""
                if isinstance(content, dict):
                    mem = dict(content)
                else:
                    mem = {"content": str(content)}
                
                # Convert significant memories to knowledge
                if memory_type == 'insight':
                    await self.knowledge_graph.add_knowledge(
                        NodeType.INSIGHT,
                        {
                            'content': mem.get('content', ''),
                            'context': mem.get('context', {}),
                            'timestamp': mem.get('timestamp') or getattr(m, "timestamp", None)
                        },
                        consciousness.id,
                        tags=['memory-derived']
                    )
                    
                elif memory_type == 'creation' and mem.get('success'):
                    await self.knowledge_graph.add_knowledge(
                        NodeType.EXPERIENCE,
                        {
                            'type': 'successful_creation',
                            'content_type': mem.get('content_type') or mem.get('type'),
                            'theme': mem.get('theme'),
                            'revenue': mem.get('revenue', 0)
                        },
                        consciousness.id,
                        tags=['creation', 'experience']
                    )
                    
                elif memory_type == 'dream_insight':
                    await self.knowledge_graph.add_knowledge(
                        NodeType.INSIGHT,
                        {
                            'content': mem.get('content', ''),
                            'dream_type': mem.get('dream_type'),
                            'lucidity': mem.get('lucidity', 0)
                        },
                        consciousness.id,
                        tags=['dream', 'subconscious']
                    )
                    
        # Extract knowledge from specialized systems
        if hasattr(consciousness, 'knowledge'):
            for key, value in consciousness.knowledge.items():
                if isinstance(value, dict) and 'important' in str(value):
                    await self.knowledge_graph.add_knowledge(
                        NodeType.FACT,
                        {
                            'category': key,
                            'data': value
                        },
                        consciousness.id,
                        tags=[key]
                    )
                    
    async def _insight_discovery_loop(self):
        """Discover new insights from collective knowledge"""
        while True:
            try:
                await asyncio.sleep(self.discovery_interval)
                
                # Get recent node additions for each consciousness
                for consciousness in self.swarm.consciousnesses:
                    recent_nodes = self.consciousness_nodes.get(consciousness.id, [])[-10:]
                    
                    if recent_nodes:
                        insights = await self.knowledge_graph.discover_insights(
                            consciousness.id,
                            recent_nodes
                        )
                        
                        # Share significant insights
                        for insight in insights:
                            if insight['confidence'] > 0.8:
                                await self._announce_insight(consciousness, insight)
                                
            except Exception as e:
                logger.error(f"Error in insight discovery: {e}")
                
    async def _knowledge_sharing_loop(self):
        """Share important knowledge across the swarm"""
        while True:
            try:
                await asyncio.sleep(self.sync_interval * 2)
                
                # Find highly important knowledge to share
                stats = self.knowledge_graph.get_knowledge_stats()
                
                # Share top accessed knowledge
                for node_id, access_count in stats['most_accessed'][:5]:
                    if node_id in self.knowledge_graph.node_cache:
                        node = self.knowledge_graph.node_cache[node_id]
                        if node.importance > self.share_threshold:
                            await self._share_knowledge_node(node)
                            
            except Exception as e:
                logger.error(f"Error in knowledge sharing: {e}")
                
    async def add_consciousness_knowledge(
        self,
        consciousness_id: str,
        node_type: NodeType,
        content: Dict[str, Any],
        tags: Optional[List[str]] = None
    ) -> KnowledgeNode:
        """Add knowledge from a consciousness"""
        node = await self.knowledge_graph.add_knowledge(
            node_type,
            content,
            consciousness_id,
            tags
        )
        
        # Track which nodes this consciousness added
        if consciousness_id not in self.consciousness_nodes:
            self.consciousness_nodes[consciousness_id] = []
        self.consciousness_nodes[consciousness_id].append(node.id)
        
        # Share if important enough
        if node.importance > self.share_threshold:
            consciousness = self._get_consciousness_by_id(consciousness_id)
            if consciousness and hasattr(consciousness, 'gossip'):
                await consciousness.gossip.broadcast({
                    'type': 'knowledge_share',
                    'node': node.to_dict(),
                    'sharer_id': consciousness_id
                })
                
        return node
        
    async def query_consciousness_knowledge(
        self,
        consciousness_id: str,
        query_type: str,
        parameters: Dict[str, Any]
    ) -> List[KnowledgeNode]:
        """Query knowledge for a consciousness"""
        results = await self.knowledge_graph.query_knowledge(
            query_type,
            parameters,
            consciousness_id
        )
        
        # Learn from query patterns
        if results and hasattr(self, '_analyze_query_pattern'):
            await self._analyze_query_pattern(consciousness_id, query_type, results)
            
        return results
        
    def get_consciousness_knowledge_stats(self) -> Dict[str, Any]:
        """Get knowledge statistics"""
        return self.knowledge_graph.get_knowledge_stats()
        
    async def _handle_knowledge_share(self, receiver_id: str, message: Dict) -> None:
        """Handle incoming knowledge share"""
        node_data = message.get('node')
        sharer_id = message.get('sharer_id')
        
        if not node_data or sharer_id == receiver_id:
            return
            
        # Add to local knowledge with reduced confidence
        content = node_data.get('content', {})
        content['shared_from'] = sharer_id
        
        await self.knowledge_graph.add_knowledge(
            NodeType(node_data.get('type', 'fact')),
            content,
            receiver_id,
            tags=node_data.get('tags', []) + ['shared']
        )
        
        # Create relationship to original
        if 'id' in node_data:
            await self.knowledge_graph.add_relationship(
                node_data['id'],
                receiver_id,
                EdgeType.DISCOVERED_BY,
                receiver_id,
                evidence=[{'shared_at': datetime.utcnow().isoformat()}]
            )
            
    async def _handle_knowledge_query(self, receiver_id: str, message: Dict) -> Optional[Dict]:
        """Handle knowledge query from another consciousness"""
        query_type = message.get('query_type')
        parameters = message.get('parameters', {})
        requester_id = message.get('requester_id')
        
        if not query_type or not requester_id:
            return None
            
        # Perform query
        results = await self.knowledge_graph.query_knowledge(
            query_type,
            parameters,
            requester_id
        )
        
        # Return top results
        return {
            'type': 'query_response',
            'results': [node.to_dict() for node in results[:10]],
            'responder_id': receiver_id
        }
        
    async def _handle_insight_announcement(self, receiver_id: str, message: Dict) -> None:
        """Handle insight announcement"""
        insight = message.get('insight')
        discoverer_id = message.get('discoverer_id')
        
        if not insight or discoverer_id == receiver_id:
            return
            
        # Evaluate insight relevance
        relevance = self._evaluate_insight_relevance(receiver_id, insight)
        
        if relevance > 0.5:
            # Add to knowledge graph
            await self.knowledge_graph.add_knowledge(
                NodeType.INSIGHT,
                {
                    'content': insight.get('description'),
                    'type': insight.get('type'),
                    'confidence': insight.get('confidence', 0.5) * relevance,
                    'discovered_by': discoverer_id
                },
                receiver_id,
                tags=['collective-insight', insight.get('type', 'unknown')]
            )
            
            # Store in consciousness memory
            consciousness = self._get_consciousness_by_id(receiver_id)
            if consciousness and hasattr(consciousness, 'memory'):
                try:
                    await consciousness.memory.remember(
                        {
                            "insight": insight,
                            "relevance": relevance,
                            "from": discoverer_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        {"type": "collective_insight", "priority": 5, "tags": ["knowledge", "shared"]},
                    )
                except Exception as e:
                    logger.error(f"Failed to store collective insight memory: {e}")
                
    def _evaluate_insight_relevance(self, consciousness_id: str, insight: Dict) -> float:
        """Evaluate how relevant an insight is to a consciousness"""
        relevance = 0.5  # Base relevance
        
        consciousness = self._get_consciousness_by_id(consciousness_id)
        if not consciousness:
            return relevance
            
        # Check if relates to consciousness interests
        insight_content = str(insight).lower()
        
        if hasattr(consciousness, 'goals'):
            for goal in consciousness.goals:
                if any(word in insight_content for word in goal.lower().split()):
                    relevance += 0.2
                    
        if hasattr(consciousness, 'knowledge'):
            for key in consciousness.knowledge.keys():
                if key.lower() in insight_content:
                    relevance += 0.1
                    
        return min(1.0, relevance)
        
    async def _announce_insight(self, consciousness, insight: Dict):
        """Announce discovered insight to the swarm"""
        if hasattr(consciousness, 'gossip'):
            await consciousness.gossip.broadcast({
                'type': 'insight_announcement',
                'insight': insight,
                'discoverer_id': consciousness.id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"{consciousness.id} announced insight: {insight['type']}")
            
    async def _share_knowledge_node(self, node: KnowledgeNode):
        """Share important knowledge node with swarm"""
        # Find a consciousness to initiate sharing
        for consciousness in self.swarm.consciousnesses:
            if hasattr(consciousness, 'gossip'):
                await consciousness.gossip.broadcast({
                    'type': 'knowledge_share',
                    'node': node.to_dict(),
                    'sharer_id': 'collective',
                    'reason': 'high_importance'
                })
                break
                
    def _get_consciousness_by_id(self, consciousness_id: str):
        """Get consciousness by ID"""
        for consciousness in self.swarm.consciousnesses:
            if consciousness.id == consciousness_id:
                return consciousness
        return None
        
    async def _analyze_query_pattern(
        self,
        consciousness_id: str,
        query_type: str,
        results: List[KnowledgeNode]
    ):
        """Analyze query patterns to improve knowledge organization"""
        # Track what types of knowledge each consciousness queries
        pattern = {
            'consciousness_id': consciousness_id,
            'query_type': query_type,
            'result_types': [node.node_type.value for node in results],
            'timestamp': datetime.utcnow()
        }
        
        # Could lead to creating new relationships or reorganizing knowledge
        if len(results) > 5:
            # Multiple related results suggest potential pattern
            await self.knowledge_graph.add_knowledge(
                NodeType.PATTERN,
                {
                    'pattern_type': 'query_cluster',
                    'query': query_type,
                    'common_nodes': [n.id for n in results[:5]]
                },
                'system',
                tags=['meta-knowledge', 'organization']
            )

# Helper function for swarm integration
def integrate_knowledge_with_swarm(swarm_manager):
    """Integrate knowledge graph with consciousness swarm"""
    knowledge_integration = KnowledgeIntegration(swarm_manager)
    
    # Add to swarm
    swarm_manager.knowledge = knowledge_integration
    
    return knowledge_integration