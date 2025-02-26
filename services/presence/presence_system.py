# Integration example showing how to use the improved components together
from PyQt5.QtWidgets import QApplication
import sys
import time
import os

# Import the refinements
from error_handling import ErrorHandler, logger
from resource_management import ResourceManager
from config_manager import ConfigManager
from event_system import EventBus, EventType, EventPriority, Event, register_animation_handler, trigger_animation_change

# Integration with presence system
from presence_enhancements import EnhancedPresenceGUI

class ImprovedPresenceSystem:
    """Integration of all presence system improvements"""
    
    def __init__(self):
        """Initialize the improved presence system"""
        # Set up error handling first
        logger.info("Initializing improved presence system")
        
        # Initialize configuration manager
        self.config_manager = ConfigManager()
        
        # Load window configuration
        window_config = self.config_manager.get_config("window")
        animation_config = self.config_manager.get_config("animations")
        
        # Initialize resource manager
        self.resource_manager = ResourceManager()
        
        # Configure resource manager from config
        advanced_config = self.config_manager.get_config("advanced")
        self.resource_manager.cleanup_threshold = advanced_config.get("resource_cleanup_threshold", 10)
        self.resource_manager.max_inactive_time = advanced_config.get("inactive_resource_timeout", 60)
        
        # Start event bus
        self.event_bus = EventBus()
        self.event_bus.start()
        
        # Create QApplication
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # Create presence GUI with config
        self.presence_gui = EnhancedPresenceGUI()
        
        # Apply configuration
        self.apply_config()
        
        # Connect event handlers
        self.register_event_handlers()
    
    def apply_config(self):
        """Apply configuration to the GUI"""
        window_config = self.config_manager.get_config("window")
        
        # Apply window settings
        if window_config:
            self.presence_gui.setGeometry(
                self.presence_gui.x(),
                self.presence_gui.y(),
                window_config.get("width", 500),
                window_config.get("height", 500)
            )
            self.presence_gui.setWindowOpacity(window_config.get("transparency_level", 0.85))
        
        # Apply animation settings
        animation_config = self.config_manager.get_config("animations")
        if animation_config and hasattr(self.presence_gui, "set_animation"):
            default_animation = animation_config.get("default_animation", "idle")
            self.presence_gui.set_animation(default_animation)
        
        # Apply interaction settings
        interaction_config = self.config_manager.get_config("interaction")
        if interaction_config and hasattr(self.presence_gui, "toggle_click_through"):
            if interaction_config.get("click_through_mode", False):
                self.presence_gui.toggle_click_through()
    
    def register_event_handlers(self):
        """Register event handlers"""
        # Register animation change handler
        register_animation_handler(self.handle_animation_event)
        
        # Register system state handler
        self.event_bus.register_handler(
            handler=EventHandler(
                callback=self.handle_system_event,
                event_types=[EventType.SYSTEM_STATE],
                min_priority=EventPriority.LOW
            )
        )
        
        # Register settings change handler
        self.event_bus.register_handler(
            handler=EventHandler(
                callback=self.handle_settings_event,
                event_types=[EventType.SETTINGS_CHANGE],
                min_priority=EventPriority.NORMAL
            )
        )
    
    def handle_animation_event(self, event):
        """Handle animation change events"""
        animation = event.data.get("animation")
        if animation and hasattr(self.presence_gui, "set_animation"):
            logger.info(f"Changing animation to {animation} from {event.source}")
            
            # Use resource manager to track the animation
            animation_path = os.path.join("assets", f"{animation}.gif")
            self.resource_manager.register_resource(
                f"animation_{animation}",
                animation_path
            )
            
            # Set the animation
            self.presence_gui.set_animation(animation)
    
    def handle_system_event(self, event):
        """Handle system state events"""
        state = event.data.get("state")
        logger.info(f"System state changed to {state}")
        
        if state == "shutdown":
            # Clean up resources
            self.resource_manager.force_cleanup()
            # Stop event bus
            self.event_bus.stop()
            # Save configuration
            self.config_manager.save_config()
            # Exit application
            self.app.quit()
    
    def handle_settings_event(self, event):
        """Handle settings change events"""
        setting = event.data.get("setting")
        value = event.data.get("value")
        section = event.data.get("section")
        
        if setting and value and section:
            logger.info(f"Setting {section}.{setting} changed to {value}")
            
            # Update configuration
            self.config_manager.set_config(section, setting, value)
            
            # Apply setting immediately if appropriate
            if section == "window" and setting == "transparency_level":
                self.presence_gui.setWindowOpacity(value)
            elif section == "interaction" and setting == "click_through_mode":
                if value != (self.presence_gui.windowFlags() & Qt.WindowTransparentForInput != 0):
                    self.presence_gui.toggle_click_through()
            
            # Save configuration
            self.config_manager.save_config()
    
    def run(self):
        """Run the presence system"""
        # Post startup event
        self.event_bus.post_event(
            Event(
                event_type=EventType.SYSTEM_STATE,
                data={"state": "startup"},
                priority=EventPriority.HIGH,
                source="presence_system"
            )
        )
        
        # Show the presence GUI
        self.presence_gui.show()
        
        # Start application event loop
        exit_code = self.app.exec_()
        
        # Post shutdown event
        self.event_bus.post_event_immediate(
            Event(
                event_type=EventType.SYSTEM_STATE,
                data={"state": "shutdown"},
                priority=EventPriority.CRITICAL,
                source="presence_system"
            )
        )
        
        return exit_code
    
if __name__ == "__main__":
    # Additional imports needed for this example
    from PyQt5.QtCore import Qt
    from event_system import EventHandler
    
    # Create and run the improved presence system
    presence_system = ImprovedPresenceSystem()
    
    # Example of triggering animation changes through events
    # These could come from other parts of Sabrina
    def trigger_example_animations():
        """Trigger some example animations after startup"""
        import threading
        import time
        
        def animation_sequence():
            # Wait for GUI to initialize
            time.sleep(2)
            
            # Trigger animation changes with different priorities
            trigger_animation_change("listening", EventPriority.NORMAL, "voice_module")
            time.sleep(3)
            
            trigger_animation_change("talking", EventPriority.HIGH, "voice_module")
            time.sleep(3)
            
            trigger_animation_change("working", EventPriority.NORMAL, "automation_module")
            time.sleep(3)
            
            trigger_animation_change("thinking", EventPriority.LOW, "ai_module")
            time.sleep(3)
            
            # Example settings change
            presence_system.event_bus.post_event(
                Event(
                    event_type=EventType.SETTINGS_CHANGE,
                    data={
                        "section": "window",
                        "setting": "transparency_level",
                        "value": 0.7
                    },
                    priority=EventPriority.NORMAL,
                    source="settings_module"
                )
            )
            
            time.sleep(3)
            
            # Return to idle
            trigger_animation_change("idle", EventPriority.NORMAL, "system")
            
        # Start animation sequence in a separate thread
        thread = threading.Thread(target=animation_sequence)
        thread.daemon = True
        thread.start()
    
    # Start example animations
    trigger_example_animations()
    
    # Run the system
    sys.exit(presence_system.run())