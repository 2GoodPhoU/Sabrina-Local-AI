"""
Optimized event system for Sabrina's Presence System

Provides an efficient, performant event handling system with support for
priorities, filtering, and asynchronous event processing
"""
# Standard imports
import threading
import queue
import time
import uuid
from enum import Enum, auto
from typing import Dict, List, Callable, Any, Optional, Union
from dataclasses import dataclass, field
from collections import defaultdict

# Local imports
from .error_handling import ErrorHandler, logger


class EventType(Enum):
    """Types of events that can be raised in the Presence System"""

    ANIMATION_CHANGE = auto()  # Animation state change
    SYSTEM_STATE = auto()  # System state events (startup, shutdown, etc.)
    USER_INTERACTION = auto()  # User interactions with presence
    VOICE_ACTIVITY = auto()  # Voice input/output activity
    SETTINGS_CHANGE = auto()  # Settings or configuration changes
    EXTERNAL_COMMAND = auto()  # Commands from external systems
    ERROR = auto()  # Error notifications
    RESOURCE = auto()  # Resource lifecycle events
    CUSTOM = auto()  # Custom event types


class EventPriority(Enum):
    """Priority levels for events"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """Represents an event in the system with optimized handling"""

    type: EventType  # Type of the event
    data: Dict[str, Any] = field(default_factory=dict)  # Dictionary with event data
    priority: EventPriority = EventPriority.NORMAL  # Event priority
    source: str = "system"  # Source of the event
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Unique event ID
    timestamp: float = field(default_factory=time.time)  # Event creation timestamp

    def __str__(self) -> str:
        """String representation of the event"""
        return f"Event(type={self.type.name}, priority={self.priority.name}, source={self.source})"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the event data

        Args:
            key: Data key to retrieve
            default: Default value if key not found

        Returns:
            Value from data dictionary or default
        """
        return self.data.get(key, default)

    def merge_data(self, additional_data: Dict[str, Any]) -> "Event":
        """Merge additional data into the event

        Args:
            additional_data: Additional data to merge

        Returns:
            Self for chaining
        """
        self.data.update(additional_data)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary

        Returns:
            Dict representation of the event
        """
        return {
            "id": self.id,
            "type": self.type.name,
            "priority": self.priority.name,
            "source": self.source,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class EventHandler:
    """Event handler with optimized filtering capability"""

    def __init__(
        self,
        callback: Callable[[Event], None],
        event_types: Optional[List[EventType]] = None,
        min_priority: EventPriority = EventPriority.LOW,
        sources: Optional[List[str]] = None,
        id: Optional[str] = None,
    ):
        """Initialize event handler

        Args:
            callback: Function to call when event is processed
            event_types: List of event types to handle (None = all)
            min_priority: Minimum priority level to handle
            sources: List of sources to accept events from (None = all)
            id: Optional custom ID (defaults to auto-generated UUID)
        """
        self.callback = callback
        self.event_types = event_types
        self.min_priority = min_priority
        self.sources = sources
        self.id = id or str(uuid.uuid4())
        self.created_at = time.time()
        self.last_called = 0
        self.call_count = 0

    def can_handle(self, event: Event) -> bool:
        """Check if this handler can handle the given event

        This method is optimized for frequent calls.

        Args:
            event: Event to check

        Returns:
            True if handler can handle event, False otherwise
        """
        # Check event type (fast path for single type)
        if self.event_types is not None:
            if len(self.event_types) == 1:
                # Optimize single type check (common case)
                if event.type != self.event_types[0]:
                    return False
            else:
                # Check multiple types
                if event.type not in self.event_types:
                    return False

        # Check priority (enum comparison)
        if event.priority.value < self.min_priority.value:
            return False

        # Check source (fast path for single source)
        if self.sources is not None:
            if len(self.sources) == 1:
                # Optimize single source check
                if event.source != self.sources[0]:
                    return False
            else:
                # Check multiple sources
                if event.source not in self.sources:
                    return False

        return True

    def handle(self, event: Event) -> bool:
        """Handle event by calling the callback

        Args:
            event: Event to handle

        Returns:
            True if handled successfully, False otherwise
        """
        try:
            self.callback(event)
            self.last_called = time.time()
            self.call_count += 1
            return True
        except Exception as e:
            ErrorHandler.log_error(e, f"Error in event handler {self.id}")
            return False


class EventBus:
    """Optimized central event bus for the Presence System"""

    def __init__(self, max_queue_size: int = 1000, worker_count: int = 1):
        """Initialize the event bus

        Args:
            max_queue_size: Maximum number of events in queue (default: 1000)
            worker_count: Number of worker threads (default: 1)
        """
        # Handlers and indexes for fast lookup
        self.handlers: Dict[str, EventHandler] = {}  # Handler ID -> Handler
        self.handlers_by_type: Dict[EventType, List[str]] = defaultdict(
            list
        )  # Type -> [Handler IDs]
        self.handlers_by_source: Dict[str, List[str]] = defaultdict(
            list
        )  # Source -> [Handler IDs]

        # Event processing
        self.event_queue = queue.PriorityQueue(
            maxsize=max_queue_size
        )  # Queue of events
        self.running = False
        self.workers: List[threading.Thread] = []
        self.worker_count = worker_count

        # Statistics and monitoring
        self.history: List[Event] = []  # Event history
        self.max_history = 100  # Maximum number of events to keep in history
        self.processed_count = 0
        self.dropped_count = 0
        self.start_time = 0

        # Performance optimization
        self.queue_high_water_mark = 0
        self.processing_times: List[float] = []  # Last 100 processing times
        self.max_processing_times = 100  # Number of processing times to keep

    def start(self):
        """Start the event processing thread(s)"""
        if self.running:
            logger.warning("Event bus already running")
            return

        self.running = True
        self.start_time = time.time()

        # Create and start worker threads
        for i in range(self.worker_count):
            worker = threading.Thread(
                target=self._process_events, name=f"EventBus-Worker-{i}", daemon=True
            )
            worker.start()
            self.workers.append(worker)

        logger.info(f"Event bus started with {self.worker_count} worker(s)")

    def stop(self, timeout: float = 1.0):
        """Stop the event processing thread(s)

        Args:
            timeout: Maximum time to wait for threads to stop (default: 1.0s)
        """
        if not self.running:
            logger.warning("Event bus not running")
            return

        self.running = False

        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=timeout)

        self.workers = []
        logger.info("Event bus stopped")

    def register_handler(self, handler: EventHandler) -> str:
        """Register a new event handler

        Args:
            handler: The event handler to register

        Returns:
            Handler ID
        """
        # Add to main handler dictionary
        self.handlers[handler.id] = handler

        # Add to type index for faster lookup
        if handler.event_types:
            for event_type in handler.event_types:
                self.handlers_by_type[event_type].append(handler.id)

        # Add to source index for faster lookup
        if handler.sources:
            for source in handler.sources:
                self.handlers_by_source[source].append(handler.id)

        logger.debug(f"Registered event handler: {handler.id}")
        return handler.id

    def create_event_handler(
        self,
        event_types: Union[EventType, List[EventType]],
        callback: Callable[[Event], None],
        min_priority: EventPriority = EventPriority.LOW,
        sources: Optional[List[str]] = None,
    ) -> EventHandler:
        """Create an event handler

        Args:
            event_types: List of event types to handle or single event type
            callback: Function to call when event is processed
            min_priority: Minimum priority level to handle
            sources: List of sources to accept events from (None = all)

        Returns:
            EventHandler instance
        """
        # Convert single event type to list
        if not isinstance(event_types, list) and event_types is not None:
            event_types = [event_types]

        return EventHandler(callback, event_types, min_priority, sources)

    def unregister_handler(self, handler_id: str) -> bool:
        """Unregister an event handler

        Args:
            handler_id: ID of the handler to unregister

        Returns:
            True if successful, False otherwise
        """
        if handler_id in self.handlers:
            handler = self.handlers[handler_id]

            # Remove from main dictionary
            del self.handlers[handler_id]

            # Remove from type index
            if handler.event_types:
                for event_type in handler.event_types:
                    if handler_id in self.handlers_by_type[event_type]:
                        self.handlers_by_type[event_type].remove(handler_id)

            # Remove from source index
            if handler.sources:
                for source in handler.sources:
                    if handler_id in self.handlers_by_source[source]:
                        self.handlers_by_source[source].remove(handler_id)

            logger.debug(f"Unregistered event handler: {handler_id}")
            return True

        logger.warning(f"Handler not found: {handler_id}")
        return False

    def post_event(self, event: Event) -> bool:
        """Post an event to the event bus

        Args:
            event: The event to post

        Returns:
            True if posted successfully, False otherwise
        """
        if not self.running:
            return False

        try:
            # Add to queue with priority (negative so higher priority is processed first)
            self.event_queue.put(
                (-event.priority.value, event.timestamp, event), block=False
            )

            # Update statistics
            self.queue_high_water_mark = max(
                self.queue_high_water_mark, self.event_queue.qsize()
            )

            # Add to history
            self._add_to_history(event)

            logger.debug(f"Posted event: {event}")
            return True
        except queue.Full:
            self.dropped_count += 1
            logger.warning(f"Event queue full, dropped event: {event}")
            return False

    def post_event_immediate(self, event: Event) -> bool:
        """Post and process an event immediately (blocking)

        Args:
            event: The event to post and process

        Returns:
            True if processed successfully, False otherwise
        """
        logger.debug(f"Processing immediate event: {event}")
        result = self._process_event(event)

        # Add to history
        self._add_to_history(event)

        return result

    def _add_to_history(self, event: Event):
        """Add event to history

        Args:
            event: Event to add
        """
        self.history.append(event)
        # Trim history if necessary
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

    def _process_events(self):
        """Process events from the queue (run in separate thread)"""
        while self.running:
            try:
                # Get event from queue with timeout
                try:
                    _, _, event = self.event_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                self._process_event(event)
                self.event_queue.task_done()
                self.processed_count += 1

            except Exception as e:
                ErrorHandler.log_error(e, "Error in event processing thread")

    def _process_event(self, event: Event) -> bool:
        """Process a single event

        Args:
            event: The event to process

        Returns:
            True if any handlers processed the event, False otherwise
        """
        start_time = time.time()

        try:
            # Find handlers more efficiently
            matching_handlers = []

            # Try to find handlers by type first (most specific)
            type_handler_ids = self.handlers_by_type.get(event.type, [])
            for handler_id in type_handler_ids:
                handler = self.handlers.get(handler_id)
                if handler and handler.can_handle(event):
                    matching_handlers.append(handler)

            # Find handlers by source if there's no type-specific handlers
            if not matching_handlers:
                source_handler_ids = self.handlers_by_source.get(event.source, [])
                for handler_id in source_handler_ids:
                    handler = self.handlers.get(handler_id)
                    if handler and handler.can_handle(event):
                        matching_handlers.append(handler)

            # If still no handlers, check all handlers
            if (
                not matching_handlers
                and event.priority.value >= EventPriority.HIGH.value
            ):
                for handler in self.handlers.values():
                    if handler.can_handle(event):
                        matching_handlers.append(handler)

            # Sort handlers by priority (highest first)
            matching_handlers.sort(key=lambda h: h.min_priority.value, reverse=True)

            # Call each handler
            handler_called = False
            for handler in matching_handlers:
                try:
                    if handler.handle(event):
                        handler_called = True
                except Exception as e:
                    ErrorHandler.log_error(e, f"Error in handler {handler.id}")

            # Log if no handlers found for high priority events
            if (
                not matching_handlers
                and event.priority.value >= EventPriority.HIGH.value
            ):
                logger.warning(f"No handlers for high-priority event: {event}")

            # Update processing time statistics
            elapsed = time.time() - start_time
            self.processing_times.append(elapsed)
            if len(self.processing_times) > self.max_processing_times:
                self.processing_times = self.processing_times[
                    -self.max_processing_times :
                ]

            return handler_called

        except Exception as e:
            ErrorHandler.log_error(e, f"Error processing event: {event}")
            return False

    def get_history(
        self,
        event_types: Optional[List[EventType]] = None,
        sources: Optional[List[str]] = None,
        min_priority: Optional[EventPriority] = None,
        count: int = 10,
    ) -> List[Event]:
        """Get event history filtered by type, source, and priority

        Args:
            event_types: List of event types to include (None = all)
            sources: List of sources to include (None = all)
            min_priority: Minimum priority level (None = all)
            count: Maximum number of events to return

        Returns:
            List of events
        """
        filtered = self.history.copy()

        # Apply filters
        if event_types:
            filtered = [e for e in filtered if e.type in event_types]

        if sources:
            filtered = [e for e in filtered if e.source in sources]

        if min_priority:
            filtered = [e for e in filtered if e.priority.value >= min_priority.value]

        return filtered[-count:]

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about event processing

        Returns:
            Dict with statistics
        """
        return {
            "processed_count": self.processed_count,
            "dropped_count": self.dropped_count,
            "queue_size": self.event_queue.qsize(),
            "queue_high_water_mark": self.queue_high_water_mark,
            "handler_count": len(self.handlers),
            "history_size": len(self.history),
            "uptime": time.time() - self.start_time,
            "avg_processing_time": sum(self.processing_times)
            / len(self.processing_times)
            if self.processing_times
            else 0,
            "max_processing_time": max(self.processing_times)
            if self.processing_times
            else 0,
            "handlers_by_type": {
                etype.name: len(hids) for etype, hids in self.handlers_by_type.items()
            },
            "workers": self.worker_count,
        }

    def clear_history(self):
        """Clear event history"""
        self.history = []


