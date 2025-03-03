#!/usr/bin/env python3
"""
Main Entry Point for Sabrina AI
==============================
Initializes all modules and starts the main loop.
"""

import os
import sys
import logging
import argparse
import traceback

# Import our core system
from core.core import SabrinaCore
from utilities.config_manager import ConfigManager

# Add project directory to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


# Configure logging
log_format = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[logging.FileHandler("logs/sabrina.log"), logging.StreamHandler()],
)
logger = logging.getLogger("sabrina_main")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Sabrina AI - Local AI Assistant")

    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.yaml",
        help="Path to configuration file",
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    parser.add_argument("--no-voice", action="store_true", help="Disable voice output")

    parser.add_argument(
        "--no-vision", action="store_true", help="Disable vision processing"
    )

    parser.add_argument(
        "--no-hearing",
        action="store_true",
        help="Disable voice input (use text input only)",
    )

    parser.add_argument(
        "--console-mode", action="store_true", help="Run in console mode (no GUI)"
    )

    parser.add_argument(
        "--test", action="store_true", help="Run in test mode (initialize and exit)"
    )

    return parser.parse_args()


def setup_directories():
    """Ensure required directories exist"""
    directories = [
        "logs",
        "data",
        "data/captures",
        "config",
        "models",
        "models/vosk-model",
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Ensured directory exists: {directory}")


def create_default_config(config_path: str):
    """Create a default configuration file if it doesn't exist"""
    if not os.path.exists(config_path):
        logger.warning(f"Configuration file not found: {config_path}")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Create a default configuration file
        config_manager = ConfigManager()
        config_manager.save_config(config_path)
        logger.info(f"Created default configuration at: {config_path}")


def apply_command_line_settings(args, config_manager):
    """Apply command line settings to configuration"""
    if args.debug:
        config_manager.set_config("core", "debug_mode", True)
        logger.setLevel(logging.DEBUG)
        logger.info("Debug mode enabled")

    if args.no_voice:
        logger.info("Voice output disabled via command line")
        config_manager.set_config("voice", "enabled", False)

    if args.no_vision:
        logger.info("Vision processing disabled via command line")
        config_manager.set_config("vision", "enabled", False)

    if args.no_hearing:
        logger.info("Voice input disabled via command line")
        config_manager.set_config("hearing", "enabled", False)

    if args.console_mode:
        logger.info("Running in console mode")
        config_manager.set_config("core", "console_mode", True)


def start_services():
    """Start any required services"""
    logger.info("Starting services...")

    # Start voice service
    from utilities.service_starter import start_voice_api

    voice_service_started = start_voice_api(os.path.dirname(__file__))

    if voice_service_started:
        logger.info("Voice API service started successfully")
    else:
        logger.warning(
            "Voice API service could not be started. Voice features may not work correctly."
        )

    # TODO: Add code to start other services

    logger.info("Services started")


def stop_services():
    """Stop any running services"""
    logger.info("Stopping services...")

    # TODO: Add code to stop services

    logger.info("Services stopped")


def main():
    """Main entry point"""
    try:
        print("\n" + "=" * 50)
        print("  Sabrina AI - Enhanced Local AI Assistant  ")
        print("=" * 50 + "\n")

        # Parse command line arguments
        args = parse_arguments()

        # Set up required directories
        setup_directories()

        # Create default configuration if it doesn't exist
        create_default_config(args.config)

        # Initialize configuration
        config_manager = ConfigManager(args.config)

        # Apply command line settings
        apply_command_line_settings(args, config_manager)

        # Start required services
        start_services()

        # Initialize the core system
        logger.info("Initializing Sabrina AI Core...")

        core = SabrinaCore(args.config)

        # Run in test mode or normal mode
        if args.test:
            logger.info("Test mode - initialization complete")
            return 0

        # Run the core system
        logger.info("Starting Sabrina AI main loop...")
        core.run()

        logger.info("Sabrina AI shutdown complete")
        return 0

    except KeyboardInterrupt:
        logger.info("Sabrina AI interrupted by user")
        return 0

    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        logger.critical(traceback.format_exc())
        print(f"Fatal error: {str(e)}")
        return 1

    finally:
        # Ensure services are stopped
        stop_services()


if __name__ == "__main__":
    sys.exit(main())
