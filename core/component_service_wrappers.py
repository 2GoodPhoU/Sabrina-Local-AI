"""
Sabrina AI Component Service Wrappers
===================================
Service component wrappers that implement the ServiceComponent interface
for each of Sabrina's core services, enabling standardized initialization,
communication, and integration through the event system.
"""

import logging
import os
import time
from typing import Dict, Any, List, Optional

# Import the ServiceComponent base class
from .core_integration import ServiceComponent, ComponentStatus
from .enhanced_event_system import Event, EventType, EventPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sabrina.components")


class VoiceService(ServiceComponent):
    """Voice service component for speech synthesis and audio playback"""

    def __init__(self, name, event_bus, state_machine, config=None):
        """Initialize the voice service component"""
        super().__init__(name, event_bus, state_machine, config)

        self.voice_client = None
        self.currently_speaking = False
        self.last_text = ""
        self.voice_api_url = self.config.get("api_url", "http://localhost:8100")
        self.default_voice = self.config.get("voice", "en_US-jenny-medium")
        self.default_speed = self.config.get("speed", 1.0)
        self.default_pitch = self.config.get("pitch", 1.0)
        self.default_volume = self.config.get("volume", 0.8)
        self.default_emotion = self.config.get("emotion", "neutral")

    def _register_handlers(self):
        """Register event handlers for the voice service"""
        # Create handler for speech events
        speech_handler = self.event_bus.create_handler(
            callback=self._handle_speech_event,
            event_types=[
                EventType.SPEECH_STARTED,
                EventType.SPEECH_COMPLETED,
                EventType.SPEECH_ERROR,
            ],
        )

        # Register the handler
        handler_id = self.event_bus.register_handler(speech_handler)
        self.handler_ids.append(handler_id)

    def initialize(self) -> bool:
        """Initialize the voice service"""
        super().initialize()

        logger.info("Initializing voice service")

        try:
            # Try to import enhanced client first
            try:
                from services.voice.enhanced_voice_client import EnhancedVoiceClient

                logger.info("Using EnhancedVoiceClient")
                self.voice_client = EnhancedVoiceClient(
                    api_url=self.voice_api_url, event_bus=self.event_bus
                )
            except ImportError:
                # Fall back to standard client
                try:
                    from services.voice.voice_api_client import VoiceAPIClient

                    logger.info("Using standard VoiceAPIClient")
                    self.voice_client = VoiceAPIClient(self.voice_api_url)
                except ImportError:
                    logger.warning("No voice client available - using placeholder")
                    self._create_placeholder_client()

            # Test connection to voice service
            connected = False
            if hasattr(self.voice_client, "test_connection"):
                connected = self.voice_client.test_connection()

            if connected:
                logger.info(
                    f"Successfully connected to Voice API at {self.voice_api_url}"
                )

                # Configure voice settings
                self._configure_voice_settings()

                self.status = ComponentStatus.READY
                return True
            else:
                logger.warning(
                    f"Could not connect to Voice API at {self.voice_api_url}"
                )
                self.status = ComponentStatus.ERROR
                self.error_message = (
                    f"Failed to connect to Voice API at {self.voice_api_url}"
                )
                return False

        except Exception as e:
            self.handle_error(e, "Failed to initialize voice service")
            return False

    def _create_placeholder_client(self):
        """Create a placeholder voice client for testing"""

        # Create a simple object with the required methods
        class PlaceholderVoiceClient:
            def __init__(self, api_url):
                self.api_url = api_url

            def speak(self, text, **kwargs):
                logger.info(f"[PLACEHOLDER] Speaking: {text}")
                return True

            def test_connection(self):
                return True

            def get_voices(self):
                return ["placeholder"]

            def get_settings(self):
                return {
                    "voice": "placeholder",
                    "speed": 1.0,
                    "pitch": 1.0,
                    "volume": 0.8,
                }

            def update_settings(self, settings):
                return True

        self.voice_client = PlaceholderVoiceClient(self.voice_api_url)

    def _configure_voice_settings(self):
        """Configure voice settings from configuration"""
        if hasattr(self.voice_client, "update_settings"):
            settings = {
                "voice": self.default_voice,
                "speed": self.default_speed,
                "pitch": self.default_pitch,
                "volume": self.default_volume,
                "emotion": self.default_emotion,
            }

            success = self.voice_client.update_settings(settings)

            if success:
                logger.info("Voice settings configured successfully")
            else:
                logger.warning("Failed to configure voice settings")

    def _handle_speech_event(self, event: Event):
        """Handle speech events"""
        event_type = event.event_type

        if event_type == EventType.SPEECH_STARTED:
            # Extract text from event
            text = event.get("text", "")
            emotion = event.get("emotion", self.default_emotion)

            if not text:
                logger.warning("Received speech event with no text")
                return

            # Speak the text
            self.speak(text, emotion=emotion)

        elif event_type == EventType.SPEECH_COMPLETED:
            # Update state
            self.currently_speaking = False

            # Transition state if needed
            if (
                self.state_machine.current_state
                == self.state_machine.SabrinaState.SPEAKING
            ):
                self.state_machine.transition_to(self.state_machine.SabrinaState.READY)

        elif event_type == EventType.SPEECH_ERROR:
            # Handle error
            error = event.get("error", "Unknown error")
            logger.error(f"Speech error: {error}")

            # Update state
            self.currently_speaking = False

            # Transition state if needed
            if (
                self.state_machine.current_state
                == self.state_machine.SabrinaState.SPEAKING
            ):
                self.state_machine.transition_to(
                    self.state_machine.SabrinaState.ERROR,
                    {"error_info": {"message": error, "source": "voice"}},
                )

    def speak(self, text: str, **kwargs) -> bool:
        """
        Speak text using the voice service

        Args:
            text: Text to speak
            **kwargs: Additional parameters (voice, speed, pitch, volume, emotion)

        Returns:
            bool: True if successful, False otherwise
        """
        if not text:
            logger.warning("Speak called with empty text")
            return False

        # Update state
        self.currently_speaking = True
        self.last_text = text

        # Log the speech
        logger.info(f"Speaking: {text[:50]}{'...' if len(text) > 50 else ''}")

        # Use voice client to speak
        if self.voice_client:
            try:
                # Create parameters
                params = kwargs

                # Make sure speech event is posted after completion
                result = self.voice_client.speak(text, **params)

                if not result:
                    logger.warning("Voice client failed to speak text")
                    self.currently_speaking = False

                    # Post error event
                    self.event_bus.post_event(
                        Event(
                            event_type=EventType.SPEECH_ERROR,
                            data={"error": "Failed to speak text"},
                            priority=EventPriority.HIGH,
                            source="voice_service",
                        )
                    )

                return result

            except Exception as e:
                self.handle_error(e, "Error speaking text")
                self.currently_speaking = False

                # Post error event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.SPEECH_ERROR,
                        data={"error": str(e)},
                        priority=EventPriority.HIGH,
                        source="voice_service",
                    )
                )

                return False
        else:
            logger.warning("No voice client available")
            self.currently_speaking = False
            return False

    def shutdown(self) -> bool:
        """Shutdown the voice service"""
        # Stop any active speech
        if self.currently_speaking and hasattr(self.voice_client, "stop_speaking"):
            self.voice_client.stop_speaking()

        # Unregister handlers
        super().shutdown()

        return True

    def get_voices(self) -> List[str]:
        """
        Get list of available voices

        Returns:
            List of voice names
        """
        if self.voice_client and hasattr(self.voice_client, "get_voices"):
            try:
                return self.voice_client.get_voices()
            except Exception as e:
                self.handle_error(e, "Error getting voices")
                return []
        return []

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Update voice settings

        Args:
            settings: Dictionary of settings to update

        Returns:
            bool: True if successful, False otherwise
        """
        if self.voice_client and hasattr(self.voice_client, "update_settings"):
            try:
                return self.voice_client.update_settings(settings)
            except Exception as e:
                self.handle_error(e, "Error updating voice settings")
                return False
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get component status information"""
        status = super().get_status()

        # Add voice-specific status
        status.update(
            {
                "currently_speaking": self.currently_speaking,
                "last_text": self.last_text[:50]
                + ("..." if len(self.last_text) > 50 else ""),
                "voice_api_url": self.voice_api_url,
                "voice_settings": {
                    "voice": self.default_voice,
                    "speed": self.default_speed,
                    "pitch": self.default_pitch,
                    "volume": self.default_volume,
                    "emotion": self.default_emotion,
                },
            }
        )

        return status


