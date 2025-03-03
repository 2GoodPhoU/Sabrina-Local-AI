"""
Event System for Sabrina AI
===========================
This module provides a robust, asynchronous event system for communication
between different components of Sabrina AI with prioritization, filtering,
and error handling.
"""

import time
import queue
import threading
import uuid
import logging
import traceback
from typing import Dict, List, Callable, Any, Optional, Union
from enum import Enum, auto
from dataclasses import dataclass, field

# Set up logging
logger = logging.getLogger("event_system")


class EventType(Enum):
    # System events
    SYSTEM = auto()
    SYSTEM_STARTUP = auto()
    SYSTEM_SHUTDOWN = auto()
    SYSTEM_ERROR = auto()

    # User interaction events
    USER_INPUT = auto()
    USER_VOICE_COMMAND = auto()
    USER_TEXT_COMMAND = auto()

    # Vision events
    VISION = auto()
    SCREEN_CAPTURED = auto()
    OCR_RESULT = auto()
    ELEMENT_DETECTED = auto()

    # Automation events
    AUTOMATION = auto()
    AUTOMATION_STARTED = auto()
    AUTOMATION_COMPLETED = auto()
    AUTOMATION_ERROR = auto()

    # Voice events
    VOICE = auto()
    SPEECH_STARTED = auto()
    SPEECH_COMPLETED = auto()
    SPEECH_ERROR = auto()

    # Hearing events
    HEARING = auto()
    WAKE_WORD_DETECTED = auto()
    LISTENING_STARTED = auto()
    LISTENING_COMPLETED = auto()

    # State events
    STATE_CHANGE = auto()

    # Smart home events
    DEVICE_COMMAND = auto()
    DEVICE_QUERY = auto()
    DEVICE_STATE = auto()
    DEVICE_STATE_CHANGED = auto()
    ROUTINE_EXECUTE = auto()

    # Animation events
    ANIMATION_CHANGE = auto()

    # Custom events
    CUSTOM = auto()


