#!/usr/bin/env python3
"""
Integration Test Script for Sabrina AI
====================================
This script tests the integration between all Sabrina AI components.
"""

import os
import sys
import time
import logging
import queue

# Import core modules
from utilities.config_manager import ConfigManager
from utilities.error_handler import ErrorHandler
from utilities.event_system import EventBus, EventType, Event, EventPriority
from services.voice.voice_api_client import VoiceAPIClient
from services.vision.vision_core import VisionCore
from services.automation.automation import Actions

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.FileHandler("logs/integration_test.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("integration_test")


class IntegrationTester:
    """Class to test integration between Sabrina AI components"""

    def __init__(self, config_path="config/settings.yaml"):
        """Initialize the integration tester"""
        self.config_path = config_path
        self.config_manager = None
        self.error_handler = None
        self.event_bus = None
        self.voice_client = None
        self.vision_core = None
        self.automation = None

        # Event processing
        self.event_queue = queue.Queue()
        self.running = False

        # Test results
        self.test_results = {
            "config_manager": False,
            "error_handler": False,
            "event_bus": False,
            "voice_client": False,
            "vision_core": False,
            "automation": False,
        }

    def initialize_components(self):
        """Initialize all components"""
        logger.info("Initializing components")

        try:
            # Initialize configuration manager
            logger.info("Initializing ConfigManager")
            self.config_manager = ConfigManager(self.config_path)
            self.test_results["config_manager"] = True

            # Initialize error handler
            logger.info("Initializing ErrorHandler")
            self.error_handler = ErrorHandler(self.config_manager)
            self.test_results["error_handler"] = True

            # Initialize event bus
            logger.info("Initializing EventBus")
            self.event_bus = EventBus()
            self.event_bus.start()
            self.test_results["event_bus"] = True

            # Register event handlers
            self._register_event_handlers()

            # Initialize voice client
            logger.info("Initializing VoiceAPIClient")
            voice_config = self.config_manager.get_config("voice", {})
            voice_api_url = voice_config.get("api_url", "http://localhost:8100")
            self.voice_client = VoiceAPIClient(voice_api_url)
            connected = self.voice_client.test_connection()

            if connected:
                logger.info("Voice API connected successfully")
                self.test_results["voice_client"] = True
            else:
                logger.warning("Voice API connection failed")

            # Initialize vision core
            logger.info("Initializing VisionCore")
            self.vision_core = VisionCore()
            self.test_results["vision_core"] = True

            # Initialize automation
            logger.info("Initializing Actions")
            self.automation = Actions()
            self.test_results["automation"] = True

            logger.info("All components initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing components: {str(e)}")
            return False

    def _register_event_handlers(self):
        """Register event handlers"""
        # Register handler for user input events
        self.event_bus.register_handler(
            self.event_bus.create_event_handler(
                event_types=[EventType.USER_INPUT],
                callback=self._handle_user_input_event,
                min_priority=EventPriority.NORMAL,
            )
        )

        # Register handler for voice output events
        self.event_bus.register_handler(
            self.event_bus.create_event_handler(
                event_types=[EventType.VOICE],
                callback=self._handle_voice_event,
                min_priority=EventPriority.NORMAL,
            )
        )

        # Register handler for vision events
        self.event_bus.register_handler(
            self.event_bus.create_event_handler(
                event_types=[EventType.VISION],
                callback=self._handle_vision_event,
                min_priority=EventPriority.NORMAL,
            )
        )

        # Register handler for automation events
        self.event_bus.register_handler(
            self.event_bus.create_event_handler(
                event_types=[EventType.AUTOMATION],
                callback=self._handle_automation_event,
                min_priority=EventPriority.NORMAL,
            )
        )

    def _handle_user_input_event(self, event):
        """Handle user input event"""
        logger.info(f"Received user input event: {event.data}")

        # Get user input from event
        user_input = event.data.get("text", "")

        if not user_input:
            return

        # Process user input
        if user_input.lower() == "exit":
            logger.info("Exit command received")
            self.running = False
            return

        # Add response to event queue
        self.event_queue.put({"type": "response", "text": f"You said: {user_input}"})

        # Send a voice event
        self.event_bus.post_event(
            Event(
                event_type=EventType.VOICE,
                data={"text": f"You said: {user_input}"},
                source="integration_test",
            )
        )

        # If "capture" command, capture screen
        if "capture" in user_input.lower():
            self.event_bus.post_event(
                Event(
                    event_type=EventType.VISION,
                    data={"command": "capture"},
                    source="integration_test",
                )
            )

        # If "click" command, simulate click
        if "click" in user_input.lower():
            self.event_bus.post_event(
                Event(
                    event_type=EventType.AUTOMATION,
                    data={"command": "click"},
                    source="integration_test",
                )
            )

    def _handle_voice_event(self, event):
        """Handle voice event"""
        logger.info(f"Received voice event: {event.data}")

        # Get text from event
        text = event.data.get("text", "")

        if not text:
            return

        # Speak the text
        if self.voice_client and self.voice_client.connected:
            self.voice_client.speak(text)

    def _handle_vision_event(self, event):
        """Handle vision event"""
        logger.info(f"Received vision event: {event.data}")

        # Get command from event
        command = event.data.get("command", "")

        if command == "capture":
            # Capture screen
            if self.vision_core:
                image_path = self.vision_core.capture_screen()

                if image_path:
                    # Run OCR on the image
                    ocr_text = self.vision_core.vision_ocr.run_ocr(image_path)

                    # Add OCR result to event queue
                    self.event_queue.put(
                        {
                            "type": "ocr_result",
                            "text": ocr_text,
                            "image_path": image_path,
                        }
                    )

                    # Speak the OCR result
                    self.event_bus.post_event(
                        Event(
                            event_type=EventType.VOICE,
                            data={
                                "text": f"I detected: {ocr_text[:100]}{'...' if len(ocr_text) > 100 else ''}"
                            },
                            source="vision_core",
                        )
                    )

    def _handle_automation_event(self, event):
        """Handle automation event"""
        logger.info(f"Received automation event: {event.data}")

        # Get command from event
        command = event.data.get("command", "")

        if command == "click":
            # Simulate click
            if self.automation:
                self.automation.click()

                # Add click result to event queue
                self.event_queue.put(
                    {"type": "click_result", "text": "Clicked at current position"}
                )

    def run_tests(self):
        """Run integration tests"""
        logger.info("Running integration tests")

        # Initialize components
        if not self.initialize_components():
            logger.error("Component initialization failed")
            return False

        # Start test
        self.running = True

        # Test event bus
        logger.info("Testing event system")
        test_event = Event(
            event_type=EventType.SYSTEM,
            data={"message": "Test event"},
            source="integration_test",
        )
        self.event_bus.post_event(test_event)

        # Test voice client
        if self.voice_client and self.voice_client.connected:
            logger.info("Testing voice client")
            self.voice_client.speak("Testing voice synthesis for Sabrina AI")

        # Test vision core
        if self.vision_core:
            logger.info("Testing vision core")
            image_path = self.vision_core.capture_screen()

            if image_path:
                logger.info(f"Screen captured: {image_path}")

                # Run OCR
                ocr_text = self.vision_core.vision_ocr.run_ocr(image_path)
                logger.info(
                    f"OCR result: {ocr_text[:100]}{'...' if len(ocr_text) > 100 else ''}"
                )

        # Test automation
        if self.automation:
            logger.info("Testing automation")
            # Move mouse to a test position
            self.automation.move_mouse_to(100, 100)
            time.sleep(1)

        # Main test loop
        logger.info("Starting interactive test")
        print("\n" + "=" * 50)
        print("  SABRINA AI - Integration Test  ")
        print("=" * 50)
        print("\nType commands or text to test the system.")
        print("Available commands:")
        print("  capture - Capture the screen and run OCR")
        print("  click - Simulate a mouse click")
        print("  exit - Exit the test")
        print("\n")

        try:
            while self.running:
                # Get user input
                user_input = input("You: ")

                # Send user input event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.USER_INPUT,
                        data={"text": user_input},
                        source="user",
                    )
                )

                # Process events
                self._process_events()

                # Sleep briefly to allow events to be processed
                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Test interrupted by user")

        # Stop event bus
        self.event_bus.stop()

        # Print test results
        self._print_test_results()

        return True

    def _process_events(self):
        """Process events from the event queue"""
        # Process up to 10 events per cycle
        for _ in range(10):
            try:
                # Get event from queue with no timeout
                event = self.event_queue.get_nowait()

                # Process event based on type
                event_type = event.get("type", "")

                if event_type == "response":
                    print(f"Sabrina: {event.get('text', '')}")
                elif event_type == "ocr_result":
                    print(
                        f"OCR: {event.get('text', '')[:100]}{'...' if len(event.get('text', '')) > 100 else ''}"
                    )
                    print(f"Image saved: {event.get('image_path', '')}")
                elif event_type == "click_result":
                    print(f"Click: {event.get('text', '')}")

                # Mark event as done
                self.event_queue.task_done()

            except queue.Empty:
                # No more events in queue
                break

    def _print_test_results(self):
        """Print test results"""
        print("\n" + "=" * 50)
        print("  SABRINA AI - Integration Test Results  ")
        print("=" * 50 + "\n")

        for component, success in self.test_results.items():
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"{component:20}: {status}")

        print("\n" + "=" * 50)


def main():
    """Main function"""
    # Create integration tester
    tester = IntegrationTester()

    # Run tests
    tester.run_tests()


if __name__ == "__main__":
    main()
