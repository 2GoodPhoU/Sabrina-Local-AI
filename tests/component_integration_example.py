#!/usr/bin/env python3
"""
Simplified Component Integration Example for Sabrina AI
======================================================
This script demonstrates the basic functionality of Sabrina AI components
with minimal dependencies and improved error handling.
"""

import os
import sys
import time
import logging
import argparse
import traceback

# Ensure the project directory is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger("simple_integration")

# Global variables to track component availability
COMPONENTS_AVAILABLE = {
    "voice": False,
    "vision": False,
    "automation": False,
    "event_bus": False,
}


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Sabrina AI Simple Integration Example"
    )
    parser.add_argument(
        "--demo",
        choices=["voice", "vision", "automation", "all"],
        default="all",
        help="Which component to demonstrate",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def setup_directories():
    """Ensure required directories exist"""
    dirs = ["logs", "data", "config", "data/captures"]
    for d in dirs:
        os.makedirs(os.path.join(project_dir, d), exist_ok=True)
    logger.info("Created necessary directories")


def init_event_bus():
    """Initialize the event bus with error handling"""
    try:
        # Import with error handling
        try:
            from utilities.event_system import EventBus

            logger.info("Event bus module found")
        except ImportError:
            logger.warning("Could not import event_system module")
            return None

        # Create event bus
        event_bus = EventBus()
        event_bus.start()
        logger.info("Event bus initialized and started")

        # Mark as available
        COMPONENTS_AVAILABLE["event_bus"] = True
        return event_bus
    except Exception as e:
        logger.error(f"Failed to initialize event bus: {str(e)}")
        traceback.print_exc()
        return None


def init_voice_client(event_bus=None):
    """Initialize voice client with fallbacks"""
    try:
        # Try to import the enhanced voice client first
        try:
            from services.voice.voice_api_client import VoiceAPIClient

            logger.info("Found VoiceAPIClient")
            voice_client_class = VoiceAPIClient
        except ImportError:
            logger.warning("VoiceAPIClient not found, voice features will be limited")
            return None

        # Create voice client
        voice_client = voice_client_class("http://localhost:8100")

        # Test connection
        connection_successful = voice_client.test_connection()
        if connection_successful:
            logger.info("Successfully connected to Voice API")
            COMPONENTS_AVAILABLE["voice"] = True
        else:
            logger.warning(
                "Voice API connection failed - voice synthesis will not work"
            )
            print(
                "\nWARNING: Voice API is not running. Start it with: python services/voice/voice_api.py"
            )

        return voice_client
    except Exception as e:
        logger.error(f"Failed to initialize voice client: {str(e)}")
        traceback.print_exc()
        return None


def init_vision_component():
    """Initialize vision component with fallbacks"""
    try:
        # Try to import vision component
        try:
            from services.vision.vision_core import VisionCore

            logger.info("Found VisionCore module")
        except ImportError:
            logger.warning("VisionCore not found, vision features will be unavailable")
            return None

        # Create vision component
        vision_core = VisionCore()

        # Verify core functionality
        if hasattr(vision_core, "capture_screen"):
            logger.info("Vision core initialized successfully")
            COMPONENTS_AVAILABLE["vision"] = True
            return vision_core
        else:
            logger.warning("Vision core missing required methods")
            return None
    except Exception as e:
        logger.error(f"Failed to initialize vision component: {str(e)}")
        traceback.print_exc()
        return None


def init_automation_component():
    """Initialize automation component with fallbacks"""
    try:
        # Try to import automation component
        try:
            from services.automation.automation import Actions

            logger.info("Found Actions module")
        except ImportError:
            logger.warning(
                "Actions module not found, automation features will be unavailable"
            )
            return None

        # Create automation component
        actions = Actions()

        # Check if PyAutoGUI is available
        pyautogui_available = getattr(actions, "pyautogui_available", False)
        if pyautogui_available:
            logger.info("Automation component initialized with PyAutoGUI support")
            COMPONENTS_AVAILABLE["automation"] = True
        else:
            logger.info(
                "Automation component initialized in simulation mode (PyAutoGUI not available)"
            )
            COMPONENTS_AVAILABLE[
                "automation"
            ] = True  # Still mark as available for demo purposes

        return actions
    except Exception as e:
        logger.error(f"Failed to initialize automation component: {str(e)}")
        traceback.print_exc()
        return None


def demonstrate_voice(voice_client):
    """Demonstrate voice capabilities"""
    if not voice_client or not COMPONENTS_AVAILABLE["voice"]:
        print("Voice component not available for demonstration")
        return

    try:
        print("\n=== Voice Component Demonstration ===")

        # Basic speech test
        print("\n1. Testing basic speech synthesis...")
        success = voice_client.speak("Hello! I'm Sabrina, your AI assistant.")

        if success:
            print("✓ Basic speech synthesis working")

            # Test different settings if available
            if hasattr(voice_client, "update_settings"):
                print("\n2. Testing voice settings...")

                # Test different speeds
                voice_client.update_settings({"speed": 1.9})
                voice_client.speak("I can speak faster when needed.")
                time.sleep(2)

                voice_client.update_settings({"speed": 0.2})
                voice_client.speak("Or I can slow down when explaining complex things.")
                time.sleep(2)

                # Reset to normal
                voice_client.update_settings({"speed": 1.0})

                print("✓ Voice settings adjustment working")
        else:
            print("✗ Speech synthesis failed - check if the voice service is running")
            print("  Start it with: python services/voice/voice_api.py")

    except Exception as e:
        print(f"Error during voice demonstration: {str(e)}")
        traceback.print_exc()

    print("\nVoice demonstration completed")


def demonstrate_vision(vision_core):
    """Demonstrate vision capabilities"""
    if not vision_core or not COMPONENTS_AVAILABLE["vision"]:
        print("Vision component not available for demonstration")
        return

    try:
        print("\n=== Vision Component Demonstration ===")

        # Screen capture test
        print("\n1. Testing screen capture...")
        print("Capturing your screen in 3 seconds...")
        time.sleep(3)

        capture_result = vision_core.capture_screen()

        if capture_result and os.path.exists(capture_result):
            print(f"✓ Screen captured successfully: {capture_result}")

            # OCR test
            if hasattr(vision_core, "vision_ocr") and hasattr(
                vision_core.vision_ocr, "run_ocr"
            ):
                print("\n2. Testing OCR functionality...")
                ocr_text = vision_core.vision_ocr.run_ocr(capture_result)

                if ocr_text:
                    print("✓ OCR working - extracted text:")
                    print("-" * 40)
                    print(ocr_text[:300] + ("..." if len(ocr_text) > 300 else ""))
                    print("-" * 40)
                else:
                    print(
                        "⚠ OCR returned no text - either no text in image or OCR not working"
                    )
            else:
                print("⚠ OCR functionality not available")

            # Active window info test
            if hasattr(vision_core, "get_active_window_info"):
                print("\n3. Testing active window detection...")
                window_info = vision_core.get_active_window_info()

                if window_info:
                    print("✓ Active window detection working:")
                    for key, value in window_info.items():
                        print(f"  {key}: {value}")
                else:
                    print("⚠ Could not detect active window information")
            else:
                print("⚠ Active window detection not available")

        else:
            print("✗ Screen capture failed")

    except Exception as e:
        print(f"Error during vision demonstration: {str(e)}")
        traceback.print_exc()

    print("\nVision demonstration completed")


def demonstrate_automation(automation):
    """Demonstrate automation capabilities"""
    if not automation or not COMPONENTS_AVAILABLE["automation"]:
        print("Automation component not available for demonstration")
        return

    try:
        print("\n=== Automation Component Demonstration ===")

        # Check if running in simulation mode
        simulation_mode = not getattr(automation, "pyautogui_available", False)
        if simulation_mode:
            print("\nRunning in simulation mode (PyAutoGUI not available)")
            print("Actions will be logged but not executed")

        # Test mouse movement
        print("\n1. Testing mouse movement...")
        print("Moving mouse to position (100, 100)...")
        automation.move_mouse_to(100, 100, duration=0.5)

        if not simulation_mode:
            print("✓ Mouse movement executed")
            time.sleep(1)
        else:
            print("✓ Mouse movement simulated")

        # Test mouse click
        print("\n2. Testing mouse click...")
        print("Clicking at current position...")
        automation.click()

        if not simulation_mode:
            print("✓ Mouse click executed")
            time.sleep(1)
        else:
            print("✓ Mouse click simulated")

        # Test typing
        if hasattr(automation, "type_text"):
            print("\n3. Testing text typing...")
            print('Typing "Hello from Sabrina AI"...')
            automation.type_text("Hello from Sabrina AI", interval=0.1)

            if not simulation_mode:
                print("✓ Text typing executed")
                time.sleep(1)
            else:
                print("✓ Text typing simulated")
        else:
            print("⚠ Text typing functionality not available")

        # Test keyboard shortcut
        if hasattr(automation, "press_key"):
            print("\n4. Testing keyboard shortcut...")
            print('Pressing "Escape" key...')
            automation.press_key("escape")

            if not simulation_mode:
                print("✓ Key press executed")
            else:
                print("✓ Key press simulated")
        else:
            print("⚠ Keyboard shortcut functionality not available")

    except Exception as e:
        print(f"Error during automation demonstration: {str(e)}")
        traceback.print_exc()

    print("\nAutomation demonstration completed")


def demonstrate_basic_integration(components):
    """Demonstrate basic integration between available components"""
    print("\n=== Basic Component Integration Demonstration ===")

    voice_client = components.get("voice")
    vision_core = components.get("vision")
    automation = components.get("automation")

    if not (voice_client and vision_core):
        print("Cannot demonstrate integration - need both voice and vision components")
        return

    try:
        # Vision to Voice integration
        print("\n1. Testing Vision → Voice integration...")
        print("Capturing screen and reading text aloud...")

        # Capture screen
        image_path = vision_core.capture_screen()
        if image_path and os.path.exists(image_path):
            # Extract text
            ocr_text = vision_core.vision_ocr.run_ocr(image_path)
            if ocr_text:
                # Speak the text
                trimmed_text = ocr_text[:200] + ("..." if len(ocr_text) > 200 else "")
                voice_client.speak(
                    f"I can see text on your screen. Here's what I found: {trimmed_text}"
                )
                print("✓ Successfully extracted text from screen and read it aloud")
            else:
                voice_client.speak("I captured your screen but couldn't find any text.")
                print("⚠ Screen captured but no text was found")
        else:
            voice_client.speak(
                "I tried to capture your screen but encountered a problem."
            )
            print("✗ Screen capture failed")

        # Automation with Voice feedback
        if automation:
            print("\n2. Testing Automation → Voice integration...")
            print("Moving mouse with voice feedback...")

            voice_client.speak(
                "I'll now move the mouse cursor to position 200, 200 on your screen."
            )
            automation.move_mouse_to(200, 200, duration=1.0)
            voice_client.speak("Mouse movement complete.")

            print("✓ Successfully coordinated automation with voice feedback")

    except Exception as e:
        print(f"Error during integration demonstration: {str(e)}")
        traceback.print_exc()

    print("\nBasic integration demonstration completed")


def main():
    """Main function"""
    # Parse arguments
    args = parse_arguments()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Welcome message
    print("\n===== Sabrina AI Simple Integration Example =====")
    print("This script demonstrates the basic functionality")
    print("of individual Sabrina AI components and their integration.")

    # Setup environment
    setup_directories()

    # Initialize components
    print("\nInitializing components...")
    event_bus = init_event_bus()
    voice_client = init_voice_client(event_bus)
    vision_core = init_vision_component()
    automation = init_automation_component()

    # Store available components
    components = {
        "event_bus": event_bus,
        "voice": voice_client,
        "vision": vision_core,
        "automation": automation,
    }

    # Report component status
    print("\nComponent Status:")
    for name, available in COMPONENTS_AVAILABLE.items():
        status = "✓ Available" if available else "✗ Not Available"
        print(f"  {name.capitalize()}: {status}")

    # Run demonstrations based on arguments
    if args.demo == "all" or args.demo == "voice":
        if COMPONENTS_AVAILABLE["voice"]:
            demonstrate_voice(voice_client)

    if args.demo == "all" or args.demo == "vision":
        if COMPONENTS_AVAILABLE["vision"]:
            demonstrate_vision(vision_core)

    if args.demo == "all" or args.demo == "automation":
        if COMPONENTS_AVAILABLE["automation"]:
            demonstrate_automation(automation)

    if args.demo == "all":
        # Check if we can demonstrate integration
        can_demonstrate_integration = (
            COMPONENTS_AVAILABLE["voice"] and COMPONENTS_AVAILABLE["vision"]
        )

        if can_demonstrate_integration:
            demonstrate_basic_integration(components)
        else:
            print(
                "\nCannot demonstrate component integration - need both voice and vision components"
            )

    # Clean up
    if event_bus:
        event_bus.stop()

    print("\n===== Demonstration Complete =====")


if __name__ == "__main__":
    main()
