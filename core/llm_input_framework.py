"""
Sabrina AI LLM Input Framework
============================
A standardized framework for LLM interaction with Sabrina's core systems
through a structured input/output protocol and function calling.
"""

import json
import logging
import time
import re
from typing import Dict, Any, List, Union, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sabrina.llm_framework")


class InputType(Enum):
    """Types of input Sabrina can accept from the LLM"""

    ACTION = "action"  # Direct action or function call
    QUERY = "query"  # Query about system state or information
    RESPONSE = "response"  # Response to user (text, voice, etc.)
    THINKING = "thinking"  # Internal reasoning/planning (not shown to user)
    DELEGATED = "delegated"  # Task delegated to a component
    STRATEGY = "strategy"  # System-level strategy or approach


class OutputType(Enum):
    """Types of output sent back to the LLM"""

    RESULT = "result"  # Result of an action
    DATA = "data"  # Raw data from system or component
    ERROR = "error"  # Error information
    STATUS = "status"  # Status update
    EVENT = "event"  # System event notification
    CONTEXT = "context"  # Context or state information


@dataclass
class LLMParameter:
    """Definition of a parameter for an LLM-callable function"""

    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None
    enum: List[str] = None
    min_value: Any = None
    max_value: Any = None
    format: str = None
    example: Any = None


@dataclass
class LLMFunction:
    """Definition of a function that can be called by the LLM"""

    name: str
    description: str
    parameters: List[LLMParameter] = field(default_factory=list)
    return_type: str = "any"
    return_description: str = ""
    examples: List[Dict[str, Any]] = field(default_factory=list)
    handler: Callable = None
    category: str = "general"


@dataclass
class LLMInput:
    """Structured input from LLM to Sabrina"""

    type: InputType
    action: str = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    thinking: str = None
    text: str = None
    context: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"input_{int(time.time()*1000)}")
    timestamp: float = field(default_factory=time.time)


@dataclass
class LLMOutput:
    """Structured output from Sabrina to LLM"""

    type: OutputType
    status: str = "success"
    data: Any = None
    error: str = None
    context: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"output_{int(time.time()*1000)}")
    timestamp: float = field(default_factory=time.time)
    reference_input_id: str = None


