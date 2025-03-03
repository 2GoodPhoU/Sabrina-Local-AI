"""
Enhanced Event System for Sabrina AI
===================================
Extended event system providing additional functionality over the base event system.
This module wraps and extends the base event system in utilities/event_system.py
"""

import logging
import time
import uuid
from typing import Dict, List, Callable, Any, Optional, Union
from enum import Enum, auto

# Import base event system
from utilities.event_system import (
    EventBus as BaseEventBus,
    Event as BaseEvent,
    EventType as BaseEventType,
    EventPriority as BaseEventPriority,
    EventHandler as BaseEventHandler,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sabrina.enhanced_event_system")


# Enhanced EventType - extends the base EventType with additional event types
class EventType(BaseEventType):
    """Enhanced event types supported by the system"""

    # System events
    SYSTEM_STARTUP = auto()
    SYSTEM_SHUTDOWN = auto()
    SYSTEM_ERROR = auto()

    # State events
    STATE_CHANGE = auto()

    # Speech events
    SPEECH_STARTED = auto()
    SPEECH_COMPLETED = auto()
    SPEECH_ERROR = auto()

    # Hearing events
    LISTENING_STARTED = auto()
    LISTENING_COMPLETED = auto()
    WAKE_WORD_DETECTED = auto()

    # User input events
    USER_VOICE_COMMAND = auto()
    USER_TEXT_COMMAND = auto()

    # Vision events
    SCREEN_CAPTURED = auto()
    ELEMENT_DETECTED = auto()
    OCR_RESULT = auto()

    # Automation events
    AUTOMATION_STARTED = auto()
    AUTOMATION_COMPLETED = auto()
    AUTOMATION_ERROR = auto()

    # Device events
    DEVICE_COMMAND = auto()
    DEVICE_QUERY = auto()
    DEVICE_STATE = auto()
    DEVICE_STATE_CHANGED = auto()
    ROUTINE_EXECUTE = auto()


# Use the base EventPriority directly
EventPriority = BaseEventPriority


# Enhanced Event class - extends the base Event class
class Event(BaseEvent):
    """Enhanced event class with additional functionality"""

    def __init__(
        self,
        event_type: Any,
        data: Dict[str, Any] = None,
        source: str = "unknown",
        priority: EventPriority = EventPriority.NORMAL,
        id: str = None,
        timestamp: float = None,
    ):
        """
        Initialize an enhanced event

        Args:
            event_type: Type of the event
            data: Event data payload
            source: Source of the event
            priority: Event priority
            id: Event ID (generated if not provided)
            timestamp: Event timestamp (current time if not provided)
        """
        # Initialize with base Event constructor
        super().__init__(
            event_type=event_type,
            data=data or {},
            source=source,
            priority=priority,
            id=id or str(uuid.uuid4()),
            timestamp=timestamp or time.time(),
        )


# Enhanced EventHandler class - extends the base EventHandler class
class EventHandler(BaseEventHandler):
    """Enhanced event handler with additional functionality"""

    def __init__(
        self,
        callback: Callable[[Event], None],
        event_types: Optional[List[Any]] = None,
        min_priority: EventPriority = EventPriority.LOW,
        sources: Optional[List[str]] = None,
        id: Optional[str] = None,
    ):
        """
        Initialize an enhanced event handler

        Args:
            callback: Function to call when an event is received
            event_types: Event types to handle
            min_priority: Minimum priority to handle
            sources: Sources to handle events from
            id: Handler ID (generated if not provided)
        """
        # Initialize with base EventHandler constructor
        super().__init__(
            callback=callback,
            event_types=event_types,
            min_priority=min_priority,
            sources=sources,
            id=id or str(uuid.uuid4()),
        )


# Enhanced EventBus class - extends the base EventBus class
class EnhancedEventBus(BaseEventBus):
    """Enhanced event bus with additional functionality"""

    def __init__(self, max_queue_size: int = 1000, worker_count: int = 1):
        """
        Initialize an enhanced event bus

        Args:
            max_queue_size: Maximum number of events in queue
            worker_count: Number of worker threads
        """
        # Initialize with base EventBus constructor
        super().__init__(max_queue_size=max_queue_size, worker_count=worker_count)

    def create_handler(
        self,
        callback: Callable[[Event], None],
        event_types: Union[Any, List[Any]],
        min_priority: EventPriority = EventPriority.LOW,
        sources: Optional[List[str]] = None,
    ) -> EventHandler:
        """
        Create an event handler

        Args:
            callback: Function to call when an event is received
            event_types: Event type or list of event types to handle
            min_priority: Minimum priority to handle
            sources: List of sources to handle events from

        Returns:
            EventHandler: Created event handler (not registered yet)
        """
        # Convert single event type to list
        if not isinstance(event_types, list):
            event_types = [event_types]

        # Create and return handler
        return EventHandler(callback, event_types, min_priority, sources)
