"""
Query Result Ranking and Scoring
Provides relevance scoring and ranking for memory query results
"""

import time
import logging
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from .core import MemCube, MemoryQuery

logger = logging.getLogger(__name__)


@dataclass
class RankedMemory:
    """Memory with relevance score and explanation"""
    memory: MemCube
    score: float
    relevance_score: float
    priority_score: float
    recency_score: float
    access_score: float
    explanation: str  # Why this memory matched
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "relevance_score": self.relevance_score,
            "priority_score": self.priority_score,
            "recency_score": self.recency_score,
            "access_score": self.access_score,
            "explanation": self.explanation
        }


class MemoryRanker:
    """
    Ranks and scores memory query results with explainability
    
    Provides:
    - Multi-factor scoring (relevance, priority, recency, access patterns)
    - Explanation of why each memory matched
    - Confidence metrics
    """
    
    def __init__(
        self,
        relevance_weight: float = 0.4,
        priority_weight: float = 0.3,
        recency_weight: float = 0.2,
        access_weight: float = 0.1
    ):
        """
        Initialize ranker with scoring weights
        
        Args:
            relevance_weight: Weight for semantic/textual relevance (default: 0.4)
            priority_weight: Weight for priority level (default: 0.3)
            recency_weight: Weight for recency (default: 0.2)
            access_weight: Weight for access frequency (default: 0.1)
        """
        self.relevance_weight = relevance_weight
        self.priority_weight = priority_weight
        self.recency_weight = recency_weight
        self.access_weight = access_weight
        
        # Ensure weights sum to 1.0
        total = relevance_weight + priority_weight + recency_weight + access_weight
        if total != 1.0:
            logger.warning(f"Ranking weights sum to {total}, normalizing to 1.0")
            self.relevance_weight /= total
            self.priority_weight /= total
            self.recency_weight /= total
            self.access_weight /= total
    
    async def rank_memories(
        self,
        memories: List[MemCube],
        query: MemoryQuery
    ) -> List[RankedMemory]:
        """
        Rank memories by relevance to query
        
        Args:
            memories: List of memories to rank
            query: Memory query with search parameters
            
        Returns:
            List of RankedMemory objects sorted by score (highest first)
        """
        ranked = []
        current_time = time.time()
        
        # Extract query text for relevance matching
        query_text = query.parameters.get("text") or query.parameters.get("raw_query", "")
        query_lower = query_text.lower() if query_text else ""
        query_words = set(query_lower.split()) if query_lower else set()
        
        for memory in memories:
            # Calculate individual scores
            relevance = self._calculate_relevance(memory, query, query_words)
            priority = self._calculate_priority_score(memory)
            recency = self._calculate_recency_score(memory, current_time)
            access = self._calculate_access_score(memory)
            
            # Weighted combined score
            combined_score = (
                relevance * self.relevance_weight +
                priority * self.priority_weight +
                recency * self.recency_weight +
                access * self.access_weight
            )
            
            # Generate explanation
            explanation = self._generate_explanation(
                memory, relevance, priority, recency, access, query
            )
            
            ranked.append(RankedMemory(
                memory=memory,
                score=combined_score,
                relevance_score=relevance,
                priority_score=priority,
                recency_score=recency,
                access_score=access,
                explanation=explanation
            ))
        
        # Sort by score (highest first)
        ranked.sort(key=lambda x: x.score, reverse=True)
        
        return ranked
    
    def _calculate_relevance(
        self,
        memory: MemCube,
        query: MemoryQuery,
        query_words: set
    ) -> float:
        """Calculate relevance score (0-1)"""
        score = 0.0
        max_score = 0.0
        
        # Content matching
        content_str = str(memory.content).lower() if memory.content else ""
        
        if query_words:
            matches = sum(1 for word in query_words if word in content_str)
            score += (matches / len(query_words)) * 0.6
            max_score += 0.6
        
        # Semantic type matching
        semantic_type = memory.semantic_type.lower()
        if query_words:
            type_matches = sum(1 for word in query_words if word in semantic_type)
            if type_matches > 0:
                score += 0.3
                max_score += 0.3
        
        # Namespace matching (boost if namespace matches query context)
        query_namespace = query.namespace
        if memory.namespace[0] == query_namespace[0] or query_namespace[0] == "*":
            score += 0.1
            max_score += 0.1
        
        # Normalize to 0-1
        return min(1.0, score / max_score) if max_score > 0 else 0.5
    
    def _calculate_priority_score(self, memory: MemCube) -> float:
        """Calculate priority score (0-1)"""
        # Normalize priority level (1-10) to 0-1
        return memory.priority_level / 10.0
    
    def _calculate_recency_score(self, memory: MemCube, current_time: float) -> float:
        """Calculate recency score (0-1)"""
        age = current_time - memory.timestamp
        
        # Decay function: more recent = higher score
        # Decays over 1 year
        decay_period = 365 * 24 * 3600  # 1 year in seconds
        score = max(0.0, 1.0 - (age / decay_period))
        
        return score
    
    def _calculate_access_score(self, memory: MemCube) -> float:
        """Calculate access frequency score (0-1)"""
        # Normalize access count (0-100+ accesses)
        access_score = min(1.0, memory.access_count / 100.0)
        
        # Boost if recently accessed
        if memory.last_access:
            age = time.time() - memory.last_access
            if age < 3600:  # Accessed in last hour
                access_score = min(1.0, access_score + 0.2)
        
        return access_score
    
    def _generate_explanation(
        self,
        memory: MemCube,
        relevance: float,
        priority: float,
        recency: float,
        access: float,
        query: MemoryQuery
    ) -> str:
        """Generate human-readable explanation of why memory matched"""
        reasons = []
        
        if relevance > 0.7:
            reasons.append(f"highly relevant to query ({relevance:.2%} relevance)")
        elif relevance > 0.4:
            reasons.append(f"moderately relevant ({relevance:.2%} relevance)")
        
        if priority > 0.7:
            reasons.append(f"high priority (level {memory.priority_level})")
        
        age_days = (time.time() - memory.timestamp) / (24 * 3600)
        if age_days < 1:
            reasons.append("created today")
        elif age_days < 7:
            reasons.append(f"created {int(age_days)} days ago")
        
        if memory.access_count > 10:
            reasons.append(f"frequently accessed ({memory.access_count} times)")
        
        if memory.last_access and (time.time() - memory.last_access) < 3600:
            reasons.append("recently accessed")
        
        if not reasons:
            return f"Matches query with relevance score {relevance:.2%}"
        
        return "; ".join(reasons) if len(reasons) <= 3 else "; ".join(reasons[:3]) + "..."
    
    def get_confidence_score(self, ranked_memories: List[RankedMemory]) -> float:
        """
        Calculate overall confidence score for query results
        
        Returns:
            Confidence score 0-1 (higher = more confident in results)
        """
        if not ranked_memories:
            return 0.0
        
        # Average score of top results
        top_scores = [r.score for r in ranked_memories[:5]]
        avg_score = sum(top_scores) / len(top_scores)
        
        # Score spread (closer scores = less confident)
        if len(top_scores) > 1:
            score_range = max(top_scores) - min(top_scores)
            spread_penalty = min(0.2, score_range * 0.5)
            avg_score -= spread_penalty
        
        return max(0.0, min(1.0, avg_score))

