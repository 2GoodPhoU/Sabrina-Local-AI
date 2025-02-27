"""
Refactored main GUI component for Sabrina's Presence System

This module provides the main GUI implementation with improved organization,
performance, and maintainability
"""
# Standard imports
import os
import json
import time

# Third-party imports
from PyQt5.QtWidgets import (
    QMainWindow, QPushButton, QWidget, QVBoxLayout, QApplication, 
    QSystemTrayIcon, QMenu, QMessageBox
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEvent, QTimer
from PyQt5.QtGui import QMovie, QPixmap, QRegion

# Local imports
from .animation_label import AnimatedLabel
from .settings_menu import SettingsMenu
from .system_tray import setup_system_tray, show_tray_notification

from ..utils.error_handling import ErrorHandler, logger
from ..utils.resource_management import ResourceManager
from ..utils.config_manager import ConfigManager
from ..utils.event_system import EventBus, EventType, EventPriority, Event
from ..animation.animation_transitions import cross_fade, optimized_transition
from ..constants import (
    ANIMATION_STATES, ASSETS_FOLDER, 
    DEFAULT_ANIMATION, WINDOW_WIDTH, WINDOW_HEIGHT
)

class SelectiveClickThroughWidget(QWidget):
    """Custom widget that allows click-through in some areas but not others"""
    
    def __init__(self, parent=None):
        """Initialize the selective click-through widget
        
        Args:
            parent: Parent widget (default: None)
        """
        super().__init__(parent)
        self.interactive_regions = []  # List of QRegion objects that should capture mouse events
        self.click_through_enabled = False
        self.debug_mode = False
        
    def add_interactive_region(self, region: QRegion):
        """Add a region that should capture mouse events
        
        Args:
            region: QRegion that should be interactive
        """
        self.interactive_regions.append(region)
        
    def clear_interactive_regions(self):
        """Clear all interactive regions"""
        self.interactive_regions = []
        
    def set_click_through(self, enabled: bool):
        """Enable or disable click-through mode
        
        Args:
            enabled: True to enable click-through, False to disable
        """
        self.click_through_enabled = enabled
        self.update()  # Force update to apply changes
        
    def set_debug_mode(self, enabled: bool):
        """Enable or disable debug mode
        
        Args:
            enabled: True to enable debugging, False to disable
        """
        self.debug_mode = enabled
        
    def event(self, event: QEvent) -> bool:
        """Override event handler with enhanced logic and optional debugging
        
        Args:
            event: Qt event object
            
        Returns:
            bool: True if event is handled, False to pass through
        """
        # If click-through is disabled, handle events normally
        if not self.click_through_enabled:
            return super().event(event)
        
        # For mouse events, check if they're in an interactive region
        if (event.type() == QEvent.MouseButtonPress or 
            event.type() == QEvent.MouseButtonRelease or 
            event.type() == QEvent.MouseButtonDblClick or
            event.type() == QEvent.MouseMove):
            
            # Check if mouse position is within any interactive region
            mouse_pos = event.pos()
            
            # Debug output if enabled
            if self.debug_mode and (event.type() == QEvent.MouseButtonPress or 
                                   event.type() == QEvent.MouseButtonRelease):
                print(f"Mouse event at position: {mouse_pos.x()}, {mouse_pos.y()}")
                print(f"Interactive regions count: {len(self.interactive_regions)}")
                
                for i, region in enumerate(self.interactive_regions):
                    contains = region.contains(mouse_pos)
                    print(f"Region {i}: Contains point: {contains}, Rect: {region.boundingRect()}")
            
            # Check if position is in any interactive region
            for region in self.interactive_regions:
                if region.contains(mouse_pos):
                    if self.debug_mode and (event.type() == QEvent.MouseButtonPress or 
                                          event.type() == QEvent.MouseButtonRelease):
                        print("Event in interactive region - handling normally")
                    # In interactive region, handle event normally
                    return super().event(event)
            
            if self.debug_mode and (event.type() == QEvent.MouseButtonPress or 
                                   event.type() == QEvent.MouseButtonRelease):
                print("Event not in any interactive region - passing through")
            # Not in any interactive region, let the event pass through
            return False
        
        # Handle all other events normally
        return super().event(event)

class PresenceGUI(QMainWindow):
    """Main Presence GUI with improved error handling, resource management, and organization"""
    
    def __init__(self, resource_manager=None, config_manager=None, event_bus=None):
        """Initialize the Presence GUI with improved components
        
        Args:
            resource_manager: ResourceManager instance (default: new instance)
            config_manager: ConfigManager instance (default: new instance)
            event_bus: EventBus instance (default: new instance)
        """
        super().__init__()
        
        # Initialize core components
        self.resource_manager = resource_manager or ResourceManager()
        self.config_manager = config_manager or ConfigManager()
        self.event_bus = event_bus or EventBus()
        
        logger.info("Initializing Presence GUI")
        
        # GUI State
        self.current_animation = None
        self.transition_in_progress = False
        self.old_pos = None
        self.animation_manager = None
        self.init_time = time.time()
        
        # Initialize configurations
        self._init_config()
        
        # Setup UI Components
        self._setup_ui()
        
        # Setup event listeners
        self._setup_event_listeners()
        
        # Set default animation
        animation_config = self.config_manager.get_config("animations", None, {})
        default_animation = animation_config.get("default_animation", DEFAULT_ANIMATION)
        self.set_animation(default_animation)
        
        # Create periodic timer for maintenance tasks
        self._setup_maintenance_timer()
        
        # Log successful initialization
        logger.info(f"Presence GUI initialized successfully in {(time.time() - self.init_time)*1000:.2f}ms")

    def _init_config(self):
        """Initialize configuration and window properties"""
        # Load configuration
        window_config = self.config_manager.get_config("window", None, {})
        interaction_config = self.config_manager.get_config("interaction", None, {})
        themes_config = self.config_manager.get_config("themes", None, {})
        
        # Get screen dimensions and position
        self._init_window_position(window_config)
        
        # Set window flags and attributes
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        # Set transparency
        transparency_level = window_config.get("transparency_level", 0.85)
        self.setWindowOpacity(transparency_level)

        # Dragging and position locking
        self.drag_enabled = window_config.get("enable_dragging", True) and not window_config.get("lock_position", False)
        self.locked = window_config.get("lock_position", False)

        # Animation and themes
        self.current_theme = themes_config.get("default_theme", "default")
        self.themes = self.load_themes()
        
        # Click-through mode
        self.click_through_enabled = interaction_config.get("click_through_mode", False)
        
        # Interactive areas tracking
        self.interactive_areas = []
    
    def _init_window_position(self, window_config):
        """Initialize window position based on screen dimensions
        
        Args:
            window_config: Window configuration dictionary
        """
        try:
            # Get screen dimensions from Qt
            screen_geometry = QApplication.desktop().screenGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
        except Exception as e:
            ErrorHandler.log_error(e, "PresenceGUI._init_window_position")
            # Fallback dimensions
            screen_width, screen_height = 1920, 1080
        
        # Window dimensions from config
        window_width = window_config.get("width", WINDOW_WIDTH)
        window_height = window_config.get("height", WINDOW_HEIGHT)
        padding_right = window_config.get("padding_right", 20)

        # Set window position
        self.x_position = screen_width - window_width - padding_right
        self.y_position = (screen_height // 2) - (window_height // 2)
        
        # Set window geometry
        self.setGeometry(self.x_position, self.y_position, window_width, window_height)
    
    def _setup_ui(self):
        """Initialize and setup all UI components"""
        # Create the selective widget first
        self.selective_widget = SelectiveClickThroughWidget(self)
        self.setCentralWidget(self.selective_widget)
        
        # Set debug mode from config
        debug_config = self.config_manager.get_config("debug", None, {})
        self.selective_widget.set_debug_mode(debug_config.get("debug_mode", False))
        
        # Setup main layout
        self._setup_main_layout()
        
        # Create animation labels
        self._setup_animation_labels()
        
        # Create settings button and menu
        self._setup_settings()
        
        # Setup System Tray
        self.tray_icon = setup_system_tray(self)
        
        # Setup Animation Manager
        self._load_animation_manager()
        
        # Update interactive regions
        self.update_interactive_regions()
    
    def _setup_main_layout(self):
        """Setup the main layout for the window"""
        # Main layout for the selective widget
        self.main_layout = QVBoxLayout(self.selective_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create animation container with absolute positioning
        self.animation_container = QWidget()
        self.animation_container.setLayout(QVBoxLayout())
        self.animation_container.layout().setContentsMargins(0, 0, 0, 0)
        
        # Add animations to main layout
        self.main_layout.addWidget(self.animation_container)
    
    def _setup_animation_labels(self):
        """Create and position animation labels"""
        window_config = self.config_manager.get_config("window", None, {})
        window_width = window_config.get("width", WINDOW_WIDTH)
        window_height = window_config.get("height", WINDOW_HEIGHT)
        animation_top_margin = 40  # Space for the settings button
        
        # Create animation labels with stacked layout
        self.current_label = AnimatedLabel(self)
        self.current_label.setAlignment(Qt.AlignCenter)
        
        self.next_label = AnimatedLabel(self)
        self.next_label.setAlignment(Qt.AlignCenter)
        self.next_label.setOpacity(0.0)  # Start with fully transparent
        
        # Position labels with absolute layout
        self.current_label.setGeometry(0, animation_top_margin, window_width, window_height - animation_top_margin)
        self.next_label.setGeometry(0, animation_top_margin, window_width, window_height - animation_top_margin)
    
    def _setup_settings(self):
        """Create settings button and menu"""
        window_config = self.config_manager.get_config("window", None, {})
        window_width = window_config.get("width", WINDOW_WIDTH)
        
        # Enhanced settings button in top right corner - LARGER and MORE VISIBLE
        self.settings_button = QPushButton("⚙ Settings", self.selective_widget)
        self.settings_button.setGeometry(window_width - 100, 10, 90, 30)
        self.settings_button.clicked.connect(self.toggle_settings)
        self.settings_button.setStyleSheet("""
            background-color: rgba(255, 255, 255, 220); 
            color: black; 
            border-radius: 5px;
            font-weight: bold;
        """)
        # Add tooltip for better usability
        self.settings_button.setToolTip("Open Settings (Right-click anywhere for menu)")

        # Create settings menu
        self.settings_menu = SettingsMenu(self, self.config_manager, self.resource_manager, self.event_bus)
        
        # Make sure settings button is above other elements
        self.settings_button.raise_()
    
    def _setup_event_listeners(self):
        """Setup event listeners for the event bus"""
        # Register animation event handler
        animation_handler = self.event_bus.create_event_handler(
            EventType.ANIMATION_CHANGE,
            self._handle_animation_event,
            EventPriority.NORMAL
        )
        self.event_bus.register_handler(animation_handler)
        
        # Register settings event handler
        settings_handler = self.event_bus.create_event_handler(
            EventType.SETTINGS_CHANGE,
            self._handle_settings_event,
            EventPriority.NORMAL
        )
        self.event_bus.register_handler(settings_handler)
        
        logger.debug("Event listeners registered")
    
    def _setup_maintenance_timer(self):
        """Setup maintenance timer for periodic tasks"""
        self.maintenance_timer = QTimer(self)
        self.maintenance_timer.timeout.connect(self._perform_maintenance)
        self.maintenance_timer.start(60000)  # Run every minute
    
    def _perform_maintenance(self):
        """Perform periodic maintenance tasks"""
        # Check if we should clean up resources
        if hasattr(self, 'resource_manager'):
            stats = self.resource_manager.get_resource_stats()
            if stats.get("active_count", 0) > 10:
                logger.debug("Performing maintenance resource cleanup")
                self.resource_manager.cleanup_inactive()
        
        # Check if config needs saving
        if hasattr(self, 'config_manager') and self.config_manager.has_unsaved_changes():
            logger.debug("Saving configuration during maintenance")
            self.config_manager.save_config()
    
    def _load_animation_manager(self):
        """Initialize and load the animation manager"""
        try:
            from ..animation.animation_manager import AnimationManager
            self.animation_manager = AnimationManager(ASSETS_FOLDER)
            logger.info("Animation manager loaded successfully")
        except ImportError as e:
            ErrorHandler.log_error(e, "PresenceGUI._load_animation_manager")
            logger.warning("Using built-in animation handling instead")
            # Create a simple dictionary for animations
            self.animations = self._load_animations_fallback()
    
    def _load_animations_fallback(self):
        """Fallback method to load animations without AnimationManager
        
        Returns:
            dict: Animation dictionary mapping names to file paths
        """
        animations = {}
        if not os.path.exists(ASSETS_FOLDER):
            logger.warning(f"Assets folder not found: {ASSETS_FOLDER}")
            return animations
        
        try:
            for file in os.listdir(ASSETS_FOLDER):
                if file.endswith((".gif", ".png")):
                    key = os.path.splitext(file)[0]  
                    file_path = os.path.join(ASSETS_FOLDER, file)
                    animations[key] = file_path
                    
                    # Register with resource manager
                    self.resource_manager.register_resource(
                        f"animation_{key}",
                        file_path,
                        resource_type="animation"
                    )
        except Exception as e:
            ErrorHandler.log_error(e, "PresenceGUI._load_animations_fallback")
        
        return animations
    
    def _handle_animation_event(self, event):
        """Handle animation change events from the event bus
        
        Args:
            event: Event object with animation data
        """
        animation = event.data.get("animation")
        if animation and animation in ANIMATION_STATES:
            logger.debug(f"Animation event received: {animation} from {event.source}")
            self.set_animation(animation)
    
    def _handle_settings_event(self, event):
        """Handle settings change events from the event bus
        
        Args:
            event: Event object with settings data
        """
        section = event.data.get("section")
        setting = event.data.get("setting")
        value = event.data.get("value")
        
        if not section or not setting:
            return
            
        logger.debug(f"Settings event received: {section}.{setting}={value}")
        
        # Handle specific settings that need immediate UI updates
        if section == "window" and setting == "transparency_level":
            self.setWindowOpacity(float(value))
        elif section == "window" and setting == "lock_position":
            self.locked = bool(value)
            self.drag_enabled = not self.locked
        elif section == "interaction" and setting == "click_through_mode":
            if bool(value) != self.click_through_enabled:
                self.toggle_click_through()
        elif section == "debug" and setting == "debug_mode":
            self.selective_widget.set_debug_mode(bool(value))
    
    def load_themes(self):
        """Load animation themes with improved error handling
        
        Returns:
            dict: Theme definitions
        """
        return ErrorHandler.handle_file_operation(
            operation=self._load_themes_internal,
            file_path=os.path.join(ASSETS_FOLDER, "themes.json"),
            fallback=self._get_default_themes(),
            context="PresenceGUI.load_themes"
        )
    
    def _load_themes_internal(self):
        """Internal method to load themes from file
        
        Returns:
            dict: Theme definitions loaded from file
        """
        themes_file = os.path.join(ASSETS_FOLDER, "themes.json")
        
        if os.path.exists(themes_file):
            with open(themes_file, 'r', encoding='utf-8') as f:
                themes = json.load(f)
            return themes
        
        # If file doesn't exist, create it with default themes
        default_themes = self._get_default_themes()
        self._save_themes_internal(default_themes)
        return default_themes
    
    def _get_default_themes(self):
        """Get default themes dictionary
        
        Returns:
            dict: Default theme definitions
        """
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
        """Save themes to JSON file with error handling
        
        Returns:
            bool: True if successful, False otherwise
        """
        return ErrorHandler.handle_file_operation(
            operation=lambda: self._save_themes_internal(self.themes),
            file_path=os.path.join(ASSETS_FOLDER, "themes.json"),
            fallback=False,
            context="PresenceGUI.save_themes"
        )
    
    def _save_themes_internal(self, themes_data):
        """Internal method to save themes to file
        
        Args:
            themes_data: Theme definitions to save
            
        Returns:
            bool: True if successful
        """
        themes_file = os.path.join(ASSETS_FOLDER, "themes.json")
        with open(themes_file, 'w', encoding='utf-8') as f:
            json.dump(themes_data, f, indent=4)
        return True

    def change_theme(self, theme_name):
        """Change the current animation theme
        
        Args:
            theme_name: Name of the theme to apply
            
        Returns:
            bool: True if theme was changed, False otherwise
        """
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
                
            return True
        
        logger.warning(f"Theme not found: {theme_name}")
        return False

    def set_animation(self, state):
        """Set the animation with improved organization and error handling
        
        Args:
            state: Animation state name
            
        Returns:
            bool: True if animation was set, False otherwise
        """
        # Validate animation state
        if not self._validate_animation_state(state):
            return False
        
        # Get animation resources
        animation_path, resource_id = self._prepare_animation_resources(state)
        if not animation_path:
            return False
        
        # Set the animation
        return self._apply_animation(state, animation_path, resource_id)
    
    def _validate_animation_state(self, state):
        """Validate that the animation state is valid
        
        Args:
            state: Animation state name
            
        Returns:
            bool: True if state is valid, False otherwise
        """
        if state not in ANIMATION_STATES:
            logger.warning(f"Unknown animation state: {state}")
            return False
        return True
    
    def _prepare_animation_resources(self, state):
        """Prepare animation resources for the specified state
        
        Args:
            state: Animation state name
            
        Returns:
            tuple: (animation_path, resource_id) or (None, None) if unavailable
        """
        try:
            # Get theme-specific animation file
            animation_file = self.themes[self.current_theme].get(state)
            if not animation_file:
                logger.warning(f"No animation file for state: {state} in theme: {self.current_theme}")
                return None, None
                
            animation_path = os.path.join(ASSETS_FOLDER, animation_file)
            if not os.path.exists(animation_path):
                logger.warning(f"Animation file not found: {animation_path}")
                # Try to find a fallback
                fallback_path = os.path.join(ASSETS_FOLDER, "static.png")
                if os.path.exists(fallback_path):
                    logger.info(f"Using fallback animation: {fallback_path}")
                    animation_path = fallback_path
                else:
                    return None, None
            
            # Register with resource manager
            resource_id = f"animation_{state}_{self.current_theme}"
            self.resource_manager.register_resource(
                resource_id, 
                animation_path,
                resource_type="animation"
            )
            
            return animation_path, resource_id
            
        except Exception as e:
            ErrorHandler.log_error(e, f"PresenceGUI._prepare_animation_resources({state})")
            return None, None
    
    def _apply_animation(self, state, animation_path, resource_id):
        """Apply the animation with proper transitions
        
        Args:
            state: Animation state name
            animation_path: Path to animation file
            resource_id: Resource ID for tracking
            
        Returns:
            bool: True if animation was applied, False otherwise
        """
        # If same animation is already playing, don't transition
        if self.current_animation == state:
            # But still register usage with resource manager
            self.resource_manager.use_resource(resource_id)
            return True
            
        # Store the animation state
        old_animation = self.current_animation
        self.current_animation = state
        
        # Post event about animation change
        self.event_bus.post_event(
            Event(
                EventType.ANIMATION_CHANGE,
                {"animation": state, "previous": old_animation},
                EventPriority.LOW,
                "presence_gui"
            )
        )
        
        # Check if transition is already in progress and cancel it if needed
        if self.transition_in_progress:
            if hasattr(self, 'fade_out') and self.fade_out.state() == QPropertyAnimation.Running:
                self.fade_out.stop()
            if hasattr(self, 'fade_in') and self.fade_in.state() == QPropertyAnimation.Running:
                self.fade_in.stop()
        
        try:
            # Get old animation path for optimization
            old_animation_path = None
            if old_animation:
                old_animation_file = self.themes[self.current_theme].get(old_animation)
                if old_animation_file:
                    old_animation_path = os.path.join(ASSETS_FOLDER, old_animation_file)
            
            # Create the new animation with optimized resource usage
            self._create_animation_on_label(self.next_label, animation_path, old_animation_path)
            
            # Get animation settings
            animation_config = self.config_manager.get_config("animations", None, {})
            enable_transitions = animation_config.get("enable_transitions", True)
            
            # Perform transition
            if enable_transitions:
                return self._transition_to_new_animation(animation_config)
            else:
                # Instant switch
                self.complete_transition()
                return True
                
        except Exception as e:
            ErrorHandler.log_error(e, f"PresenceGUI._apply_animation({state})")
            return False
    
    def _create_animation_on_label(self, label, animation_path, old_animation_path=None):
        """Create animation or static image on a label
        
        Args:
            label: Label to update
            animation_path: Path to animation file
            old_animation_path: Optional path to current animation (for optimization)
        """
        # Stop any existing movie on the label
        if hasattr(label, 'movie') and label.movie():
            label.movie().stop()
            label.setMovie(None)
            
        # Check if we're setting the same animation as before (optimization)
        if old_animation_path and old_animation_path == animation_path:
            logger.debug("Reusing existing animation (same path)")
            return
            
        # Set static image or animated GIF
        if animation_path.endswith('.png'):
            # Static image
            label.setPixmap(QPixmap(animation_path))
            label.movie_resource_id = None  # No movie resource to track
        else:
            # Animated GIF
            try:
                movie = QMovie(animation_path)
                movie.setCacheMode(QMovie.CacheAll)
                movie.setScaledSize(label.size())  # Scale to fit label
                movie.loopCount = -1  # Infinite loop
                label.setMovie(movie)
                movie.start()
            except Exception as e:
                ErrorHandler.log_error(e, f"Error loading animation {animation_path}")
                # Fallback to static image if available
                static_path = os.path.join(ASSETS_FOLDER, "static.png")
                if os.path.exists(static_path):
                    label.setPixmap(QPixmap(static_path))
                    logger.info(f"Using fallback static image: {static_path}")
                    label.movie_resource_id = None  # No movie resource to track
    
    def _transition_to_new_animation(self, animation_config):
        """Perform transition to new animation
        
        Args:
            animation_config: Animation configuration dictionary
            
        Returns:
            bool: True if transition started, False otherwise
        """
        self.transition_in_progress = True
        
        # Use the animation transitions module
        self.fade_out, self.fade_in = cross_fade(
            self.current_label, 
            self.next_label, 
            duration=animation_config.get("transition_duration", 300),
            on_complete=self.complete_transition
        )
        
        return True
    
    def complete_transition(self):
        """Complete the transition between animations by swapping labels"""
        try:
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
            
        except Exception as e:
            ErrorHandler.log_error(e, "PresenceGUI.complete_transition")
            self.transition_in_progress = False

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

    def show_settings(self):
        """Show the settings menu"""
        if hasattr(self, 'settings_menu') and not self.settings_menu.isVisible():
            self.settings_menu.show()
            logger.info("Settings menu shown")
            self.update_interactive_regions()

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
        """Handle tray icon activation events
        
        Args:
            reason: Activation reason
        """
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_visibility()

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
        
        # Update selective widget
        if hasattr(self, 'selective_widget'):
            self.selective_widget.set_click_through(self.click_through_enabled)
            # Force update of interactive regions
            self.update_interactive_regions()
        
        # Update button text
        if hasattr(self, 'settings_menu'):
            self.settings_menu.update_click_through_button()
        
        # Update configuration
        self.config_manager.set_config("interaction", "click_through_mode", self.click_through_enabled)
        
        logger.info(f"Click-through mode toggled: {self.click_through_enabled}")
        
        # If click-through is enabled, enable WindowTransparentForInput attribute
        if self.click_through_enabled:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        
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
        """Adjust the window transparency level
        
        Args:
            value: Transparency value (0-100)
        """
        opacity = value / 100.0  # Convert from 0-100 slider to 0.0-1.0 opacity
        self.setWindowOpacity(opacity)
        
        # Update configuration
        self.config_manager.set_config("window", "transparency_level", opacity)
        
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
        """Adjust the voice output volume
        
        Args:
            value: Volume value (0-100)
        """
        volume = value / 100.0  # Convert from 0-100 slider to 0.0-1.0 volume
        
        # Update configuration
        self.config_manager.set_config("voice", "volume", volume)
        
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
        """Test a specific animation state
        
        Args:
            animation_state: Animation state to test
        """
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

    def is_in_interactive_area(self, pos):
        """Check if a point is in an interactive area
        
        Args:
            pos: Point to check
            
        Returns:
            bool: True if point is in an interactive area
        """
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

    def update_interactive_regions(self):
        """Update the interactive regions that should capture mouse events
        
        This defines areas where mouse events should be captured even in click-through mode
        """
        if not hasattr(self, 'selective_widget'):
            return
            
        self.selective_widget.clear_interactive_regions()
        
        # Add settings button region - make MUCH larger for easier clicking
        if hasattr(self, 'settings_button'):
            button_geo = self.settings_button.geometry()
            # Make the clickable region significantly larger (15px padding)
            larger_region = QRegion(
                button_geo.x() - 15, 
                button_geo.y() - 15,
                button_geo.width() + 30,
                button_geo.height() + 30
            )
            self.selective_widget.add_interactive_region(larger_region)
            logger.debug(f"Added settings button region: {button_geo}")
        
        # Add settings menu region if visible
        if hasattr(self, 'settings_menu') and self.settings_menu.isVisible():
            menu_geo = self.settings_menu.geometry()
            # Add larger margin around the menu (10px)
            larger_menu_region = QRegion(
                menu_geo.x() - 10,
                menu_geo.y() - 10,
                menu_geo.width() + 20,
                menu_geo.height() + 20
            )
            self.selective_widget.add_interactive_region(larger_menu_region)
            
            # Also add all child widgets of settings menu
            for child in self.settings_menu.findChildren(QWidget):
                if child.isVisible():
                    child_geo = child.geometry().translated(menu_geo.topLeft())
                    # Make click regions larger for each child widget
                    larger_child_region = QRegion(
                        child_geo.x() - 5,
                        child_geo.y() - 5,
                        child_geo.width() + 10,
                        child_geo.height() + 10
                    )
                    self.selective_widget.add_interactive_region(larger_child_region)
        
        # Add a region for the entire top bar area to make it easier to drag the window
        top_bar_height = 40
        top_bar_region = QRegion(0, 0, self.width(), top_bar_height)
        self.selective_widget.add_interactive_region(top_bar_region)
        
        logger.debug(f"Updated interactive regions: {len(self.selective_widget.interactive_regions)} regions")
        
        # Force a redraw
        self.update()

    def safe_exit(self):
        """Safely exit the application with confirmation"""
        try:
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
                
                # Stop maintenance timer
                if hasattr(self, 'maintenance_timer') and self.maintenance_timer.isActive():
                    self.maintenance_timer.stop()
                
                # Save configuration
                if hasattr(self, 'config_manager'):
                    self.config_manager.save_config(force=True)
                
                # Cleanup resources
                if hasattr(self, 'resource_manager'):
                    self.resource_manager.force_cleanup()
                
                # Exit application
                QApplication.instance().quit()
                
        except Exception as e:
            ErrorHandler.log_error(e, "PresenceGUI.safe_exit")
            # Try to force quit in case of error
            QApplication.instance().quit()

    # QT Event Overrides
    def showEvent(self, event):
        """Override show event to update interactive regions"""
        super().showEvent(event)
        self.update_interactive_regions()
        
    def resizeEvent(self, event):
        """Override resize event to update geometry of components"""
        super().resizeEvent(event)
        self.update_interactive_regions()
    
    def contextMenuEvent(self, event):
        """Handle right-click event to show context menu"""
        # Create context menu
        context_menu = QMenu(self)
        
        # Add menu options
        settings_action = context_menu.addAction("Open Settings")
        toggle_click_through_action = context_menu.addAction(
            "Disable Click-Through" if self.click_through_enabled else "Enable Click-Through"
        )
        context_menu.addSeparator()
        exit_action = context_menu.addAction("Exit Sabrina AI")
        
        # Connect actions to their respective functions
        settings_action.triggered.connect(self.show_settings)
        toggle_click_through_action.triggered.connect(self.toggle_click_through)
        exit_action.triggered.connect(self.safe_exit)
        
        # Show the menu at the cursor position
        context_menu.exec_(self.mapToGlobal(event.pos()))

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