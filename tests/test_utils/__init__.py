"""
Sabrina AI Test Utilities
=======================
This package provides utilities for testing Sabrina AI components.

The utilities are organized into modules:
- paths.py: Path utilities for consistent path handling
- helpers.py: Helper functions and mock components
"""

from tests.test_utils.paths import (
    get_project_root,
    get_test_dir,
    get_test_unit_dir,
    get_test_integration_dir,
    get_test_e2e_dir,
    get_test_utils_dir,
    get_test_data_dir,
    get_test_temp_dir,
    get_component_path,
    get_config_path,
    get_test_config_path,
    ensure_path_in_sys_path,
    ensure_project_root_in_sys_path,
    create_test_path_context,
    create_test_file,
    get_test_resource_path,
    PROJECT_ROOT,
    TEST_DIR,
)

from tests.test_utils.helpers import (
    create_test_config,
    wait_for_condition,
    MockComponent,
    MockVoiceService,
    MockVisionService,
    MockAutomationService,
    MockHearingService,
    create_mock_event_bus,
    create_mock_state_machine,
    setup_component_test_environment,
    teardown_component_test_environment,
    SabrinaTestCase,
)

# Ensure project root is in path when importing this package
ensure_project_root_in_sys_path()
