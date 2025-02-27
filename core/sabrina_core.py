"""
Sabrina Core Integration System
================================
This module serves as the central orchestration point for Sabrina AI,
properly initializing and connecting all components with robust error handling
and event-driven communication.
"""

import os
import sys
import json
import time
import logging
import threading
import queue
from typing import Dict, Any, List, Optional, Callable
from enum import Enum, auto
import traceback

# Core modules
from services.vision.vision_core import VisionCore
from services.hearing.hearing import Hearing
from services.automation.automation import Actions
from services.voice.voice_api import VoiceAPIClient

# Configuration and utility imports
from utilities.config_manager import ConfigManager
from utilities.event_system import EventBus, EventType, Event, EventPriority
from utilities.error_handler import ErrorHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("logs/sabrina_core.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("sabrina_core")


class SabrinaCoreEvent(Enum):
    """Events specific to the Sabrina Core system"""
    STARTUP = auto()
    SHUTDOWN = auto()
    USER_INPUT = auto()
    VOICE_OUTPUT = auto()
    SCREEN_UPDATE = auto()
    AUTOMATION_ACTION = auto()
    ERROR = auto()
    STATE_CHANGE = auto()
    COMMAND_EXECUTED = auto()


class SabrinaCore:
    """
    Enhanced Sabrina AI Core Orchestration Engine
    
    This class properly initializes and manages all components of the Sabrina AI system,
    including vision, hearing, automation, and voice services. It uses a robust event-driven
    architecture for component communication and implements proper error handling.
    """
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        """Initialize the Sabrina AI Core system"""
        self.startup_time = time.time()
        logger.info("Initializing Sabrina AI Core...")
        
        # Initialize utilities first
        self._init_utilities(config_path)
        
        # Initialize core components
        self._init_components()
        
        # Initialize internal state
        self._init_state()
        
        # Register event handlers
        self._register_event_handlers()
        
        # Setup command processors
        self._setup_command_processors()
        
        # Track initialization success
        self.initialized = True
        startup_duration = time.time() - self.startup_time
        logger.info(f"Sabrina AI Core initialized in {startup_duration:.2f} seconds")
        
        # Post startup event
        self.event_bus.post_event(
            Event(
                event_type=SabrinaCoreEvent.STARTUP,
                data={"startup_duration": startup_duration},
                source="core"
            )
        )
    
    def _init_utilities(self, config_path: str):
        """Initialize utility systems like configuration and event bus"""
        try:
            # Ensure logs directory exists
            os.makedirs("logs", exist_ok=True)
            
            # Initialize configuration manager
            logger.info("Loading configuration from %s", config_path)
            self.config_manager = ConfigManager(config_path)
            
            # Initialize error handler
            self.error_handler = ErrorHandler(self.config_manager)
            
            # Initialize event bus
            logger.info("Initializing event bus")
            self.event_bus = EventBus()
            self.event_bus.start()
            
        except Exception as e:
            logger.critical(f"Failed to initialize utilities: {str(e)}")
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to initialize core utilities") from e
    
    def _init_components(self):
        """Initialize all core service components with proper error handling"""
        components_to_init = [
            ("vision", self._init_vision),
            ("hearing", self._init_hearing),
            ("automation", self._init_automation),
            ("voice", self._init_voice)
        ]
        
        # Initialize components with error tracking
        self.components = {}
        failed_components = []
        
        for component_name, init_function in components_to_init:
            try:
                logger.info(f"Initializing {component_name} component...")
                component = init_function()
                if component:
                    self.components[component_name] = component
                    logger.info(f"{component_name.capitalize()} component initialized successfully")
                else:
                    logger.error(f"Failed to initialize {component_name} component")
                    failed_components.append(component_name)
            except Exception as e:
                logger.error(f"Error initializing {component_name} component: {str(e)}")
                logger.error(traceback.format_exc())
                failed_components.append(component_name)
        
        # Check if critical components failed
        if failed_components:
            critical_components = {"vision", "hearing"}
            if any(c in critical_components for c in failed_components):
                logger.critical(f"Failed to initialize critical components: {failed_components}")
                # Allow initialization to continue but set failure flag
                self.critical_init_failure = True
            else:
                logger.warning(f"Some non-critical components failed to initialize: {failed_components}")
                self.critical_init_failure = False
    
    def _init_vision(self):
        """Initialize vision components with error handling"""
        try:
            vision_core = VisionCore()
            return vision_core
        except Exception as e:
            self.error_handler.log_error(e, "Failed to initialize vision component")
            return None
    
    def _init_hearing(self):
        """Initialize hearing components with error handling"""
        try:
            hearing = Hearing()
            return hearing
        except Exception as e:
            self.error_handler.log_error(e, "Failed to initialize hearing component")
            return None
    
    def _init_automation(self):
        """Initialize automation components with error handling"""
        try:
            actions = Actions()
            return actions
        except Exception as e:
            self.error_handler.log_error(e, "Failed to initialize automation component")
            return None
    
    def _init_voice(self):
        """Initialize voice API client with error handling"""
        try:
            # Get voice API URL from config
            voice_config = self.config_manager.get_config("voice", {})
            voice_api_url = voice_config.get("api_url", "http://localhost:8100")
            
            # Create voice API client
            voice_client = VoiceAPIClient(voice_api_url)
            
            # Test connection
            if voice_client.test_connection():
                logger.info(f"Successfully connected to Voice API at {voice_api_url}")
                return voice_client
            else:
                logger.warning(f"Voice API connection test failed at {voice_api_url}")
                return voice_client  # Still return the client even if test fails
        except Exception as e:
            self.error_handler.log_error(e, "Failed to initialize voice component")
            return None
    
    def _init_state(self):
        """Initialize internal state and memory system"""
        # Command and response queues
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        
        # Memory and context management
        self.memory_file = "data/memory.json"
        self.ensure_directory_exists("data")
        self.history = self.load_history()
        
        # System state tracking
        self.running = False
        self.paused = False
        self.last_voice_time = 0
        self.last_screen_capture_time = 0
        self.command_processors = {}
        self.critical_init_failure = False
    
    def _register_event_handlers(self):
        """Register handlers for system events"""
        # Register handlers for each event type
        self.event_bus.register_handler(
            self.event_bus.create_event_handler(
                SabrinaCoreEvent.USER_INPUT,
                self._handle_user_input,
                EventPriority.HIGH
            )
        )
        
        self.event_bus.register_handler(
            self.event_bus.create_event_handler(
                SabrinaCoreEvent.SCREEN_UPDATE,
                self._handle_screen_update,
                EventPriority.NORMAL
            )
        )
        
        self.event_bus.register_handler(
            self.event_bus.create_event_handler(
                SabrinaCoreEvent.ERROR,
                self._handle_error_event,
                EventPriority.CRITICAL
            )
        )
    
    def _setup_command_processors(self):
        """Set up command processors for handling different command types"""
        # Register command processors
        self.command_processors = {
            "exit": self._process_exit_command,
            "say": self._process_say_command,
            "click": self._process_click_command,
            "move": self._process_move_command,
            "type": self._process_type_command,
            "capture": self._process_capture_command,
            "help": self._process_help_command,
        }
    
    def load_history(self):
        """Load conversation history from file with error handling"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            return []
        except Exception as e:
            self.error_handler.log_error(e, "Failed to load history")
            return []
    
    def save_history(self):
        """Save the conversation history to file with error handling"""
        try:
            with open(self.memory_file, "w") as f:
                json.dump(self.history, f)
        except Exception as e:
            self.error_handler.log_error(e, "Failed to save history")
    
    def update_memory(self, user_input, ai_response):
        """Update conversation memory with user input and AI response"""
        try:
            self.history.append({"role": "user", "content": user_input, "timestamp": time.time()})
            self.history.append({"role": "assistant", "content": ai_response, "timestamp": time.time()})
            
            # Keep only the last N exchanges to avoid memory bloat
            memory_config = self.config_manager.get_config("memory", {})
            max_history = memory_config.get("max_entries", 20)
            
            if len(self.history) > max_history * 2:  # *2 because each exchange has 2 entries
                self.history = self.history[-(max_history * 2):]
            
            self.save_history()
        except Exception as e:
            self.error_handler.log_error(e, "Failed to update memory")
    
    def ensure_directory_exists(self, directory):
        """Ensure a directory exists, creating it if necessary"""
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                self.error_handler.log_error(e, f"Failed to create directory: {directory}")
    
    def speak(self, text):
        """Send text to the voice API for TTS processing"""
        if not text or not text.strip():
            logger.warning("Attempted to speak empty text")
            return
        
        logger.info(f"Speaking: {text}")
        
        try:
            if "voice" in self.components:
                # Post event before speaking
                self.event_bus.post_event(
                    Event(
                        event_type=SabrinaCoreEvent.VOICE_OUTPUT,
                        data={"text": text, "state": "started"},
                        source="core"
                    )
                )
                
                # Send text to voice API
                response = self.components["voice"].speak(text)
                
                if response:
                    # Post success event
                    self.event_bus.post_event(
                        Event(
                            event_type=SabrinaCoreEvent.VOICE_OUTPUT,
                            data={"text": text, "state": "completed", "success": True},
                            source="core"
                        )
                    )
                    return True
                else:
                    logger.error("Voice API returned empty response")
                    # Post failure event
                    self.event_bus.post_event(
                        Event(
                            event_type=SabrinaCoreEvent.VOICE_OUTPUT,
                            data={"text": text, "state": "completed", "success": False, 
                                  "error": "Empty response from Voice API"},
                            source="core"
                        )
                    )
                    return False
            else:
                logger.warning("Voice component not available, cannot speak")
                return False
        except Exception as e:
            self.error_handler.log_error(e, "Error in speak function")
            # Post error event
            self.event_bus.post_event(
                Event(
                    event_type=SabrinaCoreEvent.ERROR,
                    data={"function": "speak", "error": str(e), "text": text},
                    source="core",
                    priority=EventPriority.HIGH
                )
            )
            return False
    
    def process_command(self, command):
        """Process user commands with comprehensive command parsing"""
        if not command or not isinstance(command, str):
            logger.warning(f"Invalid command: {command}")
            return True, "Invalid command format"
        
        # Trim whitespace
        command = command.strip()
        
        # Exit command handling (high priority)
        if command.lower() == "exit":
            return self._process_exit_command(command)
        
        # Handle commands with ! prefix
        if command.startswith("!"):
            command_parts = command[1:].split(maxsplit=1)
            command_type = command_parts[0].lower() if command_parts else ""
            command_args = command_parts[1] if len(command_parts) > 1 else ""
            
            # Look up command processor
            processor = self.command_processors.get(command_type)
            if processor:
                # Post event about command execution
                self.event_bus.post_event(
                    Event(
                        event_type=SabrinaCoreEvent.COMMAND_EXECUTED,
                        data={"command_type": command_type, "args": command_args},
                        source="core"
                    )
                )
                return processor(command)
            else:
                logger.warning(f"Unknown command type: {command_type}")
                return True, f"Unknown command: {command_type}. Try !help for a list of commands."
        
        # If no special command handling, process as a regular voice input
        return self._handle_regular_input(command)
    
    def _process_exit_command(self, command):
        """Process exit command"""
        logger.info("Exit command received, shutting down")
        return False, "Exiting Sabrina AI"
    
    def _process_say_command(self, command):
        """Process say command to speak text"""
        text = command[5:] if command.startswith("!say ") else ""
        if text:
            self.speak(text)
            return True, f"Said: {text}"
        return True, "Error: No text provided for say command"
    
    def _process_click_command(self, command):
        """Process click command to perform mouse click"""
        try:
            if "automation" in self.components:
                self.components["automation"].click()
                return True, "Click executed"
            return True, "Error: Automation component not available"
        except Exception as e:
            self.error_handler.log_error(e, "Error executing click command")
            return True, f"Error executing click: {str(e)}"
    
    def _process_move_command(self, command):
        """Process move command to move mouse cursor"""
        try:
            parts = command.split()
            if len(parts) >= 3:
                x = int(parts[1])
                y = int(parts[2])
                if "automation" in self.components:
                    self.components["automation"].move_mouse_to(x, y)
                    return True, f"Moved cursor to ({x}, {y})"
                return True, "Error: Automation component not available"
            return True, "Error: Invalid move command. Use: !move x y"
        except Exception as e:
            self.error_handler.log_error(e, "Error executing move command")
            return True, f"Error executing move: {str(e)}"
    
    def _process_type_command(self, command):
        """Process type command to type text"""
        try:
            text = command[6:] if command.startswith("!type ") else ""
            if text:
                if "automation" in self.components:
                    self.components["automation"].type_text(text)
                    return True, f"Typed: {text}"
                return True, "Error: Automation component not available"
            return True, "Error: No text provided for type command"
        except Exception as e:
            self.error_handler.log_error(e, "Error executing type command")
            return True, f"Error executing type: {str(e)}"
    
    def _process_capture_command(self, command):
        """Process capture command to capture screen"""
        try:
            if "vision" in self.components:
                # Capture screen and run OCR
                from services.vision.constants import CaptureMode
                image_path = self.components["vision"].capture_screen(CaptureMode.FULL_SCREEN)
                if image_path:
                    # Run OCR on the captured image
                    ocr_text = self.components["vision"].vision_ocr.run_ocr(image_path)
                    # Post event with OCR results
                    self.event_bus.post_event(
                        Event(
                            event_type=SabrinaCoreEvent.SCREEN_UPDATE,
                            data={"ocr_text": ocr_text, "image_path": image_path},
                            source="core"
                        )
                    )
                    self.speak(f"I captured the screen and found: {ocr_text[:100]}...")
                    return True, f"Screen captured and OCR performed: {ocr_text[:100]}..."
                return True, "Error: Failed to capture screen"
            return True, "Error: Vision component not available"
        except Exception as e:
            self.error_handler.log_error(e, "Error executing capture command")
            return True, f"Error executing capture: {str(e)}"
    
    def _process_help_command(self, command):
        """Process help command to show available commands"""
        help_text = """
        Available Commands:
        !say <text> - Speak the given text
        !click - Click at the current cursor position
        !move <x> <y> - Move cursor to the specified coordinates
        !type <text> - Type the given text
        !capture - Capture the screen and run OCR
        !help - Show this help message
        exit - Exit the program
        """
        print(help_text)
        self.speak("I've displayed the available commands in the console.")
        return True, help_text
    
    def _handle_regular_input(self, user_input):
        """Handle regular voice input (non-command)"""
        # Here you would typically process the input with an LLM or other AI
        # For now, we'll just echo it back and capture the screen as a demo
        
        try:
            if "vision" in self.components:
                from services.vision.constants import CaptureMode
                # Capture screen
                image_path = self.components["vision"].capture_screen(CaptureMode.FULL_SCREEN)
                
                if image_path:
                    # Run OCR on the captured image
                    ocr_text = self.components["vision"].vision_ocr.run_ocr(image_path)
                    # Process input and screen context
                    response = f"You said: {user_input}. I can see: {ocr_text[:100]}"
                    self.speak(response)
                    self.update_memory(user_input, response)
                    return True, response
            
            # Fallback if vision isn't available
            response = f"You said: {user_input}"
            self.speak(response)
            self.update_memory(user_input, response)
            return True, response
            
        except Exception as e:
            self.error_handler.log_error(e, "Error processing regular input")
            response = "I encountered an error processing your request."
            self.speak(response)
            return True, response
    
    def _handle_user_input(self, event):
        """Event handler for user input events"""
        user_input = event.data.get("text", "")
        if user_input:
            logger.info(f"Handling user input event: {user_input}")
            continue_running, response = self.process_command(user_input)
            
            # Add to response queue for any listeners
            self.response_queue.put({
                "user_input": user_input,
                "response": response,
                "continue": continue_running
            })
            
            # If command indicates we should stop running, update state
            if not continue_running:
                self.running = False
    
    def _handle_screen_update(self, event):
        """Event handler for screen update events"""
        ocr_text = event.data.get("ocr_text", "")
        image_path = event.data.get("image_path", "")
        
        logger.debug(f"Screen update event received: {len(ocr_text)} chars of OCR text")
        
        # Here you would process the screen content
        # For now, we'll just log it
        if ocr_text:
            logger.info(f"Screen OCR detected: {ocr_text[:100]}...")
    
    def _handle_error_event(self, event):
        """Event handler for error events"""
        error_msg = event.data.get("error", "Unknown error")
        source = event.data.get("source", "unknown")
        
        logger.error(f"Error event from {source}: {error_msg}")
        
        # For critical errors, we might want to take recovery actions
        if event.priority == EventPriority.CRITICAL:
            logger.critical(f"Critical error from {source} - attempting recovery")
            # Implement recovery logic here
    
    def run(self):
        """Main AI loop that listens, processes, and interacts"""
        if not self.initialized:
            logger.error("Cannot run: Sabrina AI Core not properly initialized")
            return
        
        if self.critical_init_failure:
            logger.error("Cannot run: Critical components failed to initialize")
            return
        
        logger.info("Starting Sabrina AI main loop")
        print("Sabrina is ready. Say a command or type '!exit' to quit.")
        
        self.running = True
        
        try:
            while self.running:
                # Get user input
                if "hearing" in self.components:
                    # Use the hearing component to listen for voice input
                    user_input = self.components["hearing"].listen()
                    logger.info(f"User Input: {user_input}")
                    print(f"You: {user_input}")
                else:
                    # Fallback to console input if hearing component is not available
                    user_input = input("You: ")
                
                # Process the command and get response
                continue_running, response = self.process_command(user_input)
                print(f"Sabrina: {response}")
                
                # Update running state based on command processing result
                self.running = continue_running
                
                # Pause briefly to avoid excessive CPU usage
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down")
        except Exception as e:
            self.error_handler.log_error(e, "Unhandled exception in main loop")
        finally:
            self._shutdown()
    
    def _shutdown(self):
        """Clean shutdown of all components and resources"""
        logger.info("Shutting down Sabrina AI Core...")
        
        # Save history
        self.save_history()
        
        # Stop event bus
        if hasattr(self, 'event_bus'):
            logger.info("Stopping event bus")
            self.event_bus.stop()
        
        # Post shutdown event if event bus is still running
        try:
            self.event_bus.post_event_immediate(
                Event(
                    event_type=SabrinaCoreEvent.SHUTDOWN,
                    data={"uptime": time.time() - self.startup_time},
                    source="core",
                    priority=EventPriority.CRITICAL
                )
            )
        except:
            pass
        
        logger.info("Sabrina AI Core shutdown complete")


if __name__ == "__main__":
    try:
        # Create and run Sabrina AI
        sabrina = SabrinaCore()
        sabrina.run()
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        logger.critical(traceback.format_exc())
        print(f"Fatal error: {str(e)}")
        sys.exit(1)