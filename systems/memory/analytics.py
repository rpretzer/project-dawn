"""
Memory Analytics
Usage patterns, retention analysis, performance metrics
"""

import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timedelta

from .core import MemCube, MemoryType, MemoryState
from .vault import MemVault
from .interface import MemoryAPI

logger = logging.getLogger(__name__)


@dataclass
class MemoryMetrics:
    """Memory system metrics"""
    total_memories: int
    by_type: Dict[str, int]
    by_state: Dict[str, int]
    by_semantic_type: Dict[str, int]
    total_size_bytes: int
    average_priority: float
    oldest_memory_age_days: float
    newest_memory_age_days: float
    average_access_count: float
    hot_memory_count: int  # Recently accessed


@dataclass
class RetentionMetrics:
    """Memory retention analysis"""
    total_active: int
    archived_count: int
    expired_count: int
    by_ttl_bucket: Dict[str, int]  # "<1 day", "1-7 days", etc.
    average_retention_days: float
    retention_rate: float  # Percentage still active


@dataclass
class UsagePatterns:
    """Memory usage patterns"""
    access_frequency: Dict[str, int]  # memory_id -> access_count
    popular_memories: List[tuple]  # (memory_id, access_count)
    access_timeline: Dict[str, int]  # date -> access_count
    query_patterns: Dict[str, int]  # query_type -> count


