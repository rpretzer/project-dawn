"""
LLM Context Manager - Automatic context window management
Manages LLM context with automatic pruning, memory injection, and token tracking
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from .core import MemCube, MemoryQuery
from .vault import MemVault
from .interface import MemoryAPI

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """Represents a context window with token tracking"""
    max_tokens: int
    reserved_tokens: int = 100  # Reserve tokens for response
    current_tokens: int = 0
    messages: List[Dict[str, str]] = field(default_factory=list)
    memories: List[MemCube] = field(default_factory=list)
    encoding_name: str = "cl100k_base"  # OpenAI encoding, works reasonably for others
    
    def get_available_tokens(self) -> int:
        """Get available tokens for new content"""
        return max(0, self.max_tokens - self.current_tokens - self.reserved_tokens)
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        if TIKTOKEN_AVAILABLE:
            try:
                encoding = tiktoken.get_encoding(self.encoding_name)
                return len(encoding.encode(text))
            except Exception as e:
                logger.warning(f"Error encoding text: {e}")
        
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4
    
    def add_text(self, text: str, role: str = "user") -> bool:
        """Add text to context if space available"""
        tokens = self.estimate_tokens(text)
        if tokens <= self.get_available_tokens():
            self.messages.append({"role": role, "content": text})
            self.current_tokens += tokens
            return True
        return False
    
    def add_memory(self, memory: MemCube, formatted: str) -> bool:
        """Add formatted memory to context"""
        tokens = self.estimate_tokens(formatted)
        if tokens <= self.get_available_tokens():
            self.messages.append({"role": "system", "content": formatted})
            self.memories.append(memory)
            self.current_tokens += tokens
            return True
        return False


class LLMContextManager:
    """
    Manages LLM context window with automatic pruning and memory injection
    
    Features:
    - Automatic context window pruning when approaching limits
    - Intelligent memory selection based on relevance, priority, recency
    - Provider-specific formatting (OpenAI, Anthropic, Ollama)
    - Token counting and tracking
    """
    
    def __init__(
        self,
        memory_api: MemoryAPI,
        max_tokens: int = 16000,
        provider: str = "openai",
        encoding_name: str = "cl100k_base"
    ):
        self.memory_api = memory_api
        self.max_tokens = max_tokens
        self.provider = provider.lower()
        self.encoding_name = encoding_name
        
        # Pruning thresholds
        self.prune_threshold = 0.8  # Start pruning at 80% capacity
        self.aggressive_prune_threshold = 0.95  # Aggressive pruning at 95%
        
        # Memory selection weights
        self.relevance_weight = 0.4
        self.priority_weight = 0.3
        self.recency_weight = 0.2
        self.access_weight = 0.1
    
    async def build_context(
        self,
        user_query: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        namespace: Optional[Tuple[str, str, str]] = None,
        max_memory_tokens: Optional[int] = None,
        memory_limit: int = 20
    ) -> Tuple[List[Dict[str, str]], List[MemCube]]:
        """
        Build complete context for LLM with automatic memory injection
        
        Args:
            user_query: The user's current query
            system_prompt: Optional system prompt
            conversation_history: Previous conversation messages
            namespace: Memory namespace to search
            max_memory_tokens: Max tokens to use for memories (default: 30% of context)
            memory_limit: Maximum number of memories to include
            
        Returns:
            Tuple of (formatted_messages, included_memories)
        """
        # Calculate memory token budget
        if max_memory_tokens is None:
            max_memory_tokens = int(self.max_tokens * 0.3)  # 30% for memories
        
        # Create context window
        window = ContextWindow(
            max_tokens=self.max_tokens,
            encoding_name=self.encoding_name
        )
        
        # Add system prompt first
        if system_prompt:
            window.add_text(system_prompt, role="system")
        
        # Retrieve relevant memories
        memories = await self._retrieve_relevant_memories(
            user_query, 
            namespace,
            limit=memory_limit
        )
        
        # Score and sort memories
        scored_memories = await self._score_memories(memories, user_query)
        scored_memories.sort(key=lambda x: x[1], reverse=True)  # Sort by score
        
        # Add memories to context (within token budget)
        included_memories = []
        memory_tokens_used = 0
        
        for memory, score in scored_memories:
            formatted = self._format_memory_for_provider(memory, self.provider)
            tokens = window.estimate_tokens(formatted)
            
            if memory_tokens_used + tokens <= max_memory_tokens:
                if window.add_memory(memory, formatted):
                    included_memories.append(memory)
                    memory_tokens_used += tokens
                else:
                    break  # No more space
            else:
                break  # Exceeded memory token budget
        
        # Add conversation history (with pruning if needed)
        if conversation_history:
            # Reverse to get most recent first, then add in order
            history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            
            # Prune if necessary
            if window.current_tokens / window.max_tokens > self.prune_threshold:
                history = await self._prune_conversation_history(
                    history, 
                    window.get_available_tokens() - window.estimate_tokens(user_query)
                )
            
            for msg in history:
                if not window.add_text(msg.get("content", ""), role=msg.get("role", "user")):
                    logger.warning("Conversation history truncated due to token limits")
                    break
        
        # Add current user query
        if not window.add_text(user_query, role="user"):
            logger.error("User query too large for context window!")
            # Try to prune more aggressively
            window.messages = window.messages[:1] if system_prompt else []
            window.current_tokens = window.estimate_tokens(system_prompt or "")
            window.add_text(user_query, role="user")
        
        return window.messages, included_memories
    
    async def _retrieve_relevant_memories(
        self,
        query: str,
        namespace: Optional[Tuple[str, str, str]],
        limit: int = 20
    ) -> List[MemCube]:
        """Retrieve relevant memories for query"""
        try:
            if namespace:
                memories = await self.memory_api.search(
                    query,
                    namespace=namespace,
                    limit=limit * 2  # Get more, then filter
                )
            else:
                # Search without namespace restriction
                from .core import MemoryQuery
                memory_query = MemoryQuery(
                    query_type="hybrid",
                    parameters={"text": query, "limit": limit * 2, "raw_query": query},
                    namespace=("*", "*", "*"),
                    requester_id="system"
                )
                memories = await self.memory_api.retrieve(memory_query)
            
            return memories[:limit * 2]  # Return top candidates
        except Exception as e:
            logger.error(f"Error retrieving memories: {e}")
            return []
    
    async def _score_memories(
        self,
        memories: List[MemCube],
        query: str
    ) -> List[Tuple[MemCube, float]]:
        """Score memories for relevance to query"""
        scores = []
        current_time = time.time()
        
        for memory in memories:
            score = 0.0
            
            # Priority score (0-10 normalized to 0-1)
            priority_score = memory.priority_level / 10.0
            score += priority_score * self.priority_weight
            
            # Recency score (more recent = higher score)
            age = current_time - memory.timestamp
            recency_score = max(0, 1.0 - (age / (365 * 24 * 3600)))  # Decay over 1 year
            score += recency_score * self.recency_weight
            
            # Access frequency score
            access_score = min(1.0, memory.access_count / 100.0)  # Normalize to 0-1
            score += access_score * self.access_weight
            
            # Relevance score (simple keyword matching - could be enhanced with embeddings)
            query_lower = query.lower()
            content_str = str(memory.content).lower() if memory.content else ""
            semantic_type = memory.semantic_type.lower()
            
            relevance_score = 0.0
            query_words = query_lower.split()
            for word in query_words:
                if word in content_str:
                    relevance_score += 0.1
                if word in semantic_type:
                    relevance_score += 0.2
            
            relevance_score = min(1.0, relevance_score)
            score += relevance_score * self.relevance_weight
            
            # Boost hot memories (recently accessed)
            if memory.last_access and (current_time - memory.last_access) < 3600:
                score += 0.1
            
            # Penalize expired memories
            if memory.is_expired():
                score *= 0.5
            
            scores.append((memory, score))
        
        return scores
    
    async def _prune_conversation_history(
        self,
        history: List[Dict[str, str]],
        available_tokens: int
    ) -> List[Dict[str, str]]:
        """Prune conversation history to fit token budget"""
        if not TIKTOKEN_AVAILABLE:
            # Simple character-based pruning
            result = []
            total_chars = 0
            max_chars = available_tokens * 4  # Rough estimate
            
            for msg in reversed(history):
                content = msg.get("content", "")
                if total_chars + len(content) <= max_chars:
                    result.insert(0, msg)
                    total_chars += len(content)
                else:
                    break
            
            return result
        
        # Token-based pruning
        encoding = tiktoken.get_encoding(self.encoding_name)
        result = []
        tokens_used = 0
        
        # Keep most recent messages, prune older ones
        for msg in reversed(history):
            content = msg.get("content", "")
            tokens = len(encoding.encode(content))
            
            if tokens_used + tokens <= available_tokens:
                result.insert(0, msg)
                tokens_used += tokens
            else:
                break
        
        return result
    
    def _format_memory_for_provider(self, memory: MemCube, provider: str) -> str:
        """Format memory for specific LLM provider"""
        content = str(memory.content) if memory.content else ""
        semantic_type = memory.semantic_type
        timestamp = time.ctime(memory.timestamp)
        
        if provider in ("openai", "ollama", "local", "llamacpp"):
            # OpenAI-style format
            return f"[Memory: {semantic_type} from {timestamp}]\n{content}\n"
        
        elif provider == "anthropic":
            # Anthropic-style format (more structured)
            return f"<memory type=\"{semantic_type}\" timestamp=\"{timestamp}\">\n{content}\n</memory>\n"
        
        else:
            # Generic format
            return f"Memory ({semantic_type}, {timestamp}): {content}\n"
    
    def estimate_context_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Estimate total tokens in context"""
        if not TIKTOKEN_AVAILABLE:
            total_chars = sum(len(msg.get("content", "")) for msg in messages)
            return total_chars // 4
        
        encoding = tiktoken.get_encoding(self.encoding_name)
        tokens = 0
        for msg in messages:
            content = msg.get("content", "")
            tokens += len(encoding.encode(content))
            # Add overhead for role/formatting (rough estimate)
            tokens += 4
        
        return tokens
    
    async def inject_memories_into_messages(
        self,
        messages: List[Dict[str, str]],
        query: str,
        namespace: Optional[Tuple[str, str, str]] = None,
        max_memory_tokens: Optional[int] = None
    ) -> Tuple[List[Dict[str, str]], List[MemCube]]:
        """
        Inject relevant memories into existing message list
        
        This is useful when you already have messages but want to add memories
        """
        # Find system prompt position
        system_idx = -1
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                system_idx = i
        
        # Retrieve and format memories
        if max_memory_tokens is None:
            max_memory_tokens = int(self.max_tokens * 0.3)
        
        memories = await self._retrieve_relevant_memories(query, namespace, limit=20)
        scored = await self._score_memories(memories, query)
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Calculate current token usage
        current_tokens = self.estimate_context_tokens(messages)
        available = self.max_tokens - current_tokens - 100  # Reserve for response
        
        # Add memories (within budget)
        memory_messages = []
        included_memories = []
        tokens_used = 0
        
        for memory, score in scored:
            formatted = self._format_memory_for_provider(memory, self.provider)
            tokens = self.estimate_context_tokens([{"content": formatted}])
            
            if tokens_used + tokens <= min(max_memory_tokens, available):
                memory_messages.append({
                    "role": "system",
                    "content": formatted
                })
                included_memories.append(memory)
                tokens_used += tokens
            else:
                break
        
        # Insert memory messages after system prompt or at beginning
        if memory_messages:
            if system_idx >= 0:
                # Insert after system prompt
                messages = messages[:system_idx+1] + memory_messages + messages[system_idx+1:]
            else:
                # Insert at beginning
                messages = memory_messages + messages
        
        return messages, included_memories

