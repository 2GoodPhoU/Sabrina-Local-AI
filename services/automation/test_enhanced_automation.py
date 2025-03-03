#!/usr/bin/env python3
"""
Test Script for Enhanced Automation Features
===========================================
This script demonstrates the new automation capabilities:
- Click and drag functionality
- Scrolling
- Keyboard shortcuts and common PC actions
"""

import sys
import time
import logging
import argparse
from pathlib import Path

# Ensure the project root is in the Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent  # Adjust based on where this script is located
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("automation_test")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Enhanced Automation Test")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--interactive", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument(
        "--test",
        choices=["all", "drag", "scroll", "shortcuts", "tasks"],
        default="all",
        help="Test specific features",
    )
    parser.add_argument(
        "--duration", type=float, default=0.5, help="Duration for mouse movements"
    )
    return parser.parse_args()


def initialize_automation():
    """Initialize the automation module"""
    try:
        # Import the enhanced automation module
        from services.automation.automation import Actions

        logger.info("Initializing automation module...")
        automation = Actions()

        # Configure automation
        automation.configure(
            mouse_move_duration=0.5,
            typing_interval=0.05,
            failsafe=True,
            scroll_amount=3,
        )

        return automation
    except ImportError as e:
        logger.error(f"Failed to import Actions module: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error initializing automation module: {str(e)}")
        return None


def test_mouse_movement(automation, duration=0.5):
    """Test basic mouse movement"""
    print("\n=== Testing Mouse Movement ===")

    # Get current position as starting point
    start_x, start_y = automation.get_mouse_position()
    print(f"Current mouse position: ({start_x}, {start_y})")

    # Move to a few test positions
    test_positions = [
        (100, 100),
        (300, 200),
        (500, 400),
        (200, 300),
    ]

    for i, (x, y) in enumerate(test_positions):
        print(f"Moving to position {i+1}: ({x}, {y})")
        automation.move_mouse_to(x, y, duration)
        time.sleep(0.5)

    # Return to starting position
    print(f"Returning to original position: ({start_x}, {start_y})")
    automation.move_mouse_to(start_x, start_y, duration)

    print("Mouse movement test completed")
    return True


def test_click_and_drag(automation, duration=0.5):
    """Test click and drag functionality"""
    print("\n=== Testing Click and Drag ===")

    # Get screen dimensions (for calculations)
    try:
        if hasattr(automation, "screen_width") and hasattr(automation, "screen_height"):
            screen_width = automation.screen_width
            screen_height = automation.screen_height
        else:
            # Default values if not available
            screen_width = 1920
            screen_height = 1080

        print(f"Screen size: {screen_width}x{screen_height}")

        # Define drag operations to test
        # Format: (start_x, start_y, end_x, end_y, description)
        drag_operations = [
            # Small diagonal drag
            (200, 200, 300, 300, "Small diagonal drag"),
            # Horizontal drag (left to right)
            (200, 400, 600, 400, "Horizontal drag (left to right)"),
            # Vertical drag (top to bottom)
            (400, 200, 400, 500, "Vertical drag (top to bottom)"),
            # Selection-like drag (creates a rectangle)
            (300, 300, 500, 500, "Rectangle selection drag"),
        ]

        # Perform each drag operation
        for start_x, start_y, end_x, end_y, description in drag_operations:
            print(f"\nPerforming: {description}")
            print(f"Dragging from ({start_x}, {start_y}) to ({end_x}, {end_y})")

            # Execute the drag
            automation.drag_mouse(start_x, start_y, end_x, end_y, duration)

            # Pause between operations
            time.sleep(1)

        print("Click and drag test completed")
        return True

    except Exception as e:
        logger.error(f"Error in click and drag test: {str(e)}")
        return False


def test_scrolling(automation):
    """Test scrolling functionality"""
    print("\n=== Testing Scrolling ===")

    # Move to center of screen first
    try:
        if hasattr(automation, "screen_width") and hasattr(automation, "screen_height"):
            center_x = automation.screen_width // 2
            center_y = automation.screen_height // 2
        else:
            # Default values if not available
            center_x = 960
            center_y = 540

        # Move to center
        print(f"Moving to screen center: ({center_x}, {center_y})")
        automation.move_mouse_to(center_x, center_y)
        time.sleep(0.5)

        # Test scrolling down
        print("Scrolling down (3 times)")
        for i in range(3):
            automation.scroll(direction="down")
            time.sleep(0.5)

        # Test scrolling up
        print("Scrolling up (3 times)")
        for i in range(3):
            automation.scroll(direction="up")
            time.sleep(0.5)

        # Test variable amount scrolling
        print("Scrolling down (10 units)")
        automation.scroll(amount=10, direction="down")
        time.sleep(1)

        print("Scrolling up (10 units)")
        automation.scroll(amount=10, direction="up")

        print("Scrolling test completed")
        return True

    except Exception as e:
        logger.error(f"Error in scrolling test: {str(e)}")
        return False


