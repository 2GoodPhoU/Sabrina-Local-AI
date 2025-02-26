# Updating presence_gui.py to fix locking and transparency issues

from PyQt5.QtWidgets import QMainWindow, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget, QHBoxLayout
from PyQt5.QtCore import QTimer, Qt, QPoint
import sys
import screeninfo
from presence_constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, PADDING_RIGHT, ENABLE_TRANSPARENCY, TRANSPARENCY_LEVEL,
    CLICK_THROUGH_MODE, ENABLE_DRAGGING, LOCK_POSITION, ASSETS_FOLDER, DEFAULT_ANIMATION
)
from animation_manager import AnimationManager

class PresenceGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        screen = screeninfo.get_monitors()[0]  
        screen_width, screen_height = screen.width, screen.height

        self.x_position = screen_width - WINDOW_WIDTH - PADDING_RIGHT
        self.y_position = (screen_height // 2) - (WINDOW_HEIGHT // 2)

        self.setGeometry(self.x_position, self.y_position, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)  
        if ENABLE_TRANSPARENCY:
            self.setAttribute(Qt.WA_TranslucentBackground)  
            self.setWindowOpacity(TRANSPARENCY_LEVEL)  

        self.drag_enabled = ENABLE_DRAGGING and not LOCK_POSITION
        self.locked = LOCK_POSITION  # Ensure locking state persists
        self.old_pos = None

        self.label = QLabel(self)
        self.label.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: transparent;")  # Ensure no background artifacts

        # Settings button
        self.settings_button = QPushButton("⚙", self)
        self.settings_button.setGeometry(WINDOW_WIDTH - 30, 5, 25, 25)
        self.settings_button.clicked.connect(self.toggle_settings)
        self.settings_button.setStyleSheet("background-color: white; color: black; border-radius: 5px;")

        # Settings menu UI
        self.settings_menu = QWidget(self)
        self.settings_menu.setGeometry(10, 40, 250, 220)
        self.settings_menu.setStyleSheet("background-color: rgba(255, 255, 255, 220); border-radius: 10px;")
        self.settings_menu.hide()

        layout = QVBoxLayout()

        # Lock position toggle
        self.lock_button = QPushButton("Position Unlocked 🔓", self.settings_menu)
        self.lock_button.clicked.connect(self.toggle_lock)
        self.lock_button.setStyleSheet("background-color: white; color: black;")
        layout.addWidget(self.lock_button)

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
        layout.addLayout(transparency_layout)

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
        layout.addLayout(volume_layout)

        # Click-Through Mode Toggle
        self.click_through_button = QPushButton("🖱️ Click-Through: OFF", self.settings_menu)
        self.click_through_button.clicked.connect(self.toggle_click_through)
        self.click_through_button.setStyleSheet("background-color: white; color: black;")
        layout.addWidget(self.click_through_button)
        self.update_click_through_button()

        # Hide settings button
        self.hide_settings_button = QPushButton("Hide Settings", self.settings_menu)
        self.hide_settings_button.clicked.connect(self.toggle_settings)
        self.hide_settings_button.setStyleSheet("background-color: white; color: black;")
        layout.addWidget(self.hide_settings_button)

        # Safe Termination Button
        self.exit_button = QPushButton("Exit Program", self.settings_menu)
        self.exit_button.clicked.connect(self.safe_exit)
        self.exit_button.setStyleSheet("background-color: red; color: white;")
        layout.addWidget(self.exit_button)

        self.settings_menu.setLayout(layout)

        # Animation handling
        self.animation_manager = AnimationManager(ASSETS_FOLDER)
        default_animation = self.animation_manager.animations.get(DEFAULT_ANIMATION, None)
        if default_animation:
            self.animation_manager.set_animation(DEFAULT_ANIMATION, self.label)

        self.start_event_listener()

    def start_event_listener(self):
        """Start queue processing for animations."""
        QTimer.singleShot(100, self.process_queue)

    def process_queue(self):
        """Process animations from queue."""
        self.animation_manager.process_queue(self.label)
        QTimer.singleShot(100, self.process_queue)

    def toggle_settings(self):
        """Toggle the visibility of the settings menu."""
        self.settings_menu.setVisible(not self.settings_menu.isVisible())

    def toggle_lock(self):
        """Toggle Lock Position setting."""
        self.locked = not self.locked
        self.drag_enabled = not self.locked
        self.lock_button.setText("Position Unlocked 🔓" if self.locked else "Position Locked 🔒")

    def adjust_transparency(self, value):
        """Adjust window transparency using the slider."""
        self.setWindowOpacity(value / 100)
        self.repaint()  # Ensure transparency updates correctly

    def adjust_volume(self, value):
        """Adjust volume level (to be connected to voice API)."""
        print(f"Volume set to {value}%")  # Placeholder for voice API connection

    def toggle_click_through(self):
        """Toggle Click-Through mode while keeping settings interactive."""
        global CLICK_THROUGH_MODE
        CLICK_THROUGH_MODE = not CLICK_THROUGH_MODE

        if CLICK_THROUGH_MODE:
            self.setWindowFlags(self.windowFlags() | Qt.WindowTransparentForInput)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowTransparentForInput)

        self.show()  # Refresh window to apply change
        self.update_click_through_button()

    def update_click_through_button(self):
        """Update button text based on Click-Through mode."""
        self.click_through_button.setText(f"Clickable 🖱️: {'ON' if CLICK_THROUGH_MODE else 'OFF'}")

    def safe_exit(self):
        """Safely close the program."""
        print("[INFO] Safe termination initiated.")
        self.close()
        sys.exit()

    def mousePressEvent(self, event):
        """Ensure settings menu and button remain interactive when click-through is enabled."""
        if self.settings_menu.isVisible() or self.settings_button.underMouse():
            return  # Prevent click-through when interacting with settings
        if not self.locked and event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        """Allow dragging if enabled and unlocked."""
        if not self.locked and self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        """Reset position tracking on release."""
        if not self.locked and event.button() == Qt.LeftButton:
            self.old_pos = None