class LLMInputHandler:
    """
    Handles structured input from LLM and routes to appropriate components

    This class serves as the bridge between the LLM's structured input and
    Sabrina's core system, routing commands to the appropriate components
    and formatting responses.
    """

    def __init__(self, core_system):
        """
        Initialize the LLM input handler

        Args:
            core_system: Reference to the SabrinaCore instance
        """
        self.core = core_system
        self.functions: Dict[str, LLMFunction] = {}
        self.categories: Dict[str, List[str]] = {}

        # Register built-in functions
        self._register_builtin_functions()

        logger.info("LLM Input Handler initialized")

    def _register_builtin_functions(self):
        """Register built-in system functions"""
        # System status function
        self.register_function(
            name="get_system_status",
            description="Get the current status of the Sabrina AI system",
            handler=self._handle_get_system_status,
            parameters=[
                LLMParameter(
                    name="component",
                    type="string",
                    description="Specific component to get status for (optional)",
                    required=False,
                )
            ],
            category="system",
        )

        # Current state function
        self.register_function(
            name="get_current_state",
            description="Get the current state of the Sabrina AI system",
            handler=self._handle_get_current_state,
            category="system",
        )

        # Response to user function
        self.register_function(
            name="respond",
            description="Respond to the user with text and/or voice",
            handler=self._handle_respond,
            parameters=[
                LLMParameter(
                    name="text",
                    type="string",
                    description="Text to respond with",
                    required=True,
                ),
                LLMParameter(
                    name="use_voice",
                    type="boolean",
                    description="Whether to speak the response",
                    required=False,
                    default=True,
                ),
                LLMParameter(
                    name="emotion",
                    type="string",
                    description="Emotion to convey in voice response",
                    required=False,
                    enum=["neutral", "happy", "sad", "concerned", "excited"],
                    default="neutral",
                ),
            ],
            category="interaction",
        )

    def register_function(
        self,
        name: str,
        description: str,
        handler: Callable,
        parameters: List[LLMParameter] = None,
        return_type: str = "any",
        return_description: str = "",
        examples: List[Dict[str, Any]] = None,
        category: str = "general",
    ) -> bool:
        """
        Register a function that can be called by the LLM

        Args:
            name: Function name
            description: Function description
            handler: Function handler
            parameters: List of function parameters
            return_type: Type of return value
            return_description: Description of return value
            examples: Example usages with inputs and outputs
            category: Function category for organization

        Returns:
            bool: True if successful, False otherwise
        """
        if name in self.functions:
            logger.warning(f"Function {name} already registered, overwriting")

        # Create function object
        function = LLMFunction(
            name=name,
            description=description,
            parameters=parameters or [],
            return_type=return_type,
            return_description=return_description,
            examples=examples or [],
            handler=handler,
            category=category,
        )

        # Add to functions dictionary
        self.functions[name] = function

        # Add to categories dictionary
        if category not in self.categories:
            self.categories[category] = []

        if name not in self.categories[category]:
            self.categories[category].append(name)

        logger.info(f"Registered LLM function: {name} (category: {category})")
        return True

    def unregister_function(self, name: str) -> bool:
        """
        Unregister a function

        Args:
            name: Function name

        Returns:
            bool: True if successful, False otherwise
        """
        if name not in self.functions:
            logger.warning(f"Function {name} not found")
            return False

        # Get category
        category = self.functions[name].category

        # Remove from functions dictionary
        del self.functions[name]

        # Remove from categories dictionary
        if category in self.categories and name in self.categories[category]:
            self.categories[category].remove(name)

        logger.info(f"Unregistered LLM function: {name}")
        return True

    def process_input(self, input_data: Union[str, Dict, LLMInput]) -> LLMOutput:
        """
        Process input from the LLM and route to appropriate handler

        Args:
            input_data: Input from LLM (string, dict, or LLMInput object)

        Returns:
            LLMOutput: Structured output response
        """
        try:
            # Parse input if needed
            llm_input = self._parse_input(input_data)

            logger.info(
                f"Processing LLM input: {llm_input.type.value} - {llm_input.action}"
            )

            # Route based on input type
            if llm_input.type == InputType.ACTION:
                return self._handle_action(llm_input)
            elif llm_input.type == InputType.QUERY:
                return self._handle_query(llm_input)
            elif llm_input.type == InputType.RESPONSE:
                return self._handle_response(llm_input)
            elif llm_input.type == InputType.THINKING:
                return self._handle_thinking(llm_input)
            elif llm_input.type == InputType.DELEGATED:
                return self._handle_delegated(llm_input)
            elif llm_input.type == InputType.STRATEGY:
                return self._handle_strategy(llm_input)
            else:
                return LLMOutput(
                    type=OutputType.ERROR,
                    status="error",
                    error=f"Unknown input type: {llm_input.type}",
                    reference_input_id=llm_input.id,
                )

        except Exception as e:
            logger.error(f"Error processing LLM input: {str(e)}")
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Error processing input: {str(e)}",
            )

    def _parse_input(self, input_data: Union[str, Dict, LLMInput]) -> LLMInput:
        """
        Parse input from LLM into structured LLMInput

        Args:
            input_data: Input from LLM (string, dict, or LLMInput object)

        Returns:
            LLMInput: Structured input object
        """
        # If already an LLMInput, return as is
        if isinstance(input_data, LLMInput):
            return input_data

        # If string, try to parse as JSON
        if isinstance(input_data, str):
            try:
                input_data = json.loads(input_data)
            except json.JSONDecodeError:
                # If not valid JSON, assume it's a direct action/query
                # Use regex to extract potential function calls
                action_match = re.match(r"(\w+)\((.*)\)", input_data.strip())

                if action_match:
                    action_name = action_match.group(1)
                    param_str = action_match.group(2)

                    # Parse parameters
                    params = {}
                    if param_str:
                        param_parts = param_str.split(",")
                        for part in param_parts:
                            if "=" in part:
                                key, value = part.split("=", 1)
                                params[key.strip()] = self._parse_param_value(
                                    value.strip()
                                )

                    return LLMInput(
                        type=InputType.ACTION, action=action_name, parameters=params
                    )
                else:
                    # If not a function call, treat as a response to the user
                    return LLMInput(type=InputType.RESPONSE, text=input_data)

        # If dictionary, convert to LLMInput
        if isinstance(input_data, dict):
            # Extract fields
            input_type = input_data.get("type", "action")

            # Convert string type to enum
            try:
                if isinstance(input_type, str):
                    input_type = InputType(input_type)
                elif isinstance(input_type, InputType):
                    pass
                else:
                    input_type = InputType.ACTION
            except (ValueError, KeyError):
                input_type = InputType.ACTION

            # Create LLMInput
            return LLMInput(
                type=input_type,
                action=input_data.get("action"),
                parameters=input_data.get("parameters", {}),
                thinking=input_data.get("thinking"),
                text=input_data.get("text"),
                context=input_data.get("context", {}),
                id=input_data.get("id", f"input_{int(time.time()*1000)}"),
                timestamp=input_data.get("timestamp", time.time()),
            )

        # If unknown type, return error
        raise ValueError(f"Unknown input type: {type(input_data)}")

    def _parse_param_value(self, value_str: str) -> Any:
        """
        Parse parameter value from string

        Args:
            value_str: String representation of parameter value

        Returns:
            Parsed value
        """
        value_str = value_str.strip()

        # Check for boolean
        if value_str.lower() == "true":
            return True
        elif value_str.lower() == "false":
            return False

        # Check for number
        try:
            if "." in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass

        # Check for string (with or without quotes)
        if (value_str.startswith('"') and value_str.endswith('"')) or (
            value_str.startswith("'") and value_str.endswith("'")
        ):
            return value_str[1:-1]

        # Default to returning as is
        return value_str

    def _handle_action(self, llm_input: LLMInput) -> LLMOutput:
        """
        Handle an action input

        Args:
            llm_input: Structured input

        Returns:
            LLMOutput: Structured output response
        """
        action = llm_input.action

        if not action:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error="No action specified",
                reference_input_id=llm_input.id,
            )

        # Check if function exists
        if action not in self.functions:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Unknown action: {action}",
                reference_input_id=llm_input.id,
            )

        # Get function
        function = self.functions[action]

        # Validate parameters
        validation_result = self._validate_parameters(function, llm_input.parameters)

        if validation_result[0] is False:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Parameter validation failed: {validation_result[1]}",
                reference_input_id=llm_input.id,
            )

        # Execute function
        try:
            # Get validated parameters
            validated_params = validation_result[1]

            # Call handler
            result = function.handler(**validated_params)

            # Return result
            return LLMOutput(
                type=OutputType.RESULT,
                status="success",
                data=result,
                reference_input_id=llm_input.id,
            )

        except Exception as e:
            logger.error(f"Error executing action {action}: {str(e)}")
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Error executing action: {str(e)}",
                reference_input_id=llm_input.id,
            )

    def _validate_parameters(
        self, function: LLMFunction, params: Dict[str, Any]
    ) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """
        Validate parameters against function definition

        Args:
            function: Function definition
            params: Parameters to validate

        Returns:
            Tuple of (success, validated_params) or (failure, error_message)
        """
        validated_params = {}

        # Check for required parameters
        for param in function.parameters:
            if param.required and param.name not in params:
                return False, f"Missing required parameter: {param.name}"

        # Validate and convert each parameter
        for param in function.parameters:
            # Skip if not provided and not required
            if param.name not in params and not param.required:
                # Use default if specified
                if param.default is not None:
                    validated_params[param.name] = param.default
                continue

            # Get value
            if param.name in params:
                value = params[param.name]
            else:
                # This shouldn't happen due to the check above, but just in case
                return False, f"Missing required parameter: {param.name}"

            # Validate type
            if param.type == "string":
                if not isinstance(value, str):
                    try:
                        value = str(value)
                    except:
                        return False, f"Parameter {param.name} must be a string"
            elif param.type == "number":
                if not isinstance(value, (int, float)):
                    try:
                        value = float(value)
                    except:
                        return False, f"Parameter {param.name} must be a number"
            elif param.type == "integer":
                if not isinstance(value, int):
                    try:
                        value = int(value)
                    except:
                        return False, f"Parameter {param.name} must be an integer"
            elif param.type == "boolean":
                if not isinstance(value, bool):
                    if isinstance(value, str):
                        value = value.lower() in ("true", "yes", "1")
                    else:
                        try:
                            value = bool(value)
                        except:
                            return False, f"Parameter {param.name} must be a boolean"
            elif param.type == "array":
                if not isinstance(value, list):
                    try:
                        value = list(value)
                    except:
                        return False, f"Parameter {param.name} must be an array"
            elif param.type == "object":
                if not isinstance(value, dict):
                    return False, f"Parameter {param.name} must be an object"

            # Validate enum
            if param.enum is not None and value not in param.enum:
                return (
                    False,
                    f"Parameter {param.name} must be one of: {', '.join(param.enum)}",
                )

            # Validate min/max
            if param.min_value is not None and value < param.min_value:
                return (
                    False,
                    f"Parameter {param.name} must be at least {param.min_value}",
                )

            if param.max_value is not None and value > param.max_value:
                return (
                    False,
                    f"Parameter {param.name} must be at most {param.max_value}",
                )

            # Add to validated parameters
            validated_params[param.name] = value

        return True, validated_params

    def _handle_query(self, llm_input: LLMInput) -> LLMOutput:
        """
        Handle a query input

        Args:
            llm_input: Structured input

        Returns:
            LLMOutput: Structured output response
        """
        # For queries, the action is the thing being queried
        query = llm_input.action

        if not query:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error="No query specified",
                reference_input_id=llm_input.id,
            )

        # Handle different query types
        if query == "system_status":
            # Get system status
            status_data = self.core.get_status()
            return LLMOutput(
                type=OutputType.DATA, data=status_data, reference_input_id=llm_input.id
            )

        elif query == "system_state":
            # Get current state
            state_info = self.core.state_machine.get_state_info()
            return LLMOutput(
                type=OutputType.DATA, data=state_info, reference_input_id=llm_input.id
            )

        elif query == "available_commands":
            # Get available commands
            commands = {
                name: self._function_to_dict(func)
                for name, func in self.functions.items()
            }
            return LLMOutput(
                type=OutputType.DATA, data=commands, reference_input_id=llm_input.id
            )

        elif query == "available_components":
            # Get available components
            components = list(self.core.components.keys())
            return LLMOutput(
                type=OutputType.DATA, data=components, reference_input_id=llm_input.id
            )

        elif query == "command_categories":
            # Get command categories
            return LLMOutput(
                type=OutputType.DATA,
                data=self.categories,
                reference_input_id=llm_input.id,
            )

        elif query.startswith("component_status:"):
            # Get specific component status
            component_name = query.split(":", 1)[1].strip()

            if component_name in self.core.components:
                component = self.core.components[component_name]
                if hasattr(component, "get_status"):
                    status = component.get_status()
                    return LLMOutput(
                        type=OutputType.DATA,
                        data=status,
                        reference_input_id=llm_input.id,
                    )
                else:
                    return LLMOutput(
                        type=OutputType.ERROR,
                        status="error",
                        error=f"Component {component_name} does not support status queries",
                        reference_input_id=llm_input.id,
                    )
            else:
                return LLMOutput(
                    type=OutputType.ERROR,
                    status="error",
                    error=f"Component {component_name} not found",
                    reference_input_id=llm_input.id,
                )
        else:
            # Try to handle as command
            llm_input.type = InputType.ACTION
            return self._handle_action(llm_input)

    def _handle_response(self, llm_input: LLMInput) -> LLMOutput:
        """
        Handle a response input (text to send to the user)

        Args:
            llm_input: Structured input

        Returns:
            LLMOutput: Structured output response
        """
        text = llm_input.text

        if not text:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error="No response text provided",
                reference_input_id=llm_input.id,
            )

        # Determine if we should use voice (default to True)
        use_voice = llm_input.parameters.get("use_voice", True)

        # Get emotion if specified
        emotion = llm_input.parameters.get("emotion", "neutral")

        # Send response to user
        try:
            # Transition to responding state
            self.core.state_machine.transition_to(
                self.core.state_machine.SabrinaState.RESPONDING,
                {"response": text, "use_voice": use_voice, "emotion": emotion},
            )

            # If using voice, transition to speaking state
            if use_voice and "voice" in self.core.components:
                # Transition to speaking state
                self.core.state_machine.transition_to(
                    self.core.state_machine.SabrinaState.SPEAKING
                )

                # Create voice event
                from .enhanced_event_system import Event, EventType, EventPriority

                voice_event = Event(
                    event_type=EventType.SPEECH_STARTED,
                    data={"text": text, "emotion": emotion},
                    priority=EventPriority.NORMAL,
                    source="llm_framework",
                )

                # Post to event bus for voice service to handle
                self.core.event_bus.post_event(voice_event)

                # Return success response
                return LLMOutput(
                    type=OutputType.STATUS,
                    status="success",
                    data={"text": text, "voice": True, "emotion": emotion},
                    reference_input_id=llm_input.id,
                )
            else:
                # Just return to ready state
                self.core.state_machine.transition_to(
                    self.core.state_machine.SabrinaState.READY
                )

                # Return success response
                return LLMOutput(
                    type=OutputType.STATUS,
                    status="success",
                    data={"text": text, "voice": False},
                    reference_input_id=llm_input.id,
                )

        except Exception as e:
            logger.error(f"Error sending response: {str(e)}")
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Error sending response: {str(e)}",
                reference_input_id=llm_input.id,
            )

    def _handle_thinking(self, llm_input: LLMInput) -> LLMOutput:
        """
        Handle a thinking input (internal reasoning, not shown to user)

        Args:
            llm_input: Structured input

        Returns:
            LLMOutput: Structured output response
        """
        thinking = llm_input.thinking

        if not thinking:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error="No thinking content provided",
                reference_input_id=llm_input.id,
            )

        # Log thinking for debugging purposes
        logger.debug(
            f"LLM Thinking: {thinking[:100]}{'...' if len(thinking) > 100 else ''}"
        )

        # Store thinking in context if needed
        context_key = llm_input.parameters.get("context_key")
        if context_key:
            # Store in core context
            if not hasattr(self.core, "llm_context"):
                self.core.llm_context = {}

            self.core.llm_context[context_key] = thinking

        # Return acknowledgment
        return LLMOutput(
            type=OutputType.STATUS,
            status="success",
            data={"thinking_recorded": True, "length": len(thinking)},
            reference_input_id=llm_input.id,
        )

    def _handle_delegated(self, llm_input: LLMInput) -> LLMOutput:
        """
        Handle a delegated task (task assigned to a specific component)

        Args:
            llm_input: Structured input

        Returns:
            LLMOutput: Structured output response
        """
        component = llm_input.parameters.get("component")
        action = llm_input.action

        if not component:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error="No component specified for delegated task",
                reference_input_id=llm_input.id,
            )

        if not action:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error="No action specified for delegated task",
                reference_input_id=llm_input.id,
            )

        # Check if component exists
        if component not in self.core.components:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Component {component} not found",
                reference_input_id=llm_input.id,
            )

        # Get component
        component_instance = self.core.components[component]

        # Check if component has the requested action
        if not hasattr(component_instance, action):
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Action {action} not found in component {component}",
                reference_input_id=llm_input.id,
            )

        # Get action method
        action_method = getattr(component_instance, action)

        # Check if it's callable
        if not callable(action_method):
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"{action} is not a callable method in component {component}",
                reference_input_id=llm_input.id,
            )

        # Extract parameters
        params = llm_input.parameters.get("params", {})

        # Execute action
        try:
            result = action_method(**params)

            # Return result
            return LLMOutput(
                type=OutputType.RESULT,
                status="success",
                data=result,
                reference_input_id=llm_input.id,
            )

        except Exception as e:
            logger.error(
                f"Error executing delegated action {action} on {component}: {str(e)}"
            )
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Error executing delegated action: {str(e)}",
                reference_input_id=llm_input.id,
            )

    def _handle_strategy(self, llm_input: LLMInput) -> LLMOutput:
        """
        Handle a strategy input (system-level approach or plan)

        Args:
            llm_input: Structured input

        Returns:
            LLMOutput: Structured output response
        """
        strategy = llm_input.thinking

        if not strategy:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error="No strategy content provided",
                reference_input_id=llm_input.id,
            )

        # Log strategy for debugging purposes
        logger.info(
            f"LLM Strategy: {strategy[:100]}{'...' if len(strategy) > 100 else ''}"
        )

        # Store strategy in core context
        if not hasattr(self.core, "llm_strategies"):
            self.core.llm_strategies = []

        self.core.llm_strategies.append(
            {"strategy": strategy, "timestamp": time.time(), "id": llm_input.id}
        )

        # Return acknowledgment
        return LLMOutput(
            type=OutputType.STATUS,
            status="success",
            data={"strategy_recorded": True},
            reference_input_id=llm_input.id,
        )

    def _function_to_dict(self, function: LLMFunction) -> Dict[str, Any]:
        """
        Convert a function to a dictionary format for documentation

        Args:
            function: Function to convert

        Returns:
            Dictionary representation of the function
        """
        return {
            "name": function.name,
            "description": function.description,
            "parameters": [asdict(param) for param in function.parameters],
            "return_type": function.return_type,
            "return_description": function.return_description,
            "examples": function.examples,
            "category": function.category,
        }

    # Handler methods for built-in functions
    def _handle_get_system_status(self, component: str = None) -> Dict[str, Any]:
        """
        Get the current status of the Sabrina AI system

        Args:
            component: Specific component to get status for (optional)

        Returns:
            System status information
        """
        if component:
            if component in self.core.components:
                comp = self.core.components[component]
                if hasattr(comp, "get_status"):
                    return comp.get_status()
                else:
                    return {
                        "error": f"Component {component} does not support status queries"
                    }
            else:
                return {"error": f"Component {component} not found"}
        else:
            return self.core.get_status()

    def _handle_get_current_state(self) -> Dict[str, Any]:
        """
        Get the current state of the Sabrina AI system

        Returns:
            Current state information
        """
        return self.core.state_machine.get_state_info()

    def _handle_respond(
        self, text: str, use_voice: bool = True, emotion: str = "neutral"
    ) -> Dict[str, Any]:
        """
        Respond to the user with text and/or voice

        Args:
            text: Text to respond with
            use_voice: Whether to speak the response
            emotion: Emotion to convey in voice response

        Returns:
            Response status
        """
        # Create an LLMInput for the response
        response_input = LLMInput(
            type=InputType.RESPONSE,
            text=text,
            parameters={"use_voice": use_voice, "emotion": emotion},
        )

        # Process the response input
        result = self._handle_response(response_input)

        # Return the result data
        return (
            result.data
            if result.data
            else {"text": text, "voice": use_voice, "emotion": emotion}
        )


