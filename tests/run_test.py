#!/usr/bin/env python3
"""
Comprehensive Test Runner for Sabrina AI

This script discovers and runs all unit and integration tests for the Sabrina AI project.
It provides options for running specific test categories, generating coverage reports,
and viewing detailed test results.
"""

import os
import sys
import argparse
import unittest
import time
import json
import logging
from datetime import datetime
from pathlib import Path

# Ensure the project root is in the Python path
script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
project_root = script_dir.parent  # Go up one level from tests/ to project root
sys.path.insert(0, str(project_root))

# Also add the tests directory to sys.path for proper relative imports
sys.path.insert(0, str(script_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("test_run.log")],
)
logger = logging.getLogger("test_runner")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Sabrina AI Test Runner")

    # Test selection options
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument(
        "--integration", action="store_true", help="Run integration tests only"
    )
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests only")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests (default if no type specified)",
    )

    # Component selection
    parser.add_argument(
        "--component",
        type=str,
        help="Run tests for specific component(s), comma-separated",
    )

    # Pattern-based selection
    parser.add_argument(
        "--pattern", type=str, help="Pattern for test discovery (e.g., 'test_*.py')"
    )

    # Reporting options
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase output verbosity (can be used multiple times)",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Minimal output (only show failures)"
    )
    parser.add_argument("--junit-xml", type=str, help="Generate JUnit XML report")
    parser.add_argument(
        "--coverage", action="store_true", help="Generate code coverage report"
    )
    parser.add_argument(
        "--html-report", action="store_true", help="Generate HTML test report"
    )

    # Test environment options
    parser.add_argument(
        "--mock-all",
        action="store_true",
        help="Force mocking of all external dependencies",
    )
    parser.add_argument(
        "--test-config", type=str, help="Path to test configuration file"
    )
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop on first test failure"
    )

    return parser.parse_args()


def get_test_loader(pattern=None):
    """Get a test loader with optional pattern"""
    loader = unittest.TestLoader()
    if pattern:
        loader.testNamePatterns = [f"*{pattern}*"]
    return loader


def setup_test_directories():
    """
    Setup all test directories to make sure they are importable
    by creating necessary __init__.py files
    """
    # Get test directory
    test_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    # List of subdirectories to ensure exist and have __init__.py
    subdirs = ["unit", "integration", "e2e", "test_utils"]

    # Create main __init__.py
    main_init = test_dir / "__init__.py"
    if not main_init.exists():
        with open(main_init, "w") as f:
            f.write(
                """\"\"\"
Sabrina AI Test Suite
==================
This package contains tests for the Sabrina AI project.
\"\"\"
"""
            )
        logger.info(f"Created {main_init}")

    # Create subdirectories and their __init__.py files
    for subdir in subdirs:
        subdir_path = test_dir / subdir
        subdir_path.mkdir(exist_ok=True)

        init_file = subdir_path / "__init__.py"
        if not init_file.exists():
            with open(init_file, "w") as f:
                f.write(f"# {subdir.capitalize()} tests package\n")
            logger.info(f"Created {init_file}")


