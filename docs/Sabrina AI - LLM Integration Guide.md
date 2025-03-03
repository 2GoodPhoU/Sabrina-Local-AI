# Sabrina AI - LLM Integration Guide

This guide explains how to integrate large language models (LLMs) with Sabrina AI's core systems, enabling powerful AI-driven capabilities while maintaining local execution and privacy.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Input Framework](#input-framework)
- [Function Registration](#function-registration)
- [Integration Workflow](#integration-workflow)
- [Component Interaction](#component-interaction)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Sabrina AI provides a standardized framework for LLM integration that enables:

1. **Structured Input/Output**: Consistent formatting for LLM requests and responses
2. **Function Calling**: Direct access to system functionality from the LLM
3. **Component Delegation**: Ability to route tasks to specialized components
4. **Thinking & Planning**: Internal reasoning capabilities for complex tasks
5. **Stateful Context**: Persistent memory and state management

The integration works with any LLM that supports function calling (OpenAI-compatible models like Claude, Llama, Gemini, etc.) and can be adapted to work with other models using prompt engineering.

## Architecture

The LLM integration architecture consists of:

```
[LLM Provider]  ⟷  [Input Framework]  ⟷  [Core System]  ⟷  [Components]
```

Key components:

1. **LLM Input Framework** (`core/llm_input_framework.py`): Manages communication between LLM and Sabrina
2. **LLM Input Handler** (in `LLMInputHandler` class): Routes and processes LLM requests
3. **Service Component Wrappers** (`core/component_service_wrappers.py`): Standardized interfaces to system components

## Input Framework

The input framework uses structured data classes to handle LLM requests and responses:

### Input Types

The `InputType` enum defines the types of inputs from the LLM:

- `ACTION`: Direct function call or action
- `QUERY`: Request for information from the system
- `RESPONSE`: Text or speech response to the user
- `THINKING`: Internal reasoning (not shown to user)
- `DELEGATED`: Task delegated to a specific component
- `STRATEGY`: System-level planning and strategy

### Output Types

The `OutputType` enum defines the types of outputs sent back to the LLM:

- `RESULT`: Result of an action
- `DATA`: Raw data from the system
- `ERROR`: Error information
- `STATUS`: Status update
- `EVENT`: System event notification
- `CONTEXT`: Context or state information

### Data Classes

The framework uses structured data classes:

- `LLMInput`: Represents input from the LLM
- `LLMOutput`: Represents output to the LLM
- `LLMFunction`: Definition of a callable function
- `LLMParameter`: Definition of a function parameter

## Function Registration

The core system registers functions that LLMs can call. Here's an example of function registration:

```python
# From core initialization
input_handler = LLMInputHandler(core)

# Register a function
input_handler.register_function(
    name="capture_screen",
    description="Capture the current screen content as an image",
    handler=lambda: core.components["vision"].capture_screen(),
    parameters=[
        LLMParameter(
            name="mode",
            type="string",
            description="Capture mode (full_screen, active_window, specific_region)",
            required=False,
            default="full_screen",
            enum=["full_screen", "active_window", "specific_region"]
        )
    ],
    category="vision"
)
```

Each registered function becomes available to the LLM through function calling schemas.

## Integration Workflow

A typical LLM integration workflow:

1. **Initialize Components**: Core system initializes all components
2. **Register Functions**: Components register their capabilities as functions
3. **Process User Input**: User voice/text input is processed
4. **LLM Request**: Send a request to the LLM with current context
5. **Function Calls**: LLM returns function calls to perform actions
6. **Function Execution**: Input handler executes the requested functions
7. **Result Processing**: Results are returned to the LLM for further processing
8. **User Response**: Final response delivered to the user

## Component Interaction

The LLM can interact with Sabrina components in three ways:

1. **Direct Action**: Call a registered function directly
   ```python
   LLMInput(type=InputType.ACTION, action="get_system_status")
   ```

2. **Component Delegation**: Delegate to a specific component
   ```python
   LLMInput(
       type=InputType.DELEGATED,
       action="capture_screen",
       parameters={"component": "vision", "params": {"mode": "active_window"}}
   )
   ```

3. **User Response**: Generate a response to the user
   ```python
   LLMInput(
       type=InputType.RESPONSE,
       text="I've captured the screen for you.",
       parameters={"use_voice": True, "emotion": "happy"}
   )
   ```

## Examples

### Basic Function Call

```python
from core.llm_input_framework import LLMInput, InputType

# Create a function call to get system status
status_input = LLMInput(
    type=InputType.ACTION,
    action="get_system_status"
)

# Process the function call
result = input_handler.process_input(status_input)

# Extract result data
system_status = result.data
print(f"System state: {system_status.get('state')}")
print(f"Uptime: {system_status.get('uptime')} seconds")
```

### Screen Capture and Analysis

```python
from core.llm_input_framework import LLMInput, InputType

# Capture the screen
capture_input = LLMInput(
    type=InputType.DELEGATED,
    action="capture_screen",
    parameters={
        "component": "vision",
        "params": {"mode": "active_window"}
    }
)

# Process the capture request
capture_result = input_handler.process_input(capture_input)
image_path = capture_result.data

# Extract text from the captured image
ocr_input = LLMInput(
    type=InputType.DELEGATED,
    action="extract_text",
    parameters={
        "component": "vision",
        "params": {"image_path": image_path}
    }
)

# Process the OCR request
ocr_result = input_handler.process_input(ocr_input)
extracted_text = ocr_result.data

# Respond to the user
response_input = LLMInput(
    type=InputType.RESPONSE,
    text=f"I found the following text: {extracted_text[:100]}...",
    parameters={"use_voice": True}
)

input_handler.process_input(response_input)
```

### Smart Home Control

```python
from core.llm_input_framework import LLMInput, InputType

# Control a smart home device
device_input = LLMInput(
    type=InputType.DELEGATED,
    action="control_device",
    parameters={
        "component": "smart_home",
        "params": {
            "device_id": "living_room_light",
            "command": "on"
        }
    }
)

# Process the device control request
result = input_handler.process_input(device_input)

# Check if successful
if result.status == "success":
    # Notify the user
    response_input = LLMInput(
        type=InputType.RESPONSE,
        text="I've turned on the living room light.",
        parameters={"use_voice": True, "emotion": "happy"}
    )
    input_handler.process_input(response_input)
else:
    # Handle failure
    response_input = LLMInput(
        type=InputType.RESPONSE,
        text="I couldn't turn on the living room light.",
        parameters={"use_voice": True, "emotion": "concerned"}
    )
    input_handler.process_input(response_input)
```

### Internal Thinking for Complex Tasks

```python
from core.llm_input_framework import LLMInput, InputType

# First, do some internal thinking (not shown to user)
thinking_input = LLMInput(
    type=InputType.THINKING,
    thinking="""
    The user wants to set a reminder. I need to:
    1. Extract the time (3pm tomorrow)
    2. Extract the task (call doctor)
    3. Create a calendar entry
    4. Confirm with the user
    """,
    parameters={"context_key": "reminder_planning"}
)

# Process the thinking
input_handler.process_input(thinking_input)

# Create the calendar entry
calendar_input = LLMInput(
    type=InputType.ACTION,
    action="create_calendar_event",
    parameters={
        "title": "Call doctor",
        "start_time": "2025-03-03T15:00:00",
        "duration_minutes": 30,
        "reminder_minutes": 15
    }
)

# Process the calendar request
result = input_handler.process_input(calendar_input)

# Confirm with the user
confirmation_input = LLMInput(
    type=InputType.RESPONSE,
    text="I've set a reminder for you to call the doctor tomorrow at 3 PM.",
    parameters={"use_voice": True}
)

input_handler.process_input(confirmation_input)
```

## Best Practices

### Function Design

1. **Clear Function Names**: Use descriptive names that clearly indicate the function's purpose
2. **Comprehensive Descriptions**: Provide detailed descriptions for functions and parameters
3. **Parameter Validation**: Define parameter types, requirements, and valid values
4. **Error Handling**: Return informative error messages when functions fail
5. **Function Categories**: Organize functions into logical categories

### LLM Prompting

1. **System Message**: Provide a clear system message describing Sabrina's capabilities
2. **Function Context**: Include context about when to use specific functions
3. **Output Format**: Specify expected output formats for different tasks
4. **Chain of Thought**: Encourage step-by-step reasoning for complex tasks
5. **State Management**: Maintain and update system state in the prompt

### Security Considerations

1. **Input Validation**: Validate all inputs from the LLM before execution
2. **Permission Model**: Implement a permission model for sensitive operations
3. **Rate Limiting**: Prevent excessive function calls or resource usage
4. **Context Boundaries**: Maintain clear boundaries between system and LLM
5. **Sensitive Data**: Avoid passing sensitive data to external LLMs

## Troubleshooting

### Common Issues

1. **Function Calling Not Working**
   - Ensure function schemas are properly formatted
   - Check if the LLM supports function calling
   - Verify that functions are registered correctly

2. **Parameter Validation Failures**
   - Check that parameters match the expected types
   - Ensure required parameters are provided
   - Verify that enum values are valid

3. **Context Management Issues**
   - Ensure context is being properly maintained between calls
   - Check for context size limitations
   - Verify that state updates are being applied

4. **Component Integration Problems**
   - Ensure components are properly initialized
   - Check component interfaces and method signatures
   - Verify event handling between components

### Debugging Tools

1. **Event Logging**: Monitor events in the event bus using `event_bus.get_stats()`
2. **Function Registration Checks**: List registered functions with `input_handler.get_function_list()`
3. **LLM Input/Output Logging**: Enable logging for LLM inputs and outputs
4. **Component Status Checks**: Get component status via `component.get_status()`

## Advanced Topics

### Custom LLM Providers

The framework supports any LLM provider that can be integrated with Python. To add a new provider:

1. Create a provider adapter class that implements the required interface
2. Configure the provider with appropriate credentials and settings
3. Connect the provider to the input framework
4. Implement function calling support for the provider

### Model Fallbacks

For resilience, implement a fallback strategy:

```python
try:
    # Try primary LLM
    response = primary_llm.generate(prompt)
except Exception:
    # Fall back to secondary LLM
    response = fallback_llm.generate(prompt)
```

### Extending the Framework

You can extend the framework with new input or output types:

1. Add new enum values to `InputType` or `OutputType`
2. Implement handler methods in `LLMInputHandler`
3. Update documentation and examples
4. Register new capabilities with components

### Offline Operation

The LLM integration can work entirely offline with local models:

1. Use local models like Llama, Mistral, or Phi
2. Implement a local caching strategy for frequently used responses
3. Configure fallback behaviors for when models are unavailable
4. Optimize models for your hardware capabilities

## Conclusion

The Sabrina AI LLM Integration Framework provides a powerful and flexible way to connect LLMs with system components. By using a structured approach to function calling and component delegation, you can build sophisticated AI applications that maintain privacy, security, and reliability while leveraging the capabilities of modern language models.

For further assistance, consult the code documentation in `core/llm_input_framework.py` and the integration examples in `core/llm_integration_test.py`.

---

**Next Steps:**
- Learn about [Event-Driven Architecture](event_system.md) in Sabrina AI
- Explore [Component Service Wrappers](component_wrappers.md) for system integration
- Understand [State Management](state_machine.md) for complex AI behaviors
