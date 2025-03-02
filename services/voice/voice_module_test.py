#!/usr/bin/env python3
"""
Voice Module Test Script for Sabrina AI
======================================
This script tests the voice service and client components.

Usage:
    python voice_module_test.py [--url URL] [--test TEST_NAME]

Options:
    --url URL        Voice API URL (default: http://localhost:8100)
    --test TEST_NAME Run a specific test (status, speak, voices, settings, all)
"""

import os
import sys
import time
import logging
import argparse
import requests
import subprocess

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger("voice_test")

# Add parent directory to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the voice client
try:
    from voice_api_client import VoiceAPIClient
    from enhanced_voice_client import EnhancedVoiceClient
except ImportError:
    logger.error(
        "Could not import VoiceAPIClient. Make sure the module is in the correct path."
    )
    sys.exit(1)

# Import event bus if available for enhanced tests
try:
    from utilities.event_system import EventBus

    event_bus_available = True
except ImportError:
    logger.warning("EventBus not available. Enhanced tests will be limited.")
    event_bus_available = False


def get_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Test the Voice API service")
    parser.add_argument(
        "--url", type=str, default="http://localhost:8100", help="Voice API URL"
    )
    parser.add_argument(
        "--test",
        type=str,
        default="all",
        choices=["status", "speak", "voices", "settings", "enhanced", "all"],
        help="Test to run",
    )
    parser.add_argument(
        "--start-service",
        action="store_true",
        help="Start voice service if not running",
    )
    return parser.parse_args()


