#!/usr/bin/env python3
"""
Test script for the Presence System with fixed click-through functionality
This will run a simplified version of the presence system for testing
"""
import sys
import os
from PyQt5.QtWidgets import QApplication

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the necessary modules
from services.presence.gui.presence_gui import PresenceGUI
from services.presence.utils.resource_management import ResourceManager
from services.presence.utils.config_manager import ConfigManager
from services.presence.utils.event_system import EventBus

def test_presence_system():
    """Run the presence system with the fixed code"""
    print("Starting Presence System Test...")
    
    # Create the QApplication instance
    app = QApplication(sys.argv)
    
    # Initialize the core components
    resource_manager = ResourceManager()
    config_manager = ConfigManager()
    event_bus = EventBus()
    
    # Start the event bus
    event_bus.start()
    
    # Create and show the presence GUI
    presence_gui = PresenceGUI(resource_manager, config_manager, event_bus)
    presence_gui.show()
    
    # Log startup message
    print("Presence GUI initialized and shown")
    print("Click-through status:", presence_gui.click_through_enabled)
    print("Interactive regions:", len(presence_gui.selective_widget.interactive_regions))
    
    # Run the application
    exit_code = app.exec_()
    
    # Stop the event bus
    event_bus.stop()
    
    # Clean up resources
    resource_manager.force_cleanup()
    
    return exit_code

if __name__ == "__main__":
    sys.exit(test_presence_system())