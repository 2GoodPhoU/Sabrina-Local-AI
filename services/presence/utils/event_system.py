"""
Enhanced Event System for Sabrina AI
===================================
A robust event-driven communication framework that connects all components
with standardized event types, priorities, and error handling.
"""

import logging
import queue
import threading
import time
import uuid
from enum import Enum, auto
from typing import Dict, List, Callable, Any, Optional, Union
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sabrina.event_system")


class EventType(Enum):
    """Standardized event types for the Sabrina AI system"""

    # System events
    SYSTEM_STARTUP = auto()
    SYSTEM_SHUTDOWN = auto()
    SYSTEM_ERROR = auto()
    STATE_CHANGE = auto()

    # User interaction events
    USER_VOICE_COMMAND = auto()
    USER_TEXT_COMMAND = auto()
    USER_GESTURE = auto()
    WAKE_WORD_DETECTED = auto()

    # Voice service events
    SPEECH_STARTED = auto()
    SPEECH_COMPLETED = auto()
    SPEECH_ERROR = auto()

    # Hearing service events
    LISTENING_STARTED = auto()
    LISTENING_COMPLETED = auto()
    TRANSCRIPTION_RESULT = auto()

    # Vision service events
    SCREEN_CAPTURED = auto()
    ELEMENT_DETECTED = auto()
    OCR_RESULT = auto()

    # Automation events
    AUTOMATION_STARTED = auto()
    AUTOMATION_COMPLETED = auto()
    AUTOMATION_ERROR = auto()

    # Presence events
    ANIMATION_CHANGED = auto()
    PRESENCE_INTERACTION = auto()

    # Smart home events
    DEVICE_STATUS_CHANGE = auto()
    SMART_HOME_COMMAND = auto()

    # Memory events
    MEMORY_UPDATED = auto()
    MEMORY_RETRIEVED = auto()

    # LLM events
    LLM_PROMPT_SENT = auto()
    LLM_RESPONSE_RECEIVED = auto()
    LLM_ERROR = auto()

    # Generic events
    CUSTOM = auto()


