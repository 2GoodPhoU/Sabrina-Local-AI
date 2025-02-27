"""
System tray integration for Sabrina's Presence System
Provides system tray icon and menu functionality
"""
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon
import os

from ..utils.error_handling import logger, ErrorHandler
from ..constants import ANIMATION_STATES, ASSETS_FOLDER

def setup_system_tray(parent):
    """Create and configure system tray icon
    
    Args:
        parent: Parent window with required methods
        
    Returns:
        QSystemTrayIcon instance or None if failed
    """
    try:
        tray_icon = QSystemTrayIcon(parent)
        
        # Get configuration
        config_manager = parent.config_manager
        tray_config = config_manager.get_config("system_tray", None, {})
        
        # Get tray icon path from config or use default
        tray_icon_path = tray_config.get("tray_icon_path", os.path.join(ASSETS_FOLDER, "static.png"))
        
        # Set icon
        if os.path.exists(tray_icon_path):
            tray_icon.setIcon(QIcon(tray_icon_path))
        else:
            logger.warning(f"Tray icon not found: {tray_icon_path}")
            # Try to find any PNG in assets folder as fallback
            for file in os.listdir(ASSETS_FOLDER):
                if file.endswith(".png"):
                    fallback_path = os.path.join(ASSETS_FOLDER, file)
                    logger.info(f"Using fallback tray icon: {fallback_path}")
                    tray_icon.setIcon(QIcon(fallback_path))
                    break
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Add actions
        show_action = QAction("Show/Hide", parent)
        settings_action = QAction("Settings", parent)
        exit_action = QAction("Exit", parent)
        
        # Connect actions
        show_action.triggered.connect(parent.toggle_visibility)
        settings_action.triggered.connect(parent.show_settings)
        exit_action.triggered.connect(parent.safe_exit)
        
        # Add animation state submenu
        animation_menu = tray_menu.addMenu("Set Animation")
        for state in ANIMATION_STATES:
            action = QAction(state, parent)
            # We need to create a local function to capture the current state value
            def create_animation_setter(anim_state):
                return lambda: parent.set_animation(anim_state)
            action.triggered.connect(create_animation_setter(state))
            animation_menu.addAction(action)
        
        # Add actions to menu
        tray_menu.addAction(show_action)
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        
        # Set context menu
        tray_icon.setContextMenu(tray_menu)
        
        # Setup double-click behavior
        tray_icon.activated.connect(parent.tray_icon_activated)
        
        # Show tray icon
        tray_icon.show()
        
        logger.info("System tray icon initialized successfully")
        return tray_icon
        
    except Exception as e:
        ErrorHandler.log_error(e, "Failed to initialize system tray")
        return None

def show_tray_notification(tray_icon, title, message, icon=QSystemTrayIcon.Information, duration=5000):
    """Show a system tray notification
    
    Args:
        tray_icon: QSystemTrayIcon instance
        title: Notification title
        message: Notification message
        icon: Notification icon type
        duration: Display duration in milliseconds
        
    Returns:
        bool: Success or failure
    """
    try:
        if tray_icon and tray_icon.supportsMessages():
            tray_icon.showMessage(title, message, icon, duration)
            return True
        return False
    except Exception as e:
        ErrorHandler.log_error(e, "Failed to show tray notification")
        return False