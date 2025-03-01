"""
Unified Error Handler for Sabrina AI
====================================
This module provides centralized error handling, logging, and error recovery
for all Sabrina AI components with structured error tracking and reporting.
"""

import os
import time
import logging
import traceback
import json
from datetime import datetime
from enum import Enum, auto
from typing import Dict, Any, List, Optional, Callable

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler("logs/error_handler.log"), logging.StreamHandler()],
)

logger = logging.getLogger("error_handler")


class ErrorSeverity(Enum):
    """Error severity levels for prioritization and handling"""

    DEBUG = auto()  # Minor issues, debugging info
    INFO = auto()  # Informational errors, non-critical
    WARNING = auto()  # Issues that don't prevent functionality but may cause problems
    ERROR = auto()  # Serious errors that prevent certain functionality
    CRITICAL = auto()  # Severe errors that may crash the application


class ErrorCategory(Enum):
    """Categories of errors for better organization and reporting"""

    INITIALIZATION = auto()  # Errors during system initialization
    CONFIGURATION = auto()  # Configuration-related errors
    COMMUNICATION = auto()  # Communication errors between components
    RESOURCE = auto()  # Resource access/availability errors
    PROCESSING = auto()  # Data processing errors
    USER_INPUT = auto()  # User input handling errors
    EXTERNAL_API = auto()  # Errors from external APIs
    INTERNAL = auto()  # Internal system errors
    UNKNOWN = auto()  # Uncategorized errors


