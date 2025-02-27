"""
Enhanced Sabrina Core Integration System
=======================================
This module serves as the central orchestration point for Sabrina AI,
with improved component integration, event handling, and system state management.
"""

import os
import sys
import json
import time
import logging
import threading
import queue
import importlib
import re
from typing import Dict, Any, List, Optional, Callable, Tuple
from enum import Enum, auto
import traceback

# Core utilities
from utilities.config_manager import ConfigManager
from utilities.event_system import EventBus, EventType, Event, EventPriority
from utilities.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("logs/sabrina_core.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("sabrina_core")

# Define core-specific event types
class CoreEventType(Enum):
    """Events specific to the Sabrina Core system"""
    STARTUP = auto()
    SHUTDOWN = auto()
    USER_INPUT = auto()
    COMMAND_EXECUTED = auto()
    STATE_CHANGE = auto()
    MEMORY_UPDATE = auto()
    COMPONENT_STATUS = auto()

class CoreState(Enum):
    """Possible states for the Sabrina Core system"""
    INITIALIZING = auto()
    READY = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    PAUSED = auto()
    SHUTDOWN = auto()
    ERROR = auto()

class SabrinaCore:
    """
    Enhanced Sabrina AI Core Orchestration Engine
    
    This class serves as the central integration point for all Sabrina AI components,
    coordinating their interaction through a robust event system and providing
    comprehensive error handling and state management.
    
    Key improvements:
    - Modular component loading with dependency management
    - Comprehensive event-based communication
    - Enhanced state tracking and context management
    - Improved error recovery and fault tolerance
    - Dynamic command processing and routing
    """
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        """Initialize the enhanced Sabrina AI Core system"""
        self.startup_time = time.time()
        self.config_path = config_path
        
        # Set initial state
        self.current_state = CoreState.INITIALIZING
        
        logger.info("Initializing Enhanced Sabrina AI Core...")
        
        # Initialize utilities first
        self._init_utilities()
        
        # Set up state tracking
        self.state_changes = []
        self.last_state_change = time.time()
        
        # Set up command processor registry
        self.command_processors = {}
        
        # Initialize memory system
        self._init_memory()
        
        # Initialize core components
        self.components = {}
        self._init_components()
        
        # Register event handlers
        self._register_event_handlers()
        
        # Set up command processors
        self._register_command_processors()
        
        # Initialize component-specific features
        self._init_component_integrations()
        
        # Send initialization complete event
        self._change_state(CoreState.READY)
        
        # Track initialization success
        self.initialized = True
        startup_duration = time.time() - self.startup_time
        logger.info(f"Enhanced Sabrina AI Core initialized in {startup_duration:.2f} seconds")
        
        # Post startup event
        self.event_bus.post_event(
            Event(
                event_type=CoreEventType.STARTUP,
                data={
                    "startup_duration": startup_duration,
                    "components_loaded": list(self.components.keys())
                },
                source="core"
            )
        )
    
    def _init_utilities(self):
        """Initialize utility systems like configuration and event bus"""
        try:
            # Ensure required directories exist
            os.makedirs("logs", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            os.makedirs("config", exist_ok=True)
            
            # Initialize configuration manager
            logger.info(f"Loading configuration from {self.config_path}")
            self.config_manager = ConfigManager(self.config_path)
            
            # Initialize error handler
            self.error_handler = ErrorHandler(self.config_manager)
            
            # Initialize event bus
            logger.info("Initializing event bus")
            self.event_bus = EventBus()
            
            # Store core utilities in components dictionary for dependency tracking
            self.components["config_manager"] = self.config_manager
            self.components["error_handler"] = self.error_handler
            self.components["event_bus"] = self.event_bus
            
            # Start event bus
            self.event_bus.start()
            
        except Exception as e:
            logger.critical(f"Failed to initialize utilities: {str(e)}")
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to initialize core utilities") from e
    
    def _init_memory(self):
        """Initialize memory system for context and history"""
        # Setup memory paths
        self.memory_dir = "data/memory"
        os.makedirs(self.memory_dir, exist_ok=True)
        self.memory_file = os.path.join(self.memory_dir, "conversation_history.json")
        self.memory_index_file = os.path.join(self.memory_dir, "memory_index.json")
        
        # Initialize memory storage
        self.history = self._load_history()
        self.context = {}
        self.memory_index = self._load_memory_index()
        
        # Memory configuration
        memory_config = self.config_manager.get_config("memory", {})
        self.max_history_entries = memory_config.get("max_entries", 20)
        self.memory_compaction_threshold = memory_config.get("compaction_threshold", 100)
        
        # Set up conversational memory tracking
        self.conversation_id = str(int(time.time()))
        self.turn_counter = 0
        
        # System state tracking
        self.running = False
        self.paused = False
        self.critical_init_failure = False
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """Load conversation history from file"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r") as f:
                    history = json.load(f)
                logger.info(f"Loaded {len(history)} history entries from {self.memory_file}")
                return history
            return []
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to load conversation history",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.DATA
            )
            return []
    
    def _save_history(self):
        """Save conversation history to file"""
        try:
            with open(self.memory_file, "w") as f:
                json.dump(self.history, f, indent=2)
            logger.debug(f"Saved {len(self.history)} history entries to {self.memory_file}")
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to save conversation history",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.DATA
            )
    
    def _load_memory_index(self) -> Dict[str, Any]:
        """Load memory index from file"""
        try:
            if os.path.exists(self.memory_index_file):
                with open(self.memory_index_file, "r") as f:
                    index = json.load(f)
                logger.info(f"Loaded memory index with {len(index)} entries")
                return index
            return {}
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to load memory index",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.DATA
            )
            return {}
    
    def _save_memory_index(self):
        """Save memory index to file"""
        try:
            with open(self.memory_index_file, "w") as f:
                json.dump(self.memory_index, f, indent=2)
            logger.debug("Saved memory index")
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to save memory index",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.DATA
            )
    
    def _update_memory_index(self, text: str, history_index: int):
        """
        Update memory index with keywords from text
        
        Args:
            text: Text to extract keywords from
            history_index: Index in history array
        """
        try:
            # Simple keyword extraction (could be replaced with NLP in the future)
            words = text.lower().split()
            keywords = [word for word in words if len(word) > 3]  # Only keep words longer than 3 chars
            
            # Add to index
            for keyword in keywords:
                if keyword not in self.memory_index:
                    self.memory_index[keyword] = []
                
                # Only add if not already present
                if history_index not in self.memory_index[keyword]:
                    self.memory_index[keyword].append(history_index)
            
            # Only save periodically to avoid excessive writes
            if len(self.memory_index) % 10 == 0:
                self._save_memory_index()
                
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to update memory index",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.DATA
            )
    
    def update_memory(self, user_input: str, ai_response: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Update conversation memory with user input and AI response
        
        Args:
            user_input: User's input/command
            ai_response: System's response
            metadata: Optional metadata about this exchange
        """
        try:
            # Create metadata if not provided
            if metadata is None:
                metadata = {}
            
            # Add timestamp and turn information
            timestamp = time.time()
            self.turn_counter += 1
            
            # Create memory entries
            user_entry = {
                "role": "user",
                "content": user_input,
                "timestamp": timestamp,
                "turn": self.turn_counter,
                "conversation_id": self.conversation_id,
                **metadata
            }
            
            assistant_entry = {
                "role": "assistant",
                "content": ai_response,
                "timestamp": timestamp,
                "turn": self.turn_counter,
                "conversation_id": self.conversation_id,
                **metadata
            }
            
            # Add to history
            self.history.append(user_entry)
            self.history.append(assistant_entry)
            
            # Prune history if too long
            if len(self.history) > self.max_history_entries * 2:  # *2 because each exchange has 2 entries
                self.history = self.history[-(self.max_history_entries * 2):]
            
            # Update memory index (simple keyword-based indexing)
            self._update_memory_index(user_input, len(self.history) - 2)  # Index points to user message
            
            # Save history
            self._save_history()
            
            # Post memory update event
            self.event_bus.post_event(
                Event(
                    event_type=CoreEventType.MEMORY_UPDATE,
                    data={
                        "user_input": user_input,
                        "ai_response": ai_response,
                        "turn": self.turn_counter,
                        "conversation_id": self.conversation_id
                    },
                    source="core"
                )
            )
            
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to update memory",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.DATA
            )
    
    def _init_components(self):
        """Initialize core components based on configuration and dependencies"""
        # Get components to initialize from config
        core_config = self.config_manager.get_config("core", {})
        enabled_components = core_config.get("enabled_components", ["voice", "vision", "hearing", "automation"])
        
        # Dependency graph and initialization order
        self.component_dependencies = {
            "voice": ["event_bus", "config_manager", "error_handler"],
            "vision": ["event_bus", "config_manager", "error_handler"],
            "hearing": ["event_bus", "config_manager", "error_handler"],
            "automation": ["event_bus", "config_manager", "error_handler"],
            "smart_home": ["event_bus", "config_manager", "error_handler", "voice"],
            "presence": ["event_bus", "config_manager", "error_handler"]
        }
        
        # Component initialization methods
        component_initializers = {
            "voice": self._init_voice,
            "vision": self._init_vision,
            "hearing": self._init_hearing,
            "automation": self._init_automation,
            "smart_home": self._init_smart_home,
            "presence": self._init_presence
        }
        
        # Track failed components
        failed_components = []
        
        # Initialize components in dependency order
        for component_name in enabled_components:
            try:
                if component_name in self.components:
                    # Skip already initialized components
                    continue
                    
                if component_name not in component_initializers:
                    logger.warning(f"Unknown component: {component_name}")
                    continue
                
                # Check if all dependencies are met
                dependencies = self.component_dependencies.get(component_name, [])
                if not all(dep in self.components for dep in dependencies):
                    missing_deps = [dep for dep in dependencies if dep not in self.components]
                    logger.warning(f"Cannot initialize {component_name} - missing dependencies: {missing_deps}")
                    failed_components.append(component_name)
                    continue
                    
                # Initialize component
                logger.info(f"Initializing {component_name} component...")
                component = component_initializers[component_name]()
                
                if component:
                    self.components[component_name] = component
                    logger.info(f"{component_name.capitalize()} component initialized successfully")
                else:
                    logger.error(f"Failed to initialize {component_name} component")
                    failed_components.append(component_name)
                    
            except Exception as e:
                self.error_handler.log_error(
                    e,
                    f"Error initializing {component_name} component",
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.INITIALIZATION
                )
                failed_components.append(component_name)
                logger.error(traceback.format_exc())
        
        # Check for critical failures
        critical_components = {"config_manager", "error_handler", "event_bus"}
        critical_failures = [c for c in critical_components if c in failed_components]
        
        if critical_failures:
            logger.critical(f"Failed to initialize critical components: {critical_failures}")
            self.critical_init_failure = True
        else:
            if failed_components:
                logger.warning(f"Some non-critical components failed to initialize: {failed_components}")
            self.critical_init_failure = False
    
    def _init_voice(self):
        """Initialize enhanced voice client with proper event integration"""
        try:
            # Import the enhanced voice client
            try:
                from services.voice.enhanced_voice_client import EnhancedVoiceClient
                voice_client_class = EnhancedVoiceClient
                logger.info("Using EnhancedVoiceClient for voice integration")
            except ImportError:
                # Fall back to regular voice client if enhanced version is not available
                from services.voice.voice_api_client import VoiceAPIClient
                voice_client_class = VoiceAPIClient
                logger.info("Using standard VoiceAPIClient for voice integration")
            
            # Get voice configuration
            voice_config = self.config_manager.get_config("voice", {})
            voice_api_url = voice_config.get("api_url", "http://localhost:8100")
            
            # Create voice client with event bus integration
            if voice_client_class == EnhancedVoiceClient:
                voice_client = voice_client_class(voice_api_url, self.event_bus)
            else:
                voice_client = voice_client_class(voice_api_url)
            
            # Test connection
            connection_status = voice_client.test_connection()
            
            if connection_status:
                logger.info(f"Successfully connected to Voice API at {voice_api_url}")
            else:
                logger.warning(f"Voice API connection test failed at {voice_api_url}")
            
            # Configure voice settings from config
            voice_settings = {
                "speed": voice_config.get("speed", 1.0),
                "pitch": voice_config.get("pitch", 1.0),
                "emotion": voice_config.get("emotion", "normal"),
                "volume": voice_config.get("volume", 0.8)
            }
            
            # Apply settings
            voice_client.update_settings(voice_settings)
            
            # Return client even if connection failed - it might connect later
            return voice_client
            
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to initialize voice component",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.INITIALIZATION
            )
            return None
    
    def _init_vision(self):
        """Initialize vision components with error handling"""
        try:
            from services.vision.vision_core import VisionCore
            
            # Get vision configuration
            vision_config = self.config_manager.get_config("vision", {})
            enabled = vision_config.get("enabled", True)
            
            if not enabled:
                logger.info("Vision module disabled in configuration")
                return None
                
            # Create vision component
            vision_core = VisionCore()
            
            # Configure vision settings
            if hasattr(vision_core, 'set_config'):
                vision_core.set_config(vision_config)
                
            return vision_core
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to initialize vision component",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.INITIALIZATION
            )
            return None
            
    def _init_hearing(self):
        """Initialize hearing components with error handling"""
        try:
            from services.hearing.hearing import Hearing
            
            # Get hearing configuration
            hearing_config = self.config_manager.get_config("hearing", {})
            enabled = hearing_config.get("enabled", True)
            
            if not enabled:
                logger.info("Hearing module disabled in configuration")
                return None
                
            # Get wake word and model path from config
            wake_word = hearing_config.get("wake_word", "hey sabrina")
            model_path = hearing_config.get("model_path", "models/vosk-model")
            
            # Create hearing component with config
            hearing = Hearing(wake_word=wake_word, model_path=model_path)
            
            return hearing
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to initialize hearing component",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.INITIALIZATION
            )
            return None
    
    def _init_automation(self):
        """Initialize automation components with error handling"""
        try:
            from services.automation.automation import Actions
            
            # Get automation configuration
            automation_config = self.config_manager.get_config("automation", {})
            enabled = automation_config.get("enabled", True)
            
            if not enabled:
                logger.info("Automation module disabled in configuration")
                return None
                
            # Create automation component
            actions = Actions()
            
            # Configure automation settings if supported
            if hasattr(actions, 'configure'):
                actions.configure(
                    mouse_move_duration=automation_config.get("mouse_move_duration", 0.2),
                    typing_interval=automation_config.get("typing_interval", 0.1),
                    failsafe=automation_config.get("failsafe", True)
                )
                
            return actions
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to initialize automation component",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.INITIALIZATION
            )
            return None
            
    def _init_smart_home(self):
        """Initialize smart home component with error handling"""
        try:
            # Import dynamically to avoid errors if not available
            try:
                from services.smart_home.smart_home import SmartHome
                smart_home_class = SmartHome
            except ImportError:
                logger.warning("SmartHome class not found")
                return None
                
            # Get smart home configuration
            smart_home_config = self.config_manager.get_config("smart_home", {})
            enabled = smart_home_config.get("enable", False)
            
            if not enabled:
                logger.info("Smart home module disabled in configuration")
                return None
                
            # Create smart home component
            home_assistant_url = smart_home_config.get("home_assistant_url")
            if not home_assistant_url:
                logger.warning("No Home Assistant URL configured")
                return None
                
            smart_home = smart_home_class(
                home_assistant_url=home_assistant_url,
                event_bus=self.event_bus
            )
            
            # Test connection
            if hasattr(smart_home, 'test_connection'):
                connected = smart_home.test_connection()
                if connected:
                    logger.info(f"Connected to Home Assistant at {home_assistant_url}")
                else:
                    logger.warning(f"Failed to connect to Home Assistant at {home_assistant_url}")
            
            return smart_home
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to initialize smart home component",
                severity=ErrorSeverity.WARNING,  # Non-critical
                category=ErrorCategory.INITIALIZATION
            )
            return None
            
    def _init_presence(self):
        """Initialize presence component with error handling"""
        try:
            # Import dynamically to avoid errors if not available
            try:
                from services.presence.presence_system import PresenceSystem
                presence_class = PresenceSystem
            except ImportError:
                logger.warning("PresenceSystem class not found")
                return None
                
            # Get presence configuration
            presence_config = self.config_manager.get_config("presence", {})
            enabled = presence_config.get("enable", False)
            
            if not enabled:
                logger.info("Presence module disabled in configuration")
                return None
                
            # Create presence component
            presence = presence_class()
            
            return presence
        except Exception as e:
            self.error_handler.log_error(
                e, 
                "Failed to initialize presence component",
                severity=ErrorSeverity.WARNING,  # Non-critical
                category=ErrorCategory.INITIALIZATION
            )
            return None
    
    def _init_component_integrations(self):
        """Initialize integrations between components"""
        # Connect voice and presence if both are available
        if "voice" in self.components and "presence" in self.components:
            logger.info("Integrating voice and presence components")
            
            # Link voice status to presence animations
            try:
                self.event_bus.register_handler(
                    self.event_bus.create_event_handler(
                        event_types=[EventType.VOICE_STATUS],
                        callback=self._voice_to_presence_handler
                    )
                )
            except Exception as e:
                logger.error(f"Failed to set up voice-presence integration: {str(e)}")
                
        # Connect vision and voice for OCR reading
        if "vision" in self.components and "voice" in self.components:
            logger.info("Integrating vision and voice components")
            
            # Register handler for OCR to voice
            try:
                self.event_bus.register_handler(
                    self.event_bus.create_event_handler(
                        event_types=[EventType.VISION],
                        callback=self._vision_to_voice_handler
                    )
                )
            except Exception as e:
                logger.error(f"Failed to set up vision-voice integration: {str(e)}")
    
    def _voice_to_presence_handler(self, event):
        """
        Handle voice events for presence updates
        
        Args:
            event: Voice status event
        """
        if "presence" not in self.components or not hasattr(self.components["presence"], "set_animation"):
            return
            
        status = event.data.get("status", "")
        
        # Map voice status to presence animations
        animation = None
        if status == "speaking_started":
            animation = "talking"
        elif status == "speaking_completed":
            animation = "idle"
        elif status == "speaking_failed":
            animation = "error"
            
        # Set animation if applicable
        if animation:
            try:
                self.components["presence"].set_animation(animation)
            except Exception as e:
                logger.error(f"Failed to set presence animation: {str(e)}")
    
    def _vision_to_voice_handler(self, event):
        """
        Handle vision events for voice reading
        
        Args:
            event: Vision event with OCR data
        """
        # Only process if the event has read_aloud flag
        if not event.data.get("read_aloud", False):
            return
            
        ocr_text = event.data.get("ocr_text", "")
        if not ocr_text:
            return
            
        # Speak the OCR text
        self.speak(f"I can see: {ocr_text[:200]}{'...' if len(ocr_text) > 200 else ''}")
    
    def _register_command_processors(self):
        """Set up command processors for handling different command types"""
        # Default command processors
        self.command_processors = {
            "exit": self._process_exit_command,
            "say": self._process_say_command,
            "click": self._process_click_command,
            "move": self._process_move_command,
            "type": self._process_type_command,
            "capture": self._process_capture_command,
            "help": self._process_help_command,
        }
        
        # Add component-specific command processors
        if "smart_home" in self.components:
            logger.info("Adding smart home command processors")
            self.command_processors.update({
                "light": self._process_light_command,
                "temperature": self._process_temperature_command,
                "lock": self._process_lock_command,
                "home": self._process_home_command,
            })
            
        # Read custom command processors from config
        core_config = self.config_manager.get_config("core", {})
        custom_commands = core_config.get("custom_commands", {})
        
        for cmd, handler_info in custom_commands.items():
            if cmd in self.command_processors:
                logger.warning(f"Custom command '{cmd}' overrides built-in command")
                
            # Custom commands are specified as module.function strings
            try:
                module_name, function_name = handler_info.split(".")
                module = importlib.import_module(module_name)
                handler = getattr(module, function_name)
                
                # Add custom command processor
                self.command_processors[cmd] = handler
                logger.info(f"Added custom command processor for '{cmd}'")
            except Exception as e:
                logger.error(f"Failed to load custom command '{cmd}': {str(e)}")
        
        logger.info(f"Registered {len(self.command_processors)} command processors")
    
    def _change_state(self, new_state):
        """
        Change the current state of the core system
        
        Args:
            new_state: New state to transition to
        """
        if new_state == self.current_state:
            return
            
        old_state = self.current_state
        self.current_state = new_state
        
        # Record state change
        state_change = {
            "from": old_state,
            "to": new_state,
            "timestamp": time.time()
        }
        self.state_changes.append(state_change)
        self.last_state_change = time.time()
        
        # Trim state changes history if needed
        if len(self.state_changes) > 100:
            self.state_changes = self.state_changes[-100:]
        
        # Log state change
        logger.info(f"State changed: {old_state.name} -> {new_state.name}")
        
        # Post state change event
        self.event_bus.post_event(
            Event(
                event_type=CoreEventType.STATE_CHANGE,
                data={
                    "old_state": old_state.name,
                    "new_state": new_state.name,
                    "timestamp": self.last_state_change
                },
                source="core"
            )
        )
    
    def _register_event_handlers(self):
        """Register handlers for all relevant event types"""
        # Register handlers for each event type
        event_handlers = [
            (EventType.USER_INPUT, self._handle_user_input, EventPriority.HIGH),
            (EventType.VOICE_STATUS, self._handle_voice_status, EventPriority.NORMAL),
            (EventType.VISION, self._handle_vision_event, EventPriority.NORMAL),
            (EventType.ERROR, self._handle_error_event, EventPriority.CRITICAL),
            (EventType.COMPONENT_STATUS, self._handle_component_status, EventPriority.HIGH),
            (CoreEventType.STATE_CHANGE, self._handle_state_change, EventPriority.NORMAL)
        ]
        
        # Register each handler
        for event_type, handler, priority in event_handlers:
            self.event_bus.register_handler(
                self.event_bus.create_event_handler(
                    event_types=[event_type],
                    callback=handler,
                    min_priority=priority
                )
            )
        
        logger.info(f"Registered {len(event_handlers)} event handlers")
    
    def _handle_user_input(self, event):
        """
        Event handler for user input events
        
        Args:
            event: User input event
        """
        user_input = event.data.get("text", "")
        if not user_input:
            return
            
        logger.info(f"Handling user input event: {user_input}")
        
        # Update state to processing
        self._change_state(CoreState.PROCESSING)
        
        # Process the command
        continue_running, response = self.process_command(user_input)
        
        # Add to response queue for any listeners
        if hasattr(self, 'response_queue'):
            self.response_queue.put({
                "user_input": user_input,
                "response": response,
                "continue": continue_running
            })