def discover_tests(args):
    """Discover all tests based on command line arguments"""
    # Setup test directories before discovery
    setup_test_directories()

    # Create test loader
    loader = get_test_loader(args.pattern)

    # Start from the tests directory (current directory)
    test_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    # Use relative imports to avoid path issues
    unit_dir = "unit"
    integration_dir = "integration"
    e2e_dir = "e2e"

    # Create test suites for different test types
    unit_tests = unittest.TestSuite()
    integration_tests = unittest.TestSuite()
    e2e_tests = unittest.TestSuite()

    # Check for component filter
    component_filter = None
    if args.component:
        component_filter = [comp.strip() for comp in args.component.split(",")]
        logger.info(f"Filtering tests for components: {component_filter}")

    # Discover unit tests
    if args.unit or args.all or (not args.integration and not args.e2e):
        unit_path = test_dir / unit_dir
        if unit_path.exists():
            try:
                logger.info(f"Looking for unit tests in {unit_path}")
                # Use direct unittest loading rather than discovery for better control
                for test_file in unit_path.glob("test_*.py"):
                    module_name = f"unit.{test_file.stem}"
                    try:
                        module = __import__(module_name, fromlist=["*"])
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, unittest.TestCase)
                                and attr.__module__ == module.__name__
                            ):
                                tests = loader.loadTestsFromTestCase(attr)
                                if component_filter:
                                    # Filter by component name
                                    for comp in component_filter:
                                        if comp in module_name:
                                            unit_tests.addTest(tests)
                                            break
                                else:
                                    unit_tests.addTest(tests)
                    except (ImportError, AttributeError) as e:
                        logger.warning(f"Error importing {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Error discovering unit tests: {e}")
        else:
            logger.warning(f"Unit test directory not found: {unit_path}")

    # Discover integration tests
    if args.integration or args.all or (not args.unit and not args.e2e):
        integration_path = test_dir / integration_dir
        if integration_path.exists():
            try:
                logger.info(f"Looking for integration tests in {integration_path}")
                # Use direct unittest loading rather than discovery for better control
                for test_file in integration_path.glob("test_*.py"):
                    module_name = f"integration.{test_file.stem}"
                    try:
                        module = __import__(module_name, fromlist=["*"])
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, unittest.TestCase)
                                and attr.__module__ == module.__name__
                            ):
                                tests = loader.loadTestsFromTestCase(attr)
                                if component_filter:
                                    # Filter by component name
                                    for comp in component_filter:
                                        if comp in module_name:
                                            integration_tests.addTest(tests)
                                            break
                                else:
                                    integration_tests.addTest(tests)
                    except (ImportError, AttributeError) as e:
                        logger.warning(f"Error importing {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Error discovering integration tests: {e}")
        else:
            logger.warning(f"Integration test directory not found: {integration_path}")

    # Discover end-to-end tests
    if args.e2e or args.all:
        e2e_path = test_dir / e2e_dir
        if e2e_path.exists():
            try:
                logger.info(f"Looking for e2e tests in {e2e_path}")
                # Use direct unittest loading rather than discovery for better control
                for test_file in e2e_path.glob("test_*.py"):
                    module_name = f"e2e.{test_file.stem}"
                    try:
                        module = __import__(module_name, fromlist=["*"])
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, unittest.TestCase)
                                and attr.__module__ == module.__name__
                            ):
                                tests = loader.loadTestsFromTestCase(attr)
                                if component_filter:
                                    # Filter by component name
                                    for comp in component_filter:
                                        if comp in module_name:
                                            e2e_tests.addTest(tests)
                                            break
                                else:
                                    e2e_tests.addTest(tests)
                    except (ImportError, AttributeError) as e:
                        logger.warning(f"Error importing {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Error discovering e2e tests: {e}")
        else:
            logger.warning(f"E2E test directory not found: {e2e_path}")

    # Combine all test suites
    all_tests = unittest.TestSuite()
    all_tests.addTests(unit_tests)
    all_tests.addTests(integration_tests)
    all_tests.addTests(e2e_tests)

    # Log test discovery results
    logger.info(f"Discovered {all_tests.countTestCases()} tests:")
    logger.info(f"  - Unit tests: {unit_tests.countTestCases()}")
    logger.info(f"  - Integration tests: {integration_tests.countTestCases()}")
    logger.info(f"  - End-to-end tests: {e2e_tests.countTestCases()}")

    return all_tests


def run_tests_with_coverage(test_suite, args):
    """Run tests with coverage reporting if requested"""
    try:
        import coverage

        # Initialize coverage
        cov = coverage.Coverage(
            source=["core", "utilities", "services"],
            omit=["*/__pycache__/*", "*/tests/*", "*/venv/*"],
        )

        # Start coverage collection
        cov.start()

        # Run tests
        result = run_tests(test_suite, args)

        # Stop coverage collection
        cov.stop()

        # Generate reports
        logger.info("Generating coverage reports...")
        cov.save()

        # Text report
        print("\nCoverage Report:")
        total = cov.report()
        print(f"Total coverage: {total:.2f}%")

        # HTML report
        if args.html_report:
            html_dir = os.path.join(project_root, "coverage_html")
            cov.html_report(directory=html_dir)
            print(f"HTML coverage report saved to: {html_dir}")

        # XML report for CI systems
        cov.xml_report(outfile="coverage.xml")

        return result

    except ImportError:
        logger.warning(
            "Coverage package not installed. Running tests without coverage."
        )
        return run_tests(test_suite, args)