class ErrorHandler:
    """
    Centralized error handling, logging, and recovery for Sabrina AI

    Features:
    - Structured error logging with severity and categories
    - Error tracking and statistics
    - Recovery mechanism suggestions
    - Automatic error reporting
    """

    def __init__(self, config_manager=None):
        """
        Initialize the error handler

        Args:
            config_manager: Optional ConfigManager instance for error handling settings
        """
        self.config_manager = config_manager
        self.error_stats = {
            "total_errors": 0,
            "errors_by_severity": {sev.name: 0 for sev in ErrorSeverity},
            "errors_by_category": {cat.name: 0 for cat in ErrorCategory},
            "errors_by_module": {},
            "error_timestamps": [],
            "recent_errors": [],
        }

        # Maximum number of recent errors to track
        self.max_recent_errors = 50

        # Error report file path
        self.error_report_path = "logs/error_report.json"

        # Recovery functions registry
        self.recovery_functions = {}

        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)

        logger.info("Error handler initialized")

    def log_error(
        self,
        error: Exception,
        context: str = "",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        should_raise: bool = False,
    ) -> Dict[str, Any]:
        """
        Log an error with detailed context and tracking

        Args:
            error: The exception object
            context: Context information (e.g., function or component name)
            severity: Error severity level
            category: Error category
            should_raise: Whether to re-raise the exception after logging

        Returns:
            Dict with error details
        """
        # Get error details
        error_type = type(error).__name__
        error_message = str(error)
        error_traceback = traceback.format_exc()

        # Get calling file and line information
        frame = traceback.extract_stack()[-3]  # -3 to get the caller of log_error
        file_name = os.path.basename(frame[0])
        line_number = frame[1]
        module_name = os.path.splitext(file_name)[0]

        # Create structured error info
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "message": error_message,
            "context": context,
            "severity": severity.name,
            "category": category.name,
            "location": f"{file_name}:{line_number}",
            "module": module_name,
            "traceback": error_traceback,
        }

        # Create log message with context
        log_message = f"{context + ': ' if context else ''}{error_type}: {error_message} [{file_name}:{line_number}]"

        # Log based on severity
        if severity == ErrorSeverity.DEBUG:
            logger.debug(log_message)
        elif severity == ErrorSeverity.INFO:
            logger.info(log_message)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        elif severity == ErrorSeverity.ERROR:
            logger.error(log_message)
            logger.error(error_traceback)
        elif severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
            logger.critical(error_traceback)

        # Update error statistics
        self._update_error_stats(
            error_type, module_name, severity, category, error_info
        )

        # Try to recover from error
        recovery_result = self._try_recover(error_type, category, error, context)
        if recovery_result:
            error_info["recovery"] = recovery_result

        # Re-raise if requested
        if should_raise:
            raise error

        return error_info

    def _update_error_stats(
        self,
        error_type: str,
        module_name: str,
        severity: ErrorSeverity,
        category: ErrorCategory,
        error_info: Dict[str, Any],
    ):
        """
        Update error statistics

        Args:
            error_type: Type of the error
            module_name: Module where the error occurred
            severity: Error severity level
            category: Error category
            error_info: Complete error information
        """
        stats = self.error_stats

        # Update total count
        stats["total_errors"] += 1

        # Update by severity
        stats["errors_by_severity"][severity.name] += 1

        # Update by category
        stats["errors_by_category"][category.name] += 1

        # Update by module
        if module_name not in stats["errors_by_module"]:
            stats["errors_by_module"][module_name] = 0
        stats["errors_by_module"][module_name] += 1

        # Add timestamp
        stats["error_timestamps"].append(time.time())

        # Add to recent errors
        stats["recent_errors"].append(error_info)

        # Trim recent errors if needed
        if len(stats["recent_errors"]) > self.max_recent_errors:
            stats["recent_errors"] = stats["recent_errors"][-self.max_recent_errors :]

        # Periodically save error report (every 10 errors)
        if stats["total_errors"] % 10 == 0:
            self.save_error_report()

    def log_warning(
        self,
        message: str,
        context: str = "",
        category: ErrorCategory = ErrorCategory.UNKNOWN,
    ) -> Dict[str, Any]:
        """
        Log a warning message

        Args:
            message: Warning message
            context: Context information
            category: Warning category

        Returns:
            Dict with warning details
        """
        # Get calling file and line information
        frame = traceback.extract_stack()[-2]
        file_name = os.path.basename(frame[0])
        line_number = frame[1]
        module_name = os.path.splitext(file_name)[0]

        # Create log message
        log_message = (
            f"{context + ': ' if context else ''}{message} [{file_name}:{line_number}]"
        )
        logger.warning(log_message)

        # Create warning info
        warning_info = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "context": context,
            "severity": ErrorSeverity.WARNING.name,
            "category": category.name,
            "location": f"{file_name}:{line_number}",
            "module": module_name,
        }

        # Update statistics
        self._update_error_stats(
            "WARNING", module_name, ErrorSeverity.WARNING, category, warning_info
        )

        return warning_info

    def register_recovery_function(
        self, error_type: str, category: ErrorCategory, recovery_function: Callable
    ) -> bool:
        """
        Register a recovery function for a specific error type and category

        Args:
            error_type: Type of error (Exception class name)
            category: Error category
            recovery_function: Function to call for recovery

        Returns:
            bool: True if registered successfully, False otherwise
        """
        key = f"{error_type}:{category.name}"
        self.recovery_functions[key] = recovery_function
        logger.info(f"Registered recovery function for {key}")
        return True

    def _try_recover(
        self, error_type: str, category: ErrorCategory, error: Exception, context: str
    ) -> Optional[Dict[str, Any]]:
        """
        Try to recover from an error using registered recovery functions

        Args:
            error_type: Type of error
            category: Error category
            error: The exception instance
            context: Error context

        Returns:
            Dict with recovery information if successful, None otherwise
        """
        # Try specific error type and category
        key = f"{error_type}:{category.name}"
        if key in self.recovery_functions:
            try:
                recovery_function = self.recovery_functions[key]
                result = recovery_function(error, context)
                return {"success": True, "method": key, "result": str(result)}
            except Exception as e:
                logger.error(f"Recovery function for {key} failed: {str(e)}")
                return {"success": False, "method": key, "error": str(e)}

        # Try generic category recovery
        key = f"*:{category.name}"
        if key in self.recovery_functions:
            try:
                recovery_function = self.recovery_functions[key]
                result = recovery_function(error, context)
                return {"success": True, "method": key, "result": str(result)}
            except Exception as e:
                logger.error(f"Recovery function for {key} failed: {str(e)}")
                return {"success": False, "method": key, "error": str(e)}

        return None

    def save_error_report(self, file_path: str = None) -> bool:
        """
        Save error statistics to a JSON file

        Args:
            file_path: Path to save the report (default: self.error_report_path)

        Returns:
            bool: True if successful, False otherwise
        """
        if not file_path:
            file_path = self.error_report_path

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Create report with timestamp
            report = {
                "timestamp": datetime.now().isoformat(),
                "stats": {
                    "total_errors": self.error_stats["total_errors"],
                    "by_severity": self.error_stats["errors_by_severity"],
                    "by_category": self.error_stats["errors_by_category"],
                    "by_module": self.error_stats["errors_by_module"],
                },
                "recent_errors": self.error_stats["recent_errors"][
                    -10:
                ],  # Last 10 errors
            }

            # Save to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=4)

            return True

        except Exception as e:
            logger.error(f"Failed to save error report: {str(e)}")
            return False

    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get error statistics

        Returns:
            Dict with error statistics
        """
        return {
            "total_errors": self.error_stats["total_errors"],
            "by_severity": self.error_stats["errors_by_severity"],
            "by_category": self.error_stats["errors_by_category"],
            "by_module": self.error_stats["errors_by_module"],
            "recent_count": len(self.error_stats["recent_errors"]),
        }

    def get_recent_errors(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent errors

        Args:
            count: Number of recent errors to return

        Returns:
            List of recent error information
        """
        return self.error_stats["recent_errors"][-count:]

    def reset_error_stats(self) -> bool:
        """
        Reset error statistics

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Save current stats before resetting
            self.save_error_report()

            # Reset stats
            self.error_stats = {
                "total_errors": 0,
                "errors_by_severity": {sev.name: 0 for sev in ErrorSeverity},
                "errors_by_category": {cat.name: 0 for cat in ErrorCategory},
                "errors_by_module": {},
                "error_timestamps": [],
                "recent_errors": [],
            }

            logger.info("Error statistics reset")
            return True

        except Exception as e:
            logger.error(f"Failed to reset error statistics: {str(e)}")
            return False

    def handle_file_operation(
        self,
        operation: Callable,
        file_path: str,
        fallback: Any = None,
        context: str = "",
    ) -> Any:
        """
        Safely handle file operations with error handling

        Args:
            operation: Function that performs the file operation
            file_path: Path to the file
            fallback: Fallback value if operation fails
            context: Context for error reporting

        Returns:
            Result of operation or fallback value
        """
        try:
            return operation()
        except Exception as e:
            error_context = (
                f"{context} - File: {file_path}"
                if context
                else f"File operation - {file_path}"
            )
            self.log_error(
                e,
                error_context,
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.RESOURCE,
            )
            return fallback

    def try_with_recovery(
        self,
        operation: Callable,
        recovery_func: Callable = None,
        context: str = "",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
    ) -> Any:
        """
        Try an operation with automatic recovery if it fails

        Args:
            operation: Function to try
            recovery_func: Recovery function to call if operation fails
            context: Context for error reporting
            severity: Error severity if operation fails
            category: Error category if operation fails

        Returns:
            Result of operation or recovery function
        """
        try:
            return operation()
        except Exception as e:
            self.log_error(e, context, severity, category)

            if recovery_func:
                try:
                    logger.info(f"Attempting recovery for {context}")
                    return recovery_func(e)
                except Exception as recovery_error:
                    self.log_error(
                        recovery_error,
                        f"{context} - Recovery failed",
                        ErrorSeverity.ERROR,
                        category,
                    )

            return None
