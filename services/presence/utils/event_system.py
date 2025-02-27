# Event system for Sabrina's Presence System
import threading
import queue
import time
import uuid
from enum import Enum, auto
from .error_handling import ErrorHandler, logger  # Changed to relative import
from typing import Dict, List, Callable, Any, Optional

class EventType(Enum):
    """Types of events that can be raised in the Presence System"""
    ANIMATION_CHANGE = auto()       # Animation state change
    SYSTEM_STATE = auto()           # System state events (startup, shutdown, etc.)
    USER_INTERACTION = auto()       # User interactions with presence
    VOICE_ACTIVITY = auto()         # Voice input/output activity
    SETTINGS_CHANGE = auto()        # Settings or configuration changes
    EXTERNAL_COMMAND = auto()       # Commands from external systems
    ERROR = auto()                  # Error notifications
    CUSTOM = auto()                 # Custom event types

class EventPriority(Enum):
    """Priority levels for events"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

class Event:
    """Represents an event in the system"""
    
    def __init__(
        self,
        event_type: EventType,
        data: Dict[str, Any] = None,
        priority: EventPriority = EventPriority.NORMAL,
        source: str = "system"
    ):
        """Initialize a new event
        
        Args:
            event_type: Type of the event
            data: Dictionary with event data
            priority: Event priority
            source: Source of the event
        """
        self.id = str(uuid.uuid4())
        self.type = event_type
        self.data = data or {}
        self.priority = priority
        self.source = source
        self.timestamp = time.time()
    
    def __str__(self):
        return f"Event(type={self.type.name}, priority={self.priority.name}, source={self.source})"

class EventHandler:
    """Event handler callback with filtering capability"""
    
    def __init__(
        self,
        callback: Callable[[Event], None],
        event_types: List[EventType] = None,
        min_priority: EventPriority = EventPriority.LOW,
        sources: List[str] = None
    ):
        """Initialize event handler
        
        Args:
            callback: Function to call when event is processed
            event_types: List of event types to handle (None = all)
            min_priority: Minimum priority level to handle
            sources: List of sources to accept events from (None = all)
        """
        self.callback = callback
        self.event_types = event_types
        self.min_priority = min_priority
        self.sources = sources
        self.id = str(uuid.uuid4())
    
    def can_handle(self, event: Event) -> bool:
        """Check if this handler can handle the given event
        
        Args:
            event: Event to check
            
        Returns:
            True if handler can handle event, False otherwise
        """
        # Check event type
        if self.event_types is not None and event.type not in self.event_types:
            return False
        
        # Check priority
        if event.priority.value < self.min_priority.value:
            return False
        
        # Check source
        if self.sources is not None and event.source not in self.sources:
            return False
        
        return True
    
    def handle(self, event: Event) -> None:
        """Handle event by calling the callback
        
        Args:
            event: Event to handle
        """
        try:
            self.callback(event)
        except Exception as e:
            ErrorHandler.log_error(e, f"Error in event handler {self.id}")

class EventBus:
    """Central event bus for the Presence System"""
    
    def __init__(self):
        """Initialize the event bus"""
        self.handlers: Dict[str, EventHandler] = {}  # Handler ID -> Handler
        self.event_queue = queue.PriorityQueue()  # Queue of events
        self.running = False
        self.thread = None
        self.history: List[Event] = []  # Event history
        self.max_history = 100  # Maximum number of events to keep in history
    
    def start(self):
        """Start the event processing thread"""
        if self.running:
            logger.warning("Event bus already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._process_events, daemon=True)
        self.thread.start()
        logger.info("Event bus started")
    
    def stop(self):
        """Stop the event processing thread"""
        if not self.running:
            logger.warning("Event bus not running")
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info("Event bus stopped")
    
    def register_handler(self, handler: EventHandler) -> str:
        """Register a new event handler
        
        Args:
            handler: The event handler to register
            
        Returns:
            Handler ID
        """
        self.handlers[handler.id] = handler
        logger.debug(f"Registered event handler: {handler.id}")
        return handler.id
    
    # Fixed method to allow proper handler registration
    def create_event_handler(self, event_types, callback, min_priority=EventPriority.LOW, sources=None):
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
            del self.handlers[handler_id]
            logger.debug(f"Unregistered event handler: {handler_id}")
            return True
        
        logger.warning(f"Handler not found: {handler_id}")
        return False
    
    def post_event(self, event: Event):
        """Post an event to the event bus
        
        Args:
            event: The event to post
        """
        # Add to queue with priority
        self.event_queue.put((-event.priority.value, event.timestamp, event))
        logger.debug(f"Posted event: {event}")
        
        # Add to history
        self.history.append(event)
        # Trim history if necessary
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def post_event_immediate(self, event: Event):
        """Post and process an event immediately (blocking)
        
        Args:
            event: The event to post and process
        """
        logger.debug(f"Processing immediate event: {event}")
        self._process_event(event)
        
        # Add to history
        self.history.append(event)
        # Trim history if necessary
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def _process_events(self):
        """Process events from the queue (run in separate thread)"""
        while self.running:
            try:
                # Get event from queue with 0.1s timeout
                try:
                    _, _, event = self.event_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                self._process_event(event)
                self.event_queue.task_done()
            except Exception as e:
                ErrorHandler.log_error(e, "Error in event processing thread")
    
    def _process_event(self, event: Event):
        """Process a single event
        
        Args:
            event: The event to process
        """
        # Find handlers that can handle this event
        matching_handlers = [h for h in self.handlers.values() if h.can_handle(event)]
        
        # Call each handler
        for handler in matching_handlers:
            try:
                handler.handle(event)
            except Exception as e:
                ErrorHandler.log_error(e, f"Error in handler {handler.id}")
        
        if not matching_handlers:
            logger.debug(f"No handlers for event: {event}")
    
    def get_history(self, 
                   event_types: Optional[List[EventType]] = None, 
                   count: int = 10) -> List[Event]:
        """Get event history filtered by type
        
        Args:
            event_types: List of event types to include (None = all)
            count: Maximum number of events to return
            
        Returns:
            List of events
        """
        if event_types is None:
            filtered = self.history
        else:
            filtered = [e for e in self.history if e.type in event_types]
        
        return filtered[-count:]

# Singleton instance
event_bus = EventBus()

# Helper functions for common operations
def register_animation_handler(callback: Callable[[Event], None], 
                              min_priority: EventPriority = EventPriority.NORMAL) -> str:
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
        min_priority=min_priority
    )
    return event_bus.register_handler(handler)

def trigger_animation_change(animation: str, 
                            priority: EventPriority = EventPriority.NORMAL,
                            source: str = "system",
                            immediate: bool = False):
    """Trigger an animation change event
    
    Args:
        animation: Animation state to change to
        priority: Event priority
        source: Source of the event
        immediate: If True, process event immediately
    """
    event = Event(
        event_type=EventType.ANIMATION_CHANGE,
        data={"animation": animation},
        priority=priority,
        source=source
    )
    
    if immediate:
        event_bus.post_event_immediate(event)
    else:
        event_bus.post_event(event)