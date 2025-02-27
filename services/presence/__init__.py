# services/presence/__init__.py
"""
Sabrina AI Presence System
A modular and maintainable framework for creating an AI presence
"""

__version__ = "1.0.0"

# services/presence/gui/__init__.py
"""
GUI components for Sabrina's Presence System
"""
from .presence_gui import PresenceGUI
from .animated_label import AnimatedLabel
from .settings_menu import SettingsMenu
from .system_tray import setup_system_tray, show_tray_notification

# services/presence/animation/__init__.py
"""
Animation components for Sabrina's Presence System
"""
from .animation_transitions import cross_fade, pulse_animation, slide_transition

# services/presence/utils/__init__.py
"""
Utility modules for Sabrina's Presence System
"""
from .error_handling import ErrorHandler, logger
from .resource_management import ResourceManager
from .config_manager import ConfigManager
from .event_system import EventBus, EventType, EventPriority, Event