class MemoryAnalytics:
    """
    Analytics and metrics for memory system
    
    Provides:
    - Usage patterns and trends
    - Retention analysis
    - Performance metrics
    - Access pattern analysis
    """
    
    def __init__(self, memory_api: MemoryAPI, vault: MemVault):
        self.memory_api = memory_api
        self.vault = vault
    
    async def get_system_metrics(
        self,
        namespace: Optional[tuple] = None
    ) -> MemoryMetrics:
        """
        Get comprehensive system metrics
        
        Args:
            namespace: Optional namespace filter
            
        Returns:
            MemoryMetrics object
        """
        from .core import MemoryQuery
        
        query = MemoryQuery(
            query_type="hybrid",
            parameters={"limit": 1000000},
            namespace=namespace or ("*", "*", "*"),
            requester_id="system"
        )
        
        memories = await self.memory_api.retrieve(query)
        
        if not memories:
            return MemoryMetrics(
                total_memories=0,
                by_type={},
                by_state={},
                by_semantic_type={},
                total_size_bytes=0,
                average_priority=0.0,
                oldest_memory_age_days=0.0,
                newest_memory_age_days=0.0,
                average_access_count=0.0,
                hot_memory_count=0
            )
        
        # Categorize
        by_type = defaultdict(int)
        by_state = defaultdict(int)
        by_semantic = defaultdict(int)
        
        total_size = 0
        total_priority = 0
        total_access = 0
        timestamps = []
        current_time = time.time()
        hot_count = 0
        
        for memory in memories:
            by_type[memory.memory_type.value] += 1
            by_state[memory.state.value] += 1
            by_semantic[memory.semantic_type] += 1
            
            content_size = len(str(memory.content)) if memory.content else 0
            total_size += content_size
            
            total_priority += memory.priority_level
            total_access += memory.access_count
            
            timestamps.append(memory.timestamp)
            
            # Count hot memories (accessed in last hour)
            if memory.last_access and (current_time - memory.last_access) < 3600:
                hot_count += 1
        
        oldest = min(timestamps) if timestamps else current_time
        newest = max(timestamps) if timestamps else current_time
        
        return MemoryMetrics(
            total_memories=len(memories),
            by_type=dict(by_type),
            by_state=dict(by_state),
            by_semantic_type=dict(by_semantic),
            total_size_bytes=total_size,
            average_priority=total_priority / len(memories) if memories else 0.0,
            oldest_memory_age_days=(current_time - oldest) / (24 * 3600),
            newest_memory_age_days=(current_time - newest) / (24 * 3600),
            average_access_count=total_access / len(memories) if memories else 0.0,
            hot_memory_count=hot_count
        )
    
    async def get_retention_metrics(
        self,
        namespace: Optional[tuple] = None
    ) -> RetentionMetrics:
        """
        Analyze memory retention patterns
        
        Args:
            namespace: Optional namespace filter
            
        Returns:
            RetentionMetrics object
        """
        from .core import MemoryQuery
        
        query = MemoryQuery(
            query_type="hybrid",
            parameters={"limit": 1000000},
            namespace=namespace or ("*", "*", "*"),
            requester_id="system"
        )
        
        memories = await self.memory_api.retrieve(query)
        
        active_count = sum(1 for m in memories if m.state != MemoryState.ARCHIVED)
        archived_count = sum(1 for m in memories if m.state == MemoryState.ARCHIVED)
        expired_count = sum(1 for m in memories if m.is_expired())
        
        # TTL buckets
        ttl_buckets = {
            "<1 day": 0,
            "1-7 days": 0,
            "7-30 days": 0,
            "30-90 days": 0,
            "90-365 days": 0,
            ">365 days": 0,
            "no_ttl": 0
        }
        
        current_time = time.time()
        total_retention = 0
        retention_count = 0
        
        for memory in memories:
            if memory.ttl:
                age_days = (current_time - memory.timestamp) / (24 * 3600)
                total_retention += age_days
                retention_count += 1
                
                if age_days < 1:
                    ttl_buckets["<1 day"] += 1
                elif age_days < 7:
                    ttl_buckets["1-7 days"] += 1
                elif age_days < 30:
                    ttl_buckets["7-30 days"] += 1
                elif age_days < 90:
                    ttl_buckets["30-90 days"] += 1
                elif age_days < 365:
                    ttl_buckets["90-365 days"] += 1
                else:
                    ttl_buckets[">365 days"] += 1
            else:
                ttl_buckets["no_ttl"] += 1
        
        retention_rate = (active_count / len(memories) * 100) if memories else 0.0
        
        return RetentionMetrics(
            total_active=active_count,
            archived_count=archived_count,
            expired_count=expired_count,
            by_ttl_bucket=ttl_buckets,
            average_retention_days=total_retention / retention_count if retention_count > 0 else 0.0,
            retention_rate=retention_rate
        )
    
    async def get_usage_patterns(
        self,
        namespace: Optional[tuple] = None,
        days: int = 30
    ) -> UsagePatterns:
        """
        Analyze memory usage patterns
        
        Args:
            namespace: Optional namespace filter
            days: Number of days to analyze
            
        Returns:
            UsagePatterns object
        """
        from .core import MemoryQuery
        
        query = MemoryQuery(
            query_type="hybrid",
            parameters={"limit": 100000},
            namespace=namespace or ("*", "*", "*"),
            requester_id="system"
        )
        
        memories = await self.memory_api.retrieve(query)
        
        # Access frequency
        access_frequency = {
            m.memory_id: m.access_count
            for m in memories
        }
        
        # Popular memories (most accessed)
        popular = sorted(
            [(m.memory_id, m.access_count) for m in memories],
            key=lambda x: x[1],
            reverse=True
        )[:100]  # Top 100
        
        # Access timeline (last N days)
        cutoff_time = time.time() - (days * 24 * 3600)
        access_timeline = defaultdict(int)
        
        for memory in memories:
            if memory.last_access and memory.last_access >= cutoff_time:
                date_str = datetime.fromtimestamp(memory.last_access).strftime("%Y-%m-%d")
                access_timeline[date_str] += 1
        
        # Query patterns (from access log if available)
        query_patterns = defaultdict(int)
        if hasattr(self.memory_api, 'access_log'):
            for log_entry in self.memory_api.access_log[-1000:]:  # Last 1000 queries
                operation = log_entry.get("operation", "unknown")
                query_patterns[operation] += 1
        
        return UsagePatterns(
            access_frequency=access_frequency,
            popular_memories=popular,
            access_timeline=dict(access_timeline),
            query_patterns=dict(query_patterns)
        )
    
    async def get_namespace_stats(
        self,
        namespace: tuple
    ) -> Dict[str, Any]:
        """
        Get statistics for a specific namespace
        
        Args:
            namespace: Namespace tuple
            
        Returns:
            Namespace statistics
        """
        metrics = await self.get_system_metrics(namespace)
        retention = await self.get_retention_metrics(namespace)
        usage = await self.get_usage_patterns(namespace)
        
        return {
            "namespace": list(namespace),
            "metrics": {
                "total_memories": metrics.total_memories,
                "by_type": metrics.by_type,
                "by_state": metrics.by_state,
                "total_size_bytes": metrics.total_size_bytes,
                "average_priority": metrics.average_priority,
                "hot_memory_count": metrics.hot_memory_count
            },
            "retention": {
                "active_count": retention.total_active,
                "archived_count": retention.archived_count,
                "retention_rate": retention.retention_rate
            },
            "usage": {
                "most_accessed": usage.popular_memories[:10],
                "total_accesses": sum(usage.access_frequency.values())
            }
        }
    
    async def generate_report(
        self,
        namespace: Optional[tuple] = None,
        output_format: str = "dict"
    ) -> Any:
        """
        Generate comprehensive analytics report
        
        Args:
            namespace: Optional namespace filter
            output_format: "dict", "json", or "text"
            
        Returns:
            Analytics report in requested format
        """
        metrics = await self.get_system_metrics(namespace)
        retention = await self.get_retention_metrics(namespace)
        usage = await self.get_usage_patterns(namespace)
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "namespace": list(namespace) if namespace else "all",
            "metrics": {
                "total_memories": metrics.total_memories,
                "by_type": metrics.by_type,
                "by_state": metrics.by_state,
                "total_size_mb": round(metrics.total_size_bytes / (1024 * 1024), 2),
                "average_priority": round(metrics.average_priority, 2),
                "oldest_memory_days": round(metrics.oldest_memory_age_days, 1),
                "hot_memories": metrics.hot_memory_count
            },
            "retention": {
                "active": retention.total_active,
                "archived": retention.archived_count,
                "expired": retention.expired_count,
                "retention_rate_pct": round(retention.retention_rate, 2),
                "average_retention_days": round(retention.average_retention_days, 1)
            },
            "usage": {
                "most_popular": usage.popular_memories[:20],
                "total_accesses": sum(usage.access_frequency.values()),
                "query_patterns": usage.query_patterns
            }
        }
        
        if output_format == "json":
            import json
            return json.dumps(report, indent=2)
        
        elif output_format == "text":
            lines = [
                "=" * 60,
                "MEMORY ANALYTICS REPORT",
                "=" * 60,
                f"Generated: {report['generated_at']}",
                f"Namespace: {report['namespace']}",
                "",
                "METRICS:",
                f"  Total Memories: {metrics.total_memories}",
                f"  Total Size: {report['metrics']['total_size_mb']} MB",
                f"  Average Priority: {report['metrics']['average_priority']}",
                f"  Hot Memories: {metrics.hot_memory_count}",
                "",
                "RETENTION:",
                f"  Active: {retention.total_active}",
                f"  Archived: {retention.archived_count}",
                f"  Retention Rate: {report['retention']['retention_rate_pct']}%",
                "",
                "USAGE:",
                f"  Total Accesses: {report['usage']['total_accesses']}",
                f"  Top 10 Most Accessed Memories:"
            ]
            
            for i, (mem_id, count) in enumerate(report['usage']['most_popular'][:10], 1):
                lines.append(f"    {i}. {mem_id}: {count} accesses")
            
            return "\n".join(lines)
        
        return report