class HearingService(ServiceComponent):
    """Hearing service component for speech recognition and wake word detection"""

    def __init__(self, name, event_bus, state_machine, config=None):
        """Initialize the hearing service component"""
        super().__init__(name, event_bus, state_machine, config)

        self.hearing_client = None
        self.currently_listening = False
        self.last_transcription = ""
        self.wake_word = self.config.get("wake_word", "hey sabrina")
        self.hotkey = self.config.get("hotkey", "ctrl+shift+s")

    def _register_handlers(self):
        """Register event handlers for the hearing service"""
        # Create handler for listening events
        listening_handler = self.event_bus.create_handler(
            callback=self._handle_listening_event,
            event_types=[
                EventType.LISTENING_STARTED,
                EventType.LISTENING_COMPLETED,
                EventType.WAKE_WORD_DETECTED,
            ],
        )

        # Register the handler
        handler_id = self.event_bus.register_handler(listening_handler)
        self.handler_ids.append(handler_id)

    def initialize(self) -> bool:
        """Initialize the hearing service"""
        super().initialize()

        logger.info("Initializing hearing service")

        try:
            # Try to import hearing class
            try:
                from services.hearing.hearing import Hearing

                logger.info("Using Hearing class")

                # Get model path from config
                model_path = self.config.get("model_path", "models/vosk-model")

                # Initialize hearing client
                self.hearing_client = Hearing(
                    wake_word=self.wake_word, model_path=model_path
                )

                # Set hotkey if provided
                if hasattr(self.hearing_client, "hotkey") and self.hotkey:
                    self.hearing_client.hotkey = self.hotkey

                self.status = ComponentStatus.READY
                logger.info("Hearing service initialized successfully")
                return True

            except ImportError:
                logger.warning("Hearing class not available - using placeholder")
                self._create_placeholder_client()
                self.status = ComponentStatus.READY
                return True

        except Exception as e:
            self.handle_error(e, "Failed to initialize hearing service")
            return False

    def _create_placeholder_client(self):
        """Create a placeholder hearing client for testing"""

        # Create a simple object with the required methods
        class PlaceholderHearingClient:
            def __init__(self, wake_word):
                self.wake_word = wake_word
                self.hotkey = "ctrl+shift+s"

            def listen_for_wake_word(self):
                return True

            def listen(self, timeout=10.0):
                return "This is a placeholder transcription"

            def close(self):
                pass

        self.hearing_client = PlaceholderHearingClient(self.wake_word)

    def _handle_listening_event(self, event: Event):
        """Handle listening events"""
        event_type = event.event_type

        if event_type == EventType.LISTENING_STARTED:
            # Start listening
            self.start_listening()

        elif event_type == EventType.LISTENING_COMPLETED:
            # Extract transcription from event
            transcription = event.get("transcription", "")

            if transcription:
                # Create user command event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.USER_VOICE_COMMAND,
                        data={"command": transcription},
                        priority=EventPriority.HIGH,
                        source="hearing_service",
                    )
                )

            # Update state
            self.currently_listening = False

            # Transition state if needed
            if (
                self.state_machine.current_state
                == self.state_machine.SabrinaState.LISTENING
            ):
                self.state_machine.transition_to(
                    self.state_machine.SabrinaState.PROCESSING
                )

        elif event_type == EventType.WAKE_WORD_DETECTED:
            logger.info("Wake word detected")

            # Transition to listening state
            self.state_machine.transition_to(self.state_machine.SabrinaState.LISTENING)

            # Start listening
            self.start_listening()

    def start_listening(self) -> bool:
        """
        Start listening for user speech

        Returns:
            bool: True if successful, False otherwise
        """
        # Update state
        self.currently_listening = True

        # Use hearing client to listen
        if self.hearing_client:
            try:
                # Log the action
                logger.info("Started listening for user speech")

                # Start listening in a separate thread to avoid blocking
                import threading

                def listen_thread():
                    try:
                        # Listen for speech with timeout
                        transcription = self.hearing_client.listen(timeout=10.0)

                        # Update last transcription
                        self.last_transcription = transcription or ""

                        # Post completion event
                        self.event_bus.post_event(
                            Event(
                                event_type=EventType.LISTENING_COMPLETED,
                                data={"transcription": transcription},
                                priority=EventPriority.HIGH,
                                source="hearing_service",
                            )
                        )

                    except Exception as e:
                        logger.error(f"Error in listen thread: {str(e)}")

                        # Post completion event with empty transcription
                        self.event_bus.post_event(
                            Event(
                                event_type=EventType.LISTENING_COMPLETED,
                                data={"transcription": "", "error": str(e)},
                                priority=EventPriority.HIGH,
                                source="hearing_service",
                            )
                        )

                # Start the thread
                thread = threading.Thread(target=listen_thread)
                thread.daemon = True
                thread.start()

                return True

            except Exception as e:
                self.handle_error(e, "Error starting listening")
                self.currently_listening = False
                return False
        else:
            logger.warning("No hearing client available")
            self.currently_listening = False
            return False

    def listen_for_wake_word(self) -> bool:
        """
        Listen for wake word

        Returns:
            bool: True if wake word detected, False otherwise
        """
        if self.hearing_client and hasattr(self.hearing_client, "listen_for_wake_word"):
            try:
                # Start listening for wake word in a separate thread
                import threading

                def wake_word_thread():
                    try:
                        # Listen for wake word
                        detected = self.hearing_client.listen_for_wake_word()

                        if detected:
                            # Post wake word event
                            self.event_bus.post_event(
                                Event(
                                    event_type=EventType.WAKE_WORD_DETECTED,
                                    priority=EventPriority.HIGH,
                                    source="hearing_service",
                                )
                            )

                    except Exception as e:
                        logger.error(f"Error in wake word thread: {str(e)}")

                # Start the thread
                thread = threading.Thread(target=wake_word_thread)
                thread.daemon = True
                thread.start()

                return True

            except Exception as e:
                self.handle_error(e, "Error listening for wake word")
                return False

        return False

    def shutdown(self) -> bool:
        """Shutdown the hearing service"""
        # Stop any active listening
        if self.hearing_client and hasattr(self.hearing_client, "close"):
            try:
                self.hearing_client.close()
            except Exception as e:
                logger.error(f"Error closing hearing client: {str(e)}")

        # Unregister handlers
        super().shutdown()

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get component status information"""
        status = super().get_status()

        # Add hearing-specific status
        status.update(
            {
                "currently_listening": self.currently_listening,
                "last_transcription": self.last_transcription[:50]
                + ("..." if len(self.last_transcription) > 50 else ""),
                "wake_word": self.wake_word,
                "hotkey": self.hotkey,
            }
        )

        return status


class VisionService(ServiceComponent):
    """Vision service component for screen capture, OCR, and object detection"""

    def __init__(self, name, event_bus, state_machine, config=None):
        """Initialize the vision service component"""
        super().__init__(name, event_bus, state_machine, config)

        self.vision_core = None
        self.last_capture_path = None
        self.last_ocr_text = ""
        self.last_detected_elements = []
        self.capture_directory = "data/captures"
        self.capture_method = self.config.get("capture_method", "auto")
        self.use_ocr = self.config.get("use_ocr", True)
        self.use_object_detection = self.config.get("use_object_detection", True)

    def _register_handlers(self):
        """Register event handlers for the vision service"""
        # Create handler for vision events
        vision_handler = self.event_bus.create_handler(
            callback=self._handle_vision_event,
            event_types=[
                EventType.SCREEN_CAPTURED,
                EventType.ELEMENT_DETECTED,
                EventType.OCR_RESULT,
            ],
        )

        # Register the handler
        handler_id = self.event_bus.register_handler(vision_handler)
        self.handler_ids.append(handler_id)

    def initialize(self) -> bool:
        """Initialize the vision service"""
        super().initialize()

        logger.info("Initializing vision service")

        try:
            # Create capture directory if it doesn't exist
            os.makedirs(self.capture_directory, exist_ok=True)

            # Try to import vision class
            try:
                from services.vision.vision_core import VisionCore

                logger.info("Using VisionCore class")

                # Initialize vision core
                self.vision_core = VisionCore()

                # Set capture directory
                if hasattr(self.vision_core, "capture_directory"):
                    self.vision_core.capture_directory = self.capture_directory

                # Check if vision AI is available
                has_vision_ai = (
                    hasattr(self.vision_core, "vision_ai")
                    and self.vision_core.vision_ai is not None
                )

                logger.info(f"Vision AI available: {has_vision_ai}")

                self.status = ComponentStatus.READY
                logger.info("Vision service initialized successfully")
                return True

            except ImportError:
                logger.warning("VisionCore class not available - using placeholder")
                self._create_placeholder_client()
                self.status = ComponentStatus.READY
                return True

        except Exception as e:
            self.handle_error(e, "Failed to initialize vision service")
            return False

    def _create_placeholder_client(self):
        """Create a placeholder vision client for testing"""

        # Create a simple object with the required methods
        class PlaceholderVisionCore:
            def __init__(self):
                self.capture_directory = "data/captures"
                self.vision_ai = None

            def capture_screen(self, mode="full_screen", region=None):
                import time

                return f"data/captures/placeholder_{int(time.time())}.png"

            def analyze_screen(self, image_path=None):
                return {
                    "ocr_text": "This is a placeholder OCR text",
                    "ui_elements": [],
                    "timestamp": time.time(),
                    "image_path": image_path
                    or f"data/captures/placeholder_{int(time.time())}.png",
                }

            def detect_ui_elements(self, image_path):
                return []

        self.vision_core = PlaceholderVisionCore()

    def _handle_vision_event(self, event: Event):
        """Handle vision events"""
        event_type = event.event_type

        if event_type == EventType.SCREEN_CAPTURED:
            # Extract image path from event
            image_path = event.get("image_path", "")

            if not image_path:
                logger.warning("Received screen capture event with no image path")
                return

            # Process the captured screen
            self._process_captured_screen(image_path)

        elif event_type == EventType.ELEMENT_DETECTED:
            # Extract elements from event
            elements = event.get("elements", [])

            if not elements:
                logger.warning("Received element detection event with no elements")
                return

            # Update last detected elements
            self.last_detected_elements = elements

        elif event_type == EventType.OCR_RESULT:
            # Extract OCR text from event
            ocr_text = event.get("text", "")

            if not ocr_text:
                logger.warning("Received OCR event with no text")
                return

            # Update last OCR text
            self.last_ocr_text = ocr_text

    def _process_captured_screen(self, image_path: str):
        """
        Process a captured screen image

        Args:
            image_path: Path to the captured image
        """
        # Update last capture path
        self.last_capture_path = image_path

        # Analyze the screen
        if self.vision_core:
            try:
                # Run analysis
                analysis = self.vision_core.analyze_screen(image_path)

                # Extract OCR text if available
                if "ocr_text" in analysis and analysis["ocr_text"]:
                    self.last_ocr_text = analysis["ocr_text"]

                    # Post OCR result event
                    self.event_bus.post_event(
                        Event(
                            event_type=EventType.OCR_RESULT,
                            data={
                                "text": analysis["ocr_text"],
                                "image_path": image_path,
                            },
                            priority=EventPriority.NORMAL,
                            source="vision_service",
                        )
                    )

                # Extract UI elements if available
                if "ui_elements" in analysis and analysis["ui_elements"]:
                    self.last_detected_elements = analysis["ui_elements"]

                    # Post element detection event
                    self.event_bus.post_event(
                        Event(
                            event_type=EventType.ELEMENT_DETECTED,
                            data={
                                "elements": analysis["ui_elements"],
                                "image_path": image_path,
                            },
                            priority=EventPriority.NORMAL,
                            source="vision_service",
                        )
                    )

            except Exception as e:
                self.handle_error(e, "Error analyzing screen")

    def capture_screen(
        self, mode: str = "full_screen", region: Dict[str, int] = None
    ) -> Optional[str]:
        """
        Capture the screen

        Args:
            mode: Capture mode (full_screen, active_window, specific_region)
            region: Screen region to capture (if mode is specific_region)

        Returns:
            Path to the captured image, or None if failed
        """
        if self.vision_core:
            try:
                # Capture screen
                image_path = self.vision_core.capture_screen(mode=mode, region=region)

                if image_path:
                    # Update last capture path
                    self.last_capture_path = image_path

                    # Post screen captured event
                    self.event_bus.post_event(
                        Event(
                            event_type=EventType.SCREEN_CAPTURED,
                            data={"image_path": image_path, "mode": mode},
                            priority=EventPriority.NORMAL,
                            source="vision_service",
                        )
                    )

                    return image_path
                else:
                    logger.warning("Failed to capture screen")
                    return None

            except Exception as e:
                self.handle_error(e, "Error capturing screen")
                return None
        else:
            logger.warning("No vision core available")
            return None

    def analyze_screen(self, image_path: str = None) -> Dict[str, Any]:
        """
        Analyze the screen

        Args:
            image_path: Path to the image to analyze, or None to capture a new one

        Returns:
            Analysis results
        """
        if not image_path:
            # Capture a new image
            image_path = self.capture_screen()

            if not image_path:
                return {"error": "Failed to capture screen"}

        if self.vision_core:
            try:
                # Analyze screen
                analysis = self.vision_core.analyze_screen(image_path)

                # Extract OCR text if available
                if "ocr_text" in analysis and analysis["ocr_text"]:
                    self.last_ocr_text = analysis["ocr_text"]

                # Extract UI elements if available
                if "ui_elements" in analysis and analysis["ui_elements"]:
                    self.last_detected_elements = analysis["ui_elements"]

                return analysis

            except Exception as e:
                self.handle_error(e, "Error analyzing screen")
                return {"error": str(e)}
        else:
            logger.warning("No vision core available")
            return {"error": "No vision core available"}

    def detect_ui_elements(self, image_path: str = None) -> List[Dict[str, Any]]:
        """
        Detect UI elements in the given image

        Args:
            image_path: Path to the image to analyze, or None to capture a new one

        Returns:
            List of detected UI elements
        """
        if not image_path:
            # Capture a new image
            image_path = self.capture_screen()

            if not image_path:
                return []

        if self.vision_core and hasattr(self.vision_core, "detect_ui_elements"):
            try:
                # Detect UI elements
                elements = self.vision_core.detect_ui_elements(image_path)

                # Update last detected elements
                self.last_detected_elements = elements

                return elements

            except Exception as e:
                self.handle_error(e, "Error detecting UI elements")
                return []
        else:
            logger.warning("UI element detection not available")
            return []

    def extract_text(self, image_path: str = None) -> str:
        """
        Extract text from the given image using OCR

        Args:
            image_path: Path to the image to analyze, or None to capture a new one

        Returns:
            Extracted text
        """
        if not image_path:
            # Capture a new image
            image_path = self.capture_screen()

            if not image_path:
                return ""

        if self.vision_core and hasattr(self.vision_core, "vision_ocr"):
            try:
                # Run OCR
                text = self.vision_core.vision_ocr.run_ocr(image_path)

                # Update last OCR text
                self.last_ocr_text = text

                return text

            except Exception as e:
                self.handle_error(e, "Error extracting text")
                return ""
        else:
            logger.warning("OCR not available")
            return ""

    def shutdown(self) -> bool:
        """Shutdown the vision service"""
        # Unregister handlers
        super().shutdown()

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get component status information"""
        status = super().get_status()

        # Add vision-specific status
        status.update(
            {
                "last_capture_path": self.last_capture_path,
                "last_ocr_text": self.last_ocr_text[:50]
                + ("..." if len(self.last_ocr_text) > 50 else ""),
                "last_element_count": len(self.last_detected_elements),
                "capture_directory": self.capture_directory,
                "capture_method": self.capture_method,
                "use_ocr": self.use_ocr,
                "use_object_detection": self.use_object_detection,
                "has_vision_ai": bool(
                    self.vision_core
                    and hasattr(self.vision_core, "vision_ai")
                    and self.vision_core.vision_ai
                ),
            }
        )

        return status