class EventPriority(Enum):
    """Priority levels for event processing"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """Enhanced event object for Sabrina AI communications"""

    # Basic event properties
    event_type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    source: str = "unknown"

    # Unique identifiers and timestamps
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    # Tracking and debugging info
    parent_event_id: Optional[str] = None
    trace_id: Optional[str] = None

    def __str__(self) -> str:
        """Create a readable string representation of the event"""
        return f"Event(type={self.event_type.name}, priority={self.priority.name}, source={self.source})"

    def get(self, key: str, default: Any = None) -> Any:
        """Safely get a value from the event data"""
        return self.data.get(key, default)

    def add_data(self, additional_data: Dict[str, Any]) -> "Event":
        """Add additional data to the event (returns self for chaining)"""
        self.data.update(additional_data)
        return self

    def create_child_event(
        self, event_type: EventType, data: Dict[str, Any] = None
    ) -> "Event":
        """Create a child event that inherits the parent's trace ID"""
        child_data = {} if data is None else data

        # Ensure we have a trace ID (use our ID if no trace exists)
        trace_id = self.trace_id or self.id

        return Event(
            event_type=event_type,
            data=child_data,
            priority=self.priority,
            source=self.source,
            parent_event_id=self.id,
            trace_id=trace_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to a dictionary for serialization/storage"""
        return {
            "id": self.id,
            "type": self.event_type.name,
            "priority": self.priority.name,
            "source": self.source,
            "timestamp": self.timestamp,
            "data": self.data,
            "parent_event_id": self.parent_event_id,
            "trace_id": self.trace_id,
        }


class EventFilter:
    """Filter for matching events based on type, source, and other attributes"""

    def __init__(
        self,
        event_types: Optional[List[EventType]] = None,
        sources: Optional[List[str]] = None,
        min_priority: EventPriority = EventPriority.LOW,
        data_filters: Optional[Dict[str, Any]] = None,
    ):
        """Initialize an event filter with flexible matching criteria"""
        self.event_types = event_types
        self.sources = sources
        self.min_priority = min_priority
        self.data_filters = data_filters or {}

    def matches(self, event: Event) -> bool:
        """Check if an event matches this filter"""
        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            return False

        # Check source
        if self.sources and event.source not in self.sources:
            return False

        # Check priority
        if event.priority.value < self.min_priority.value:
            return False

        # Check data filters (if any)
        for key, value in self.data_filters.items():
            if event.data.get(key) != value:
                return False

        return True


class EventHandler:
    """Enhanced event handler with robust filtering and error recovery"""

    def __init__(
        self,
        callback: Callable[[Event], None],
        filter: EventFilter,
        id: Optional[str] = None,
    ):
        """Initialize an event handler with a callback and filter"""
        self.callback = callback
        self.filter = filter
        self.id = id or str(uuid.uuid4())

        # Tracking statistics
        self.call_count = 0
        self.error_count = 0
        self.last_called_at = 0
        self.last_error_at = 0
        self.total_execution_time = 0

    def can_handle(self, event: Event) -> bool:
        """Check if this handler can process the event"""
        return self.filter.matches(event)

    def handle(self, event: Event) -> bool:
        """Process an event with timing and error handling"""
        try:
            start_time = time.time()
            self.callback(event)
            execution_time = time.time() - start_time

            # Update statistics
            self.call_count += 1
            self.last_called_at = time.time()
            self.total_execution_time += execution_time

            return True
        except Exception as e:
            # Update error statistics
            self.error_count += 1
            self.last_error_at = time.time()

            # Log the error
            logger.error(f"Error in event handler {self.id}: {str(e)}", exc_info=True)
            return False


class EnhancedEventBus:
    """Enhanced event bus with improved reliability, performance, and monitoring"""

    def __init__(self, worker_count: int = 2, max_queue_size: int = 1000):
        """Initialize the enhanced event bus"""
        # Handlers and indexes
        self.handlers: Dict[str, EventHandler] = {}
        self.handlers_by_type: Dict[EventType, List[str]] = {}

        # Event queue and processing
        self.event_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.workers: List[threading.Thread] = []
        self.worker_count = worker_count
        self.running = False

        # Statistics
        self.processed_count = 0
        self.dropped_count = 0
        self.start_time = 0
        self.recent_events: List[Event] = []
        self.max_recent_events = 100

        # Performance monitoring
        self.processing_times = []
        self.max_processing_times = 100

        # Durability - store unprocessed events
        self.unprocessed_events = []

    def start(self):
        """Start the event processing workers"""
        if self.running:
            logger.warning("Event bus already running")
            return

        self.running = True
        self.start_time = time.time()

        # Start worker threads
        for i in range(self.worker_count):
            worker = threading.Thread(
                target=self._process_events, name=f"EventBus-Worker-{i}", daemon=True
            )
            worker.start()
            self.workers.append(worker)

        logger.info(f"Enhanced event bus started with {self.worker_count} workers")

    def stop(self, timeout: float = 2.0, save_unprocessed: bool = True):
        """Stop the event processing workers"""
        if not self.running:
            return

        self.running = False

        # Save unprocessed events if requested
        if save_unprocessed:
            try:
                # Copy all unprocessed events from the queue
                while not self.event_queue.empty():
                    try:
                        _, _, event = self.event_queue.get(block=False)
                        self.unprocessed_events.append(event)
                    except queue.Empty:
                        break
            except Exception as e:
                logger.error(f"Error saving unprocessed events: {str(e)}")

        # Wait for workers to finish with timeout
        for worker in self.workers:
            worker.join(timeout=timeout)

        self.workers = []
        logger.info("Enhanced event bus stopped")

    def register_handler(self, handler: EventHandler) -> str:
        """Register an event handler"""
        # Add to main handlers dictionary
        self.handlers[handler.id] = handler

        # Add to type index for faster lookups
        if handler.filter.event_types:
            for event_type in handler.filter.event_types:
                if event_type not in self.handlers_by_type:
                    self.handlers_by_type[event_type] = []

                if handler.id not in self.handlers_by_type[event_type]:
                    self.handlers_by_type[event_type].append(handler.id)

        logger.debug(f"Registered event handler: {handler.id}")
        return handler.id

    def create_handler(
        self,
        callback: Callable[[Event], None],
        event_types: Optional[Union[EventType, List[EventType]]] = None,
        sources: Optional[List[str]] = None,
        min_priority: EventPriority = EventPriority.LOW,
        data_filters: Optional[Dict[str, Any]] = None,
    ) -> EventHandler:
        """Create an event handler with the specified parameters"""
        # Convert single event type to list if needed
        if event_types is not None and not isinstance(event_types, list):
            event_types = [event_types]

        # Create filter
        filter = EventFilter(event_types, sources, min_priority, data_filters)

        # Create handler
        return EventHandler(callback, filter)

    def unregister_handler(self, handler_id: str) -> bool:
        """Unregister an event handler"""
        if handler_id not in self.handlers:
            logger.warning(f"Handler not found: {handler_id}")
            return False

        handler = self.handlers[handler_id]

        # Remove from main dictionary
        del self.handlers[handler_id]

        # Remove from type index
        if handler.filter.event_types:
            for event_type in handler.filter.event_types:
                if (
                    event_type in self.handlers_by_type
                    and handler_id in self.handlers_by_type[event_type]
                ):
                    self.handlers_by_type[event_type].remove(handler_id)

        logger.debug(f"Unregistered event handler: {handler_id}")
        return True

    def post_event(self, event: Event) -> bool:
        """Post an event to the queue for asynchronous processing"""
        if not self.running:
            logger.warning("Event bus not running, cannot post event")
            return False

        try:
            # Add to queue with priority (negative value so higher priorities come first)
            priority_tuple = (-event.priority.value, event.timestamp, event)
            self.event_queue.put(priority_tuple, block=False)

            # Add to recent events
            self._add_to_recent_events(event)

            logger.debug(f"Posted event: {event}")
            return True
        except queue.Full:
            self.dropped_count += 1
            logger.warning(f"Event queue full, dropped event: {event}")
            return False

    def post_event_immediate(self, event: Event) -> bool:
        """Process an event immediately (synchronously)"""
        # Add to recent events
        self._add_to_recent_events(event)

        # Process the event
        return self._process_event(event)

    def _add_to_recent_events(self, event: Event):
        """Add event to recent events list with size limit"""
        self.recent_events.append(event)

        # Trim list if needed
        if len(self.recent_events) > self.max_recent_events:
            self.recent_events = self.recent_events[-self.max_recent_events :]

    def _process_events(self):
        """Worker thread function to process events from the queue"""
        while self.running:
            try:
                # Get event with timeout
                try:
                    priority, timestamp, event = self.event_queue.get(timeout=0.1)
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

    def _process_event(self, event: Event) -> bool:
        """Process a single event with handler selection and timing"""
        start_time = time.time()
        handlers_called = 0

        try:
            # Find handlers for this event efficiently
            matching_handlers = []

            # First try handlers registered for this specific event type
            if event.event_type in self.handlers_by_type:
                for handler_id in self.handlers_by_type[event.event_type]:
                    handler = self.handlers.get(handler_id)
                    if handler and handler.can_handle(event):
                        matching_handlers.append(handler)

            # For high priority events, check all handlers if we found no matches
            if (
                not matching_handlers
                and event.priority.value >= EventPriority.HIGH.value
            ):
                for handler in self.handlers.values():
                    if handler.can_handle(event):
                        matching_handlers.append(handler)

            # Call all matching handlers
            for handler in matching_handlers:
                if handler.handle(event):
                    handlers_called += 1

            # Log a warning for high priority events with no handlers
            if (
                not matching_handlers
                and event.priority.value >= EventPriority.HIGH.value
            ):
                logger.warning(f"No handlers for high-priority event: {event}")

            # Update processing time statistics
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)

            # Trim processing times if needed
            if len(self.processing_times) > self.max_processing_times:
                self.processing_times = self.processing_times[
                    -self.max_processing_times :
                ]

            return handlers_called > 0

        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times
            else 0
        )

        max_processing_time = max(self.processing_times) if self.processing_times else 0

        return {
            "processed_count": self.processed_count,
            "dropped_count": self.dropped_count,
            "queue_size": self.event_queue.qsize() if self.running else 0,
            "handler_count": len(self.handlers),
            "uptime": time.time() - self.start_time if self.running else 0,
            "avg_processing_time": avg_processing_time,
            "max_processing_time": max_processing_time,
            "event_types": {
                event_type.name: len(handlers)
                for event_type, handlers in self.handlers_by_type.items()
            },
            "worker_count": len(self.workers),
            "recent_event_count": len(self.recent_events),
        }

    def get_recent_events(self, count: int = 10) -> List[Event]:
        """Get recent events from the history"""
        return self.recent_events[-count:]
