#!/usr/bin/env python3
"""
Unit tests for Sabrina AI Error Handler
"""

import os
import sys
import unittest
from unittest.mock import MagicMock
import tempfile
import json

# Import components to test
from utilities.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)


class TestErrorHandler(unittest.TestCase):
    """Test case for ErrorHandler class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()

        # Create a test config manager mock
        self.config_manager = MagicMock()

        # Create error handler with test config
        self.error_handler = ErrorHandler(self.config_manager)

        # Set test error report path
        self.error_handler.error_report_path = os.path.join(
            self.temp_dir.name, "error_report.json"
        )

    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary directory
        self.temp_dir.cleanup()

    def test_initialization(self):
        """Test error handler initialization"""
        # Check initial values
        self.assertEqual(self.error_handler.error_stats["total_errors"], 0)
        self.assertIn("errors_by_severity", self.error_handler.error_stats)
        self.assertIn("errors_by_category", self.error_handler.error_stats)
        self.assertIn("errors_by_module", self.error_handler.error_stats)
        self.assertIn("error_timestamps", self.error_handler.error_stats)
        self.assertIn("recent_errors", self.error_handler.error_stats)

    def test_log_error(self):
        """Test logging an error"""
        # Create a test exception
        test_exception = ValueError("Test error message")

        # Log the error
        error_info = self.error_handler.log_error(
            error=test_exception,
            context="Test context",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )

        # Check error info
        self.assertIsInstance(error_info, dict)
        self.assertEqual(error_info["error_type"], "ValueError")
        self.assertEqual(error_info["message"], "Test error message")
        self.assertEqual(error_info["context"], "Test context")
        self.assertEqual(error_info["severity"], "ERROR")
        self.assertEqual(error_info["category"], "PROCESSING")

        # Check stats update
        self.assertEqual(self.error_handler.error_stats["total_errors"], 1)
        self.assertEqual(
            self.error_handler.error_stats["errors_by_severity"]["ERROR"], 1
        )
        self.assertEqual(
            self.error_handler.error_stats["errors_by_category"]["PROCESSING"], 1
        )

        # Check that error is in recent errors
        self.assertEqual(len(self.error_handler.error_stats["recent_errors"]), 1)
        self.assertEqual(
            self.error_handler.error_stats["recent_errors"][0]["error_type"],
            "ValueError",
        )

        # Test that should_raise works
        with self.assertRaises(ValueError):
            self.error_handler.log_error(
                error=test_exception,
                context="Test should_raise",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.PROCESSING,
                should_raise=True,
            )

    def test_log_warning(self):
        """Test logging a warning"""
        # Log a warning
        warning_info = self.error_handler.log_warning(
            message="Test warning message",
            context="Test warning context",
            category=ErrorCategory.CONFIGURATION,
        )

        # Check warning info
        self.assertIsInstance(warning_info, dict)
        self.assertEqual(warning_info["message"], "Test warning message")
        self.assertEqual(warning_info["context"], "Test warning context")
        self.assertEqual(warning_info["severity"], "WARNING")
        self.assertEqual(warning_info["category"], "CONFIGURATION")

        # Check stats update
        self.assertEqual(
            self.error_handler.error_stats["errors_by_severity"]["WARNING"], 1
        )
        self.assertEqual(
            self.error_handler.error_stats["errors_by_category"]["CONFIGURATION"], 1
        )

    def test_register_recovery_function(self):
        """Test registering a recovery function"""

        # Create a test recovery function
        def test_recovery(error, context):
            return "Recovered"

        # Register the function
        result = self.error_handler.register_recovery_function(
            error_type="ValueError",
            category=ErrorCategory.PROCESSING,
            recovery_function=test_recovery,
        )

        # Check result
        self.assertTrue(result)
        self.assertIn("ValueError:PROCESSING", self.error_handler.recovery_functions)
        self.assertEqual(
            self.error_handler.recovery_functions["ValueError:PROCESSING"],
            test_recovery,
        )

    def test_recovery_execution(self):
        """Test that recovery functions are executed"""
        # Create a mock recovery function
        recovery_mock = MagicMock(return_value="Recovered")

        # Register the function
        self.error_handler.register_recovery_function(
            error_type="ValueError",
            category=ErrorCategory.PROCESSING,
            recovery_function=recovery_mock,
        )

        # Log an error that should trigger recovery
        error_info = self.error_handler.log_error(
            error=ValueError("Test error"),
            context="Test recovery",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )

        # Check that recovery was attempted
        recovery_mock.assert_called_once()

        # Check that recovery info is in the error info
        self.assertIn("recovery", error_info)
        self.assertTrue(error_info["recovery"]["success"])
        self.assertEqual(error_info["recovery"]["result"], "Recovered")

    def test_save_error_report(self):
        """Test saving error report to file"""
        # Log some errors and warnings
        self.error_handler.log_error(
            error=ValueError("Error 1"),
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )
        self.error_handler.log_error(
            error=RuntimeError("Error 2"),
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.COMMUNICATION,
        )
        self.error_handler.log_warning(
            message="Warning 1", category=ErrorCategory.CONFIGURATION
        )

        # Save error report
        result = self.error_handler.save_error_report()

        # Check result
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.error_handler.error_report_path))

        # Check report content
        with open(self.error_handler.error_report_path, "r") as f:
            report = json.load(f)

        self.assertIn("timestamp", report)
        self.assertIn("stats", report)
        self.assertEqual(report["stats"]["total_errors"], 3)
        self.assertEqual(report["stats"]["by_severity"]["ERROR"], 1)
        self.assertEqual(report["stats"]["by_severity"]["CRITICAL"], 1)
        self.assertEqual(report["stats"]["by_severity"]["WARNING"], 1)
        self.assertEqual(report["stats"]["by_category"]["PROCESSING"], 1)
        self.assertEqual(report["stats"]["by_category"]["COMMUNICATION"], 1)
        self.assertEqual(report["stats"]["by_category"]["CONFIGURATION"], 1)
        self.assertIn("recent_errors", report)

    def test_get_error_stats(self):
        """Test getting error statistics"""
        # Log some errors
        self.error_handler.log_error(
            error=ValueError("Error 1"),
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )
        self.error_handler.log_error(
            error=RuntimeError("Error 2"),
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.COMMUNICATION,
        )

        # Get stats
        stats = self.error_handler.get_error_stats()

        # Check stats
        self.assertEqual(stats["total_errors"], 2)
        self.assertEqual(stats["by_severity"]["ERROR"], 1)
        self.assertEqual(stats["by_severity"]["CRITICAL"], 1)
        self.assertEqual(stats["by_category"]["PROCESSING"], 1)
        self.assertEqual(stats["by_category"]["COMMUNICATION"], 1)

    def test_get_recent_errors(self):
        """Test getting recent errors"""
        # Log some errors
        for i in range(5):
            self.error_handler.log_error(
                error=ValueError(f"Error {i}"),
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.PROCESSING,
            )

        # Get recent errors (default count = 10)
        recent_errors = self.error_handler.get_recent_errors()

        # Check recent errors
        self.assertEqual(len(recent_errors), 5)

        # Get subset of recent errors
        subset = self.error_handler.get_recent_errors(count=3)
        self.assertEqual(len(subset), 3)

        # Check order (most recent first)
        self.assertEqual(subset[0]["message"], "Error 4")
        self.assertEqual(subset[2]["message"], "Error 2")

    def test_reset_error_stats(self):
        """Test resetting error statistics"""
        # Log some errors
        self.error_handler.log_error(
            error=ValueError("Error 1"),
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )

        # Verify errors exist
        self.assertEqual(self.error_handler.error_stats["total_errors"], 1)

        # Reset stats
        result = self.error_handler.reset_error_stats()

        # Check result
        self.assertTrue(result)
        self.assertEqual(self.error_handler.error_stats["total_errors"], 0)
        self.assertEqual(len(self.error_handler.error_stats["recent_errors"]), 0)

    def test_handle_file_operation(self):
        """Test safe file operation handling"""

        # Define a test file operation that succeeds
        def successful_operation():
            return "success"

        # Define a test file operation that fails
        def failing_operation():
            raise IOError("File operation failed")

        # Test successful operation
        result = self.error_handler.handle_file_operation(
            operation=successful_operation,
            file_path="test_file.txt",
            fallback="fallback",
            context="Test success",
        )
        self.assertEqual(result, "success")

        # Test failing operation
        result = self.error_handler.handle_file_operation(
            operation=failing_operation,
            file_path="test_file.txt",
            fallback="fallback",
            context="Test failure",
        )
        self.assertEqual(result, "fallback")

        # Check that error was logged
        self.assertEqual(self.error_handler.error_stats["total_errors"], 1)
        self.assertEqual(
            self.error_handler.error_stats["errors_by_category"]["RESOURCE"], 1
        )

    def test_try_with_recovery(self):
        """Test try_with_recovery method"""

        # Define a test operation that succeeds
        def successful_operation():
            return "success"

        # Define a test operation that fails
        def failing_operation():
            raise ValueError("Operation failed")

        # Define a recovery function
        def recovery_function(error):
            return "recovered"

        # Test successful operation
        result = self.error_handler.try_with_recovery(
            operation=successful_operation,
            recovery_func=recovery_function,
            context="Test success",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )
        self.assertEqual(result, "success")

        # Test failing operation with recovery
        result = self.error_handler.try_with_recovery(
            operation=failing_operation,
            recovery_func=recovery_function,
            context="Test failure",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )
        self.assertEqual(result, "recovered")

        # Test failing operation with failing recovery
        def failing_recovery(error):
            raise RuntimeError("Recovery failed")

        result = self.error_handler.try_with_recovery(
            operation=failing_operation,
            recovery_func=failing_recovery,
            context="Test failing recovery",
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
        )
        self.assertIsNone(result)

        # Check that errors were logged
        self.assertGreaterEqual(self.error_handler.error_stats["total_errors"], 3)


if __name__ == "__main__":
    unittest.main()
