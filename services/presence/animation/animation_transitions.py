"""
Animation transition utilities for Sabrina's Presence System

Provides optimized transitions between animation states with
improved memory usage and performance
"""
# Standard imports
import time

# Third-party imports
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PyQt5.QtGui import QMovie

# Local imports
from ..utils.error_handling import logger, ErrorHandler

class TransitionManager:
    """Manages transitions between animations with improved performance"""
    
    def __init__(self):
        """Initialize the transition manager"""
        self.active_transitions = {}  # Track active transitions
        self.last_transition_time = 0  # Track when the last transition occurred
        self.default_duration = 300    # Default transition duration
        
    def cancel_transition(self, transition_id):
        """Cancel an active transition
        
        Args:
            transition_id: ID of the transition to cancel
            
        Returns:
            bool: True if transition was cancelled, False otherwise
        """
        if transition_id in self.active_transitions:
            try:
                # Get animation objects
                animations = self.active_transitions[transition_id]
                
                # Stop animations
                for anim in animations:
                    if anim.state() == QPropertyAnimation.Running:
                        anim.stop()
                
                # Remove from tracking
                del self.active_transitions[transition_id]
                return True
            except Exception as e:
                ErrorHandler.log_error(e, f"TransitionManager.cancel_transition({transition_id})")
        
        return False
        
    def cancel_all_transitions(self):
        """Cancel all active transitions
        
        Returns:
            int: Number of transitions cancelled
        """
        transition_ids = list(self.active_transitions.keys())
        cancelled_count = 0
        
        for transition_id in transition_ids:
            if self.cancel_transition(transition_id):
                cancelled_count += 1
                
        if cancelled_count > 0:
            logger.debug(f"Cancelled {cancelled_count} active transitions")
            
        return cancelled_count

def cross_fade(current_label, next_label, duration=300, on_complete=None, transition_id=None):
    """Perform cross-fade transition between animations with optimized resource usage
    
    Args:
        current_label: The currently visible label
        next_label: The label to fade in
        duration: Transition duration in milliseconds (default: 300)
        on_complete: Callback function when transition completes (default: None)
        transition_id: Optional ID for tracking/cancelling the transition (default: None)
        
    Returns:
        tuple: (fade_out, fade_in) animation objects
        
    Example:
        ```python
        fade_out, fade_in = cross_fade(
            current_label=self.idle_label,
            next_label=self.talking_label,
            duration=500,
            on_complete=self.transition_completed,
            transition_id="idle_to_talking"
        )
        ```
    """
    start_time = time.time()
    
    # Check if labels are valid
    if not current_label or not next_label:
        logger.warning("Invalid labels provided for cross_fade transition")
        if on_complete:
            on_complete()
        return None, None
    
    try:
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
        
        # Log timing
        elapsed = (time.time() - start_time) * 1000
        logger.debug(f"Started cross-fade transition in {elapsed:.2f}ms (duration: {duration}ms)")
        
        return fade_out, fade_in
        
    except Exception as e:
        ErrorHandler.log_error(e, "cross_fade transition")
        if on_complete:
            on_complete()
        return None, None

def optimized_transition(current_label, next_label, old_animation_path, new_animation_path, 
                       duration=300, on_complete=None, transition_id=None):
    """Optimized transition that only creates new QMovie when necessary
    
    Args:
        current_label: The currently visible label
        next_label: The label to fade in
        old_animation_path: Path to the current animation file
        new_animation_path: Path to the new animation file
        duration: Transition duration in milliseconds (default: 300)
        on_complete: Callback function when transition completes (default: None)
        transition_id: Optional ID for tracking/cancelling the transition (default: None)
        
    Returns:
        tuple: (fade_out, fade_in, movie) animation objects and new movie if created
    """
    # Only create a new QMovie if really needed
    new_movie = None
    
    # Static image to static image - no movie needed
    if new_animation_path.endswith('.png') and (old_animation_path is None or 
                                               old_animation_path.endswith('.png')):
        next_label.setPixmap(QPixmap(new_animation_path))
        
    # GIF animation - only create new movie if path changed
    elif new_animation_path.endswith('.gif') and (old_animation_path is None or 
                                                 old_animation_path != new_animation_path):
        new_movie = QMovie(new_animation_path)
        new_movie.setCacheMode(QMovie.CacheAll)
        new_movie.loopCount = -1  # Infinite loop
        next_label.setMovie(new_movie)
        new_movie.start()
    
    # Run the cross-fade transition
    fade_out, fade_in = cross_fade(
        current_label=current_label, 
        next_label=next_label, 
        duration=duration, 
        on_complete=on_complete,
        transition_id=transition_id
    )
    
    return fade_out, fade_in, new_movie

