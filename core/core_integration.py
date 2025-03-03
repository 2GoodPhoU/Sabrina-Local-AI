"""
Sabrina Core Integration Components
=================================
Base classes and utilities for integrating components with the Sabrina core system.
"""

import time
import logging
from enum import Enum, auto
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sabrina.core_integration")


class ComponentStatus(Enum):
    """Status of a component in the system"""

    UNINITIALIZED = auto()
    INITIALIZING = auto()
    READY = auto()
    ERROR = auto()
    PAUSED = auto()
    SHUTDOWN = auto()


class ServiceComponent:
    """Base class for all service components in Sabrina AI"""

    def __init__(
        self,
        name: str,
        event_bus,
        state_machine,
        config: Dict[str, Any] = None,
    ):
        """
        Initialize a service component

        Args:
            name: Component name
            event_bus: Event bus for communication
            state_machine: System state machine
            config: Component configuration
        """
        self.name = name
        self.event_bus = event_bus
        self.state_machine = state_machine
        self.config = config or {}
        self.status = ComponentStatus.UNINITIALIZED
        self.error_message = None
        self.last_error_time = None
        self.start_time = time.time()
        self.handler_ids = []

        # Register basic handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register event handlers for this component"""
        # This should be overridden by subclasses
        pass

    def initialize(self) -> bool:
        """Initialize the component"""
        self.status = ComponentStatus.INITIALIZING
        return True

    def shutdown(self) -> bool:
        """Shutdown the component"""
        # Unregister event handlers
        for handler_id in self.handler_ids:
            self.event_bus.unregister_handler(handler_id)

        self.status = ComponentStatus.SHUTDOWN
        return True

    def pause(self) -> bool:
        """Pause component operations"""
        self.status = ComponentStatus.PAUSED
        return True

    def resume(self) -> bool:
        """Resume component operations"""
        if self.status == ComponentStatus.PAUSED:
            self.status = ComponentStatus.READY
            return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get component status information"""
        return {
            "name": self.name,
            "status": self.status.name,
            "uptime": time.time() - self.start_time,
            "error": self.error_message,
            "last_error_time": self.last_error_time,
            "handlers_registered": len(self.handler_ids),
        }

    def handle_error(self, error: Exception, context: str = ""):
        """Handle an error in this component"""
        self.status = ComponentStatus.ERROR
        self.error_message = f"{context}: {str(error)}" if context else str(error)
        self.last_error_time = time.time()

        logger.error(f"Error in component {self.name}: {self.error_message}")

        # Post error event
        if self.event_bus:
            try:
                from core.enhanced_event_system import Event, EventType, EventPriority

                event = Event(
                    event_type=EventType.SYSTEM_ERROR,
                    data={
                        "component": self.name,
                        "error": self.error_message,
                        "timestamp": self.last_error_time,
                    },
                    priority=EventPriority.HIGH,
                    source=self.name,
                )
                self.event_bus.post_event(event)
            except ImportError:
                logger.error(
                    "Could not import enhanced_event_system for error reporting"
                )