# Singleton instance (optional usage)
event_bus = EventBus()


# Helper functions for common operations
def register_animation_handler(
    callback: Callable[[Event], None],
    min_priority: EventPriority = EventPriority.NORMAL,
) -> str:
    """Register a handler for animation change events

    Args:
        callback: Function to call when animation event is processed
        min_priority: Minimum priority level to handle

    Returns:
        Handler ID
    """
    handler = EventHandler(
        callback=callback,
        event_types=[EventType.ANIMATION_CHANGE],
        min_priority=min_priority,
    )
    return event_bus.register_handler(handler)


def trigger_animation_change(
    animation: str,
    priority: EventPriority = EventPriority.NORMAL,
    source: str = "system",
    immediate: bool = False,
) -> bool:
    """Trigger an animation change event

    Args:
        animation: Animation state to change to
        priority: Event priority
        source: Source of the event
        immediate: If True, process event immediately

    Returns:
        True if event was posted/processed, False otherwise
    """
    event = Event(
        event_type=EventType.ANIMATION_CHANGE,
        data={"animation": animation},
        priority=priority,
        source=source,
    )

    if immediate:
        return event_bus.post_event_immediate(event)
    else:
        return event_bus.post_event(event)


def register_settings_handler(
    callback: Callable[[Event], None],
    min_priority: EventPriority = EventPriority.NORMAL,
) -> str:
    """Register a handler for settings change events

    Args:
        callback: Function to call when settings change event is processed
        min_priority: Minimum priority level to handle

    Returns:
        Handler ID
    """
    handler = EventHandler(
        callback=callback,
        event_types=[EventType.SETTINGS_CHANGE],
        min_priority=min_priority,
    )
    return event_bus.register_handler(handler)


def trigger_settings_change(
    section: str,
    setting: str,
    value: Any,
    priority: EventPriority = EventPriority.NORMAL,
    source: str = "system",
) -> bool:
    """Trigger a settings change event

    Args:
        section: Settings section
        setting: Setting name
        value: New value
        priority: Event priority
        source: Source of the event

    Returns:
        True if event was posted, False otherwise
    """
    event = Event(
        event_type=EventType.SETTINGS_CHANGE,
        data={"section": section, "setting": setting, "value": value},
        priority=priority,
        source=source,
    )

    return event_bus.post_event(event)
