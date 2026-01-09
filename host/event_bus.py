"""
Event Bus for MCP Host

Pub/sub system for state changes and events.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types"""
    CONNECTION = "connection"
    DISCONNECTION = "disconnection"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    STATE_CHANGED = "state_changed"
    MESSAGE = "message"
    CUSTOM = "custom"


@dataclass
class Event:
    """Event representation"""
    type: EventType
    source: str  # Who generated the event
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dict"""
        return {
            "type": self.type.value,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp,
            "id": self.id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create event from dict"""
        return cls(
            type=EventType(data["type"]),
            source=data["source"],
            data=data["data"],
            timestamp=data.get("timestamp", time.time()),
            id=data.get("id"),
        )


class EventBus:
    """
    Event bus for pub/sub messaging
    
    Allows components to publish events and subscribe to event types.
    """
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable[[Event], Awaitable[None]]]] = {}
        self.all_subscribers: List[Callable[[Event], Awaitable[None]]] = []
        self.event_log: List[Event] = []
        self.max_log_size = 10000
        logger.debug("Event bus initialized")
    
    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Awaitable[None]]
    ) -> None:
        """
        Subscribe to specific event type
        
        Args:
            event_type: Type of event to subscribe to
            handler: Async handler function
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append(handler)
        logger.debug(f"Subscriber added for event type: {event_type.value}")
    
    def subscribe_all(self, handler: Callable[[Event], Awaitable[None]]) -> None:
        """
        Subscribe to all events
        
        Args:
            handler: Async handler function
        """
        self.all_subscribers.append(handler)
        logger.debug("Subscriber added for all events")
    
    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Awaitable[None]]
    ) -> None:
        """
        Unsubscribe from event type
        
        Args:
            event_type: Event type
            handler: Handler to remove
        """
        if event_type in self.subscribers:
            if handler in self.subscribers[event_type]:
                self.subscribers[event_type].remove(handler)
                logger.debug(f"Subscriber removed for event type: {event_type.value}")
    
    def unsubscribe_all(self, handler: Callable[[Event], Awaitable[None]]) -> None:
        """
        Unsubscribe from all events
        
        Args:
            handler: Handler to remove
        """
        if handler in self.all_subscribers:
            self.all_subscribers.remove(handler)
            logger.debug("Subscriber removed for all events")
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event
        
        Args:
            event: Event to publish
        """
        # Add to event log
        self.event_log.append(event)
        
        # Trim log if too large
        if len(self.event_log) > self.max_log_size:
            self.event_log = self.event_log[-self.max_log_size:]
        
        logger.debug(f"Publishing event: {event.type.value} from {event.source}")
        
        # Notify type-specific subscribers
        if event.type in self.subscribers:
            for handler in self.subscribers[event.type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event.type.value}: {e}", exc_info=True)
        
        # Notify all-event subscribers
        for handler in self.all_subscribers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in all-event handler: {e}", exc_info=True)
    
    async def publish_event(
        self,
        event_type: EventType,
        source: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None
    ) -> Event:
        """
        Create and publish an event
        
        Args:
            event_type: Event type
            source: Event source
            data: Event data
            event_id: Optional event ID
            
        Returns:
            Created event
        """
        event = Event(
            type=event_type,
            source=source,
            data=data,
            id=event_id,
        )
        await self.publish(event)
        return event
    
    def get_events(
        self,
        event_type: Optional[EventType] = None,
        source: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Get recent events from log
        
        Args:
            event_type: Filter by event type (optional)
            source: Filter by source (optional)
            limit: Maximum number of events to return
            
        Returns:
            List of events
        """
        events = self.event_log
        
        # Filter by type
        if event_type:
            events = [e for e in events if e.type == event_type]
        
        # Filter by source
        if source:
            events = [e for e in events if e.source == source]
        
        # Return most recent
        return list(reversed(events[-limit:]))
    
    def clear_log(self) -> None:
        """Clear event log"""
        self.event_log.clear()
        logger.debug("Event log cleared")