def run_tests(test_suite, args):
    """Run a test suite with the specified options"""
    # Set up verbosity
    verbosity = args.verbose + 1
    if args.quiet:
        verbosity = 0

    # Set up test runner
    runner_kwargs = {"verbosity": verbosity, "failfast": args.fail_fast}

    # Use XML test runner if JUnit report is requested
    if args.junit_xml:
        try:
            from xmlrunner import XMLTestRunner

            runner = XMLTestRunner(
                output=os.path.dirname(args.junit_xml), verbosity=verbosity
            )
            logger.info(f"Using XML test runner, output to: {args.junit_xml}")
        except ImportError:
            logger.warning("XMLTestRunner not installed. Using standard test runner.")
            runner = unittest.TextTestRunner(**runner_kwargs)
    else:
        runner = unittest.TextTestRunner(**runner_kwargs)

    # Run the tests
    start_time = time.time()
    result = runner.run(test_suite)
    elapsed_time = time.time() - start_time

    # Print summary
    print("\nTest Run Summary:")
    print(f"  Ran {result.testsRun} tests in {elapsed_time:.2f} seconds")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Skipped: {len(getattr(result, 'skipped', []))}")

    # Save test results summary
    save_test_results(result, elapsed_time, args)

    return result


def save_test_results(result, elapsed_time, args):
    """Save test results to a JSON file"""
    results_dir = os.path.join(project_root, "test_results")
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(results_dir, f"test_results_{timestamp}.json")

    # Collect results data
    test_data = {
        "timestamp": timestamp,
        "execution_time": elapsed_time,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(getattr(result, "skipped", [])),
        "was_successful": result.wasSuccessful(),
        "command_line_args": vars(args),
    }

    # Add failure details
    test_data["failure_details"] = [
        {"test": test[0].id(), "message": test[1]} for test in result.failures
    ]

    # Add error details
    test_data["error_details"] = [
        {"test": test[0].id(), "message": test[1]} for test in result.errors
    ]

    # Save to JSON file
    with open(results_file, "w") as f:
        json.dump(test_data, f, indent=2)

    logger.info(f"Test results saved to: {results_file}")


def generate_html_report(result, elapsed_time, args):
    """Generate an HTML test report"""
    if not args.html_report:
        return

    try:
        from jinja2 import Template

        # Create reports directory
        reports_dir = os.path.join(project_root, "test_reports")
        os.makedirs(reports_dir, exist_ok=True)

        # Get timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build report data
        report_data = {
            "title": "Sabrina AI Test Report",
            "timestamp": timestamp,
            "execution_time": f"{elapsed_time:.2f}",
            "tests_run": result.testsRun,
            "tests_passed": result.testsRun - len(result.failures) - len(result.errors),
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(getattr(result, "skipped", [])),
            "was_successful": result.wasSuccessful(),
            "failure_details": [
                {"test": test[0].id(), "message": test[1]} for test in result.failures
            ],
            "error_details": [
                {"test": test[0].id(), "message": test[1]} for test in result.errors
            ],
        }

        # Load report template
        report_template_path = os.path.join(
            project_root, "tests", "report_template.html"
        )

        # If template doesn't exist, create a basic one
        if not os.path.exists(report_template_path):
            create_basic_report_template(report_template_path)

        with open(report_template_path, "r") as f:
            template = Template(f.read())

        # Render report
        report_html = template.render(**report_data)

        # Save report
        report_filename = f'test_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        report_path = os.path.join(reports_dir, report_filename)

        with open(report_path, "w") as f:
            f.write(report_html)

        logger.info(f"HTML test report saved to: {report_path}")

    except ImportError:
        logger.warning("Jinja2 not installed. HTML report generation skipped.")


