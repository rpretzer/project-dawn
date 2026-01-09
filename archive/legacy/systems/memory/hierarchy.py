"""
Memory Hierarchy Helpers
Convenience methods for common hierarchy patterns (enterprise/project/user/session)
"""

from typing import Tuple, Optional, Dict, Any
from .core import MemCube, MemoryType, MemoryState
import time


class MemoryHierarchy:
    """
    Convenience methods for common memory hierarchy patterns
    
    Supports patterns like:
    - Enterprise/Organization-level (policies, standards)
    - Project-level (team-shared knowledge)
    - User-level (personal preferences, memories)
    - Session-level (temporary context)
    """
    
    @staticmethod
    def enterprise_namespace(org_id: str, scope: str = "policy") -> Tuple[str, str, str]:
        """
        Create enterprise/organization-level namespace
        
        Args:
            org_id: Organization identifier
            scope: Scope within organization (default: "policy")
            
        Returns:
            Namespace tuple: (org_id, "enterprise", scope)
            
        Example:
            namespace = MemoryHierarchy.enterprise_namespace("acme-corp")
            # Returns: ("acme-corp", "enterprise", "policy")
        """
        return (org_id, "enterprise", scope)
    
    @staticmethod
    def project_namespace(project_id: str, user_id: str, scope: str = "shared") -> Tuple[str, str, str]:
        """
        Create project-level namespace for team-shared memories
        
        Args:
            project_id: Project identifier
            user_id: User/team identifier
            scope: Scope within project (default: "shared")
            
        Returns:
            Namespace tuple: (project_id, user_id, scope)
            
        Example:
            namespace = MemoryHierarchy.project_namespace("project-alpha", "team-1")
            # Returns: ("project-alpha", "team-1", "shared")
        """
        return (project_id, user_id, scope)
    
    @staticmethod
    def user_namespace(user_id: str, context: str = "personal", scope: str = "default") -> Tuple[str, str, str]:
        """
        Create user-level namespace for personal memories
        
        Args:
            user_id: User identifier
            context: Context within user (default: "personal")
            scope: Scope (default: "default")
            
        Returns:
            Namespace tuple: (user_id, context, scope)
            
        Example:
            namespace = MemoryHierarchy.user_namespace("user123", "preferences")
            # Returns: ("user123", "preferences", "default")
        """
        return (user_id, context, scope)
    
    @staticmethod
    def session_namespace(session_id: str, user_id: Optional[str] = None) -> Tuple[str, str, str]:
        """
        Create session-level namespace for temporary context
        
        Args:
            session_id: Session identifier
            user_id: Optional user identifier
            
        Returns:
            Namespace tuple: (session_id or user_id, "session", "temp")
            
        Example:
            namespace = MemoryHierarchy.session_namespace("session-abc123", "user123")
            # Returns: ("session-abc123", "session", "temp")
        """
        if user_id:
            return (user_id, "session", session_id)
        return (session_id, "session", "temp")
    
    @staticmethod
    def create_enterprise_memory(
        content: Any,
        org_id: str,
        semantic_type: str = "policy",
        priority: int = 8,
        **kwargs
    ) -> MemCube:
        """
        Create an enterprise-level memory (policies, standards, etc.)
        
        Args:
            content: Memory content
            org_id: Organization ID
            semantic_type: Type of memory (default: "policy")
            priority: Priority level 1-10 (default: 8, high for enterprise)
            **kwargs: Additional MemCube parameters
            
        Returns:
            MemCube configured for enterprise namespace
        """
        namespace = MemoryHierarchy.enterprise_namespace(org_id)
        return MemCube(
            memory_id=None,
            content=content,
            memory_type=kwargs.get("memory_type", MemoryType.PLAINTEXT),
            timestamp=time.time(),
            origin_signature=f"enterprise:{org_id}",
            semantic_type=semantic_type,
            namespace=namespace,
            access_control={"enterprise": ["read"], "admin": ["read", "write", "delete"]},
            priority_level=priority,
            compliance_tags=kwargs.get("compliance_tags", []),
            ttl=kwargs.get("ttl"),  # Enterprise policies often have long/no TTL
            **{k: v for k, v in kwargs.items() if k not in ["memory_type", "compliance_tags", "ttl"]}
        )
    
    @staticmethod
    def create_project_memory(
        content: Any,
        project_id: str,
        user_id: str,
        semantic_type: str = "knowledge",
        priority: int = 5,
        **kwargs
    ) -> MemCube:
        """
        Create a project-level memory (team-shared knowledge)
        
        Args:
            content: Memory content
            project_id: Project ID
            user_id: User/team ID
            semantic_type: Type of memory (default: "knowledge")
            priority: Priority level 1-10 (default: 5)
            **kwargs: Additional MemCube parameters
            
        Returns:
            MemCube configured for project namespace
        """
        namespace = MemoryHierarchy.project_namespace(project_id, user_id)
        return MemCube(
            memory_id=None,
            content=content,
            memory_type=kwargs.get("memory_type", MemoryType.PLAINTEXT),
            timestamp=time.time(),
            origin_signature=f"project:{project_id}:{user_id}",
            semantic_type=semantic_type,
            namespace=namespace,
            access_control={"team": ["read", "write"], "owner": ["read", "write", "delete"]},
            priority_level=priority,
            compliance_tags=kwargs.get("compliance_tags", []),
            ttl=kwargs.get("ttl"),
            **{k: v for k, v in kwargs.items() if k not in ["memory_type", "compliance_tags", "ttl"]}
        )
    
    @staticmethod
    def create_user_memory(
        content: Any,
        user_id: str,
        semantic_type: str = "personal",
        context: str = "personal",
        priority: int = 5,
        **kwargs
    ) -> MemCube:
        """
        Create a user-level memory (personal preferences, memories)
        
        Args:
            content: Memory content
            user_id: User ID
            semantic_type: Type of memory (default: "personal")
            context: Context within user space (default: "personal")
            priority: Priority level 1-10 (default: 5)
            **kwargs: Additional MemCube parameters
            
        Returns:
            MemCube configured for user namespace
        """
        namespace = MemoryHierarchy.user_namespace(user_id, context)
        return MemCube(
            memory_id=None,
            content=content,
            memory_type=kwargs.get("memory_type", MemoryType.PLAINTEXT),
            timestamp=time.time(),
            origin_signature=f"user:{user_id}",
            semantic_type=semantic_type,
            namespace=namespace,
            access_control={"owner": ["read", "write", "delete"]},
            priority_level=priority,
            compliance_tags=kwargs.get("compliance_tags", []),
            ttl=kwargs.get("ttl"),
            **{k: v for k, v in kwargs.items() if k not in ["memory_type", "compliance_tags", "ttl"]}
        )
    
    @staticmethod
    def create_session_memory(
        content: Any,
        session_id: str,
        user_id: Optional[str] = None,
        semantic_type: str = "context",
        priority: int = 3,
        ttl: Optional[int] = 3600,  # 1 hour default for session memories
        **kwargs
    ) -> MemCube:
        """
        Create a session-level memory (temporary context)
        
        Args:
            content: Memory content
            session_id: Session ID
            user_id: Optional user ID
            semantic_type: Type of memory (default: "context")
            priority: Priority level 1-10 (default: 3, lower for temporary)
            ttl: Time-to-live in seconds (default: 3600 = 1 hour)
            **kwargs: Additional MemCube parameters
            
        Returns:
            MemCube configured for session namespace
        """
        namespace = MemoryHierarchy.session_namespace(session_id, user_id)
        return MemCube(
            memory_id=None,
            content=content,
            memory_type=kwargs.get("memory_type", MemoryType.PLAINTEXT),
            timestamp=time.time(),
            origin_signature=f"session:{session_id}",
            semantic_type=semantic_type,
            namespace=namespace,
            access_control={"owner": ["read", "write", "delete"]},
            priority_level=priority,
            compliance_tags=kwargs.get("compliance_tags", []),
            ttl=ttl,
            state=MemoryState.GENERATED,
            **{k: v for k, v in kwargs.items() if k not in ["memory_type", "compliance_tags", "ttl"]}
        )
    
    @staticmethod
    def matches_hierarchy_pattern(
        namespace: Tuple[str, str, str],
        pattern: str
    ) -> bool:
        """
        Check if namespace matches a hierarchy pattern
        
        Args:
            namespace: Namespace tuple to check
            pattern: Pattern to match ("enterprise", "project", "user", "session")
            
        Returns:
            True if namespace matches pattern
            
        Example:
            ns = ("acme-corp", "enterprise", "policy")
            MemoryHierarchy.matches_hierarchy_pattern(ns, "enterprise")  # True
        """
        pattern = pattern.lower()
        user_id, context, scope = namespace
        
        if pattern == "enterprise":
            return context == "enterprise"
        elif pattern == "project":
            return context not in ("enterprise", "session") and scope in ("shared", "project")
        elif pattern == "user":
            return context in ("personal", "user", "preferences") or scope == "default"
        elif pattern == "session":
            return context == "session" or scope == "temp"
        
        return False
    
    @staticmethod
    def get_hierarchy_level(namespace: Tuple[str, str, str]) -> str:
        """
        Determine hierarchy level from namespace
        
        Returns:
            "enterprise", "project", "user", or "session"
        """
        if MemoryHierarchy.matches_hierarchy_pattern(namespace, "enterprise"):
            return "enterprise"
        elif MemoryHierarchy.matches_hierarchy_pattern(namespace, "session"):
            return "session"
        elif MemoryHierarchy.matches_hierarchy_pattern(namespace, "project"):
            return "project"
        else:
            return "user"

