"""
Enhanced error handling utilities for Sabrina's Presence System

Provides comprehensive error tracking, logging, and recovery mechanisms with
improved context information and structured error reporting
"""
# Standard imports
import os
import sys
import time
import logging
import traceback
import json
from datetime import datetime
from enum import Enum, auto

# Create log directory
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Error severity levels
class ErrorSeverity(Enum):
    """Error severity levels for better categorization and handling"""
    DEBUG = auto()      # Minor issues, debugging info
    INFO = auto()       # Informational errors, non-critical
    WARNING = auto()    # Issues that don't prevent functionality but may cause problems
    ERROR = auto()      # Serious errors that prevent certain functionality
    CRITICAL = auto()   # Severe errors that may crash the application

# Configure logging with rotating file handler
def setup_logger():
    """Set up the logger with file rotation and proper formatting"""
    # Create a logger with appropriate settings
    logger = logging.getLogger("presence_system")
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers = []
    
    # Current date for log filename
    current_date = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"presence_{current_date}.log")
    
    # Create file handler with encoding specified
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Less verbose on console
    
    # Create formatter and attach to handlers
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logger()

class ErrorHandler:
    """Enhanced centralized error handling for Presence System"""
    
    # Track error statistics
    error_stats = {
        "total_errors": 0,
        "errors_by_type": {},
        "errors_by_module": {},
        "error_timestamps": [],
        "recent_errors": []  # Store recent errors for debugging
    }
    
    # Maximum number of recent errors to keep
    max_recent_errors = 10
    
    @staticmethod
    def log_error(error, context="", severity=ErrorSeverity.ERROR, include_traceback=True):
        """Log an error with enhanced context information
        
        Args:
            error: The exception object
            context: Optional context information (e.g., class.method)
            severity: Error severity level (default: ERROR)
            include_traceback: Whether to include traceback (default: True)
            
        Returns:
            str: Error message
        """
        # Get exception details
        error_type = type(error).__name__
        error_message = str(error)
        
        # Detailed message with context
        log_message = f"{context}: {error_type}: {error_message}" if context else f"{error_type}: {error_message}"
        
        # Get calling information
        frame = traceback.extract_stack()[-2]
        file_name = os.path.basename(frame[0])
        line_no = frame[1]
        module_name = os.path.splitext(file_name)[0]
        
        # Add file location to context
        location = f"{file_name}:{line_no}"
        detailed_message = f"[{location}] {log_message}"
        
        # Log based on severity
        if severity == ErrorSeverity.DEBUG:
            logger.debug(detailed_message)
        elif severity == ErrorSeverity.INFO:
            logger.info(detailed_message)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(detailed_message)
        elif severity == ErrorSeverity.ERROR:
            logger.error(detailed_message)
        elif severity == ErrorSeverity.CRITICAL:
            logger.critical(detailed_message)
        else:
            logger.error(detailed_message)  # Default to ERROR
        
        # Add traceback for WARNING and higher if requested
        if include_traceback and severity.value >= ErrorSeverity.WARNING.value:
            logger.debug(traceback.format_exc())
        
        # Update error statistics
        ErrorHandler._update_error_stats(error_type, module_name, log_message)
        
        return log_message
    
    @staticmethod
    def _update_error_stats(error_type, module_name, message):
        """Update internal error statistics
        
        Args:
            error_type: Type of the error
            module_name: Module where the error occurred
            message: Error message
        """
        stats = ErrorHandler.error_stats
        
        # Update total count
        stats["total_errors"] += 1
        
        # Update by type
        if error_type not in stats["errors_by_type"]:
            stats["errors_by_type"][error_type] = 0
        stats["errors_by_type"][error_type] += 1
        
        # Update by module
        if module_name not in stats["errors_by_module"]:
            stats["errors_by_module"][module_name] = 0
        stats["errors_by_module"][module_name] += 1
        
        # Add timestamp
        stats["error_timestamps"].append(time.time())
        
        # Add to recent errors (limited queue)
        stats["recent_errors"].append({
            "type": error_type,
            "module": module_name,
            "message": message,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        })
        
        # Trim recent errors if needed
        if len(stats["recent_errors"]) > ErrorHandler.max_recent_errors:
            stats["recent_errors"] = stats["recent_errors"][-ErrorHandler.max_recent_errors:]
    
    @staticmethod
    def log_warning(message, context=""):
        """Log a warning message with context
        
        Args:
            message: Warning message
            context: Optional context information
            
        Returns:
            str: Warning message
        """
        # Format message with context
        warning_message = f"{context}: {message}" if context else message
        
        # Get calling information
        frame = traceback.extract_stack()[-2]
        file_name = os.path.basename(frame[0])
        line_no = frame[1]
        
        # Add file location to context
        location = f"{file_name}:{line_no}"
        detailed_message = f"[{location}] {warning_message}"
        
        logger.warning(detailed_message)
        return warning_message
    
    @staticmethod
    def log_info(message, context=""):
        """Log an info message with context
        
        Args:
            message: Info message
            context: Optional context information
            
        Returns:
            str: Info message
        """
        # Format message with context
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
        
    @staticmethod
    def get_error_stats():
        """Get current error statistics
        
        Returns:
            dict: Dictionary with error statistics
        """
        stats = ErrorHandler.error_stats.copy()
        
        # Calculate recent error rate (errors per minute in the last 5 minutes)
        recent_time = time.time() - 300  # Last 5 minutes
        recent_count = sum(1 for t in stats["error_timestamps"] if t >= recent_time)
        stats["recent_error_rate"] = recent_count / 5 if recent_count > 0 else 0
        
        return stats
        
    @staticmethod
    def reset_error_stats():
        """Reset error statistics"""
        ErrorHandler.error_stats = {
            "total_errors": 0,
            "errors_by_type": {},
            "errors_by_module": {},
            "error_timestamps": [],
            "recent_errors": []
        }
        
    @staticmethod
    def save_error_report(file_path="logs/error_report.json"):
        """Save error statistics to a JSON file
        
        Args:
            file_path: Path to save the error report
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Get current stats with timestamp
            stats = ErrorHandler.get_error_stats()
            stats["report_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=4)
                
            logger.info(f"Error report saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save error report: {str(e)}")
            return False
            
    @staticmethod
    def try_with_recovery(operation, context="", recovery_func=None):
        """Try an operation with recovery mechanism
        
        Args:
            operation: Function to try
            context: Optional context for error message
            recovery_func: Optional recovery function to call on error
            
        Returns:
            The result of the operation or recovery function
        """
        try:
            return operation()
        except Exception as e:
            ErrorHandler.log_error(e, context)
            if recovery_func:
                try:
                    logger.info(f"Attempting recovery for {context}")
                    return recovery_func(e)
                except Exception as recovery_error:
                    ErrorHandler.log_error(recovery_error, f"{context} - Recovery failed")
            return None