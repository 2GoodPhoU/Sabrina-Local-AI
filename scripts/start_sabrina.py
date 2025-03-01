#!/usr/bin/env python3
"""
Sabrina AI Startup Script
=========================
This script initializes and starts the Sabrina AI system with proper
error handling and component initialization.
"""

import os
import sys
import logging
import argparse
import traceback

# Import core system components
from core.enhanced_sabrina_core import SabrinaCore
from utilities.config_manager import ConfigManager

# Ensure the project directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler("logs/sabrina.log"), logging.StreamHandler()],
)

logger = logging.getLogger("sabrina_startup")


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

    return parser.parse_args()


def setup_directories():
    """Ensure required directories exist"""
    directories = ["logs", "data", "config", "models"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Ensured directory exists: {directory}")


def ensure_config_exists(config_path: str):
    """Ensure the configuration file exists, create if it doesn't"""
    if not os.path.exists(config_path):
        logger.warning(f"Configuration file not found: {config_path}")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Create a minimal configuration file
        config_manager = ConfigManager()
        config_manager.save_config(config_path)
        logger.info(f"Created default configuration at: {config_path}")


def apply_command_line_settings(args, config_manager: ConfigManager):
    """Apply command line settings to configuration"""
    if args.debug:
        config_manager.set_config("core", "debug_mode", True)
        logger.setLevel(logging.DEBUG)
        logger.info("Debug mode enabled")

    if args.no_voice:
        logger.info("Voice output disabled via command line")
        # Set voice settings to indicate it's disabled
        config_manager.set_config("voice", "enabled", False)

    if args.no_vision:
        logger.info("Vision processing disabled via command line")
        # Set vision settings to indicate it's disabled
        config_manager.set_config("vision", "enabled", False)


def main():
    """Main entry point"""
    try:
        # Parse command line arguments
        args = parse_arguments()

        # Set up required directories
        setup_directories()

        # Ensure configuration file exists
        ensure_config_exists(args.config)

        # Initialize configuration
        config_manager = ConfigManager(args.config)

        # Apply command line settings
        apply_command_line_settings(args, config_manager)

        # Initialize the core system
        logger.info("Initializing Sabrina AI Core...")

        core = SabrinaCore(args.config)

        # Run the core system
        logger.info("Starting Sabrina AI...")
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


if __name__ == "__main__":
    sys.exit(main())
