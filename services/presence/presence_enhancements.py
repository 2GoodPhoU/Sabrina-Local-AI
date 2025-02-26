from PyQt5.QtWidgets import (QMainWindow, QLabel, QPushButton, QSlider, QVBoxLayout, 
                            QWidget, QHBoxLayout, QSystemTrayIcon, QMenu, QAction, 
                            QColorDialog, QComboBox, QFileDialog, QMessageBox)
from PyQt5.QtCore import QTimer, Qt, QPoint, QPropertyAnimation, QEasingCurve, QByteArray, pyqtProperty, QRect
from PyQt5.QtGui import QMovie, QPixmap, QIcon, QColor, QPainter, QImage
import sys
import os
import json
import screeninfo
from presence_constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, PADDING_RIGHT, ENABLE_TRANSPARENCY, TRANSPARENCY_LEVEL,
    CLICK_THROUGH_MODE, ENABLE_DRAGGING, LOCK_POSITION, ASSETS_FOLDER, DEFAULT_ANIMATION,
    ANIMATION_PRIORITY, ANIMATION_STATES
)
from animation_manager import AnimationManager

class AnimatedLabel(QLabel):
    """Enhanced QLabel with animation properties"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 1.0
        self.setStyleSheet("background: transparent;")

    def setOpacity(self, opacity):
        self._opacity = opacity
        self.update()

    def getOpacity(self):
        return self._opacity

    # Define property for QPropertyAnimation
    opacity = pyqtProperty(float, getOpacity, setOpacity)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        super().paintEvent(event)


class EnhancedPresenceGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # Get screen dimensions
        screen = screeninfo.get_monitors()[0]  
        screen_width, screen_height = screen.width, screen.height

        # Set window position
        self.x_position = screen_width - WINDOW_WIDTH - PADDING_RIGHT
        self.y_position = (screen_height // 2) - (WINDOW_HEIGHT // 2)

        # Configure window properties - important to set flags here
        self.setGeometry(self.x_position, self.y_position, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)  
        
        # Set transparency
        if ENABLE_TRANSPARENCY:
            self.setAttribute(Qt.WA_TranslucentBackground)  
            self.setWindowOpacity(TRANSPARENCY_LEVEL)  

        # Dragging and position locking
        self.drag_enabled = ENABLE_DRAGGING and not LOCK_POSITION
        self.locked = LOCK_POSITION
        self.old_pos = None

        # Animation and themes
        self.current_theme = "default"
        self.themes = self.load_themes()
        
        # Interactive areas tracking
        self.interactive_areas = []

        # Setup UI Components
        self.setup_ui()
        
        # Initial click-through status - make sure flags are set correctly based on initial state
        if CLICK_THROUGH_MODE:
            self.setWindowFlags(self.windowFlags() | Qt.WindowTransparentForInput)
            
        # Setup System Tray
        self.setup_system_tray()
        
        # Setup Animation Manager
        self.animation_manager = AnimationManager(ASSETS_FOLDER)
        self.current_animation = None
        self.animation_opacity = 1.0
        self.transition_in_progress = False
        
        # Set default animation
        default_animation = self.animation_manager.animations.get(DEFAULT_ANIMATION, None)
        if default_animation:
            self.set_animation(DEFAULT_ANIMATION)

        # Start event listener
        self.start_event_listener()
        
    def is_in_interactive_area(self, pos):
        """Check if a point is in an interactive area (settings menu, buttons)"""
        # Check settings menu
        if self.settings_menu.isVisible() and self.settings_menu.geometry().contains(pos):
            return True
            
        # Check settings button
        if self.settings_button.geometry().contains(pos):
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
        self.current_label.setGeometry(0, animation_top_margin, WINDOW_WIDTH, WINDOW_HEIGHT - animation_top_margin)
        self.next_label.setGeometry(0, animation_top_margin, WINDOW_WIDTH, WINDOW_HEIGHT - animation_top_margin)
        
        # Settings button in top right corner
        self.settings_button = QPushButton("⚙", self)
        self.settings_button.setGeometry(WINDOW_WIDTH - 30, 5, 25, 25)
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
        self.transparency_slider.setValue(int(TRANSPARENCY_LEVEL * 100))
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
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(os.path.join(ASSETS_FOLDER, "static.png")))
        
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

    def tray_icon_activated(self, reason):
        """Handle tray icon activation events"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_visibility()

    def toggle_visibility(self):
        """Toggle the visibility of the main window"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    def load_themes(self):
        """Load animation themes"""
        themes_file = os.path.join(ASSETS_FOLDER, "themes.json")
        default_themes = {
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
        
        if os.path.exists(themes_file):
            try:
                with open(themes_file, 'r') as f:
                    themes = json.load(f)
                return themes
            except Exception as e:
                print(f"Error loading themes file: {e}")
        
        # Create default themes file if it doesn't exist
        try:
            with open(themes_file, 'w') as f:
                json.dump(default_themes, f, indent=4)
        except Exception as e:
            print(f"Error creating themes file: {e}")
        
        return default_themes

    def save_themes(self):
        """Save themes to JSON file"""
        themes_file = os.path.join(ASSETS_FOLDER, "themes.json")
        try:
            with open(themes_file, 'w') as f:
                json.dump(self.themes, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving themes file: {e}")
            return False

    def change_theme(self, theme_name):
        """Change the current animation theme"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            # Refresh current animation
            if self.current_animation:
                self.set_animation(self.current_animation)

    def import_custom_theme(self):
        """Import a custom theme from a directory"""
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
        for state in ANIMATION_STATES:
            # Look for file with same name as state
            for ext in ['.gif', '.png']:
                file_path = os.path.join(theme_dir, f"{state}{ext}")
                if os.path.exists(file_path):
                    # Copy file to assets folder
                    target_file = f"{theme_name}_{state}{ext}"
                    target_path = os.path.join(ASSETS_FOLDER, target_file)
                    try:
                        with open(file_path, 'rb') as src, open(target_path, 'wb') as dst:
                            dst.write(src.read())
                        new_theme[state] = target_file
                        break
                    except Exception as e:
                        print(f"Error copying theme file: {e}")
            
            # If no file found for this state, use default
            if state not in new_theme:
                new_theme[state] = self.themes["default"].get(state, "static.png")
        
        # Add new theme
        self.themes[theme_name] = new_theme
        self.save_themes()
        
        # Update theme selector
        self.theme_selector.addItem(theme_name)
        self.theme_selector.setCurrentText(theme_name)

    def set_animation(self, state):
        """Set the animation with smooth transition"""
        if state not in ANIMATION_STATES:
            print(f"Unknown animation state: {state}")
            return False
            
        # Get theme-specific animation file
        animation_file = self.themes[self.current_theme].get(state)
        if not animation_file:
            print(f"No animation file for state: {state} in theme: {self.current_theme}")
            return False
            
        animation_path = os.path.join(ASSETS_FOLDER, animation_file)
        if not os.path.exists(animation_path):
            print(f"Animation file not found: {animation_path}")
            return False
        
        # If same animation is already playing, don't transition
        if self.current_animation == state:
            return True
            
        # Store the animation state
        self.current_animation = state
        
        # Check if transition is already in progress and cancel it if needed
        if self.transition_in_progress:
            if hasattr(self, 'fade_out') and self.fade_out.state() == QPropertyAnimation.Running:
                self.fade_out.stop()
            if hasattr(self, 'fade_in') and self.fade_in.state() == QPropertyAnimation.Running:
                self.fade_in.stop()
        
        # Stop any existing movie on the next label
        if hasattr(self.next_label, 'movie') and self.next_label.movie():
            self.next_label.movie().stop()
            self.next_label.setMovie(None)
            
        # Prepare next animation
        if animation_path.endswith('.png'):
            # Static image
            self.next_label.setPixmap(QPixmap(animation_path))
        else:
            # Animated GIF
            try:
                movie = QMovie(animation_path)
                movie.setCacheMode(QMovie.CacheAll)
                movie.setScaledSize(self.next_label.size())  # Scale to fit label
                movie.loopCount = -1  # Infinite loop
                self.next_label.setMovie(movie)
                movie.start()
            except Exception as e:
                print(f"Error loading animation {animation_path}: {e}")
                # Fallback to static image if available
                static_path = os.path.join(ASSETS_FOLDER, "static.png")
                if os.path.exists(static_path):
                    self.next_label.setPixmap(QPixmap(static_path))
                    print(f"Using fallback static image: {static_path}")
        
        # Perform cross-fade transition
        self.cross_fade()
        return True

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

    def complete_transition(self):
        """Complete the transition by swapping labels"""
        # Stop the old animation completely before swapping
        if hasattr(self.current_label, 'movie') and self.current_label.movie():
            self.current_label.movie().stop()
            self.current_label.setMovie(None)  # Remove the movie entirely
        
        # Swap the current and next labels
        temp_label = self.current_label
        self.current_label = self.next_label
        self.next_label = temp_label
        
        # Make sure the next label is completely transparent
        self.next_label.setOpacity(0.0)
        
        # Mark transition as completed
        self.transition_in_progress = False

    def update_interactive_areas(self):
        """Update the list of interactive areas"""
        self.interactive_areas = []
        
        # Add settings button
        self.interactive_areas.append(self.settings_button.geometry())
        
        # Add settings menu and all its children if visible
        if self.settings_menu.isVisible():
            self.interactive_areas.append(self.settings_menu.geometry())
            
            # Add all buttons and controls in the settings menu
            for child in self.settings_menu.findChildren(QWidget):
                if child.isVisible():
                    # Convert child's local coordinates to parent coordinates
                    child_geo = child.geometry()
                    global_geo = QRect(
                        self.settings_menu.mapToParent(child_geo.topLeft()),
                        child_geo.size()
                    )
                    self.interactive_areas.append(global_geo)

    def toggle_lock(self):
        """Toggle Lock Position setting"""
        self.locked = not self.locked
        self.drag_enabled = not self.locked
        self.lock_button.setText("Position Locked 🔒" if self.locked else "Position Unlocked 🔓")

    def adjust_transparency(self, value):
        """Adjust window transparency using the slider"""
        self.setWindowOpacity(value / 100)
        self.repaint()

    def adjust_volume(self, value):
        """Adjust volume level (to be connected to voice API)"""
        print(f"Volume set to {value}%")  # Placeholder for voice API connection

    def toggle_click_through(self):
        """Toggle Click-Through mode while keeping settings interactive"""
        global CLICK_THROUGH_MODE
        CLICK_THROUGH_MODE = not CLICK_THROUGH_MODE
        
        # Update window flag to enable click-through
        if CLICK_THROUGH_MODE:
            # Set window to be transparent for input
            self.setWindowFlags(self.windowFlags() | Qt.WindowTransparentForInput)
            self.show()  # Need to call show() to apply flag changes
            
            # Make settings button interactive again by setting it as a subwindow
            # This is a trick to override the parent window's transparent input flag
            self.settings_button.setWindowFlags(Qt.SubWindow)
            self.settings_button.show()
            
            # If settings menu is visible, keep it interactive
            if self.settings_menu.isVisible():
                self.settings_menu.setWindowFlags(Qt.SubWindow)
                self.settings_menu.show()
        else:
            # Remove transparent input flag
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowTransparentForInput)
            self.show()  # Need to call show() to apply flag changes
            
            # Reset settings button flags
            self.settings_button.setWindowFlags(Qt.Widget)
            self.settings_button.show()
            
            # Reset settings menu flags if visible
            if self.settings_menu.isVisible():
                self.settings_menu.setWindowFlags(Qt.Widget)
                self.settings_menu.show()
        
        self.update_click_through_button()
        
    def toggle_settings(self):
        """Toggle the visibility of the settings menu"""
        visible = not self.settings_menu.isVisible()
        self.settings_menu.setVisible(visible)
        
        # If in click-through mode, we need to handle settings menu visibility specially
        if CLICK_THROUGH_MODE and visible:
            self.settings_menu.setWindowFlags(Qt.SubWindow)
            self.settings_menu.show()
        
        # Update interactive areas when settings visibility changes
        self.update_interactive_areas()
    
    def update_click_through_button(self):
        """Update button text based on Click-Through mode"""
        self.click_through_button.setText(f"🖱️ Click-Through: {'ON' if CLICK_THROUGH_MODE else 'OFF'}")
    
    def test_animation(self, state):
        """Test a specific animation state"""
        if state in ANIMATION_STATES:
            self.set_animation(state)

    def show_settings(self):
        """Show the settings menu"""
        self.show()  # Make sure window is visible
        self.settings_menu.show()
        self.activateWindow()
        self.update_interactive_areas()
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        # With the new approach using WindowTransparentForInput,
        # this will only be called when click-through is OFF or
        # when clicking on the settings button or menu
        
        if event.button() == Qt.RightButton:
            # Show context menu on right-click
            self.show_context_menu(event.globalPos())
        elif event.button() == Qt.LeftButton:
            # Check if we're on a draggable area (not settings)
            if not self.locked and not self.is_in_interactive_area(event.pos()):
                self.old_pos = event.globalPos()
                # Also handle interaction
                self.handle_interaction()
            else:
                # Let the event propagate to interactive elements
                super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Allow dragging if enabled and unlocked"""
        # Let interactive elements handle their own mouse moves
        if self.is_in_interactive_area(event.pos()):
            super().mouseMoveEvent(event)
            return
            
        # Handle dragging
        if not self.locked and self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
            
    def mouseReleaseEvent(self, event):
        """Reset position tracking on release"""
        # Let interactive elements handle their own mouse releases
        if self.is_in_interactive_area(event.pos()):
            super().mouseReleaseEvent(event)
            return
            
        # Reset dragging position
        if not self.locked and event.button() == Qt.LeftButton:
            self.old_pos = None
    
    def show_context_menu(self, position):
        """Show a context menu at the given position"""
        context_menu = QMenu()
        
        # Animation states submenu
        animation_menu = context_menu.addMenu("Set Animation")
        for state in ANIMATION_STATES:
            action = QAction(f"{state}", self)
            action.triggered.connect(lambda checked=False, s=state: self.set_animation(s))
            animation_menu.addAction(action)
            
        # Other quick actions
        context_menu.addSeparator()
        settings_action = context_menu.addAction("Open Settings")
        toggle_visibility = context_menu.addAction("Hide Window")
        context_menu.addSeparator()
        exit_action = context_menu.addAction("Exit")
        
        # Connect actions
        settings_action.triggered.connect(self.show_settings)
        toggle_visibility.triggered.connect(self.toggle_visibility)
        exit_action.triggered.connect(self.safe_exit)
        
        # Show the menu
        context_menu.exec_(position)

    def handle_interaction(self):
        """Handle direct interaction with the AI presence"""
        # Example: Trigger the "listening" state when clicked
        self.set_animation("listening")
        
        # Here you could also:
        # 1. Trigger voice activation
        # 2. Show a quick command panel
        # 3. Trigger a specific AI function
        print("[INTERACTION] User clicked on AI presence")
    
    def start_event_listener(self):
        """Start queue processing for animations"""
        QTimer.singleShot(100, self.process_queue)
    
    def process_queue(self):
        """Process animations from queue"""
        if hasattr(self, 'animation_manager'):
            if self.animation_manager.queue:
                next_animation = self.animation_manager.queue.pop(0)
                self.set_animation(next_animation)
        QTimer.singleShot(100, self.process_queue)
    
    def safe_exit(self):
        """Safely close the program"""
        print("[INFO] Safe termination initiated.")
        
        # Stop all animations
        if hasattr(self.current_label, 'movie') and self.current_label.movie():
            self.current_label.movie().stop()
        
        if hasattr(self.next_label, 'movie') and self.next_label.movie():
            self.next_label.movie().stop()
            
        # Hide tray icon before exiting
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
            
        # Save themes if modified
        self.save_themes()
        
        # Close window and exit application
        self.close()
        sys.exit()