#!/usr/bin/env python3
"""
Main entry point for Sabrina's Presence System
Handles initialization, event processing, and lifecycle management
"""

import sys
import os
import argparse
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer

# Import from restructured modules
from .utils.error_handling import ErrorHandler, logger
from .utils.resource_management import ResourceManager
from .utils.config_manager import ConfigManager
from .utils.event_system import EventBus, EventType, EventPriority, Event
from .gui.presence_gui import PresenceGUI

class PresenceSystem:
    """Main Presence System with improved error handling, resource management, and event-driven architecture"""
    
    def __init__(self):
        """Initialize the Sabrina AI Presence System"""
        # Initialize core systems
        self.config_manager = ConfigManager()
        self.resource_manager = ResourceManager()
        self.event_bus = EventBus()
        
        # Log startup
        logger.info("Initializing Sabrina AI Presence System")
        
        # Parse command line arguments
        self.args = self.parse_arguments()
        
        # Create QApplication instance
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Prevent app from quitting when window is closed
        
        # Start the event bus before creating GUI
        logger.info("Starting event bus")
        self.event_bus.start()
        
        # Create presence GUI with resource manager
        logger.info("Creating presence GUI")
        self.presence = PresenceGUI(
            resource_manager=self.resource_manager,
            config_manager=self.config_manager,
            event_bus=self.event_bus
        )
        
        # Apply command line settings
        self.apply_cli_settings()
        
        # Register event handlers
        self.register_event_handlers()
        
        # Start performance monitoring if enabled
        debug_config = self.config_manager.get_config("debug")
        if debug_config and debug_config.get("performance_stats", False):
            self.start_performance_monitoring()
    
    def parse_arguments(self):
        """Parse command line arguments."""
        parser = argparse.ArgumentParser(description="Sabrina AI Presence System")
        parser.add_argument("--theme", help="Start with a specific theme", default=None)
        parser.add_argument("--animation", help="Start with a specific animation state", default=None)
        parser.add_argument("--minimized", help="Start minimized to system tray", action="store_true")
        parser.add_argument("--transparent", help="Enable transparent background", action="store_true")
        parser.add_argument("--opacity", help="Set initial opacity (10-100)", type=int, default=None)
        parser.add_argument("--test", help="Run animation test mode", action="store_true")
        parser.add_argument("--config", help="Path to alternative config file", default=None)
        parser.add_argument("--debug", help="Enable debug mode", action="store_true")
        
        return parser.parse_args()
    
    def apply_cli_settings(self):
        """Apply command line settings, overriding config file values"""
        # Handle custom config file
        if self.args.config:
            try:
                self.config_manager.load_config_from_file(self.args.config)
                logger.info(f"Loaded custom config from {self.args.config}")
            except Exception as e:
                ErrorHandler.log_error(e, f"Failed to load custom config from {self.args.config}")
        
        # Apply theme override if specified
        if self.args.theme:
            self.presence.change_theme(self.args.theme)
            logger.info(f"Set theme to {self.args.theme} from command line argument")
        
        # Apply animation override if specified
        if self.args.animation:
            self.presence.set_animation(self.args.animation)
            logger.info(f"Set animation to {self.args.animation} from command line argument")
        
        # Apply transparency setting if specified
        if self.args.transparent:
            self.presence.setAttribute(Qt.WA_TranslucentBackground)
            logger.info("Enabled transparent background from command line argument")
        
        # Apply opacity setting if specified
        if self.args.opacity is not None:
            opacity = max(10, min(100, self.args.opacity))  # Keep between 10-100
            self.presence.setWindowOpacity(opacity / 100)
            self.presence.settings_menu.transparency_slider.setValue(opacity)
            logger.info(f"Set opacity to {opacity}% from command line argument")
        
        # Set debug mode if specified
        if self.args.debug:
            self.config_manager.set_config("debug", "debug_mode", True)
            logger.info("Enabled debug mode from command line argument")
    
    def register_event_handlers(self):
        """Register event handlers for the system"""
        # Register animation event handler
        animation_handler = self.event_bus.create_event_handler(
            EventType.ANIMATION_CHANGE,
            self.handle_animation_event,
            EventPriority.LOW
        )
        self.event_bus.register_handler(animation_handler)
        
        # Register system event handler
        system_handler = self.event_bus.create_event_handler(
            EventType.SYSTEM_STATE,
            self.handle_system_event,
            EventPriority.LOW
        )
        self.event_bus.register_handler(system_handler)
        
        # Register settings event handler
        settings_handler = self.event_bus.create_event_handler(
            EventType.SETTINGS_CHANGE,
            self.handle_settings_event,
            EventPriority.NORMAL
        )
        self.event_bus.register_handler(settings_handler)
        
        logger.info("Registered event handlers")
    
    def handle_animation_event(self, event):
        """Handle animation change events"""
        animation = event.data.get("animation")
        if animation and hasattr(self.presence, "set_animation"):
            logger.info(f"Changing animation to {animation} from {event.source}")
            self.presence.set_animation(animation)
    
    def handle_system_event(self, event):
        """Handle system state events"""
        state = event.data.get("state")
        logger.info(f"System state changed to {state}")
        
        if state == "shutdown":
            self.shutdown()
    
    def handle_settings_event(self, event):
        """Handle settings change events"""
        setting = event.data.get("setting")
        value = event.data.get("value")
        section = event.data.get("section")
        
        if setting and value is not None and section:
            logger.info(f"Setting {section}.{setting} changed to {value}")
            
            # Update configuration
            self.config_manager.set_config(section, setting, value)
            
            # Apply setting immediately if appropriate
            if section == "window" and setting == "transparency_level":
                self.presence.setWindowOpacity(float(value))
            elif section == "interaction" and setting == "click_through_mode":
                if bool(value) != self.presence.click_through_enabled:
                    self.presence.toggle_click_through()
            
            # Save configuration
            self.config_manager.save_config()
    
    def start_performance_monitoring(self):
        """Start periodic performance monitoring"""
        def check_performance():
            # Get resource statistics
            stats = self.resource_manager.get_resource_stats()
            logger.debug(f"Performance stats: {stats}")
            
            # Check for memory issues
            if stats["memory_usage_mb"] > 500:  # 500MB threshold
                logger.warning(f"High memory usage: {stats['memory_usage_mb']:.2f} MB")
                # Force resource cleanup if memory usage is too high
                if stats["memory_usage_mb"] > 800:  # 800MB threshold
                    logger.warning("Memory usage critical - forcing resource cleanup")
                    self.resource_manager.force_cleanup()
        
        # Check performance every 30 seconds
        self.performance_timer = QTimer()
        self.performance_timer.timeout.connect(check_performance)
        self.performance_timer.start(30000)  # 30 seconds
        logger.info("Started performance monitoring")
    
    def run(self):
        """Run the Sabrina AI Presence System."""
        logger.info("Starting Sabrina AI Presence System")
        
        # Post startup event
        self.event_bus.post_event(
            Event(
                EventType.SYSTEM_STATE,
                {"state": "startup"},
                EventPriority.HIGH,
                "presence_system"
            )
        )
        
        # Show window unless minimized flag is set
        if not self.args.minimized:
            self.presence.show()
            logger.info("Presence window shown")
        else:
            logger.info("Starting minimized to system tray")
        
        # If test mode is enabled, run the animation test sequence
        if self.args.test:
            logger.info("Running in animation test mode")
            self.run_animation_test()
        
        # Start the application event loop
        exit_code = self.app.exec_()
        logger.info(f"Application exited with code {exit_code}")
        
        # Handle shutdown
        self.shutdown()
        return exit_code
    
    def run_animation_test(self):
        """Run a test sequence of animations."""
        from .constants import ANIMATION_STATES
        from PyQt5.QtCore import QTimer
        
        logger.info(f"Available animations: {', '.join(ANIMATION_STATES)}")
        
        # Create a test sequence
        test_sequence = ["idle", "listening", "talking", "working", "thinking", 
                         "error", "success", "waiting", "idle"]
        current_index = 0
        
        def next_animation():
            nonlocal current_index
            if current_index < len(test_sequence):
                state = test_sequence[current_index]
                logger.info(f"Test sequence: Setting animation to {state}")
                self.presence.set_animation(state)
                current_index += 1
                QTimer.singleShot(3000, next_animation)  # 3 second delay
            else:
                logger.info("Animation test sequence completed")
        
        # Start the test sequence
        QTimer.singleShot(1000, next_animation)  # 1 second initial delay
    
    def shutdown(self):
        """Safely shut down the Presence System"""
        logger.info("Shutting down Sabrina AI Presence System")
        
        # Stop performance timer if running
        if hasattr(self, 'performance_timer') and self.performance_timer.isActive():
            self.performance_timer.stop()
        
        # Clean up resources
        self.resource_manager.force_cleanup()
        
        # Stop event bus
        self.event_bus.stop()
        
        # Save configuration
        self.config_manager.save_config()
        
        # Post shutdown event
        self.event_bus.post_event_immediate(
            Event(
                EventType.SYSTEM_STATE,
                {"state": "shutdown_complete"},
                EventPriority.CRITICAL,
                "presence_system"
            )
        )
        
        logger.info("Shutdown complete")

if __name__ == "__main__":
    # Set working directory to script location for asset loading
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Create and run the presence system
    presence_system = PresenceSystem()
    sys.exit(presence_system.run())