class LLMSchema:
    """
    Generate OpenAI function calling schema from Sabrina's function registry
    """

    @staticmethod
    def generate_function_schemas(
        functions: Dict[str, LLMFunction]
    ) -> List[Dict[str, Any]]:
        """
        Generate OpenAI-compatible function schemas

        Args:
            functions: Dictionary of LLMFunction objects

        Returns:
            List of function schema dictionaries
        """
        schemas = []

        for name, function in functions.items():
            schema = {
                "name": name,
                "description": function.description,
                "parameters": {"type": "object", "properties": {}, "required": []},
            }

            # Add parameters
            for param in function.parameters:
                # Add to properties
                param_schema = {
                    "type": param.type if param.type != "integer" else "number",
                    "description": param.description,
                }

                # Add enum if specified
                if param.enum is not None:
                    param_schema["enum"] = param.enum

                # Add min/max if specified
                if param.min_value is not None:
                    param_schema["minimum"] = param.min_value

                if param.max_value is not None:
                    param_schema["maximum"] = param.max_value

                # Add format if specified
                if param.format is not None:
                    param_schema["format"] = param.format

                # Add to properties
                schema["parameters"]["properties"][param.name] = param_schema

                # Add to required if required
                if param.required:
                    schema["parameters"]["required"].append(param.name)

            # Add to schemas
            schemas.append(schema)

        return schemas

    @staticmethod
    def generate_tool_schemas(
        functions: Dict[str, LLMFunction]
    ) -> List[Dict[str, Any]]:
        """
        Generate OpenAI-compatible tool schemas

        Args:
            functions: Dictionary of LLMFunction objects

        Returns:
            List of tool schema dictionaries
        """
        # This is similar to function schemas but in the tools format
        function_schemas = LLMSchema.generate_function_schemas(functions)

        tool_schemas = []
        for func_schema in function_schemas:
            tool_schemas.append({"type": "function", "function": func_schema})

        return tool_schemas

    @staticmethod
    def process_tool_call(
        tool_call: Dict[str, Any], handler: LLMInputHandler
    ) -> LLMOutput:
        """
        Process a tool call from an LLM

        Args:
            tool_call: Tool call from LLM response
            handler: LLMInputHandler instance

        Returns:
            LLMOutput: Result of the tool call
        """
        try:
            # Extract function name and arguments
            function_name = tool_call.get("function", {}).get("name")
            arguments_str = tool_call.get("function", {}).get("arguments", "{}")

            # Parse arguments
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                return LLMOutput(
                    type=OutputType.ERROR,
                    status="error",
                    error=f"Invalid JSON in arguments: {arguments_str}",
                )

            # Create LLMInput
            llm_input = LLMInput(
                type=InputType.ACTION, action=function_name, parameters=arguments
            )

            # Process input
            return handler.process_input(llm_input)

        except Exception as e:
            return LLMOutput(
                type=OutputType.ERROR,
                status="error",
                error=f"Error processing tool call: {str(e)}",
            )
