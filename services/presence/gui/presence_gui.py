"""
Main GUI component for Sabrina's Presence System
"""
from PyQt5.QtWidgets import QMainWindow, QPushButton, QWidget, QVBoxLayout, QApplication, QSystemTrayIcon
from PyQt5.QtCore import Qt, QPropertyAnimation, QEvent
from PyQt5.QtGui import QMovie, QPixmap, QRegion
import os
import json
import time
import screeninfo

from .animation_label import AnimatedLabel
from .settings_menu import SettingsMenu
from .system_tray import setup_system_tray, show_tray_notification

from ..utils.error_handling import logger, ErrorHandler
from ..utils.resource_management import ResourceManager
from ..utils.config_manager import ConfigManager
from ..utils.event_system import EventBus, EventType, EventPriority, Event
from ..animation.animation_transitions import cross_fade
from ..constants import ANIMATION_STATES, ANIMATION_PRIORITY, ASSETS_FOLDER, DEFAULT_ANIMATION

# Define SelectiveClickThroughWidget before PresenceGUI to ensure it exists
class SelectiveClickThroughWidget(QWidget):
    """Custom widget that allows click-through in some areas but not others"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.interactive_regions = []  # List of QRegion objects that should capture mouse events
        self.click_through_enabled = False
        
    def add_interactive_region(self, region):
        """Add a region that should capture mouse events"""
        self.interactive_regions.append(region)
        
    def clear_interactive_regions(self):
        """Clear all interactive regions"""
        self.interactive_regions = []
        
    def set_click_through(self, enabled):
        """Enable or disable click-through mode"""
        self.click_through_enabled = enabled
        
    def event(self, event):
        """Override event handler to implement selective click-through"""
        # If click-through is disabled, handle events normally
        if not self.click_through_enabled:
            return super().event(event)
            
        # For mouse events, check if they're in an interactive region
        if (event.type() == QEvent.MouseButtonPress or 
            event.type() == QEvent.MouseButtonRelease or 
            event.type() == QEvent.MouseMove or
            event.type() == QEvent.MouseButtonDblClick):
            
            # Check if mouse position is within any interactive region
            mouse_pos = event.pos()
            for region in self.interactive_regions:
                if region.contains(mouse_pos):
                    # In interactive region, handle event normally
                    return super().event(event)
                    
            # Not in any interactive region, let the event pass through (ignore it)
            return False
            
        # Handle all other events normally
        return super().event(event)

class PresenceGUI(QMainWindow):
    """Main Presence GUI with improved error handling, resource management, and event-driven architecture"""
    
    def __init__(self, resource_manager=None, config_manager=None, event_bus=None):
        """Initialize the Presence GUI with improved components"""
        super().__init__()
        
        # Initialize improved components
        self.resource_manager = resource_manager or ResourceManager()
        self.config_manager = config_manager or ConfigManager()
        self.event_bus = event_bus or EventBus()
        
        logger.info("Initializing Presence GUI")
        
        # Load configuration
        window_config = self.config_manager.get_config("window", None, {})
        interaction_config = self.config_manager.get_config("interaction", None, {})
        
        # Get screen dimensions
        try:
            screen = screeninfo.get_monitors()[0]  
            screen_width, screen_height = screen.width, screen.height
        except Exception as e:
            ErrorHandler.log_error(e, "Failed to get screen dimensions")
            # Fallback dimensions
            screen_width, screen_height = 1920, 1080
        
        # Window dimensions from config
        window_width = window_config.get("width", 500)
        window_height = window_config.get("height", 500)
        padding_right = window_config.get("padding_right", 20)

        # Set window position
        self.x_position = screen_width - window_width - padding_right
        self.y_position = (screen_height // 2) - (window_height // 2)

        # Configure window properties - important to set flags here
        self.setGeometry(self.x_position, self.y_position, window_width, window_height)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)  
        
        # Set transparency
        transparency_level = window_config.get("transparency_level", 0.85)

        # Dragging and position locking
        self.drag_enabled = window_config.get("enable_dragging", True) and not window_config.get("lock_position", False)
        self.locked = window_config.get("lock_position", False)
        self.old_pos = None

        # Animation and themes
        themes_config = self.config_manager.get_config("themes", None, {})
        self.current_theme = themes_config.get("default_theme", "default")
        self.themes = self.load_themes()
        
        # Click-through mode - IMPORTANT: This needs to be set BEFORE creating settings_menu
        self.click_through_enabled = interaction_config.get("click_through_mode", False)
        
        # Interactive areas tracking
        self.interactive_areas = []

        # Setup UI Components
        self.setup_ui()
        
        # Initial click-through status - make sure flags are set correctly based on initial state
        if self.click_through_enabled:
            self.setWindowFlags(self.windowFlags() | Qt.WindowTransparentForInput)
            self.show()  # Need to show again after changing flags
            
        # Setup System Tray
        self.tray_icon = setup_system_tray(self)
        
        # Setup Animation Manager with ResourceManager integration
        self.animation_manager = None
        self.load_animation_manager()
        
        self.current_animation = None
        self.animation_opacity = 1.0
        self.transition_in_progress = False
        
        # Set default animation
        animation_config = self.config_manager.get_config("animations", None, {})
        default_animation = animation_config.get("default_animation", DEFAULT_ANIMATION)
        self.set_animation(default_animation)

        # Start event listener
        self.start_event_listener()
        
        # Log successful initialization
        logger.info("Presence GUI initialized successfully")

    def setup_ui(self):
        """Initialize the UI components with improved layout"""
        # Create the selective widget first
        self.selective_widget = SelectiveClickThroughWidget(self)
        self.setCentralWidget(self.selective_widget)
        
        # Main layout for the selective widget
        self.main_layout = QVBoxLayout(self.selective_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create animation container with absolute positioning
        self.animation_container = QWidget()
        self.animation_container.setLayout(QVBoxLayout())
        self.animation_container.layout().setContentsMargins(0, 0, 0, 0)
        
        # Create animation labels with stacked layout
        self.current_label = AnimatedLabel(self)
        self.current_label.setAlignment(Qt.AlignCenter)
        self.next_label = AnimatedLabel(self)
        self.next_label.setAlignment(Qt.AlignCenter)
        self.next_label.setOpacity(0.0)  # Start with fully transparent
        
        # Position labels with absolute layout
        window_config = self.config_manager.get_config("window", None, {})
        window_width = window_config.get("width", 500)
        window_height = window_config.get("height", 500)
        animation_top_margin = 30  # Below settings button
        
        self.current_label.setGeometry(0, animation_top_margin, window_width, window_height - animation_top_margin)
        self.next_label.setGeometry(0, animation_top_margin, window_width, window_height - animation_top_margin)
        
        # Settings button in top right corner
        self.settings_button = QPushButton("⚙", self.selective_widget)
        self.settings_button.setGeometry(window_width - 30, 5, 25, 25)
        self.settings_button.clicked.connect(self.toggle_settings)
        self.settings_button.setStyleSheet("background-color: white; color: black; border-radius: 5px;")

        # Settings menu
        self.settings_menu = SettingsMenu(self, self.config_manager, self.resource_manager, self.event_bus)

        # Add animations to main layout
        self.main_layout.addWidget(self.animation_container)

    # Rest of the class methods remain unchanged...

    def load_animation_manager(self):
        """Initialize and load the animation manager"""
        try:
            from ..animation.animation_manager import AnimationManager
            self.animation_manager = AnimationManager(ASSETS_FOLDER)
            logger.info("Animation manager loaded successfully")
        except ImportError as e:
            ErrorHandler.log_error(e, "Failed to import AnimationManager")
            logger.warning("Using built-in animation handling instead")
            # Create a simple dictionary for animations
            self.animations = self.load_animations_fallback()
    
    def load_animations_fallback(self):
        """Fallback method to load animations without AnimationManager"""
        animations = {}
        if not os.path.exists(ASSETS_FOLDER):
            logger.warning(f"Assets folder not found: {ASSETS_FOLDER}")
            return animations
        
        try:
            for file in os.listdir(ASSETS_FOLDER):
                if file.endswith((".gif", ".png")):
                    key = os.path.splitext(file)[0]  
                    animations[key] = os.path.join(ASSETS_FOLDER, file)
                    # Register with resource manager
                    self.resource_manager.register_resource(
                        f"animation_{key}",
                        os.path.join(ASSETS_FOLDER, file)
                    )
        except Exception as e:
            ErrorHandler.log_error(e, "Failed to load animations")
        
        return animations

    
    def is_in_interactive_area(self, pos):
        """Check if a point is in an interactive area (settings menu, buttons)"""
        # Check settings menu
        if hasattr(self, 'settings_menu') and self.settings_menu.isVisible() and self.settings_menu.geometry().contains(pos):
            return True
            
        # Check settings button
        if hasattr(self, 'settings_button') and self.settings_button.geometry().contains(pos):
            return True
            
        # Check other interactive areas
        for area in self.interactive_areas:
            if area.contains(pos):
                return True
                
        return False
    
    def update_click_through_mode(self):
        """Update click-through mode based on current settings"""
        if hasattr(self, 'selective_widget'):
            self.selective_widget.set_click_through(self.click_through_enabled)
            logger.info(f"Click-through mode updated: {self.click_through_enabled}")

    def update_interactive_regions(self):
        """Update the interactive regions that should capture mouse events"""
        if not hasattr(self, 'selective_widget'):
            return
            
        self.selective_widget.clear_interactive_regions()
        
        # Add settings button region
        if hasattr(self, 'settings_button'):
            self.selective_widget.add_interactive_region(QRegion(self.settings_button.geometry()))
        
        # Add settings menu region
        if hasattr(self, 'settings_menu') and self.settings_menu.isVisible():
            self.selective_widget.add_interactive_region(QRegion(self.settings_menu.geometry()))
            
        # Add any other interactive elements here
        
        logger.debug(f"Updated interactive regions: {len(self.selective_widget.interactive_regions)} regions")

    def setup_ui(self):
        """Initialize the UI components with improved layout"""
        # Create the selective widget first
        self.selective_widget = SelectiveClickThroughWidget(self)
        self.setCentralWidget(self.selective_widget)
        
        # Main layout for the selective widget
        self.main_layout = QVBoxLayout(self.selective_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create animation container with absolute positioning
        self.animation_container = QWidget()
        self.animation_container.setLayout(QVBoxLayout())
        self.animation_container.layout().setContentsMargins(0, 0, 0, 0)
        
        # Create animation labels with stacked layout
        self.current_label = AnimatedLabel(self)
        self.current_label.setAlignment(Qt.AlignCenter)
        self.next_label = AnimatedLabel(self)
        self.next_label.setAlignment(Qt.AlignCenter)
        self.next_label.setOpacity(0.0)  # Start with fully transparent
        
        # Position labels with absolute layout
        window_config = self.config_manager.get_config("window", None, {})
        window_width = window_config.get("width", 500)
        window_height = window_config.get("height", 500)
        animation_top_margin = 30  # Below settings button
        
        self.current_label.setGeometry(0, animation_top_margin, window_width, window_height - animation_top_margin)
        self.next_label.setGeometry(0, animation_top_margin, window_width, window_height - animation_top_margin)
        
        # Settings button in top right corner
        self.settings_button = QPushButton("⚙", self.selective_widget)
        self.settings_button.setGeometry(window_width - 30, 5, 25, 25)
        self.settings_button.clicked.connect(self.toggle_settings)
        self.settings_button.setStyleSheet("background-color: white; color: black; border-radius: 5px;")

        # Settings menu
        self.settings_menu = SettingsMenu(self, self.config_manager, self.resource_manager, self.event_bus)

        # Add animations to main layout
        self.main_layout.addWidget(self.animation_container)

    def toggle_settings(self):
        """Show or hide the settings menu"""
        if hasattr(self, 'settings_menu'):
            if self.settings_menu.isVisible():
                self.settings_menu.hide()
                logger.info("Settings menu hidden")
            else:
                self.settings_menu.show()
                logger.info("Settings menu shown")
                
            # Update interactive regions when settings visibility changes
            self.update_interactive_regions()

    # Override show event to update interactive regions
    def showEvent(self, event):
        super().showEvent(event)
        self.update_interactive_regions()
        
    # Override resize event to update geometry of components
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_interactive_regions()

    def show_settings(self):
        """Show the settings menu"""
        if hasattr(self, 'settings_menu') and not self.settings_menu.isVisible():
            self.settings_menu.show()
            logger.info("Settings menu shown")

    def toggle_visibility(self):
        """Toggle the visibility of the main window"""
        if self.isVisible():
            self.hide()
            logger.info("Presence window hidden")
            
            # Post event about visibility change
            self.event_bus.post_event(
                Event(
                    EventType.SYSTEM_STATE,
                    {"state": "window_hidden"},
                    EventPriority.LOW,
                    "presence_gui"
                )
            )
        else:
            self.show()
            self.activateWindow()
            logger.info("Presence window shown")
            
            # Post event about visibility change
            self.event_bus.post_event(
                Event(
                    EventType.SYSTEM_STATE,
                    {"state": "window_shown"},
                    EventPriority.LOW,
                    "presence_gui"
                )
            )

    def tray_icon_activated(self, reason):
        """Handle tray icon activation events"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_visibility()

    def load_themes(self):
        """Load animation themes with improved error handling"""
        return ErrorHandler.handle_file_operation(
            operation=self._load_themes_internal,
            file_path=os.path.join(ASSETS_FOLDER, "themes.json"),
            fallback=self._get_default_themes(),
            context="Loading themes"
        )
    
    def _load_themes_internal(self):
        """Internal method to load themes from file"""
        themes_file = os.path.join(ASSETS_FOLDER, "themes.json")
        
        if os.path.exists(themes_file):
            with open(themes_file, 'r') as f:
                themes = json.load(f)
            return themes
        
        # If file doesn't exist, create it with default themes
        default_themes = self._get_default_themes()
        self._save_themes_internal(default_themes)
        return default_themes
    
    def _get_default_themes(self):
        """Get default themes dictionary"""
        return {
            "default": {
                "idle": "idle.gif",
                "listening": "listening.gif",
                "talking": "talking.gif",
                "working": "working.gif",
                "static": "static.png",
                "thinking": "idle.gif",  # Fallback to existing animations
                "error": "static.png",
                "success": "talking.gif",
                "waiting": "idle.gif"
            }
        }

    def save_themes(self):
        """Save themes to JSON file with error handling"""
        return ErrorHandler.handle_file_operation(
            operation=lambda: self._save_themes_internal(self.themes),
            file_path=os.path.join(ASSETS_FOLDER, "themes.json"),
            fallback=False,
            context="Saving themes"
        )
    
    def _save_themes_internal(self, themes_data):
        """Internal method to save themes to file"""
        themes_file = os.path.join(ASSETS_FOLDER, "themes.json")
        with open(themes_file, 'w') as f:
            json.dump(themes_data, f, indent=4)
        return True

    def change_theme(self, theme_name):
        """Change the current animation theme"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            logger.info(f"Changed theme to: {theme_name}")
            
            # Update config
            self.config_manager.set_config("themes", "default_theme", theme_name)
            
            # Post event about theme change
            self.event_bus.post_event(
                Event(
                    EventType.SYSTEM_STATE,
                    {"state": "theme_changed", "theme": theme_name},
                    EventPriority.NORMAL,
                    "presence_gui"
                )
            )
            
            # Refresh current animation
            if self.current_animation:
                self.set_animation(self.current_animation)

    def set_animation(self, state):
        """Set the animation with smooth transition and resource management"""
        # Skip if state is not valid
        if state not in ANIMATION_STATES:
            logger.warning(f"Unknown animation state: {state}")
            return False
            
        # Track animation start time for performance monitoring
        start_time = time.time()
            
        # Get theme-specific animation file
        try:
            animation_file = self.themes[self.current_theme].get(state)
            if not animation_file:
                logger.warning(f"No animation file for state: {state} in theme: {self.current_theme}")
                return False
                
            animation_path = os.path.join(ASSETS_FOLDER, animation_file)
            if not os.path.exists(animation_path):
                logger.warning(f"Animation file not found: {animation_path}")
                # Try to find a fallback
                fallback_path = os.path.join(ASSETS_FOLDER, "static.png")
                if os.path.exists(fallback_path):
                    logger.info(f"Using fallback animation: {fallback_path}")
                    animation_path = fallback_path
                else:
                    return False
            
            # If same animation is already playing, don't transition
            if self.current_animation == state:
                # But still register usage with resource manager
                self.resource_manager.use_resource(f"animation_{state}")
                return True
                
            # Store the animation state
            self.current_animation = state
            
            # Post event about animation change
            self.event_bus.post_event(
                Event(
                    EventType.ANIMATION_CHANGE,
                    {"animation": state},
                    EventPriority.LOW,
                    "presence_gui"
                )
            )
            
            # Register with resource manager
            resource_id = f"animation_{state}"
            self.resource_manager.register_resource(resource_id, animation_path)
            
            # Check if transition is already in progress and cancel it if needed
            if self.transition_in_progress:
                if hasattr(self, 'fade_out') and self.fade_out.state() == QPropertyAnimation.Running:
                    self.fade_out.stop()
                if hasattr(self, 'fade_in') and self.fade_in.state() == QPropertyAnimation.Running:
                    self.fade_in.stop()
            
            # Stop any existing movie on the next label and unregister old resource
            if hasattr(self.next_label, 'movie') and self.next_label.movie():
                self.next_label.movie().stop()
                self.next_label.setMovie(None)
                
                # Unregister old resource if it exists
                if hasattr(self.next_label, 'movie_resource_id') and self.next_label.movie_resource_id:
                    self.resource_manager.unregister_resource(self.next_label.movie_resource_id)
                
            # Prepare next animation
            if animation_path.endswith('.png'):
                # Static image
                self.next_label.setPixmap(QPixmap(animation_path))
                self.next_label.movie_resource_id = None  # No movie resource to track
            else:
                # Animated GIF
                try:
                    movie = QMovie(animation_path)
                    movie.setCacheMode(QMovie.CacheAll)
                    movie.setScaledSize(self.next_label.size())  # Scale to fit label
                    movie.loopCount = -1  # Infinite loop
                    self.next_label.setMovie(movie)
                    self.next_label.movie_resource_id = resource_id  # Track resource ID
                    movie.start()
                except Exception as e:
                    ErrorHandler.log_error(e, f"Error loading animation {animation_path}")
                    # Fallback to static image if available
                    static_path = os.path.join(ASSETS_FOLDER, "static.png")
                    if os.path.exists(static_path):
                        self.next_label.setPixmap(QPixmap(static_path))
                        logger.info(f"Using fallback static image: {static_path}")
                        self.next_label.movie_resource_id = None  # No movie resource to track
            
            # Get animation settings
            animation_config = self.config_manager.get_config("animations", None, {})
            enable_transitions = animation_config.get("enable_transitions", True)
            
            # Perform cross-fade transition if enabled
            if enable_transitions:
                self.transition_in_progress = True
                
                # Use the animation transitions module
                self.fade_out, self.fade_in = cross_fade(
                    self.current_label, 
                    self.next_label, 
                    duration=animation_config.get("transition_duration", 300),
                    on_complete=self.complete_transition
                )
            else:
                # Instant switch
                self.complete_transition()
            
            # Log animation change with timing
            elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.debug(f"Set animation to {state} in {elapsed_time:.2f}ms")
            
            return True
            
        except Exception as e:
            ErrorHandler.log_error(e, f"Failed to set animation: {state}")
            return False

    # In presence_gui.py, modify the complete_transition method to have proper null checks:
    def complete_transition(self):
        """Complete the transition between animations by swapping labels"""
        # Swap the current and next label references
        temp_movie = None
        temp_pixmap = None
        temp_resource_id = None
        
        # Save current movie or pixmap
        if (hasattr(self.current_label, 'movie') and self.current_label.movie()):
            temp_movie = self.current_label.movie()
        elif (hasattr(self.current_label, 'pixmap') and 
            self.current_label.pixmap() is not None and 
            not self.current_label.pixmap().isNull()):
            temp_pixmap = self.current_label.pixmap()
        
        # Save resource ID
        if hasattr(self.current_label, 'movie_resource_id'):
            temp_resource_id = self.current_label.movie_resource_id
        
        # Update current label with next label's content
        if (hasattr(self.next_label, 'movie') and self.next_label.movie()):
            self.current_label.setMovie(self.next_label.movie())
            self.current_label.movie_resource_id = self.next_label.movie_resource_id
            self.next_label.setMovie(None)
        elif (hasattr(self.next_label, 'pixmap') and 
            self.next_label.pixmap() is not None and 
            not self.next_label.pixmap().isNull()):
            self.current_label.setPixmap(self.next_label.pixmap())
            self.current_label.movie_resource_id = None
            self.next_label.setPixmap(QPixmap())
        
        # Reset opacity
        self.current_label.setOpacity(1.0)
        self.next_label.setOpacity(0.0)
        
        # Unregister old resource if it exists
        if temp_resource_id:
            self.resource_manager.unregister_resource(temp_resource_id)
        
        # Mark transition as complete
        self.transition_in_progress = False
        
        logger.debug(f"Animation transition completed to {self.current_animation}")

    def toggle_lock(self):
        """Toggle window position lock"""
        self.locked = not self.locked
        self.drag_enabled = not self.locked
        
        # Update button text
        if hasattr(self, 'settings_menu') and hasattr(self.settings_menu, 'lock_button'):
            lock_text = "Position Locked 🔒" if self.locked else "Position Unlocked 🔓"
            self.settings_menu.lock_button.setText(lock_text)
        
        # Update configuration
        self.config_manager.set_config("window", "lock_position", self.locked)
        self.config_manager.save_config()
        
        logger.info(f"Window position lock toggled: {self.locked}")
        
        # Post event about lock change
        self.event_bus.post_event(
            Event(
                EventType.SETTINGS_CHANGE,
                {"section": "window", "setting": "lock_position", "value": self.locked},
                EventPriority.LOW,
                "presence_gui"
            )
        )
    
    def toggle_click_through(self):
        """Toggle click-through mode (allows clicking through the AI window)"""
        # Toggle state
        self.click_through_enabled = not self.click_through_enabled
        
        # Update button text
        if hasattr(self, 'settings_menu'):
            self.settings_menu.update_click_through_button()
        
        # Update configuration
        self.config_manager.set_config("interaction", "click_through_mode", self.click_through_enabled)
        self.config_manager.save_config()
        
        logger.info(f"Click-through mode toggled: {self.click_through_enabled}")
        
        # Post event about click-through change
        self.event_bus.post_event(
            Event(
                EventType.SETTINGS_CHANGE,
                {"section": "interaction", "setting": "click_through_mode", "value": self.click_through_enabled},
                EventPriority.LOW,
                "presence_gui"
            )
        )

    def adjust_transparency(self, value):
        """Adjust the window transparency level"""
        opacity = value / 100.0  # Convert from 0-100 slider to 0.0-1.0 opacity
        self.setWindowOpacity(opacity)
        
        # Update configuration
        self.config_manager.set_config("window", "transparency_level", opacity)
        self.config_manager.save_config()
        
        logger.info(f"Transparency adjusted to {value}% ({opacity:.2f})")
        
        # Post event about transparency change
        self.event_bus.post_event(
            Event(
                EventType.SETTINGS_CHANGE,
                {"section": "window", "setting": "transparency_level", "value": opacity},
                EventPriority.LOW,
                "presence_gui"
            )
        )

    def adjust_volume(self, value):
        """Adjust the voice output volume"""
        volume = value / 100.0  # Convert from 0-100 slider to 0.0-1.0 volume
        
        # Update configuration
        self.config_manager.set_config("voice", "volume", volume)
        self.config_manager.save_config()
        
        logger.info(f"Volume adjusted to {value}% ({volume:.2f})")
        
        # Post event about volume change
        self.event_bus.post_event(
            Event(
                EventType.SETTINGS_CHANGE,
                {"section": "voice", "setting": "volume", "value": volume},
                EventPriority.LOW,
                "presence_gui"
            )
        )

    def test_animation(self, animation_state):
        """Test a specific animation state"""
        if animation_state in ANIMATION_STATES:
            logger.info(f"Testing animation: {animation_state}")
            self.set_animation(animation_state)
            
            # Post event about animation test
            self.event_bus.post_event(
                Event(
                    EventType.ANIMATION_CHANGE,
                    {"animation": animation_state, "test": True},
                    EventPriority.NORMAL,
                    "presence_gui"
                )
            )

    def update_interactive_areas(self):
        """Update the list of interactive areas where click-through should be disabled"""
        self.interactive_areas = []
        
        # Add settings button area
        if hasattr(self, 'settings_button'):
            self.interactive_areas.append(self.settings_button.geometry())
        
        # Add settings menu area
        if hasattr(self, 'settings_menu'):
            self.interactive_areas.append(self.settings_menu.geometry())
        
        # Add any other interactive UI elements here
        logger.debug(f"Updated interactive areas: {len(self.interactive_areas)} regions")

    def safe_exit(self):
        """Safely exit the application with confirmation"""
        from PyQt5.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self, 'Exit Confirmation',
            'Are you sure you want to exit Sabrina AI?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            logger.info("User requested application exit")
            
            # Post shutdown event
            self.event_bus.post_event(
                Event(
                    EventType.SYSTEM_STATE,
                    {"state": "shutdown"},
                    EventPriority.HIGH,
                    "presence_gui"
                )
            )
            
            # Cleanup resources
            self.resource_manager.force_cleanup()
            
            # Exit application
            QApplication.instance().quit()

    def mousePressEvent(self, event):
        """Handle mouse press events for dragging the window or pass through if needed"""
        if not self.click_through_enabled or self.is_in_interactive_area(event.pos()):
            # Normal handling - capture the event
            if event.button() == Qt.LeftButton and self.drag_enabled:
                # Store the position for dragging if in a non-interactive area
                if not self.is_in_interactive_area(event.pos()):
                    self.old_pos = event.pos()
            super().mousePressEvent(event)
        # If click-through is enabled and we're not in an interactive area,
        # don't process the event (allow it to pass through)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events for dragging the window or pass through if needed"""
        if not self.click_through_enabled or self.is_in_interactive_area(event.pos()):
            # Normal handling - capture the event
            if event.button() == Qt.LeftButton:
                self.old_pos = None
            super().mouseReleaseEvent(event)
        # If click-through is enabled and we're not in an interactive area,
        # don't process the event (allow it to pass through)

    def mouseMoveEvent(self, event):
        """Handle mouse move events for dragging the window or pass through if needed"""
        if not self.click_through_enabled or self.is_in_interactive_area(event.pos()):
            # Normal handling - capture the event
            if self.old_pos and self.drag_enabled:
                delta = event.pos() - self.old_pos
                self.move(self.pos() + delta)
            super().mouseMoveEvent(event)
        # If click-through is enabled and we're not in an interactive area,
        # don't process the event (allow it to pass through)
    
    
    def start_event_listener(self):
        """Start event listener for external events"""
        logger.info("Started event listener")
        # This method is called during initialization to set up event listeners
        # It's already implemented in the __init__ method but needs to be defined
        pass