#!/usr/bin/env python3
"""
Sabrina AI Test Runner
============================
This script runs all tests for the Sabrina AI system.
"""

import os
import sys
import argparse
import pytest
import unittest
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("test_runner")

def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Sabrina AI Test Runner")
    
    parser.add_argument(
        "--unit-only",
        action="store_true",
        help="Run only unit tests"
    )
    
    parser.add_argument(
        "--integration-only",
        action="store_true",
        help="Run only integration tests"
    )
    
    parser.add_argument(
        "--component",
        type=str,
        choices=["core", "voice", "vision", "automation", "all"],
        default="all",
        help="Which component to test"
    )
    
    parser.add_argument(
        "--xml-report",
        action="store_true",
        help="Generate XML test report"
    )
    
    parser.add_argument(
        "--html-report",
        action="store_true",
        help="Generate HTML test report"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate test coverage report"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Run tests in verbose mode"
    )
    
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip slow tests"
    )
    
    return parser.parse_args()

def run_tests(args):
    """Run the tests based on arguments"""
    logger.info("Starting Sabrina AI test run")
    
    # Build pytest arguments
    pytest_args = []
    
    # Verbose mode
    if args.verbose:
        pytest_args.append("-v")
    
    # Test selection
    if args.unit_only:
        pytest_args.append("-m")
        pytest_args.append("not integration")
    elif args.integration_only:
        pytest_args.append("-m")
        pytest_args.append("integration")
    
    # Skip slow tests if requested
    if args.fast:
        pytest_args.append("-m")
        if "not integration" in pytest_args:
            # Update the existing marker
            index = pytest_args.index("not integration")
            pytest_args[index] = "not integration and not slow"
        elif "integration" in pytest_args:
            # Update the existing marker
            index = pytest_args.index("integration")
            pytest_args[index] = "integration and not slow"
        else:
            # Add new marker
            pytest_args.extend(["-m", "not slow"])
    
    # Component selection
    if args.component != "all":
        test_files = []
        if args.component == "core":
            test_files.append("tests/test_framework.py")
        elif args.component == "voice":
            test_files.append("tests/test_voice.py")
        elif args.component == "vision":
            test_files.append("tests/test_vision.py")
        elif args.component == "automation":
            test_files.append("tests/test_automation.py")
        
        pytest_args.extend(test_files)
    else:
        # Run all tests
        pytest_args.append("tests/")
    
    # Report generation
    if args.xml_report:
        pytest_args.extend(["--junitxml", "test-reports/junit-report.xml"])
        os.makedirs("test-reports", exist_ok=True)
    
    if args.html_report:
        pytest_args.extend(["--html", "test-reports/report.html", "--self-contained-html"])
        os.makedirs("test-reports", exist_ok=True)
    
    # Coverage
    if args.coverage:
        pytest_args = [
            "--cov=core",
            "--cov=utilities",
            "--cov=services",
            "--cov-report", "html:test-reports/coverage",
            "--cov-report", "term"
        ] + pytest_args
        os.makedirs("test-reports/coverage", exist_ok=True)
    
    # Log the command
    logger.info(f"Running pytest with arguments: {pytest_args}")
    
    # Run the tests
    result = pytest.main(pytest_args)
    
    # Log the result
    if result == 0:
        logger.info("All tests passed successfully")
    else:
        logger.error(f"Tests failed with exit code: {result}")
    
    return result

def main():
    """Main entry point"""
    # Ensure required directories exist
    os.makedirs("logs", exist_ok=True)
    
    # Parse arguments
    args = parse_arguments()
    
    # Run tests
    result = run_tests(args)
    
    return result

if __name__ == "__main__":
    sys.exit(main())