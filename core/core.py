"""
Sabrina Core Integration System
=============================
Central orchestration system that integrates all Sabrina AI components through
a unified event-driven architecture and standardized interfaces.
"""

import logging
import time
import json
import importlib
from typing import Dict, Any, List, Optional, Callable, Type
from enum import Enum

# Import core components
from .enhanced_event_system import EnhancedEventBus, Event, EventType, EventPriority
from .state_machine import StateMachine, SabrinaState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sabrina.core")


class ComponentStatus(Enum):
    """Status of a component in the system"""

    UNINITIALIZED = 0
    INITIALIZING = 1
    READY = 2
    ERROR = 3
    PAUSED = 4
    SHUTDOWN = 5


class ServiceComponent:
    """Base class for all service components in Sabrina AI"""

    def __init__(
        self,
        name: str,
        event_bus: EnhancedEventBus,
        state_machine: StateMachine,
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
        """Get system status information"""
        component_statuses = {}

        # Avoid recursion by excluding self from component list
        for name, component in list(self.components.items()):
            if hasattr(component, "get_status") and component != self:  # Add this check
                try:
                    component_statuses[name] = component.get_status()
                except Exception as e:
                    component_statuses[name] = {"error": str(e)}

        return {
            "name": "Sabrina AI Core",
            "status": self.status.name,
            "uptime": time.time() - self.start_time,
            "state": self.state_machine.current_state.name,
            "components": component_statuses,
            "event_bus": self.event_bus.get_stats(),
            "initialized": self.initialized,
            "running": self.running,
        }

    def handle_error(self, error: Exception, context: str = ""):
        """Handle an error in this component"""
        self.status = ComponentStatus.ERROR
        self.error_message = f"{context}: {str(error)}" if context else str(error)
        self.last_error_time = time.time()

        logger.error(f"Error in component {self.name}: {self.error_message}")

        # Post error event
        if self.event_bus:
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


class SabrinaCore:
    """
    Core integration system for Sabrina AI

    This is the central orchestration point that initializes, manages, and coordinates
    all components and services through the event system and state machine.
    """

    def __init__(self, config_path: str = "config/settings.yaml"):
        """
        Initialize the Sabrina Core system

        Args:
            config_path: Path to the configuration file
        """
        self.start_time = time.time()
        self.running = False
        self.initialized = False
        self.config_path = config_path

        logger.info("Initializing Sabrina AI Core System")

        # Create core infrastructure
        self.event_bus = EnhancedEventBus(worker_count=2)
        self.state_machine = StateMachine(event_bus=self.event_bus)

        # Load configuration
        self.config = self._load_configuration()

        # Initialize component registry
        self.components: Dict[str, ServiceComponent] = {}
        self.component_dependencies = self._map_component_dependencies()

        # Set up event handlers
        self._register_core_handlers()

        # Memory system for context
        self.memory = {}
        self.context = {}

        # Initialize command registry for LLM
        self.commands = {}
        self.command_documentation = {}

        # Start event bus
        self.event_bus.start()

        # Register core as a component
        self._register_self()

    def _register_self(self):
        """Register the core system itself as a component"""
        self.components["core"] = self
        self.status = ComponentStatus.INITIALIZING
        self.name = "core"
        self.error_message = None
        self.last_error_time = None

    def _load_configuration(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            # Check for ConfigManager in project
            try:
                from utilities.config_manager import ConfigManager

                config_manager = ConfigManager(self.config_path)
                logger.info(
                    f"Loaded configuration using ConfigManager from {self.config_path}"
                )
                return config_manager.export_config("dict")
            except ImportError:
                # Fallback to direct loading
                pass

            # If not available, try direct loading
            if self.config_path.endswith(".yaml") or self.config_path.endswith(".yml"):
                import yaml

                with open(self.config_path, "r") as f:
                    config = yaml.safe_load(f)
                    logger.info(f"Loaded YAML configuration from {self.config_path}")
                    return config
            elif self.config_path.endswith(".json"):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    logger.info(f"Loaded JSON configuration from {self.config_path}")
                    return config
            else:
                logger.warning(f"Unknown configuration file format: {self.config_path}")
                return {}

        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return {}

    def _map_component_dependencies(self) -> Dict[str, List[str]]:
        """Define component dependencies for initialization order"""
        return {
            "voice": ["event_bus", "config", "core"],
            "hearing": ["event_bus", "config", "core"],
            "vision": ["event_bus", "config", "core"],
            "automation": ["event_bus", "config", "core"],
            "presence": ["event_bus", "config", "core", "voice"],
            "smart_home": ["event_bus", "config", "core", "voice"],
            "llm": ["event_bus", "config", "core", "voice"],
        }

    def _register_core_handlers(self):
        """Register event handlers for the core system"""
        # Create handler for state change events
        state_change_handler = self.event_bus.create_handler(
            callback=self._handle_state_change,
            event_types=[EventType.STATE_CHANGE],
            min_priority=EventPriority.LOW,
        )

        # Create handler for system errors
        error_handler = self.event_bus.create_handler(
            callback=self._handle_system_error,
            event_types=[EventType.SYSTEM_ERROR],
            min_priority=EventPriority.HIGH,
        )

        # Create handler for user commands
        command_handler = self.event_bus.create_handler(
            callback=self._handle_user_command,
            event_types=[EventType.USER_VOICE_COMMAND, EventType.USER_TEXT_COMMAND],
            min_priority=EventPriority.NORMAL,
        )

        # Register the handlers
        self.event_bus.register_handler(state_change_handler)
        self.event_bus.register_handler(error_handler)
        self.event_bus.register_handler(command_handler)

    def _handle_state_change(self, event: Event):
        """Handle state change events"""
        new_state = event.get("new_state")
        previous_state = event.get("previous_state")

        logger.debug(f"State change: {previous_state} -> {new_state}")

        # Check for specific state transitions that need special handling
        if new_state == SabrinaState.ERROR.name:
            # System entered error state
            error_info = event.get("context", {}).get("error_info", {})
            logger.error(f"System entered ERROR state: {error_info}")

        elif (
            new_state == SabrinaState.READY.name
            and previous_state == SabrinaState.INITIALIZING.name
        ):
            # System finished initialization
            if not self.initialized:
                self.initialized = True
                logger.info("Sabrina AI Core System initialization complete")

                # Post system ready event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.SYSTEM_STARTUP,
                        data={"startup_time": time.time() - self.start_time},
                        priority=EventPriority.NORMAL,
                        source="core",
                    )
                )

    def _handle_system_error(self, event: Event):
        """Handle system error events"""
        component = event.get("component", "unknown")
        error = event.get("error", "Unknown error")

        logger.error(f"System error in component {component}: {error}")

        # Check if this is a critical error
        is_critical = event.priority == EventPriority.CRITICAL

        if is_critical:
            # For critical errors, transition to ERROR state
            # Add missing context info for the transition
            self.state_machine.transition_to(
                SabrinaState.ERROR,
                {
                    "critical_error": True,
                    "error_info": {"component": component, "message": error},
                },
            )

    def _handle_user_command(self, event: Event):
        """Handle user command events (voice or text)"""
        command = event.get("command", "")

        if not command:
            logger.warning("Received empty user command")
            return

        # Determine command source (voice or text)
        is_voice = event.event_type == EventType.USER_VOICE_COMMAND

        logger.info(f"Received {'voice' if is_voice else 'text'} command: {command}")

        # Transition to processing state
        self.state_machine.transition_to(
            SabrinaState.PROCESSING, {"command": command, "is_voice_command": is_voice}
        )

        # Process the command - in a production system, this would involve
        # sending to an LLM for understanding, then routing to the appropriate
        # component or action
        self.process_command(command, is_voice)

    def process_command(self, command: str, is_voice: bool = False):
        """
        Process a user command (this is where LLM integration would happen)

        Args:
            command: User command text
            is_voice: Whether the command came from voice input
        """
        # This is a placeholder implementation that would be replaced with actual LLM integration
        response = f"Processing command: {command}"

        # For demonstration, simulate different responses based on command keywords
        if "hello" in command.lower():
            response = "Hello! How can I help you today?"
        elif "time" in command.lower():
            import datetime

            now = datetime.datetime.now()
            response = f"The current time is {now.strftime('%I:%M %p')}"
        elif "weather" in command.lower():
            response = "I'm sorry, I don't have access to weather information yet."

        # Generate response
        self.state_machine.transition_to(
            SabrinaState.RESPONDING, {"response": response}
        )

        # If voice command, speak the response
        if is_voice and "voice" in self.components:
            # Transition to speaking state
            self.state_machine.transition_to(SabrinaState.SPEAKING)

            # Create voice event
            voice_event = Event(
                event_type=EventType.SPEECH_STARTED,
                data={"text": response},
                priority=EventPriority.NORMAL,
                source="core",
            )

            # Post to event bus for voice service to handle
            self.event_bus.post_event(voice_event)
        else:
            # Just return to ready state
            self.state_machine.transition_to(SabrinaState.READY)

    def initialize_components(self):
        """Initialize all components in dependency order"""
        # First, create instances of the required components
        self._create_component_instances()

        # Get initialization order based on dependencies
        init_order = self._get_initialization_order()

        # Initialize in proper order
        for component_name in init_order:
            if component_name in self.components and component_name != "core":
                logger.info(f"Initializing component: {component_name}")

                try:
                    component = self.components[component_name]
                    success = component.initialize()

                    if success:
                        logger.info(
                            f"Component {component_name} initialized successfully"
                        )
                    else:
                        logger.error(
                            f"Component {component_name} initialization failed"
                        )

                        # Post error event
                        self.event_bus.post_event(
                            Event(
                                event_type=EventType.SYSTEM_ERROR,
                                data={
                                    "component": component_name,
                                    "error": "Initialization failed",
                                },
                                priority=EventPriority.HIGH,
                                source="core",
                            )
                        )

                except Exception as e:
                    logger.error(
                        f"Error initializing component {component_name}: {str(e)}"
                    )

                    # Post error event
                    self.event_bus.post_event(
                        Event(
                            event_type=EventType.SYSTEM_ERROR,
                            data={"component": component_name, "error": str(e)},
                            priority=EventPriority.HIGH,
                            source="core",
                        )
                    )

        # Update core status
        self.status = ComponentStatus.READY

        # Transition to READY state
        self.state_machine.transition_to(SabrinaState.READY)

    def get_status(self) -> Dict[str, Any]:
        """Get system status information"""
        component_statuses = {}

        # Avoid recursion by excluding self from component list
        for name, component in self.components.items():
            if hasattr(component, "get_status") and component != self:
                try:
                    component_statuses[name] = component.get_status()
                except Exception as e:
                    component_statuses[name] = {"error": str(e)}

        return {
            "name": "Sabrina AI Core",
            "status": self.status.name,
            "uptime": time.time() - self.start_time,
            "state": self.state_machine.current_state.name,
            "components": component_statuses,
            "event_bus": self.event_bus.get_stats(),
            "initialized": self.initialized,
            "running": self.running,
        }

    def _create_component_instances(self):
        """Create instances of all enabled components"""
        # Check which components are enabled in the configuration
        core_config = self.config.get("core", {})
        enabled_components = core_config.get(
            "enabled_components",
            ["voice", "hearing", "vision", "automation", "presence"],
        )

        for component_name in enabled_components:
            # Skip if already initialized
            if component_name in self.components:
                continue

            # Get component configuration
            component_config = self.config.get(component_name, {})

            # Skip if explicitly disabled
            if (
                isinstance(component_config, dict)
                and component_config.get("enabled", True) is False
            ):
                logger.info(f"Component {component_name} is disabled in configuration")
                continue

            # Try to load the component class
            component_class = self._load_component_class(component_name)

            if component_class:
                try:
                    # Create component instance
                    component = component_class(
                        name=component_name,
                        event_bus=self.event_bus,
                        state_machine=self.state_machine,
                        config=component_config,
                    )

                    # Add to components dictionary
                    self.components[component_name] = component
                    logger.info(f"Created component instance: {component_name}")

                except Exception as e:
                    logger.error(f"Error creating component {component_name}: {str(e)}")
            else:
                logger.warning(f"Component class not found for: {component_name}")

    def _load_component_class(
        self, component_name: str
    ) -> Optional[Type[ServiceComponent]]:
        """
        Load a component class by name

        Args:
            component_name: Name of the component to load

        Returns:
            Component class or None if not found
        """
        # Map of component names to their expected class paths
        component_classes = {
            "voice": "services.voice.VoiceService",
            "hearing": "services.hearing.HearingService",
            "vision": "services.vision.VisionService",
            "automation": "services.automation.AutomationService",
            "presence": "services.presence.PresenceService",
            "smart_home": "services.smart_home.SmartHomeService",
        }

        if component_name not in component_classes:
            logger.warning(f"Unknown component name: {component_name}")
            return None

        class_path = component_classes[component_name]
        module_path, class_name = class_path.rsplit(".", 1)

        try:
            # Try to import the module
            module = importlib.import_module(module_path)

            # Get the class
            component_class = getattr(module, class_name)

            # Verify it's a subclass of ServiceComponent
            if not issubclass(component_class, ServiceComponent):
                logger.warning(
                    f"Component class {class_name} is not a ServiceComponent subclass"
                )
                return None

            return component_class

        except ImportError:
            logger.warning(f"Could not import module: {module_path}")
            return None
        except AttributeError:
            logger.warning(f"Class {class_name} not found in module {module_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading component class {class_path}: {str(e)}")
            return None

    def _get_initialization_order(self) -> List[str]:
        """
        Determine the order to initialize components based on dependencies

        Returns:
            List of component names in initialization order
        """
        # Start with core infrastructure components
        order = ["core"]

        # Track which components have been added to the order
        added = set(order)

        # Continue until all components are added
        remaining = set(self.components.keys()) - added

        while remaining:
            # Find components whose dependencies are all satisfied
            added_in_this_iteration = False

            for component_name in list(remaining):
                # Skip if already added
                if component_name in added:
                    continue

                # Get dependencies
                dependencies = self.component_dependencies.get(component_name, [])

                # Check if all dependencies are satisfied
                if all(
                    dep in added or dep not in self.components for dep in dependencies
                ):
                    # Add to order
                    order.append(component_name)
                    added.add(component_name)
                    remaining.remove(component_name)
                    added_in_this_iteration = True

            # Check for circular dependencies
            if not added_in_this_iteration and remaining:
                logger.warning(
                    f"Circular dependencies detected for components: {remaining}"
                )
                # Add remaining components in alphabetical order to ensure consistent behavior
                for name in sorted(list(remaining)):
                    order.append(name)
                break

        return order

    def run(self):
        """Run the Sabrina AI Core System"""
        if self.running:
            logger.warning("Sabrina AI Core System is already running")
            return

        logger.info("Starting Sabrina AI Core System")
        self.running = True

        try:
            # Initialize components
            self.initialize_components()

            # Main loop
            while self.running:
                try:
                    # Check for state timeouts
                    if self.state_machine.is_state_expired():
                        current_state = self.state_machine.current_state
                        logger.debug(f"State {current_state.name} has expired")

                        # Handle specific state timeouts
                        if current_state == SabrinaState.LISTENING:
                            # If listening timed out, go back to ready
                            self.state_machine.transition_to(SabrinaState.READY)
                        elif current_state == SabrinaState.WAITING:
                            # If waiting timed out, go back to ready
                            self.state_machine.transition_to(
                                SabrinaState.READY, {"timeout": True}
                            )

                    # Process any tasks in the current state
                    self._process_current_state()

                    # Sleep to avoid busy loop
                    time.sleep(0.1)

                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt")
                    self.shutdown()
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {str(e)}")

                    # Transition to error state
                    self.state_machine.transition_to(
                        SabrinaState.ERROR,
                        {"error_info": {"message": str(e), "source": "main_loop"}},
                    )

                    # Continue running, but give some time for error handling
                    time.sleep(1)

        except Exception as e:
            logger.critical(f"Critical error in Sabrina AI Core: {str(e)}")

        finally:
            # Ensure clean shutdown
            if self.running:
                self.shutdown()

    def _process_current_state(self):
        """Process tasks based on the current state"""
        current_state = self.state_machine.current_state

        # State-specific processing
        if current_state == SabrinaState.MONITORING:
            # When in monitoring state, periodically check for conditions
            self._process_monitoring_state()
        elif current_state == SabrinaState.EXECUTING_TASK:
            # Check task progress
            self._process_task_execution_state()

    def _process_monitoring_state(self):
        """Process tasks in the monitoring state"""
        # This would trigger periodic screen captures, audio monitoring, etc.
        pass

    def _process_task_execution_state(self):
        """Process tasks in the task execution state"""
        # Check task progress and update state accordingly
        task_info = self.state_machine.context.get("task_info", {})
        task_id = task_info.get("id")

        if task_id:
            # Logic to check task status would go here
            pass

    def shutdown(self):
        """Shut down the Sabrina AI Core System"""
        logger.info("Shutting down Sabrina AI Core System")

        # Transition to shutting down state
        self.state_machine.transition_to(SabrinaState.SHUTTING_DOWN)

        # Stop running
        self.running = False

        # Shutdown components in reverse initialization order
        component_names = list(self.components.keys())
        component_names.remove("core")  # Remove core (we're shutting it down last)
        component_names.reverse()

        for component_name in component_names:
            logger.info(f"Shutting down component: {component_name}")

            try:
                component = self.components[component_name]
                component.shutdown()
            except Exception as e:
                logger.error(
                    f"Error shutting down component {component_name}: {str(e)}"
                )

        # Stop event bus
        logger.info("Stopping event bus")
        self.event_bus.stop()

        logger.info("Sabrina AI Core System shutdown complete")

    # Command handling for LLM integration
    def register_command(
        self,
        command_name: str,
        handler: Callable,
        description: str,
        parameters: Dict[str, Any] = None,
        examples: List[str] = None,
    ):
        """
        Register a command that can be called by the LLM

        Args:
            command_name: Name of the command
            handler: Function to handle the command
            description: Description of what the command does
            parameters: Description of command parameters
            examples: Example usages of the command
        """
        self.commands[command_name] = handler

        # Store documentation
        self.command_documentation[command_name] = {
            "description": description,
            "parameters": parameters or {},
            "examples": examples or [],
        }

        logger.info(f"Registered command: {command_name}")

    def execute_command(self, command_name: str, **kwargs) -> Any:
        """
        Execute a registered command

        Args:
            command_name: Name of the command to execute
            **kwargs: Arguments to pass to the command handler

        Returns:
            The result of the command or None if command not found
        """
        if command_name not in self.commands:
            logger.warning(f"Command not found: {command_name}")
            return None

        try:
            handler = self.commands[command_name]
            return handler(**kwargs)
        except Exception as e:
            logger.error(f"Error executing command {command_name}: {str(e)}")
            return None

    def get_command_documentation(self) -> Dict[str, Any]:
        """
        Get documentation for all registered commands

        Returns:
            Dictionary of command documentation
        """
        return self.command_documentation
