# Error handling utilities for Sabrina's Presence System
import os
import logging
import traceback
from datetime import datetime

# Configure logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Create a logger with appropriate settings
logger = logging.getLogger("presence_system")
logger.setLevel(logging.DEBUG)

# Current date for log filename
current_date = datetime.now().strftime("%Y-%m-%d")
log_file = os.path.join(log_dir, f"presence_{current_date}.log")

# Create file handler
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # Only warnings and above to console

# Create formatter and attach to handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class ErrorHandler:
    """Centralized error handling for Presence System"""
    
    @staticmethod
    def log_error(error, context=""):
        """Log an error with optional context information"""
        error_message = f"{context}: {str(error)}" if context else str(error)
        logger.error(error_message)
        logger.debug(traceback.format_exc())
        return error_message
    
    @staticmethod
    def log_warning(message, context=""):
        """Log a warning with optional context information"""
        warning_message = f"{context}: {message}" if context else message
        logger.warning(warning_message)
        return warning_message
    
    @staticmethod
    def log_info(message, context=""):
        """Log an info message with optional context information"""
        info_message = f"{context}: {message}" if context else message
        logger.info(info_message)
        return info_message
    
    @staticmethod
    def handle_file_operation(operation, file_path, fallback=None, context=""):
        """Handle file operations with proper error handling
        
        Args:
            operation: Function that performs the file operation
            file_path: Path to the file being operated on
            fallback: Optional fallback value to return on error
            context: Optional context for error message
            
        Returns:
            The result of the operation or fallback value on error
        """
        try:
            return operation()
        except Exception as e:
            error_context = f"{context} - File: {file_path}" if context else f"File operation - {file_path}"
            ErrorHandler.log_error(e, error_context)
            return fallback
    
    @staticmethod
    def handle_animation_error(animation_state, animation_path, fallback_path=None, context=""):
        """Handle animation loading errors with proper fallback
        
        Args:
            animation_state: The state name of the animation
            animation_path: Path to the animation file
            fallback_path: Optional fallback animation path
            context: Optional context for error message
            
        Returns:
            fallback_path if provided, otherwise None
        """
        error_context = f"{context} - Animation: {animation_state}" if context else f"Animation loading - {animation_state}"
        logger.error(f"{error_context} - Failed to load: {animation_path}")
        
        if fallback_path and os.path.exists(fallback_path):
            logger.info(f"Using fallback animation: {fallback_path}")
            return fallback_path
        
        logger.warning("No fallback animation available")
        return None
    
    @staticmethod
    def validate_theme(theme_data, required_states):
        """Validate theme data to ensure all required states are present
        
        Args:
            theme_data: The theme data dictionary
            required_states: List of required animation states
            
        Returns:
            (is_valid, missing_states)
        """
        if not isinstance(theme_data, dict):
            logger.error("Theme data is not a dictionary")
            return False, required_states
        
        missing_states = [state for state in required_states if state not in theme_data]
        
        if missing_states:
            logger.warning(f"Theme is missing required states: {', '.join(missing_states)}")
            return False, missing_states
        
        return True, []