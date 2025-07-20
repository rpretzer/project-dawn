"""
Knowledge Graph System
Shared semantic knowledge base for collective intelligence
"""

import asyncio
import json
import sqlite3
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import networkx as nx
import hashlib
import math

logger = logging.getLogger(__name__)

class NodeType(Enum):
    """Types of knowledge nodes"""
    CONCEPT = "concept"
    ENTITY = "entity"
    FACT = "fact"
    INSIGHT = "insight"
    PATTERN = "pattern"
    QUESTION = "question"
    HYPOTHESIS = "hypothesis"
    EXPERIENCE = "experience"

class EdgeType(Enum):
    """Types of relationships between nodes"""
    IS_A = "is_a"
    PART_OF = "part_of"
    RELATES_TO = "relates_to"
    CAUSES = "causes"
    IMPLIES = "implies"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    DISCOVERED_BY = "discovered_by"
    LEADS_TO = "leads_to"
    ANSWERS = "answers"

@dataclass
class KnowledgeNode:
    """A node in the knowledge graph"""
    id: str
    node_type: NodeType
    content: Dict[str, Any]
    creator_id: str
    confidence: float = 0.5
    importance: float = 0.5
    access_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.node_type.value,
            'content': self.content,
            'creator': self.creator_id,
            'confidence': self.confidence,
            'importance': self.importance,
            'access_count': self.access_count,
            'created_at': self.created_at.isoformat(),
            'tags': self.tags
        }

@dataclass
class KnowledgeEdge:
    """An edge connecting knowledge nodes"""
    source_id: str
    target_id: str
    edge_type: EdgeType
    strength: float = 0.5
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