def create_basic_report_template(template_path):
    """Create a basic HTML report template if one doesn't exist"""
    os.makedirs(os.path.dirname(template_path), exist_ok=True)

    template_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ title }}</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #333; }
            .summary { margin: 20px 0; padding: 15px; background-color: #f5f5f5; border-radius: 5px; }
            .success { color: green; }
            .failure { color: red; }
            .detail-section { margin-top: 30px; }
            .error-detail, .failure-detail {
                margin: 10px 0;
                padding: 10px;
                border-left: 5px solid #ff6b6b;
                background-color: #fff0f0;
            }
            pre { white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <h1>{{ title }}</h1>
        <div class="summary">
            <p><strong>Date:</strong> {{ timestamp }}</p>
            <p><strong>Execution Time:</strong> {{ execution_time }} seconds</p>
            <p><strong>Result:</strong>
                {% if was_successful %}
                <span class="success">SUCCESS</span>
                {% else %}
                <span class="failure">FAILURE</span>
                {% endif %}
            </p>
            <p><strong>Tests Run:</strong> {{ tests_run }}</p>
            <p><strong>Tests Passed:</strong> {{ tests_passed }}</p>
            <p><strong>Failures:</strong> {{ failures }}</p>
            <p><strong>Errors:</strong> {{ errors }}</p>
            <p><strong>Skipped:</strong> {{ skipped }}</p>
        </div>

        {% if failures > 0 %}
        <div class="detail-section">
            <h2>Failures</h2>
            {% for failure in failure_details %}
            <div class="failure-detail">
                <h3>{{ failure.test }}</h3>
                <pre>{{ failure.message }}</pre>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if errors > 0 %}
        <div class="detail-section">
            <h2>Errors</h2>
            {% for error in error_details %}
            <div class="error-detail">
                <h3>{{ error.test }}</h3>
                <pre>{{ error.message }}</pre>
            </div>
            {% endfor %}
        </div>
        {% endif %}
    </body>
    </html>
    """

    with open(template_path, "w") as f:
        f.write(template_html)


def check_test_dependencies():
    """Check if required test dependencies are installed"""
    missing_deps = []

    # Check for test dependencies
    try:
        import unittest
    except ImportError:
        missing_deps.append("unittest")

    # Check for optional dependencies
    optional_deps = {
        "coverage": "coverage reporting",
        "xmlrunner": "JUnit XML reports",
        "jinja2": "HTML reports",
    }

    for dep, description in optional_deps.items():
        try:
            __import__(dep)
        except ImportError:
            logger.warning(
                f"Optional dependency '{dep}' not found. {description} will be limited."
            )

    # Return True if all required dependencies are met
    return len(missing_deps) == 0


def setup_test_environment(args):
    """Set up the testing environment"""
    logger.info("Setting up test environment...")

    # Set up environment variables
    os.environ["SABRINA_TESTING"] = "true"

    # If mock_all is enabled, set environment variable
    if args.mock_all:
        os.environ["SABRINA_MOCK_ALL"] = "true"
        logger.info("Forcing mock mode for all external dependencies")

    # If test_config is provided, set environment variable
    if args.test_config:
        if os.path.exists(args.test_config):
            os.environ["SABRINA_TEST_CONFIG"] = args.test_config
            logger.info(f"Using test configuration from: {args.test_config}")
        else:
            logger.warning(f"Test configuration file not found: {args.test_config}")

    # Create test logs directory
    logs_dir = os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Create test results directory
    os.makedirs(os.path.join(project_root, "test_results"), exist_ok=True)


def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print(" Sabrina AI Test Runner ".center(60))
    print("=" * 60 + "\n")

    # Parse command line arguments
    args = parse_arguments()

    # Check dependencies
    if not check_test_dependencies():
        logger.error(
            "Missing required test dependencies. Please install them and try again."
        )
        return 1

    # Set up test environment
    setup_test_environment(args)

    # Discover tests
    test_suite = discover_tests(args)

    if test_suite.countTestCases() == 0:
        logger.warning("No tests discovered. Check test patterns and paths.")
        return 0

    # Run tests (with coverage if requested)
    if args.coverage:
        result = run_tests_with_coverage(test_suite, args)
    else:
        result = run_tests(test_suite, args)

    # Generate HTML report if requested
    if args.html_report:
        elapsed_time = getattr(result, "_elapsed_time", 0)
        generate_html_report(result, elapsed_time, args)

    # Return success or failure
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