def pulse_animation(label, duration=500, min_opacity=0.6, max_opacity=1.0, loop_count=-1):
    """Create a pulsing animation effect with optimized performance
    
    Args:
        label: The label to animate
        duration: Duration of one pulse cycle in milliseconds (default: 500)
        min_opacity: Minimum opacity in the pulse (default: 0.6)
        max_opacity: Maximum opacity in the pulse (default: 1.0) 
        loop_count: Number of loops (-1 for infinite) (default: -1)
        
    Returns:
        QPropertyAnimation: The configured animation object
    """
    try:
        # Create the pulse animation
        pulse = QPropertyAnimation(label, b"opacity")
        pulse.setDuration(duration)
        pulse.setStartValue(max_opacity)
        pulse.setEndValue(min_opacity)
        pulse.setEasingCurve(QEasingCurve.InOutSine)
        pulse.setLoopCount(loop_count)
        
        # Make it ping-pong between min and max
        pulse.setDirection(QPropertyAnimation.Forward)
        
        # Start animation
        pulse.start()
        
        logger.debug(f"Started pulse animation with duration {duration}ms")
        return pulse
        
    except Exception as e:
        ErrorHandler.log_error(e, "pulse_animation")
        return None

def slide_transition(current_label, next_label, direction="right", distance=100, 
                   duration=300, on_complete=None, transition_id=None):
    """Slide transition between two labels with optimized performance
    
    Args:
        current_label: The currently visible label
        next_label: The label to slide in
        direction: Slide direction ("left", "right", "up", "down") (default: "right")
        distance: Slide distance in pixels (default: 100)
        duration: Transition duration in milliseconds (default: 300)
        on_complete: Callback function when transition completes (default: None)
        transition_id: Optional ID for tracking/cancelling the transition (default: None)
        
    Returns:
        QParallelAnimationGroup: Animation group containing all animations
    """
    try:
        # Get the position properties based on direction
        if direction == "left":
            prop = b"x"
            current_end = -distance
            next_start = distance
            next_end = 0
        elif direction == "right":
            prop = b"x"
            current_end = distance
            next_start = -distance
            next_end = 0
        elif direction == "up":
            prop = b"y"
            current_end = -distance
            next_start = distance
            next_end = 0
        elif direction == "down":
            prop = b"y"
            current_end = distance
            next_start = -distance
            next_end = 0
        else:
            logger.warning(f"Invalid slide direction: {direction}, defaulting to 'right'")
            return slide_transition(current_label, next_label, "right", distance, duration, on_complete)
        
        # Create animation group
        animation_group = QParallelAnimationGroup()
        
        # Create slide-out animation for current label
        slide_out = QPropertyAnimation(current_label, prop)
        slide_out.setDuration(duration)
        slide_out.setStartValue(0)
        slide_out.setEndValue(current_end)
        slide_out.setEasingCurve(QEasingCurve.InOutCubic)
        
        # Create fade-out animation for current label
        fade_out = QPropertyAnimation(current_label, b"opacity")
        fade_out.setDuration(duration)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.OutQuad)
        
        # Set initial position of next label
        next_label.setProperty(prop.decode(), next_start)
        next_label.setOpacity(0.0)
        
        # Create slide-in animation for next label
        slide_in = QPropertyAnimation(next_label, prop)
        slide_in.setDuration(duration)
        slide_in.setStartValue(next_start)
        slide_in.setEndValue(next_end)
        slide_in.setEasingCurve(QEasingCurve.InOutCubic)
        
        # Create fade-in animation for next label
        fade_in = QPropertyAnimation(next_label, b"opacity")
        fade_in.setDuration(duration)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InQuad)
        
        # Add animations to group
        animation_group.addAnimation(slide_out)
        animation_group.addAnimation(fade_out)
        animation_group.addAnimation(slide_in)
        animation_group.addAnimation(fade_in)
        
        # Connect finished signal to callback if provided
        if on_complete:
            animation_group.finished.connect(on_complete)
        
        # Start animation group
        animation_group.start()
        
        logger.debug(f"Started slide transition ({direction}) with duration {duration}ms")
        return animation_group
        
    except Exception as e:
        ErrorHandler.log_error(e, f"slide_transition ({direction})")
        # Fallback to cross-fade
        logger.info(f"Falling back to cross-fade transition due to error")
        return cross_fade(current_label, next_label, duration, on_complete, transition_id)