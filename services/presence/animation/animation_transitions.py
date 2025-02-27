"""
Animation transition utilities for Sabrina's Presence System
Provides smooth transitions between animation states
"""
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from ..utils.error_handling import logger

def cross_fade(current_label, next_label, duration=300, on_complete=None):
    """Perform cross-fade transition between animations
    
    Args:
        current_label: The currently visible label
        next_label: The label to fade in
        duration: Transition duration in milliseconds
        on_complete: Callback function when transition completes
        
    Returns:
        tuple: (fade_out, fade_in) animation objects
    """
    # Create fade-out animation for current label
    fade_out = QPropertyAnimation(current_label, b"opacity")
    fade_out.setDuration(duration)
    fade_out.setStartValue(1.0)
    fade_out.setEndValue(0.0)
    fade_out.setEasingCurve(QEasingCurve.OutQuad)
    
    # Create fade-in animation for next label
    fade_in = QPropertyAnimation(next_label, b"opacity")
    fade_in.setDuration(duration)
    fade_in.setStartValue(0.0)
    fade_in.setEndValue(1.0)
    fade_in.setEasingCurve(QEasingCurve.InQuad)
    
    # Connect finished signal to callback if provided
    if on_complete:
        fade_out.finished.connect(on_complete)
    
    # Start animations
    fade_out.start()
    fade_in.start()
    
    logger.debug(f"Started cross-fade animation with duration {duration}ms")
    return fade_out, fade_in

def pulse_animation(label, duration=500, min_opacity=0.6, max_opacity=1.0):
    """Create a pulsing animation effect
    
    Args:
        label: The label to animate
        duration: Duration of one pulse cycle in milliseconds
        min_opacity: Minimum opacity in the pulse
        max_opacity: Maximum opacity in the pulse
        
    Returns:
        QPropertyAnimation: The configured animation object
    """
    pulse = QPropertyAnimation(label, b"opacity")
    pulse.setDuration(duration)
    pulse.setStartValue(max_opacity)
    pulse.setEndValue(min_opacity)
    pulse.setEasingCurve(QEasingCurve.InOutSine)
    pulse.setLoopCount(-1)  # Infinite looping
    
    # Make it ping-pong between min and max
    pulse.setDirection(QPropertyAnimation.Forward)
    
    # Start animation
    pulse.start()
    
    logger.debug(f"Started pulse animation with duration {duration}ms")
    return pulse

def slide_transition(current_label, next_label, direction="right", duration=300, on_complete=None):
    """Slide transition between two labels
    
    Args:
        current_label: The currently visible label
        next_label: The label to slide in
        direction: Slide direction ("left", "right", "up", "down")
        duration: Transition duration in milliseconds
        on_complete: Callback function when transition completes
        
    Returns:
        tuple: (slide_out, slide_in) animation objects
    """
    # Implementation for future enhancement
    logger.info(f"Slide transition ({direction}) not yet implemented, using cross-fade instead")
    return cross_fade(current_label, next_label, duration, on_complete)