class EventPriority(Enum):
    """Priority levels for event processing"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """
    Event object representing a message passed through the system

    Contains event type, data payload, source information, and priority.
    """

    event_type: Any  # Can be EventType or a custom enum
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    priority: EventPriority = EventPriority.NORMAL
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        """String representation of the event"""
        event_type_name = (
            self.event_type.name
            if isinstance(self.event_type, Enum)
            else str(self.event_type)
        )
        return f"Event(type={event_type_name}, priority={self.priority.name}, source={self.source})"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the event data"""
        return self.data.get(key, default)

    def merge_data(self, additional_data: Dict[str, Any]) -> "Event":
        """Merge additional data into the event"""
        self.data.update(additional_data)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation"""
        event_type_name = (
            self.event_type.name
            if isinstance(self.event_type, Enum)
            else str(self.event_type)
        )
        priority_name = (
            self.priority.name
            if isinstance(self.priority, Enum)
            else str(self.priority)
        )

        return {
            "id": self.id,
            "type": event_type_name,
            "priority": priority_name,
            "source": self.source,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class EventHandler:
    """
    Event handler with filtering capability

    Handles events based on type, priority, and source filters.
    """

    def __init__(
        self,
        callback: Callable[[Event], None],
        event_types: Optional[List[Any]] = None,
        min_priority: EventPriority = EventPriority.LOW,
        sources: Optional[List[str]] = None,
        id: Optional[str] = None,
    ):
        """Initialize event handler with filters"""
        self.callback = callback
        self.event_types = event_types
        self.min_priority = min_priority
        self.sources = sources
        self.id = id or str(uuid.uuid4())
        self.created_at = time.time()
        self.last_called = 0
        self.call_count = 0

    def can_handle(self, event: Event) -> bool:
        """
        Check if this handler can handle the given event

        Args:
            event: Event to check

        Returns:
            bool: True if this handler can handle the event, False otherwise
        """
        # Check event type
        if self.event_types is not None:
            if event.event_type not in self.event_types:
                return False

        # Check priority
        if event.priority.value < self.min_priority.value:
            return False

        # Check source
        if self.sources is not None:
            if event.source not in self.sources:
                return False

        return True

    def handle(self, event: Event) -> bool:
        """
        Handle an event by calling the callback

        Args:
            event: Event to handle

        Returns:
            bool: True if handled successfully, False otherwise
        """
        try:
            self.callback(event)
            self.last_called = time.time()
            self.call_count += 1
            return True
        except Exception as e:
            logger.error(f"Error in event handler {self.id}: {str(e)}")
            logger.error(traceback.format_exc())
            return False


class EventBus:
    """
    Central event bus for managing event distribution

    Features:
    - Asynchronous event processing
    - Priority-based processing
    - Event filtering
    - Error handling and recovery
    """

    def __init__(self, max_queue_size: int = 1000, worker_count: int = 1):
        """
        Initialize the event bus

        Args:
            max_queue_size: Maximum number of events in queue (default: 1000)
            worker_count: Number of worker threads (default: 1)
        """
        # Handlers storage
        self.handlers: Dict[str, EventHandler] = {}
        self.handlers_by_type: Dict[Any, List[str]] = {}

        # Event queue and processing
        self.event_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.running = False
        self.workers: List[threading.Thread] = []
        self.worker_count = worker_count

        # Statistics
        self.processed_count = 0
        self.dropped_count = 0
        self.start_time = 0
        self.history: List[Event] = []
        self.max_history = 100

        logger.info(f"Event bus initialized with {worker_count} worker(s)")

    def start(self):
        """Start event processing workers"""
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
        """
        Stop event processing

        Args:
            timeout: Timeout for worker threads to stop (default: 1.0 seconds)
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
        """
        Register an event handler

        Args:
            handler: EventHandler to register

        Returns:
            str: Handler ID
        """
        handler_id = handler.id

        # Add to main handlers dictionary
        self.handlers[handler_id] = handler

        # Add to type index for faster lookup
        if handler.event_types:
            for event_type in handler.event_types:
                if event_type not in self.handlers_by_type:
                    self.handlers_by_type[event_type] = []
                self.handlers_by_type[event_type].append(handler_id)

        logger.debug(f"Registered event handler: {handler_id}")
        return handler_id

    def unregister_handler(self, handler_id: str) -> bool:
        """
        Unregister an event handler

        Args:
            handler_id: ID of the handler to unregister

        Returns:
            bool: True if handler was unregistered, False otherwise
        """
        if handler_id not in self.handlers:
            logger.warning(f"Handler not found: {handler_id}")
            return False

        handler = self.handlers[handler_id]

        # Remove from main dictionary
        del self.handlers[handler_id]

        # Remove from type index
        if handler.event_types:
            for event_type in handler.event_types:
                if (
                    event_type in self.handlers_by_type
                    and handler_id in self.handlers_by_type[event_type]
                ):
                    self.handlers_by_type[event_type].remove(handler_id)

        logger.debug(f"Unregistered event handler: {handler_id}")
        return True

    def create_event_handler(
        self,
        event_types: Union[Any, List[Any]],
        callback: Callable[[Event], None],
        min_priority: EventPriority = EventPriority.LOW,
        sources: Optional[List[str]] = None,
    ) -> EventHandler:
        """
        Create an event handler

        Args:
            event_types: Event type or list of event types to handle
            callback: Function to call when an event is received
            min_priority: Minimum priority to handle
            sources: List of sources to handle events from

        Returns:
            EventHandler: Created event handler (not registered yet)
        """
        # Convert single event type to list
        if not isinstance(event_types, list):
            event_types = [event_types]

        return EventHandler(callback, event_types, min_priority, sources)

    def post_event(self, event: Event) -> bool:
        """
        Post an event to the event bus for asynchronous processing

        Args:
            event: Event to post

        Returns:
            bool: True if posted successfully, False otherwise
        """
        if not self.running:
            logger.warning("Event bus not running, cannot post event")
            return False

        try:
            # Add to queue with priority (negative so higher priority is processed first)
            # Use timestamp as tiebreaker for events with same priority
            self.event_queue.put(
                (-event.priority.value, event.timestamp, event), block=False
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
        """
        Post and process an event immediately (blocking)

        Args:
            event: Event to post and process

        Returns:
            bool: True if processed successfully, False otherwise
        """
        logger.debug(f"Processing immediate event: {event}")

        # Add to history
        self._add_to_history(event)

        # Process the event
        return self._process_event(event)

    def _add_to_history(self, event: Event):
        """Add event to history with size limiting"""
        self.history.append(event)

        # Trim history if needed
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

    def _process_events(self):
        """Worker thread function to process events from queue"""
        while self.running:
            try:
                # Get event from queue with timeout
                try:
                    _, _, event = self.event_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Process the event
                self._process_event(event)

                # Mark task as done
                self.event_queue.task_done()

                # Update statistics
                self.processed_count += 1

            except Exception as e:
                logger.error(f"Error in event processing thread: {str(e)}")
                logger.error(traceback.format_exc())

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

    def _process_event(self, event: Event) -> bool:
        """
        Process a single event

        Args:
            event: Event to process

        Returns:
            bool: True if any handlers processed the event, False otherwise
        """
        start_time = time.time()

        try:
            # Find handlers for this event type first (most efficient)
            matching_handlers = []

            # Get handlers that explicitly handle this event type
            if event.event_type in self.handlers_by_type:
                for handler_id in self.handlers_by_type[event.event_type]:
                    handler = self.handlers.get(handler_id)
                    if handler and handler.can_handle(event):
                        matching_handlers.append(handler)

            # If no type-specific handlers and event is high priority,
            # check all handlers (less efficient)
            if (
                not matching_handlers
                and event.priority.value >= EventPriority.HIGH.value
            ):
                for handler in self.handlers.values():
                    if handler.can_handle(event):
                        matching_handlers.append(handler)

            # Call handlers
            handler_called = False
            for handler in matching_handlers:
                if handler.handle(event):
                    handler_called = True

            # Log warning if no handlers for high priority events
            if (
                not matching_handlers
                and event.priority.value >= EventPriority.HIGH.value
            ):
                logger.warning(f"No handlers for high-priority event: {event}")

            # Debug timing for slow event processing
            elapsed = time.time() - start_time
            if elapsed > 0.1:  # More than 100ms is slow
                logger.debug(f"Slow event processing: {elapsed:.3f}s for {event}")

            return handler_called

        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get event bus statistics

        Returns:
            Dict with statistics
        """
        return {
            "processed_count": self.processed_count,
            "dropped_count": self.dropped_count,
            "queue_size": self.event_queue.qsize() if self.running else 0,
            "handler_count": len(self.handlers),
            "uptime": time.time() - self.start_time if self.running else 0,
            "handlers_by_type": {
                str(event_type): len(handlers)
                for event_type, handlers in self.handlers_by_type.items()
            },
            "running": self.running,
            "worker_count": len(self.workers),
        }

    def clear_history(self):
        """Clear event history"""
        self.history = []