def check_service(url):
    """Check if the voice service is running"""
    try:
        response = requests.get(f"{url}/status", timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False


def start_voice_service():
    """Start the voice service"""
    logger.info("Starting voice service...")
    script_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "services", "voice", "voice_api.py"
        )
    )

    if not os.path.exists(script_path):
        logger.error(f"Voice API script not found: {script_path}")
        return False

    # Start the service in a separate process
    try:
        if sys.platform == "win32":
            # Windows
            subprocess.Popen(
                [sys.executable, script_path],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            # Linux/Mac
            subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

        # Wait for service to start
        logger.info("Waiting for voice service to start...")
        for _ in range(10):  # Try for 10 seconds
            time.sleep(1)
            if check_service("http://localhost:8100"):
                logger.info("Voice service started successfully")
                return True

        logger.error("Voice service did not start within the timeout period")
        return False

    except Exception as e:
        logger.error(f"Error starting voice service: {str(e)}")
        return False


def test_status(client):
    """Test the status endpoint"""
    logger.info("Testing status endpoint...")
    connected = client.test_connection()

    if connected:
        logger.info("✓ Voice API is running")
        return True
    else:
        logger.error("✗ Voice API is not running")
        return False


def test_speak(client):
    """Test the speak functionality"""
    logger.info("Testing speak functionality...")
    texts = [
        "Hello, I am Sabrina, your AI assistant.",
        "I can help you with tasks, answer questions, and automate your computer.",
        "What would you like me to do today?",
    ]

    success_count = 0
    for text in texts:
        logger.info(f"Speaking: {text}")
        result = client.speak(text)

        if result:
            logger.info("✓ Speech generated successfully")
            success_count += 1
        else:
            logger.error("✗ Failed to generate speech")

    logger.info(f"Speak test: {success_count}/{len(texts)} successful")
    return success_count == len(texts)


def test_voices(client):
    """Test the voices endpoint"""
    logger.info("Testing voices endpoint...")
    voices = client.get_voices()

    if voices:
        logger.info(f"✓ Retrieved {len(voices)} voices: {', '.join(voices)}")
        return True
    else:
        logger.error("✗ Failed to retrieve voices")
        return False


def test_settings(client):
    """Test the settings endpoints"""
    logger.info("Testing settings endpoints...")

    # Get current settings
    settings = client.get_settings()
    if not settings:
        logger.error("✗ Failed to get current settings")
        return False

    logger.info(f"✓ Current settings: {settings}")

    # Test updating settings
    new_settings = {"speed": 1.2, "pitch": 0.9, "volume": 0.85}

    logger.info(f"Updating settings: {new_settings}")
    result = client.update_settings(new_settings)

    if result:
        logger.info("✓ Settings updated successfully")

        # Verify settings were updated
        updated_settings = client.get_settings()

        # Check if settings match
        settings_match = all(
            updated_settings.get(key) == value for key, value in new_settings.items()
        )

        if settings_match:
            logger.info("✓ Settings verification successful")
        else:
            logger.error("✗ Settings verification failed")
            logger.error(f"Expected: {new_settings}")
            logger.error(f"Actual: {updated_settings}")
            return False

        # Test effect of settings
        logger.info("Testing speech with new settings...")
        speak_result = client.speak(
            "This is a test with new voice settings. Do I sound different?"
        )

        if speak_result:
            logger.info("✓ Speech with new settings generated successfully")
        else:
            logger.error("✗ Failed to generate speech with new settings")
            return False

        # Restore original settings
        logger.info("Restoring original settings...")
        restore_result = client.update_settings(
            {key: settings.get(key) for key in new_settings.keys()}
        )

        if restore_result:
            logger.info("✓ Original settings restored")
        else:
            logger.error("✗ Failed to restore original settings")
            return False

        return True
    else:
        logger.error("✗ Failed to update settings")
        return False


def test_enhanced_client():
    """Test the enhanced voice client with event bus"""
    if not event_bus_available:
        logger.warning("EventBus not available. Skipping enhanced client test.")
        return False

    logger.info("Testing enhanced voice client with event bus...")

    # Create event bus
    event_bus = EventBus()
    event_bus.start()

    # Create enhanced client
    client = EnhancedVoiceClient(api_url="http://localhost:8100", event_bus=event_bus)

    # Track events
    events_received = []

    # Create event handler
    def event_handler(event):
        logger.info(f"Received event: {event}")
        events_received.append(event)

    # Register event handler for the correct event type
    handler_id = event_bus.register_handler(
        event_bus.create_event_handler(
            event_types=[
                "VOICE_STATUS"
            ],  # Make sure this matches what the client is sending
            callback=event_handler,
        )
    )

    # Test speaking
    logger.info("Testing speaking with events...")
    result = client.speak(
        "This is a test of the enhanced voice client with event notifications."
    )

    # Wait for events to be processed
    time.sleep(1)

    # Check results
    success = (
        result
        and len(events_received) >= 2
        and any(e.data.get("status") == "speaking_started" for e in events_received)
        and any(e.data.get("status") == "speaking_completed" for e in events_received)
    )

    if success:
        logger.info("✓ Enhanced client test successful")
    else:
        logger.error("✗ Enhanced client test failed")
        logger.error(f"  - Speech result: {result}")
        logger.error(f"  - Events received: {len(events_received)}")

    # Clean up
    event_bus.unregister_handler(handler_id)
    event_bus.stop()

    return success


def run_tests(args):
    """Run the specified tests"""
    # Create client
    client = VoiceAPIClient(api_url=args.url)

    # Track test results
    results = {}

    if args.test == "status" or args.test == "all":
        results["status"] = test_status(client)

    if args.test == "speak" or args.test == "all":
        results["speak"] = test_speak(client)

    if args.test == "voices" or args.test == "all":
        results["voices"] = test_voices(client)

    if args.test == "settings" or args.test == "all":
        results["settings"] = test_settings(client)

    if args.test == "enhanced" or args.test == "all":
        results["enhanced"] = test_enhanced_client()

    # Print summary
    print("\n" + "=" * 50)
    print("  VOICE MODULE TEST RESULTS  ".center(50))
    print("=" * 50)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name:20}: {status}")

    print("=" * 50)

    # Check if all tests passed
    all_passed = all(results.values())
    return all_passed


def main():
    """Main entry point"""
    args = get_args()

    # Check if service is running
    if not check_service(args.url):
        logger.warning(f"Voice service not running at {args.url}")

        if args.start_service:
            if not start_voice_service():
                logger.error("Could not start voice service")
                return 1
        else:
            logger.info("Use --start-service to start the voice service automatically")
            return 1

    # Run tests
    success = run_tests(args)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