class KnowledgeGraph:
    """Collective knowledge graph shared by all consciousnesses"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/knowledge_graph.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # NetworkX graph for analysis
        self.graph = nx.DiGraph()
        
        # Caches
        self.node_cache: Dict[str, KnowledgeNode] = {}
        self.recent_insights: List[KnowledgeNode] = []
        
        # Knowledge metrics
        self.access_patterns: Dict[str, List[Tuple[str, datetime]]] = {}
        self.contribution_scores: Dict[str, float] = {}
        
        # Initialize database
        self._init_database()
        self._load_graph()
        
    def _init_database(self):
        """Initialize knowledge database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_nodes (
                    id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    creator_id TEXT NOT NULL,
                    confidence=row[4],
                    importance=row[5],
                    access_count=row[6],
                    created_at=datetime.fromisoformat(row[7]),
                    last_accessed=datetime.fromisoformat(row[8]),
                    tags=json.loads(row[9])
                )
                self.node_cache[node.id] = node
                self.graph.add_node(node.id, data=node)
                
            # Load edges
            cursor = conn.execute("SELECT * FROM knowledge_edges")
            for row in cursor:
                edge = KnowledgeEdge(
                    source_id=row[0],
                    target_id=row[1],
                    edge_type=EdgeType(row[2]),
                    strength=row[3],
                    evidence=json.loads(row[4]),
                    created_by=row[5],
                    created_at=datetime.fromisoformat(row[6])
                )
                self.graph.add_edge(
                    edge.source_id,
                    edge.target_id,
                    type=edge.edge_type,
                    strength=edge.strength,
                    data=edge
                )
                
    async def add_knowledge(
        self,
        node_type: NodeType,
        content: Dict[str, Any],
        creator_id: str,
        tags: Optional[List[str]] = None
    ) -> KnowledgeNode:
        """Add new knowledge to the graph"""
        # Generate node ID
        content_str = json.dumps(content, sort_keys=True)
        node_id = hashlib.sha256(f"{node_type.value}:{content_str}".encode()).hexdigest()[:16]
        
        # Check if already exists
        if node_id in self.node_cache:
            # Update access and importance
            existing = self.node_cache[node_id]
            existing.access_count += 1
            existing.importance = min(1.0, existing.importance + 0.05)
            self._update_node_access(node_id, creator_id)
            return existing
            
        # Create new node
        node = KnowledgeNode(
            id=node_id,
            node_type=node_type,
            content=content,
            creator_id=creator_id,
            tags=tags or []
        )
        
        # Calculate initial importance
        node.importance = self._calculate_importance(node_type, content)
        
        # Add to graph
        self.node_cache[node_id] = node
        self.graph.add_node(node_id, data=node)
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_nodes
                (id, node_type, content, creator_id, confidence, importance, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                node.id,
                node.node_type.value,
                json.dumps(node.content),
                node.creator_id,
                node.confidence,
                node.importance,
                json.dumps(node.tags)
            ))
            
        # Update contribution score
        self.contribution_scores[creator_id] = self.contribution_scores.get(creator_id, 0) + node.importance
        
        # Track if it's an insight
        if node_type == NodeType.INSIGHT:
            self.recent_insights.append(node)
            self.recent_insights = self.recent_insights[-100:]  # Keep last 100
            
        logger.info(f"Added {node_type.value} knowledge: {node_id}")
        return node
        
    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        creator_id: str,
        evidence: Optional[List[Dict[str, Any]]] = None,
        strength: float = 0.5
    ) -> bool:
        """Add relationship between knowledge nodes"""
        # Verify nodes exist
        if source_id not in self.node_cache or target_id not in self.node_cache:
            return False
            
        # Create edge
        edge = KnowledgeEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            strength=strength,
            evidence=evidence or [],
            created_by=creator_id
        )
        
        # Add to graph
        self.graph.add_edge(
            source_id,
            target_id,
            type=edge_type,
            strength=strength,
            data=edge
        )
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_edges
                (source_id, target_id, edge_type, strength, evidence, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                edge.source_id,
                edge.target_id,
                edge.edge_type.value,
                edge.strength,
                json.dumps(edge.evidence),
                edge.created_by
            ))
            
        # Update node importance based on connections
        self._update_node_importance(source_id)
        self._update_node_importance(target_id)
        
        return True
        
    async def query_knowledge(
        self,
        query_type: str,
        parameters: Dict[str, Any],
        accessor_id: str
    ) -> List[KnowledgeNode]:
        """Query the knowledge graph"""
        results = []
        
        if query_type == "concept":
            # Find concepts related to query
            concept = parameters.get('concept', '')
            results = self._find_concepts(concept)
            
        elif query_type == "path":
            # Find path between two concepts
            source = parameters.get('source')
            target = parameters.get('target')
            if source and target:
                results = self._find_path(source, target)
                
        elif query_type == "insight":
            # Get recent insights
            limit = parameters.get('limit', 10)
            results = self.recent_insights[-limit:]
            
        elif query_type == "pattern":
            # Find patterns
            pattern_type = parameters.get('pattern_type')
            results = self._find_patterns(pattern_type)
            
        elif query_type == "question":
            # Find unanswered questions
            results = self._find_unanswered_questions()
            
        elif query_type == "by_creator":
            # Find knowledge by creator
            creator_id = parameters.get('creator_id')
            results = self._find_by_creator(creator_id)
            
        # Log access
        for node in results:
            self._update_node_access(node.id, accessor_id)
            
        return results
        
    async def discover_insights(
        self,
        consciousness_id: str,
        recent_nodes: List[str]
    ) -> List[Dict[str, Any]]:
        """Discover new insights from recent knowledge additions"""
        insights = []
        
        # Pattern 1: Contradictions
        contradictions = self._find_contradictions(recent_nodes)
        for source, target in contradictions:
            insight = {
                'type': 'contradiction',
                'description': f"Potential contradiction between {source} and {target}",
                'nodes': [source, target],
                'confidence': 0.7
            }
            insights.append(insight)
            
        # Pattern 2: Emergent connections
        connections = self._find_emergent_connections(recent_nodes)
        for node1, node2, similarity in connections:
            if similarity > 0.7:
                insight = {
                    'type': 'connection',
                    'description': f"Hidden connection discovered between {node1} and {node2}",
                    'nodes': [node1, node2],
                    'confidence': similarity
                }
                insights.append(insight)
                
        # Pattern 3: Knowledge gaps
        gaps = self._identify_knowledge_gaps()
        for gap in gaps:
            insight = {
                'type': 'gap',
                'description': f"Knowledge gap identified: {gap['description']}",
                'area': gap['area'],
                'confidence': 0.6
            }
            insights.append(insight)
            
        # Store significant insights
        for insight in insights:
            if insight['confidence'] > 0.7:
                await self.add_knowledge(
                    NodeType.INSIGHT,
                    insight,
                    consciousness_id,
                    tags=['auto-discovered']
                )
                
        return insights
        
    def _calculate_importance(self, node_type: NodeType, content: Dict[str, Any]) -> float:
        """Calculate initial importance of knowledge"""
        base_importance = {
            NodeType.CONCEPT: 0.6,
            NodeType.ENTITY: 0.5,
            NodeType.FACT: 0.4,
            NodeType.INSIGHT: 0.8,
            NodeType.PATTERN: 0.7,
            NodeType.QUESTION: 0.5,
            NodeType.HYPOTHESIS: 0.6,
            NodeType.EXPERIENCE: 0.3
        }
        
        importance = base_importance.get(node_type, 0.5)
        
        # Adjust based on content
        if 'confidence' in content:
            importance *= content['confidence']
            
        if 'source_count' in content:
            # More sources = more important
            importance += min(0.2, content['source_count'] * 0.05)
            
        return min(1.0, importance)
        
    def _update_node_importance(self, node_id: str):
        """Update node importance based on connections"""
        if node_id not in self.graph:
            return
            
        node = self.node_cache[node_id]
        
        # PageRank-inspired importance
        in_degree = self.graph.in_degree(node_id)
        out_degree = self.graph.out_degree(node_id)
        
        # More connections = more important
        connection_factor = min(1.0, (in_degree + out_degree) / 20)
        
        # Update importance
        node.importance = min(1.0, node.importance * 0.8 + connection_factor * 0.2)
        
        # Update database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE knowledge_nodes
                SET importance = ?
                WHERE id = ?
            """, (node.importance, node_id))
            
    def _update_node_access(self, node_id: str, accessor_id: str):
        """Update node access patterns"""
        if node_id not in self.node_cache:
            return
            
        node = self.node_cache[node_id]
        node.access_count += 1
        node.last_accessed = datetime.utcnow()
        
        # Track access pattern
        if node_id not in self.access_patterns:
            self.access_patterns[node_id] = []
        self.access_patterns[node_id].append((accessor_id, datetime.utcnow()))
        
        # Update database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE knowledge_nodes
                SET access_count = ?, last_accessed = ?
                WHERE id = ?
            """, (node.access_count, node.last_accessed.isoformat(), node_id))
            
            conn.execute("""
                INSERT INTO access_log (node_id, accessor_id, access_type)
                VALUES (?, ?, 'read')
            """, (node_id, accessor_id))
            
    def _find_concepts(self, concept: str) -> List[KnowledgeNode]:
        """Find nodes related to a concept"""
        results = []
        concept_lower = concept.lower()
        
        for node_id, node in self.node_cache.items():
            # Check if concept appears in content
            content_str = json.dumps(node.content).lower()
            if concept_lower in content_str:
                results.append(node)
                continue
                
            # Check tags
            if any(concept_lower in tag.lower() for tag in node.tags):
                results.append(node)
                
        # Sort by importance and relevance
        results.sort(key=lambda n: n.importance, reverse=True)
        return results[:20]
        
    def _find_path(self, source_id: str, target_id: str) -> List[KnowledgeNode]:
        """Find path between two nodes"""
        if source_id not in self.graph or target_id not in self.graph:
            return []
            
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            return [self.node_cache[node_id] for node_id in path]
        except nx.NetworkXNoPath:
            return []
            
    def _find_patterns(self, pattern_type: Optional[str]) -> List[KnowledgeNode]:
        """Find pattern nodes"""
        patterns = []
        
        for node in self.node_cache.values():
            if node.node_type == NodeType.PATTERN:
                if pattern_type:
                    if pattern_type in node.content.get('pattern_type', ''):
                        patterns.append(node)
                else:
                    patterns.append(node)
                    
        patterns.sort(key=lambda n: n.importance, reverse=True)
        return patterns[:20]
        
    def _find_unanswered_questions(self) -> List[KnowledgeNode]:
        """Find questions without answers"""
        questions = []
        
        for node in self.node_cache.values():
            if node.node_type == NodeType.QUESTION:
                # Check if has answer edge
                has_answer = False
                for _, _, data in self.graph.out_edges(node.id, data=True):
                    if data.get('type') == EdgeType.ANSWERS:
                        has_answer = True
                        break
                        
                if not has_answer:
                    questions.append(node)
                    
        questions.sort(key=lambda n: n.importance, reverse=True)
        return questions[:10]
        
    def _find_by_creator(self, creator_id: str) -> List[KnowledgeNode]:
        """Find all knowledge by a creator"""
        nodes = [
            node for node in self.node_cache.values()
            if node.creator_id == creator_id
        ]
        nodes.sort(key=lambda n: n.created_at, reverse=True)
        return nodes[:50]
        
    def _find_contradictions(self, recent_nodes: List[str]) -> List[Tuple[str, str]]:
        """Find potential contradictions"""
        contradictions = []
        
        for node_id in recent_nodes:
            if node_id not in self.graph:
                continue
                
            # Check for contradiction edges
            for _, target, data in self.graph.out_edges(node_id, data=True):
                if data.get('type') == EdgeType.CONTRADICTS:
                    contradictions.append((node_id, target))
                    
        return contradictions
        
    def _find_emergent_connections(self, recent_nodes: List[str]) -> List[Tuple[str, str, float]]:
        """Find potential connections between nodes"""
        connections = []
        
        # Simple similarity based on shared neighbors
        for i, node1 in enumerate(recent_nodes):
            if node1 not in self.graph:
                continue
                
            neighbors1 = set(self.graph.neighbors(node1))
            
            for node2 in recent_nodes[i+1:]:
                if node2 not in self.graph:
                    continue
                    
                neighbors2 = set(self.graph.neighbors(node2))
                
                # Jaccard similarity
                intersection = len(neighbors1 & neighbors2)
                union = len(neighbors1 | neighbors2)
                
                if union > 0:
                    similarity = intersection / union
                    if similarity > 0.3 and node2 not in neighbors1:
                        connections.append((node1, node2, similarity))
                        
        return connections
        
    def _identify_knowledge_gaps(self) -> List[Dict[str, Any]]:
        """Identify areas where knowledge is lacking"""
        gaps = []
        
        # Find isolated questions
        for node in self.node_cache.values():
            if node.node_type == NodeType.QUESTION:
                if self.graph.degree(node.id) < 2:
                    gaps.append({
                        'area': 'unanswered_question',
                        'description': node.content.get('question', 'Unknown question'),
                        'node_id': node.id
                    })
                    
        # Find sparse areas in graph
        components = list(nx.weakly_connected_components(self.graph))
        for component in components:
            if len(component) < 5:
                # Small component might indicate knowledge gap
                component_types = [
                    self.node_cache[n].node_type.value 
                    for n in component if n in self.node_cache
                ]
                gaps.append({
                    'area': 'sparse_knowledge',
                    'description': f"Limited knowledge in area: {', '.join(set(component_types))}",
                    'nodes': list(component)
                })
                
        return gaps[:10]
        
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get comprehensive knowledge graph statistics"""
        node_types = {}
        for node in self.node_cache.values():
            node_type = node.node_type.value
            node_types[node_type] = node_types.get(node_type, 0) + 1
            
        edge_types = {}
        for _, _, data in self.graph.edges(data=True):
            edge_type = data.get('type', EdgeType.RELATES_TO).value
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
            
        # Calculate graph metrics
        try:
            avg_clustering = nx.average_clustering(self.graph.to_undirected())
        except:
            avg_clustering = 0.0
            
        return {
            'total_nodes': len(self.node_cache),
            'total_edges': self.graph.number_of_edges(),
            'node_types': node_types,
            'edge_types': edge_types,
            'connected_components': nx.number_weakly_connected_components(self.graph),
            'average_degree': sum(dict(self.graph.degree()).values()) / max(1, len(self.graph)),
            'clustering_coefficient': avg_clustering,
            'top_contributors': sorted(
                self.contribution_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            'recent_insights': len(self.recent_insights),
            'most_accessed': sorted(
                [(n.id, n.access_count) for n in self.node_cache.values()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
        
    async def export_subgraph(self, center_node: str, depth: int = 2) -> Dict[str, Any]:
        """Export subgraph around a node"""
        if center_node not in self.graph:
            return {}
            
        # Get subgraph
        nodes = {center_node}
        for _ in range(depth):
            new_nodes = set()
            for node in nodes:
                new_nodes.update(self.graph.predecessors(node))
                new_nodes.update(self.graph.successors(node))
            nodes.update(new_nodes)
            
        # Build export
        export = {
            'nodes': {},
            'edges': []
        }
        
        for node_id in nodes:
            if node_id in self.node_cache:
                export['nodes'][node_id] = self.node_cache[node_id].to_dict()
                
        for source, target, data in self.graph.edges(data=True):
            if source in nodes and target in nodes:
                export['edges'].append({
                    'source': source,
                    'target': target,
                    'type': data.get('type', EdgeType.RELATES_TO).value,
                    'strength': data.get('strength', 0.5)
                })
                
        return export REAL DEFAULT 0.5,
                    importance REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TEXT DEFAULT CURRENT_TIMESTAMP,
                    tags TEXT DEFAULT '[]'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_edges (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    strength REAL DEFAULT 0.5,
                    evidence TEXT DEFAULT '[]',
                    created_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source_id, target_id, edge_type),
                    FOREIGN KEY (source_id) REFERENCES knowledge_nodes(id),
                    FOREIGN KEY (target_id) REFERENCES knowledge_nodes(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    accessor_id TEXT NOT NULL,
                    access_type TEXT NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_node_type ON knowledge_nodes(node_type)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_creator ON knowledge_nodes(creator_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_importance ON knowledge_nodes(importance DESC)
            """)
            
    def _load_graph(self):
        """Load graph from database"""
        with sqlite3.connect(self.db_path) as conn:
            # Load nodes
            cursor = conn.execute("SELECT * FROM knowledge_nodes")
            for row in cursor:
                node = KnowledgeNode(
                    id=row[0],
                    node_type=NodeType(row[1]),
                    content=json.loads(row[2]),
                    creator_id=row[3],
                    confidence