from PyQt5.QtWidgets import (QMainWindow, QLabel, QPushButton, QSlider, QVBoxLayout, 
                            QWidget, QHBoxLayout, QSystemTrayIcon, QMenu, QAction, 
                            QColorDialog, QComboBox, QFileDialog, QMessageBox)
from PyQt5.QtCore import QTimer, Qt, QPoint, QPropertyAnimation, QEasingCurve, QByteArray, pyqtProperty, QRect
from PyQt5.QtGui import QMovie, QPixmap, QIcon, QColor, QPainter, QImage
import sys
import os
import json
import screeninfo
import time

# Import the improved modules
from error_handling import ErrorHandler, logger
from resource_management import ResourceManager
from config_manager import ConfigManager
from event_system import EventBus, EventType, EventPriority, Event, register_animation_handler, trigger_animation_change

# Import constants - now using config_manager for dynamic settings
from presence_constants import (
    ANIMATION_STATES, ANIMATION_PRIORITY, ASSETS_FOLDER, DEFAULT_ANIMATION
)

class AnimatedLabel(QLabel):
    """Enhanced QLabel with animation properties and opacity control"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 1.0
        self.setStyleSheet("background: transparent;")
        
        # Add resource tracking
        self.movie_resource_id = None

    def setOpacity(self, opacity):
        """Set the opacity level of the label"""
        self._opacity = opacity
        self.update()

    def getOpacity(self):
        """Get the current opacity level"""
        return self._opacity

    # Define property for QPropertyAnimation
    opacity = pyqtProperty(float, getOpacity, setOpacity)

    def paintEvent(self, event):
        """Override paintEvent for custom opacity rendering"""
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        super().paintEvent(event)


class EnhancedPresenceGUI(QMainWindow):
    def __init__(self, resource_manager=None, config_manager=None, event_bus=None):
        """Initialize the Presence GUI with improved components
        
        Args:
            resource_manager: Optional ResourceManager instance
            config_manager: Optional ConfigManager instance
            event_bus: Optional EventBus instance
        """
        super().__init__()
        
        # Initialize improved components
        self.resource_manager = resource_manager or ResourceManager()
        self.config_manager = config_manager or ConfigManager()
        self.event_bus = event_bus or EventBus()
        
        logger.info("Initializing Enhanced Presence GUI")
        
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
        enable_transparency = window_config.get("enable_transparency", True)
        transparency_level = window_config.get("transparency_level", 0.85)
        if enable_transparency:
            self.setAttribute(Qt.WA_TranslucentBackground)  
            self.setWindowOpacity(transparency_level)  

        # Dragging and position locking
        self.drag_enabled = window_config.get("enable_dragging", True) and not window_config.get("lock_position", False)
        self.locked = window_config.get("lock_position", False)
        self.old_pos = None

        # Animation and themes
        themes_config = self.config_manager.get_config("themes", None, {})
        self.current_theme = themes_config.get("default_theme", "default")
        self.themes = self.load_themes()
        
        # Click-through mode
        self.click_through_enabled = interaction_config.get("click_through_mode", False)
        
        # Interactive areas tracking
        self.interactive_areas = []

        # Setup UI Components
        self.setup_ui()
        
        # Initial click-through status - make sure flags are set correctly based on initial state
        if self.click_through_enabled:
            self.setWindowFlags(self.windowFlags() | Qt.WindowTransparentForInput)
            
        # Setup System Tray
        self.setup_system_tray()
        
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
        logger.info("Enhanced Presence GUI initialized successfully")

    def load_animation_manager(self):
        """Initialize and load the animation manager"""
        try:
            from animation_manager import AnimationManager
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

    def setup_ui(self):
        """Initialize the UI components with improved layout"""
        # Create the main container
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Create main vertical layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create animation container with absolute positioning
        self.animation_container = QWidget()
        self.animation_container.setLayout(QVBoxLayout())
        self.animation_container.layout().setContentsMargins(0, 0, 0, 0)
        
        # Create animation labels with stacked layout
        # They will overlay each other in the same position
        self.current_label = AnimatedLabel(self)
        self.current_label.setAlignment(Qt.AlignCenter)
        self.next_label = AnimatedLabel(self)
        self.next_label.setAlignment(Qt.AlignCenter)
        self.next_label.setOpacity(0.0)  # Start with fully transparent
        
        # Position labels with absolute layout
        # Top-right corner, below settings button
        animation_top_margin = 30  # Below settings button
        window_config = self.config_manager.get_config("window", None, {})
        window_width = window_config.get("width", 500)
        window_height = window_config.get("height", 500)
        
        self.current_label.setGeometry(0, animation_top_margin, window_width, window_height - animation_top_margin)
        self.next_label.setGeometry(0, animation_top_margin, window_width, window_height - animation_top_margin)
        
        # Settings button in top right corner
        self.settings_button = QPushButton("⚙", self)
        self.settings_button.setGeometry(window_width - 30, 5, 25, 25)
        self.settings_button.clicked.connect(self.toggle_settings)
        self.settings_button.setStyleSheet("background-color: white; color: black; border-radius: 5px;")

        # Settings menu UI
        self.settings_menu = QWidget(self)
        self.settings_menu.setGeometry(10, 40, 250, 300)
        self.settings_menu.setStyleSheet("background-color: rgba(255, 255, 255, 220); border-radius: 10px;")
        self.settings_menu.hide()

        # Create settings layout
        settings_layout = QVBoxLayout(self.settings_menu)

        # Lock position toggle
        self.lock_button = QPushButton("Position Unlocked 🔓" if not self.locked else "Position Locked 🔒", self.settings_menu)
        self.lock_button.clicked.connect(self.toggle_lock)
        self.lock_button.setStyleSheet("background-color: white; color: black;")
        settings_layout.addWidget(self.lock_button)

        # Theme selector
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:", self.settings_menu)
        self.theme_selector = QComboBox(self.settings_menu)
        
        # Add available themes
        for theme in self.themes.keys():
            self.theme_selector.addItem(theme)
        
        # Set current theme
        index = self.theme_selector.findText(self.current_theme)
        if index >= 0:
            self.theme_selector.setCurrentIndex(index)
        
        self.theme_selector.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_selector)
        settings_layout.addLayout(theme_layout)

        # Transparency Slider with Label
        transparency_layout = QHBoxLayout()
        self.transparency_label = QLabel("Transparency:", self.settings_menu)
        self.transparency_slider = QSlider(Qt.Horizontal, self.settings_menu)
        self.transparency_slider.setMinimum(10)
        self.transparency_slider.setMaximum(100)
        
        # Get transparency level from config
        window_config = self.config_manager.get_config("window", None, {})
        transparency_level = window_config.get("transparency_level", 0.85)
        self.transparency_slider.setValue(int(transparency_level * 100))
        
        self.transparency_slider.valueChanged.connect(self.adjust_transparency)
        transparency_layout.addWidget(self.transparency_label)
        transparency_layout.addWidget(self.transparency_slider)
        settings_layout.addLayout(transparency_layout)

        # Volume Slider with Label
        volume_layout = QHBoxLayout()
        self.volume_label = QLabel("Volume:", self.settings_menu)
        self.volume_slider = QSlider(Qt.Horizontal, self.settings_menu)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(80)  # Default volume level
        self.volume_slider.valueChanged.connect(self.adjust_volume)
        volume_layout.addWidget(self.volume_label)
        volume_layout.addWidget(self.volume_slider)
        settings_layout.addLayout(volume_layout)

        # Click-Through Mode Toggle
        self.click_through_button = QPushButton("🖱️ Click-Through: OFF", self.settings_menu)
        self.click_through_button.clicked.connect(self.toggle_click_through)
        self.click_through_button.setStyleSheet("background-color: white; color: black;")
        settings_layout.addWidget(self.click_through_button)
        self.update_click_through_button()

        # Animation Test Dropdown
        animation_test_layout = QHBoxLayout()
        animation_test_label = QLabel("Test Animation:", self.settings_menu)
        self.animation_test_dropdown = QComboBox(self.settings_menu)
        
        # Add animation states to dropdown
        for state in ANIMATION_STATES:
            self.animation_test_dropdown.addItem(state)
        
        self.animation_test_dropdown.currentTextChanged.connect(self.test_animation)
        animation_test_layout.addWidget(animation_test_label)
        animation_test_layout.addWidget(self.animation_test_dropdown)
        settings_layout.addLayout(animation_test_layout)

        # Import Custom Theme Button
        self.import_theme_button = QPushButton("Import Custom Theme", self.settings_menu)
        self.import_theme_button.clicked.connect(self.import_custom_theme)
        self.import_theme_button.setStyleSheet("background-color: white; color: black;")
        settings_layout.addWidget(self.import_theme_button)

        # Hide settings button
        self.hide_settings_button = QPushButton("Hide Settings", self.settings_menu)
        self.hide_settings_button.clicked.connect(self.toggle_settings)
        self.hide_settings_button.setStyleSheet("background-color: white; color: black;")
        settings_layout.addWidget(self.hide_settings_button)

        # Safe Termination Button
        self.exit_button = QPushButton("Exit Program", self.settings_menu)
        self.exit_button.clicked.connect(self.safe_exit)
        self.exit_button.setStyleSheet("background-color: red; color: white;")
        settings_layout.addWidget(self.exit_button)

        # Add animations to main layout (won't use the container's layout)
        self.main_layout.addWidget(self.animation_container)
        
        # Register interactive areas
        self.update_interactive_areas()

    def setup_system_tray(self):
        """Create system tray icon with menu"""
        try:
            self.tray_icon = QSystemTrayIcon(self)
            
            # Get tray icon path from config or use default
            tray_config = self.config_manager.get_config("system_tray", None, {})
            tray_icon_path = tray_config.get("tray_icon_path", os.path.join(ASSETS_FOLDER, "static.png"))
            
            if os.path.exists(tray_icon_path):
                self.tray_icon.setIcon(QIcon(tray_icon_path))
            else:
                logger.warning(f"Tray icon not found: {tray_icon_path}")
                # Try to find any PNG in assets folder as fallback
                for file in os.listdir(ASSETS_FOLDER):
                    if file.endswith(".png"):
                        fallback_path = os.path.join(ASSETS_FOLDER, file)
                        logger.info(f"Using fallback tray icon: {fallback_path}")
                        self.tray_icon.setIcon(QIcon(fallback_path))
                        break
            
            # Create tray menu
            tray_menu = QMenu()
            show_action = QAction("Show/Hide", self)
            settings_action = QAction("Settings", self)
            exit_action = QAction("Exit", self)
            
            # Add animation state submenu
            animation_menu = tray_menu.addMenu("Set Animation")
            for state in ANIMATION_STATES:
                action = QAction(f"{state}", self)
                action.triggered.connect(lambda checked=False, s=state: self.set_animation(s))
                animation_menu.addAction(action)
            
            # Add actions to menu
            tray_menu.addAction(show_action)
            tray_menu.addAction(settings_action)
            tray_menu.addSeparator()
            tray_menu.addAction(exit_action)
            
            # Connect actions
            show_action.triggered.connect(self.toggle_visibility)
            settings_action.triggered.connect(self.show_settings)
            exit_action.triggered.connect(self.safe_exit)
            
            # Set context menu and show tray icon
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()
            
            # Setup double-click behavior
            self.tray_icon.activated.connect(self.tray_icon_activated)
            
            logger.info("System tray icon initialized successfully")
        except Exception as e:
            ErrorHandler.log_error(e, "Failed to initialize system tray")

    def tray_icon_activated(self, reason):
        """Handle tray icon activation events"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_visibility()

    def toggle_visibility(self):
        """Toggle the visibility of the main window"""
        if self.isVisible():
            self.hide()
            logger.info("Presence window hidden")
            
            # Post event about visibility change
            self.event_bus.post_event(
                Event(
                    EventType.WINDOW_STATE,
                    {"visible": False},
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
                    EventType.WINDOW_STATE,
                    {"visible": True},
                    EventPriority.LOW,
                    "presence_gui"
                )
            )

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
                    EventType.THEME_CHANGE,
                    {"theme": theme_name},
                    EventPriority.NORMAL,
                    "presence_gui"
                )
            )
            
            # Refresh current animation
            if self.current_animation:
                self.set_animation(self.current_animation)

    def import_custom_theme(self):
        """Import a custom theme from a directory with robust error handling"""
        try:
            theme_dir = QFileDialog.getExistingDirectory(self, "Select Theme Directory")
            if not theme_dir:
                return
            
            # Get theme name
            theme_name = os.path.basename(theme_dir)
            if theme_name in self.themes:
                confirm = QMessageBox.question(self, "Theme Already Exists", 
                                            f"Theme '{theme_name}' already exists. Overwrite?", 
                                            QMessageBox.Yes | QMessageBox.No)
                if confirm == QMessageBox.No:
                    return
            
            # Create theme structure
            new_theme = {}
            
            # Track import success
            success_count = 0
            error_count = 0
            
            for state in ANIMATION_STATES:
                # Look for file with same name as state
                imported = False
                for ext in ['.gif', '.png']:
                    file_path = os.path.join(theme_dir, f"{state}{ext}")
                    if os.path.exists(file_path):
                        # Copy file to assets folder
                        target_file = f"{theme_name}_{state}{ext}"
                        target_path = os.path.join(ASSETS_FOLDER, target_file)
                        try:
                            with open(file_path, 'rb') as src, open(target_path, 'wb') as dst:
                                dst.write(src.read())
                            
                            # Register with resource manager
                            self.resource_manager.register_resource(
                                f"theme_{theme_name}_{state}",
                                target_path
                            )
                            
                            new_theme[state] = target_file
                            success_count += 1
                            imported = True
                            break
                        except Exception as e:
                            ErrorHandler.log_error(e, f"Error copying theme file: {file_path}")
                            error_count += 1
                
                # If no file found for this state, use default
                if not imported:
                    new_theme[state] = self.themes["default"].get(state, "static.png")
            
            # Add new theme
            self.themes[theme_name] = new_theme
            self.save_themes()
            
            # Update theme selector
            self.theme_selector.addItem(theme_name)
            self.theme_selector.setCurrentText(theme_name)
            
            # Show status message
            if error_count > 0:
                QMessageBox.warning(self, "Theme Import", 
                                    f"Theme imported with {success_count} files.\n{error_count} files failed to import.")
            else:
                QMessageBox.information(self, "Theme Import", 
                                        f"Theme '{theme_name}' imported successfully with {success_count} animations.")
            
            logger.info(f"Imported theme: {theme_name} with {success_count} animations")
        except Exception as e:
            ErrorHandler.log_error(e, "Failed to import theme")
            QMessageBox.critical(self, "Theme Import Error", 
                                 f"Failed to import theme: {str(e)}")

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
                self.cross_fade(animation_config.get("transition_duration", 300))
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

    def cross_fade(self, duration=300):
        """Perform cross-fade transition between animations"""
        self.transition_in_progress = True
        
        # Create fade-out animation for current label
        self.fade_out = QPropertyAnimation(self.current_label, b"opacity")
        self.fade_out.setDuration(duration)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.OutQuad)
        
        # Create fade-in animation for next label
        self.fade_in = QPropertyAnimation(self.next_label, b"opacity")
        self.fade_in.setDuration(duration)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.InQuad)
        
        # Connect finished signal to complete transition
        self.fade_out.finished.connect(self.complete_transition)
        
        # Start animations
        self.fade_out.start()
        self.fade_in.start()

    def toggle_settings(self):
        """Show or hide the settings menu"""
        if hasattr(self, 'settings_menu'):
            if self.settings_menu.isVisible():
                self.settings_menu.hide()
                logger.info("Settings menu hidden")
            else:
                self.settings_menu.show()
                logger.info("Settings menu shown")

    def complete_transition(self):
        """Complete the transition between animations by swapping labels"""
        # Swap the current and next label references
        temp_movie = None
        temp_pixmap = None
        temp_resource_id = None
        
        # Save current movie or pixmap
        if hasattr(self.current_label, 'movie') and self.current_label.movie():
            temp_movie = self.current_label.movie()
        elif hasattr(self.current_label, 'pixmap') and not self.current_label.pixmap().isNull():
            temp_pixmap = self.current_label.pixmap()
        
        # Save resource ID
        if hasattr(self.current_label, 'movie_resource_id'):
            temp_resource_id = self.current_label.movie_resource_id
        
        # Update current label with next label's content
        if hasattr(self.next_label, 'movie') and self.next_label.movie():
            self.current_label.setMovie(self.next_label.movie())
            self.current_label.movie_resource_id = self.next_label.movie_resource_id
            self.next_label.setMovie(None)
        elif hasattr(self.next_label, 'pixmap') and not self.next_label.pixmap().isNull():
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
        lock_text = "Position Locked 🔒" if self.locked else "Position Unlocked 🔓"
        self.lock_button.setText(lock_text)
        
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
        
        # Update flags based on new state
        if self.click_through_enabled:
            # Enable click-through
            self.setWindowFlags(self.windowFlags() | Qt.WindowTransparentForInput)
        else:
            # Disable click-through
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowTransparentForInput)
        
        # Update button text
        self.update_click_through_button()
        
        # Show window again since changing flags hides it
        self.show()
        
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

    def update_click_through_button(self):
        """Update the click-through button text based on current state"""
        if hasattr(self, 'click_through_button'):
            button_text = "🖱️ Click-Through: ON" if self.click_through_enabled else "🖱️ Click-Through: OFF"
            self.click_through_button.setText(button_text)

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

    def show_settings(self):
        """Show the settings menu"""
        if hasattr(self, 'settings_menu') and not self.settings_menu.isVisible():
            self.settings_menu.show()
            logger.info("Settings menu shown")

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
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().quit()

    def mousePressEvent(self, event):
        """Handle mouse press events for dragging the window"""
        if event.button() == Qt.LeftButton and self.drag_enabled:
            # Store the position if clicking on a non-interactive area
            if not self.is_in_interactive_area(event.pos()):
                self.old_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move events for dragging the window"""
        if self.old_pos and self.drag_enabled:
            delta = event.pos() - self.old_pos
            self.move(self.pos() + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events for dragging the window"""
        if event.button() == Qt.LeftButton:
            self.old_pos = None
        super().mouseReleaseEvent(event)

    def start_event_listener(self):
        """Start event listener for external events"""
        logger.info("Started event listener")
        # This method is called during initialization to set up event listeners
        # It's already implemented in the __init__ method but needs to be defined
        pass

    def toggle_settings(self):
        """Show or hide the settings menu"""
        if hasattr(self, 'settings_menu'):
            if self.settings_menu.isVisible():
                self.settings_menu.hide()
                logger.info("Settings menu hidden")
            else:
                self.settings_menu.show()
                logger.info("Settings menu shown")