class AutomationService(ServiceComponent):
    """Automation service component for PC automation and control"""

    def __init__(self, name, event_bus, state_machine, config=None):
        """Initialize the automation service component"""
        super().__init__(name, event_bus, state_machine, config)

        self.actions = None
        self.last_action = ""
        self.last_action_result = None
        self.mouse_move_duration = self.config.get("mouse_move_duration", 0.2)
        self.typing_interval = self.config.get("typing_interval", 0.1)
        self.failsafe = self.config.get("failsafe", True)

    def _register_handlers(self):
        """Register event handlers for the automation service"""
        # Create handler for automation events
        automation_handler = self.event_bus.create_handler(
            callback=self._handle_automation_event,
            event_types=[
                EventType.AUTOMATION_STARTED,
                EventType.AUTOMATION_COMPLETED,
                EventType.AUTOMATION_ERROR,
            ],
        )

        # Register the handler
        handler_id = self.event_bus.register_handler(automation_handler)
        self.handler_ids.append(handler_id)

    def initialize(self) -> bool:
        """Initialize the automation service"""
        super().initialize()

        logger.info("Initializing automation service")

        try:
            # Try to import automation class
            try:
                from services.automation.automation import Actions

                logger.info("Using Actions class")

                # Initialize automation client
                self.actions = Actions()

                # Configure settings
                if hasattr(self.actions, "configure"):
                    self.actions.configure(
                        mouse_move_duration=self.mouse_move_duration,
                        typing_interval=self.typing_interval,
                        failsafe=self.failsafe,
                    )

                self.status = ComponentStatus.READY
                logger.info("Automation service initialized successfully")
                return True

            except ImportError:
                logger.warning("Actions class not available - using placeholder")
                self._create_placeholder_client()
                self.status = ComponentStatus.READY
                return True

        except Exception as e:
            self.handle_error(e, "Failed to initialize automation service")
            return False

    def _create_placeholder_client(self):
        """Create a placeholder automation client for testing"""

        # Create a simple object with the required methods
        class PlaceholderActions:
            def __init__(self):
                self.screen_width = 1920
                self.screen_height = 1080
                self.pyautogui_available = False

            def configure(self, **kwargs):
                pass

            def move_mouse_to(self, x, y, duration=None):
                logger.info(f"[PLACEHOLDER] Moving mouse to ({x}, {y})")
                return True

            def click(self, button="left", clicks=1):
                logger.info(f"[PLACEHOLDER] Clicking {button} button {clicks} times")
                return True

            def click_at(self, x, y, button="left", clicks=1):
                logger.info(f"[PLACEHOLDER] Clicking {button} button at ({x}, {y})")
                return True

            def type_text(self, text, interval=None):
                logger.info(f"[PLACEHOLDER] Typing: {text}")
                return True

            def press_key(self, key):
                logger.info(f"[PLACEHOLDER] Pressing key: {key}")
                return True

            def get_mouse_position(self):
                return (0, 0)

            def drag_mouse(
                self, start_x, start_y, end_x, end_y, duration=None, button="left"
            ):
                logger.info(
                    f"[PLACEHOLDER] Dragging from ({start_x}, {start_y}) to ({end_x}, {end_y})"
                )
                return True

            def scroll(self, amount=None, direction="down"):
                logger.info(f"[PLACEHOLDER] Scrolling {direction}")
                return True

            def hotkey(self, *keys):
                logger.info(f"[PLACEHOLDER] Pressing hotkey: {', '.join(keys)}")
                return True

            def run_shortcut(self, shortcut_name):
                logger.info(f"[PLACEHOLDER] Running shortcut: {shortcut_name}")
                return True

            def get_available_shortcuts(self):
                return ["copy", "paste", "save", "select_all"]

            def run_common_task(self, task_name, **kwargs):
                logger.info(f"[PLACEHOLDER] Running task: {task_name}")
                return True

        self.actions = PlaceholderActions()

    def _handle_automation_event(self, event: Event):
        """Handle automation events"""
        event_type = event.event_type

        if event_type == EventType.AUTOMATION_STARTED:
            # Extract action from event
            action = event.get("action", "")
            parameters = event.get("parameters", {})

            if not action:
                logger.warning("Received automation event with no action")
                return

            # Run the action
            self._run_action(action, parameters)

        elif event_type == EventType.AUTOMATION_COMPLETED:
            # Extract result from event
            result = event.get("result", None)
            action = event.get("action", "")

            # Update last action result
            self.last_action_result = result

            # Log success
            logger.info(f"Automation action '{action}' completed successfully")

            # Transition state if needed
            if (
                self.state_machine.current_state
                == self.state_machine.SabrinaState.EXECUTING_TASK
            ):
                self.state_machine.transition_to(self.state_machine.SabrinaState.READY)

        elif event_type == EventType.AUTOMATION_ERROR:
            # Extract error from event
            error = event.get("error", "Unknown error")
            action = event.get("action", "")

            # Log error
            logger.error(f"Automation error in action '{action}': {error}")

            # Transition state if needed
            if (
                self.state_machine.current_state
                == self.state_machine.SabrinaState.EXECUTING_TASK
            ):
                self.state_machine.transition_to(
                    self.state_machine.SabrinaState.ERROR,
                    {
                        "error_info": {
                            "message": error,
                            "source": "automation",
                            "action": action,
                        }
                    },
                )

    def _run_action(self, action: str, parameters: Dict[str, Any]):
        """
        Run an automation action

        Args:
            action: Action to run
            parameters: Action parameters
        """
        # Update last action
        self.last_action = action

        # Check if actions client is available
        if not self.actions:
            logger.warning("No automation client available")

            # Post error event
            self.event_bus.post_event(
                Event(
                    event_type=EventType.AUTOMATION_ERROR,
                    data={"error": "No automation client available", "action": action},
                    priority=EventPriority.HIGH,
                    source="automation_service",
                )
            )

            return

        # Check if action is available
        if not hasattr(self.actions, action):
            logger.warning(f"Action '{action}' not available")

            # Post error event
            self.event_bus.post_event(
                Event(
                    event_type=EventType.AUTOMATION_ERROR,
                    data={
                        "error": f"Action '{action}' not available",
                        "action": action,
                    },
                    priority=EventPriority.HIGH,
                    source="automation_service",
                )
            )

            return

        # Get the action method
        action_method = getattr(self.actions, action)

        # Check if it's callable
        if not callable(action_method):
            logger.warning(f"Action '{action}' is not callable")

            # Post error event
            self.event_bus.post_event(
                Event(
                    event_type=EventType.AUTOMATION_ERROR,
                    data={
                        "error": f"Action '{action}' is not callable",
                        "action": action,
                    },
                    priority=EventPriority.HIGH,
                    source="automation_service",
                )
            )

            return

        # Run the action in a separate thread
        import threading

        def action_thread():
            try:
                # Run the action
                result = action_method(**parameters)

                # Update last action result
                self.last_action_result = result

                # Post completion event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.AUTOMATION_COMPLETED,
                        data={"result": result, "action": action},
                        priority=EventPriority.NORMAL,
                        source="automation_service",
                    )
                )

            except Exception as e:
                # Log error
                logger.error(f"Error in automation action '{action}': {str(e)}")

                # Post error event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.AUTOMATION_ERROR,
                        data={"error": str(e), "action": action},
                        priority=EventPriority.HIGH,
                        source="automation_service",
                    )
                )

        # Start the thread
        thread = threading.Thread(target=action_thread)
        thread.daemon = True
        thread.start()

    def execute_task(self, action: str, **kwargs) -> bool:
        """
        Execute an automation task

        Args:
            action: Action to execute
            **kwargs: Additional parameters for the action

        Returns:
            bool: True if task was started, False otherwise
        """
        # Update state
        self.state_machine.transition_to(
            self.state_machine.SabrinaState.EXECUTING_TASK,
            {"task_info": {"action": action, "parameters": kwargs}},
        )

        # Post event to trigger action
        self.event_bus.post_event(
            Event(
                event_type=EventType.AUTOMATION_STARTED,
                data={"action": action, "parameters": kwargs},
                priority=EventPriority.HIGH,
                source="automation_service",
            )
        )

        return True

    def shutdown(self) -> bool:
        """Shutdown the automation service"""
        # Unregister handlers
        super().shutdown()

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get component status information"""
        status = super().get_status()

        # Add automation-specific status
        status.update(
            {
                "last_action": self.last_action,
                "mouse_move_duration": self.mouse_move_duration,
                "typing_interval": self.typing_interval,
                "failsafe": self.failsafe,
                "pyautogui_available": getattr(
                    self.actions, "pyautogui_available", False
                )
                if self.actions
                else False,
            }
        )

        return status


class PresenceService(ServiceComponent):
    """Presence service component for AI avatar animation and visual feedback"""

    def __init__(self, name, event_bus, state_machine, config=None):
        """Initialize the presence service component"""
        super().__init__(name, event_bus, state_machine, config)

        self.presence_system = None
        self.current_animation = None
        self.theme = self.config.get("theme", "default")
        self.transparency = self.config.get("transparency", 0.85)
        self.click_through = self.config.get("click_through", False)

    def _register_handlers(self):
        """Register event handlers for the presence service"""
