# Enhanced Automation for Sabrina AI

This document describes the enhanced automation capabilities added to the Sabrina AI project, including:
- Click-and-drag functionality
- Scrolling support
- Keyboard shortcuts for common PC actions

## Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Installation & Dependencies](#installation--dependencies)
4. [Basic Usage](#basic-usage)
5. [Advanced Features](#advanced-features)
6. [Common Tasks](#common-tasks)
7. [Integration Examples](#integration-examples)
8. [Troubleshooting](#troubleshooting)

## Overview

The enhanced automation module provides comprehensive PC control capabilities through an easy-to-use API. It allows Sabrina AI to interact with applications, manipulate content, and automate routine tasks through mouse and keyboard actions.

The module is designed with graceful degradation in mind - if advanced automation libraries are not available, it falls back to simpler methods or simulation mode to maintain compatibility across different environments.

## Key Features

### Mouse Control
- **Basic Movement**: Precise cursor positioning with configurable movement duration
- **Click Operations**: Single, double, and right-clicks at current or specified positions
- **Click-and-Drag**: Drag operations for selecting text, moving objects, and drawing
- **Scrolling**: Vertical scrolling with configurable direction and amount

### Keyboard Control
- **Text Input**: Type text with configurable intervals between keystrokes
- **Key Presses**: Individual key presses and key combinations (hotkeys)
- **Predefined Shortcuts**: Ready-to-use shortcuts for common operations (copy, paste, etc.)
- **Custom Shortcuts**: Create and execute custom key combinations

### Task Automation
- **Common Tasks**: Predefined methods for everyday PC tasks
- **Multi-Step Actions**: Combined operations for complex workflows
- **Application Control**: Launch, interact with, and close applications

## Installation & Dependencies

The enhanced automation module builds on the existing Sabrina AI framework and requires the following optional dependencies for full functionality:

```bash
# Core dependency - required for basic functionality
pip install pyautogui

# Optional dependencies for enhanced features
pip install mouse
pip install keyboard
```

If these libraries are not available, the module will operate in a fallback mode with limited functionality.

## Basic Usage

### Initialization

```python
from services.automation.automation import Actions

# Create automation instance
automation = Actions()

# Configure settings (optional)
automation.configure(
    mouse_move_duration=0.3,  # Duration for mouse movements in seconds
    typing_interval=0.05,     # Delay between keystrokes
    failsafe=True,            # Enable corner-of-screen failsafe
    scroll_amount=3           # Default scroll amount
)
```

### Mouse Operations

```python
# Move mouse to coordinates
automation.move_mouse_to(500, 300)

# Click at current position
automation.click()

# Right-click at specific coordinates
automation.click_at(800, 400, button="right")

# Double-click
automation.click(clicks=2)

# Drag operation (click, hold, move, release)
automation.drag_mouse(200, 200, 400, 400)

# Scroll up or down
automation.scroll(direction="down")
automation.scroll(amount=5, direction="up")
```

### Keyboard Operations

```python
# Type text
automation.type_text("Hello, Sabrina AI!")

# Press a single key
automation.press_key("enter")

# Press a key combination (hotkey)
automation.hotkey("ctrl", "s")  # Save

# Use a predefined shortcut
automation.run_shortcut("copy")
automation.run_shortcut("paste")
```

## Advanced Features

### Click-and-Drag Operations

The new click-and-drag functionality allows Sabrina AI to:
- Select text in documents and web pages
- Move files and folders in file explorers
- Interact with slider controls and other draggable UI elements
- Draw shapes in graphics applications

```python
# Select text by dragging
automation.select_text(200, 300, 400, 300)

# Select a rectangular region
automation.select_region(100, 100, 300, 300)

# Drag with specific mouse button
automation.drag_mouse(200, 200, 300, 300, button="left")

# Drag with custom duration
automation.drag_mouse(200, 200, 300, 300, duration=1.0)
```

### Enhanced Scrolling

Scrolling capabilities allow Sabrina AI to navigate through documents, web pages, and other scrollable content:

```python
# Simple scrolling (positive = down, negative = up)
automation.scroll(5)      # Scroll down
automation.scroll(-5)     # Scroll up

# Direction-based scrolling
automation.scroll(direction="up")
automation.scroll(direction="down")

# Scroll to make an element visible
automation.scroll_to_element(target_y=500)
```

### Custom Shortcuts

You can define custom keyboard shortcuts for specific applications or workflows:

```python
# Add a custom shortcut
automation.add_custom_shortcut("launch_terminal", ["ctrl", "alt", "t"])
automation.add_custom_shortcut("refresh_browser", ["f5"])

# Execute custom shortcut
automation.run_shortcut("launch_terminal")
```

## Common Tasks

The module includes predefined methods for common PC tasks:

```python
# Copy selected content
automation.run_common_task("copy")

# Paste at current position
automation.run_common_task("paste")

# Copy and paste to a new location
automation.run_common_task("copy_paste", target_x=500, target_y=300)

# Open search dialog and enter search term
automation.run_common_task("search", search_text="automation example")

# Take a screenshot
automation.run_common_task("take_screenshot")

# Save current document
automation.run_common_task("save_document")

# Open browser with specific URL
automation.run_common_task("open_browser", url="https://example.com")
```

Available common tasks:
- `copy` - Copy selected content
- `paste` - Paste content
- `copy_paste` - Copy and paste in one operation
- `select_all` - Select all content
- `search` - Open search dialog
- `take_screenshot` - Capture screen
- `new_document` - Create new document/tab
- `save_document` - Save current document
- `close_window` - Close current window/tab
- `switch_window` - Switch between windows
- `open_browser` - Launch browser

## Integration Examples

### Voice Command Integration

```python
def handle_voice_command(command):
    """Handle voice commands for automation"""
    automation = Actions()

    if "select all" in command:
        automation.run_shortcut("select_all")
        return "Selected all content"

    elif "copy" in command and "paste" in command:
        automation.run_common_task("copy_paste")
        return "Copied and pasted content"

    elif "scroll down" in command:
        automation.scroll(direction="down")
        return "Scrolled down"

    elif "take screenshot" in command:
        automation.run_common_task("take_screenshot")
        return "Taking screenshot"

    return "Command not recognized"
```

### Vision Integration

```python
def click_detected_button(vision_core, automation):
    """Use vision to detect and click a button"""
    # Capture screen
    image_path = vision_core.capture_screen()

    # Detect UI elements
    ui_elements = vision_core.detect_ui_elements(image_path)

    # Find first button element
    for element in ui_elements:
        if element.get("type") == "button":
            # Get coordinates of the button center
            coords = element.get("coordinates", [0, 0, 0, 0])
            x1, y1, x2, y2 = coords
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2

            # Click the button
            automation.click_at(center_x, center_y)
            return f"Clicked button at ({center_x}, {center_y})"

    return "No buttons detected"
```

## Troubleshooting

### Common Issues

1. **Mouse movements not working**
   - Ensure PyAutoGUI is installed
   - Check if you have permission to control mouse (especially on macOS)
   - Verify your screen resolution matches what the automation module detects

2. **Keyboard input not working**
   - Some systems restrict programmatic keyboard input
   - Try running your script with administrative privileges
   - On macOS, ensure you've granted accessibility permissions

3. **Actions happen too quickly**
   - Increase the `mouse_move_duration` and `typing_interval` settings
   - Add explicit `time.sleep()` calls between actions

4. **Failsafe triggering unexpectedly**
   - The failsafe is triggered when the mouse moves to the very corner of the screen
   - Disable it with `automation.configure(failsafe=False)` if needed

### Debugging Tips

1. Use simulation mode to test automation logic:
   ```python
   # Force simulation mode for testing
   automation.pyautogui_available = False
   ```

2. Get current mouse position to debug coordinate issues:
   ```python
   x, y = automation.get_mouse_position()
   print(f"Current position: ({x}, {y})")
   ```

3. Run the included test script with debug logging:
   ```bash
   python tests/test_enhanced_automation.py --debug --interactive
   ```

## Conclusion

The enhanced automation module provides Sabrina AI with comprehensive PC control capabilities, enabling fluid interaction with applications and content through mouse and keyboard operations. By implementing click-and-drag, scrolling, and common shortcuts, Sabrina AI can now perform more complex tasks and manipulate content more naturally.
