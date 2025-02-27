"""
Fixed SettingsMenu initialization to handle potential missing attributes safely.
"""
from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QSlider, QVBoxLayout,
                             QHBoxLayout, QComboBox, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt
import os
import json

from ..utils.error_handling import logger, ErrorHandler
from ..constants import ANIMATION_STATES, ASSETS_FOLDER

class SettingsMenu(QWidget):
    """Settings menu UI and functionality"""
    
    def __init__(self, parent, config_manager, resource_manager, event_bus):
        """Initialize settings menu
        
        Args:
            parent: Parent window (PresenceGUI)
            config_manager: Configuration manager instance
            resource_manager: Resource manager instance
            event_bus: Event bus instance
        """
        super().__init__(parent)
        
        self.parent = parent
        self.config_manager = config_manager
        self.resource_manager = resource_manager
        self.event_bus = event_bus
        
        # Get configuration
        window_config = self.config_manager.get_config("window", None, {})
        interaction_config = self.config_manager.get_config("interaction", None, {})
        
        # Configure widget
        self.setGeometry(10, 40, 250, 300)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 220); border-radius: 10px;")
        
        # Setup UI components
        self.setup_ui()
        
        # Hide initially
        self.hide()
    
    def setup_ui(self):
        """Setup settings menu UI components"""
        # Create layout
        layout = QVBoxLayout(self)
        
        # Position lock toggle
        is_locked = getattr(self.parent, 'locked', False)
        self.lock_button = QPushButton(
            "Position Locked 🔒" if is_locked else "Position Unlocked 🔓", 
            self
        )
        self.lock_button.clicked.connect(self.parent.toggle_lock)
        self.lock_button.setStyleSheet("background-color: white; color: black;")
        layout.addWidget(self.lock_button)

        # Theme selector
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:", self)
        self.theme_selector = QComboBox(self)
        
        # Add available themes
        themes = getattr(self.parent, 'themes', {})
        for theme in themes.keys():
            self.theme_selector.addItem(theme)
        
        # Set current theme
        current_theme = getattr(self.parent, 'current_theme', 'default')
        index = self.theme_selector.findText(current_theme)
        if index >= 0:
            self.theme_selector.setCurrentIndex(index)
        
        self.theme_selector.currentTextChanged.connect(self.parent.change_theme)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_selector)
        layout.addLayout(theme_layout)

        # Transparency Slider with Label
        transparency_layout = QHBoxLayout()
        self.transparency_label = QLabel("Transparency:", self)
        self.transparency_slider = QSlider(Qt.Horizontal, self)
        self.transparency_slider.setMinimum(10)
        self.transparency_slider.setMaximum(100)
        
        # Get transparency level from config
        window_config = self.config_manager.get_config("window", None, {})
        transparency_level = window_config.get("transparency_level", 0.85)
        self.transparency_slider.setValue(int(transparency_level * 100))
        
        self.transparency_slider.valueChanged.connect(self.parent.adjust_transparency)
        transparency_layout.addWidget(self.transparency_label)
        transparency_layout.addWidget(self.transparency_slider)
        layout.addLayout(transparency_layout)

        # Volume Slider with Label
        volume_layout = QHBoxLayout()
        self.volume_label = QLabel("Volume:", self)
        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        
        # Get volume from config
        voice_config = self.config_manager.get_config("voice", None, {})
        volume = voice_config.get("volume", 0.8)
        self.volume_slider.setValue(int(volume * 100))
        
        self.volume_slider.valueChanged.connect(self.parent.adjust_volume)
        volume_layout.addWidget(self.volume_label)
        volume_layout.addWidget(self.volume_slider)
        layout.addLayout(volume_layout)

        # Click-Through Mode Toggle
        self.click_through_button = QPushButton("🖱️ Click-Through: OFF", self)
        self.click_through_button.clicked.connect(self.parent.toggle_click_through)
        self.click_through_button.setStyleSheet("background-color: white; color: black;")
        layout.addWidget(self.click_through_button)
        self.update_click_through_button()

        # Animation Test Dropdown
        animation_test_layout = QHBoxLayout()
        animation_test_label = QLabel("Test Animation:", self)
        self.animation_test_dropdown = QComboBox(self)
        
        # Add animation states to dropdown
        for state in ANIMATION_STATES:
            self.animation_test_dropdown.addItem(state)
        
        self.animation_test_dropdown.currentTextChanged.connect(self.parent.test_animation)
        animation_test_layout.addWidget(animation_test_label)
        animation_test_layout.addWidget(self.animation_test_dropdown)
        layout.addLayout(animation_test_layout)

        # Import Custom Theme Button
        self.import_theme_button = QPushButton("Import Custom Theme", self)
        self.import_theme_button.clicked.connect(self.import_custom_theme)
        self.import_theme_button.setStyleSheet("background-color: white; color: black;")
        layout.addWidget(self.import_theme_button)

        # Hide settings button
        self.hide_settings_button = QPushButton("Hide Settings", self)
        self.hide_settings_button.clicked.connect(self.parent.toggle_settings)
        self.hide_settings_button.setStyleSheet("background-color: white; color: black;")
        layout.addWidget(self.hide_settings_button)

        # Safe Termination Button
        self.exit_button = QPushButton("Exit Program", self)
        self.exit_button.clicked.connect(self.parent.safe_exit)
        self.exit_button.setStyleSheet("background-color: red; color: white;")
        layout.addWidget(self.exit_button)
    
    def update_click_through_button(self):
        """Update click-through button text based on current state"""
        if hasattr(self, 'click_through_button'):
            # Safely get click_through_enabled from parent with fallback to config
            is_enabled = False
            if hasattr(self.parent, 'click_through_enabled'):
                is_enabled = self.parent.click_through_enabled
            else:
                # Fallback to config if attribute is not set yet
                interaction_config = self.config_manager.get_config("interaction", None, {})
                is_enabled = interaction_config.get("click_through_mode", False)
                
            button_text = "🖱️ Click-Through: ON" if is_enabled else "🖱️ Click-Through: OFF"
            self.click_through_button.setText(button_text)
    
    def import_custom_theme(self):
        """Import a custom theme from a directory"""
        try:
            theme_dir = QFileDialog.getExistingDirectory(self, "Select Theme Directory")
            if not theme_dir:
                return
            
            # Get theme name
            theme_name = os.path.basename(theme_dir)
            if theme_name in self.parent.themes:
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
                    new_theme[state] = self.parent.themes["default"].get(state, "static.png")
            
            # Add new theme
            self.parent.themes[theme_name] = new_theme
            self.parent.save_themes()
            
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