def test_shortcuts(automation):
    """Test keyboard shortcuts"""
    print("\n=== Testing Keyboard Shortcuts ===")

    try:
        # List available shortcuts
        shortcuts = automation.get_available_shortcuts()
        print(f"Available shortcuts: {', '.join(shortcuts)}")

        # Test a few common shortcuts
        shortcuts_to_test = ["copy", "paste", "select_all", "undo", "redo", "find"]

        for shortcut in shortcuts_to_test:
            if shortcut in shortcuts:
                print(f"Executing shortcut: {shortcut}")
                automation.run_shortcut(shortcut)
                time.sleep(1)
            else:
                print(f"Shortcut not available: {shortcut}")

        # Test custom shortcut addition
        print("\nAdding custom shortcut 'launch_calculator'")
        automation.add_custom_shortcut("launch_calculator", ["win", "r"])

        # Execute the custom shortcut
        print("Executing custom shortcut")
        automation.run_shortcut("launch_calculator")
        time.sleep(0.5)

        # Type "calc" and press Enter to launch calculator
        automation.type_text("calc")
        time.sleep(0.5)
        automation.press_key("enter")

        # Wait for calculator to open
        time.sleep(2)

        # Close calculator
        print("Closing calculator")
        automation.hotkey("alt", "f4")

        print("Shortcut test completed")
        return True

    except Exception as e:
        logger.error(f"Error in shortcuts test: {str(e)}")
        return False


def test_common_tasks(automation):
    """Test common PC tasks"""
    print("\n=== Testing Common PC Tasks ===")

    try:
        # Test search task
        print("Testing 'search' task")
        automation.run_common_task("search", search_text="automation test")
        time.sleep(2)

        # Cancel search dialog
        automation.press_key("escape")
        time.sleep(0.5)

        # Test select all and copy
        print("Testing 'select_all' followed by 'copy'")
        automation.run_common_task("select_all")
        time.sleep(0.5)
        automation.run_common_task("copy")
        time.sleep(0.5)

        # Try taking a screenshot (only works on some systems)
        try:
            print("Attempting to take a screenshot")
            automation.run_common_task("take_screenshot")
            time.sleep(1)
            # Cancel screenshot UI if it's active
            automation.press_key("escape")
            time.sleep(0.5)
        except Exception as e:
            print(f"Screenshot test failed (may not be supported): {e}")

        print("Common tasks test completed")
        return True

    except Exception as e:
        logger.error(f"Error in common tasks test: {str(e)}")
        return False


def interactive_test(automation, duration=0.5):
    """Run an interactive test with user prompts"""
    print("\n=== Interactive Automation Test ===")
    print("This test allows you to try specific automation features interactively.")

    while True:
        print("\nAvailable actions:")
        print("1. Move mouse to coordinates")
        print("2. Click at current position")
        print("3. Drag mouse")
        print("4. Scroll up/down")
        print("5. Type text")
        print("6. Execute shortcut")
        print("7. Run common task")
        print("8. Get current mouse position")
        print("9. Exit interactive test")

        choice = input("\nEnter your choice (1-9): ")

        try:
            if choice == "1":
                x = int(input("Enter X coordinate: "))
                y = int(input("Enter Y coordinate: "))
                automation.move_mouse_to(x, y, duration)

            elif choice == "2":
                button = input("Enter button (left, right, middle) [left]: ") or "left"
                clicks = int(input("Enter number of clicks [1]: ") or "1")
                automation.click(button=button, clicks=clicks)

            elif choice == "3":
                start_x = int(input("Enter start X coordinate: "))
                start_y = int(input("Enter start Y coordinate: "))
                end_x = int(input("Enter end X coordinate: "))
                end_y = int(input("Enter end Y coordinate: "))
                automation.drag_mouse(start_x, start_y, end_x, end_y, duration)

            elif choice == "4":
                direction = input("Enter direction (up, down) [down]: ") or "down"
                amount = int(input("Enter scroll amount [3]: ") or "3")
                if direction == "up":
                    amount = -amount
                automation.scroll(amount)

            elif choice == "5":
                text = input("Enter text to type: ")
                automation.type_text(text)

            elif choice == "6":
                shortcuts = automation.get_available_shortcuts()
                print(f"Available shortcuts: {', '.join(shortcuts)}")
                shortcut = input("Enter shortcut name: ")
                if shortcut in shortcuts:
                    automation.run_shortcut(shortcut)
                else:
                    print(f"Unknown shortcut: {shortcut}")

            elif choice == "7":
                print("Common tasks: copy, paste, select_all, search, take_screenshot")
                task = input("Enter task name: ")
                if task == "search":
                    search_text = input("Enter search text: ")
                    automation.run_common_task(task, search_text=search_text)
                else:
                    automation.run_common_task(task)

            elif choice == "8":
                x, y = automation.get_mouse_position()
                print(f"Current mouse position: ({x}, {y})")

            elif choice == "9":
                print("Exiting interactive test")
                break

            else:
                print("Invalid choice, please try again")

        except Exception as e:
            print(f"Error executing command: {str(e)}")

    return True


def main():
    """Main function"""
    # Parse arguments
    args = parse_arguments()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    print("\n===== Enhanced Automation Test =====")

    # Initialize automation
    automation = initialize_automation()

    if not automation:
        print("Failed to initialize automation module. Exiting.")
        return 1

    print(f"PyAutoGUI available: {'Yes' if automation.pyautogui_available else 'No'}")

    # Run in interactive mode if requested
    if args.interactive:
        interactive_test(automation, args.duration)
        return 0

    # Run specific tests based on command line argument
    test_results = {}

    if args.test in ["all", "drag"]:
        test_results["drag"] = test_click_and_drag(automation, args.duration)

    if args.test in ["all", "scroll"]:
        test_results["scroll"] = test_scrolling(automation)

    if args.test in ["all", "shortcuts"]:
        test_results["shortcuts"] = test_shortcuts(automation)

    if args.test in ["all", "tasks"]:
        test_results["tasks"] = test_common_tasks(automation)

    # Print test results
    print("\n===== Test Results =====")
    for test_name, result in test_results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name.capitalize()} Test: {status}")

    if all(test_results.values()):
        print("\nAll tests passed successfully!")
    else:
        print("\nSome tests failed. Check the output for details.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
