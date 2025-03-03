#!/usr/bin/env python3
"""
LLM Integration Test for Sabrina AI
==================================
This script demonstrates the integration of an LLM with Sabrina's core system.
It shows how the LLM input framework processes function calls and interacts with
various Sabrina components through the core infrastructure.
"""

import sys
import logging
import time
import threading
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("llm_integration_test")

# Ensure the project root is in the Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent  # Adjust if needed
sys.path.insert(0, str(project_root))


# Mock LLM for testing
class MockLLM:
    """Mock LLM for testing input framework integration"""

    def __init__(self, llm_input_handler):
        """Initialize the mock LLM"""
        self.input_handler = llm_input_handler
        self.conversation_history = []

    def generate_response(self, user_input):
        """
        Generate a response using the input handler

        Args:
            user_input: User input text

        Returns:
            Response text and optionally function calls
        """
        # Add user input to conversation history
        self.conversation_history.append({"role": "user", "content": user_input})

        # Parse input for commands
        if user_input.startswith("/"):
            # This is a command, parse it
            return self._handle_command(user_input)

        # For demonstration purposes, use some basic templates
        if "hello" in user_input.lower() or "hi" in user_input.lower():
            response = "Hello! I'm Sabrina AI. How can I help you today?"
        elif "status" in user_input.lower() or "how are you" in user_input.lower():
            # Create a function call
            from core.llm_input_framework import LLMInput, InputType

            system_status_input = LLMInput(
                type=InputType.ACTION, action="get_system_status"
            )

            # Process the function call
            result = self.input_handler.process_input(system_status_input)

            response = "I'm running smoothly! Here's my current status:\n\n"
            response += f"System Status: {result.data.get('status', 'Unknown')}\n"
            response += f"Uptime: {result.data.get('uptime', 0):.1f} seconds\n"

            if "components" in result.data:
                response += "\nActive components:\n"
                for component, status in result.data["components"].items():
                    component_status = status.get("status", "Unknown")
                    response += f"- {component}: {component_status}\n"

        elif "help" in user_input.lower():
            response = self._generate_help_text()

        elif any(
            kw in user_input.lower() for kw in ["screen", "see", "look", "capture"]
        ):
            # Create a function call to capture screen
            from core.llm_input_framework import LLMInput, InputType

            capture_input = LLMInput(
                type=InputType.DELEGATED,
                action="capture_screen",
                parameters={"component": "vision"},
            )

            # Process the function call
            result = self.input_handler.process_input(capture_input)

            if result.status == "success" and result.data:
                response = "I've captured the screen. Here's what I see:\n\n"

                # Now try to extract text
                ocr_input = LLMInput(
                    type=InputType.DELEGATED,
                    action="extract_text",
                    parameters={
                        "component": "vision",
                        "params": {"image_path": result.data},
                    },
                )

                ocr_result = self.input_handler.process_input(ocr_input)

                if ocr_result.status == "success" and ocr_result.data:
                    response += f"Text found on screen: {ocr_result.data[:300]}"
                    if len(ocr_result.data) > 300:
                        response += "...(truncated)..."
                else:
                    response += "I couldn't extract any text from the screen."
            else:
                response += "I tried to capture the screen, but encountered an issue."

        elif any(kw in user_input.lower() for kw in ["say", "speak", "tell"]):
            # Extract what to say
            text_to_say = user_input.lower()
            for prefix in ["say", "speak", "tell me", "tell"]:
                if prefix in text_to_say:
                    text_to_say = text_to_say.split(prefix, 1)[1].strip()
                    break

            # Create a function call to speak
            from core.llm_input_framework import LLMInput, InputType

            speak_input = LLMInput(
                type=InputType.RESPONSE,
                text=text_to_say,
                parameters={"use_voice": True, "emotion": "neutral"},
            )

            # Process the function call
            result = self.input_handler.process_input(speak_input)

            if result.status == "success":
                response = f'I said: "{text_to_say}"'
            else:
                response = "I tried to speak but encountered an issue."

        elif any(kw in user_input.lower() for kw in ["click", "button"]):
            # Extract coordinates or button description
            # For test purposes, use fixed coordinates
            x, y = 500, 400

            # Create a function call to click
            from core.llm_input_framework import LLMInput, InputType

            click_input = LLMInput(
                type=InputType.DELEGATED,
                action="click_at",
                parameters={
                    "component": "automation",
                    "params": {"x": x, "y": y},
                },
            )

            # Process the function call
            result = self.input_handler.process_input(click_input)

            if result.status == "success":
                response = f"I clicked at coordinates ({x}, {y})."
            else:
                response = "I tried to click but encountered an issue."

        elif "type" in user_input.lower():
            # Extract text to type
            text_to_type = "Hello from Sabrina AI!"
            if "type " in user_input.lower():
                text_to_type = user_input.lower().split("type ", 1)[1].strip()

            # Create a function call to type
            from core.llm_input_framework import LLMInput, InputType

            type_input = LLMInput(
                type=InputType.DELEGATED,
                action="type_text",
                parameters={
                    "component": "automation",
                    "params": {"text": text_to_type},
                },
            )

            # Process the function call
            result = self.input_handler.process_input(type_input)

            if result.status == "success":
                response = f'I typed: "{text_to_type}"'
            else:
                response = "I tried to type but encountered an issue."

        else:
            # Default response with thinking example
            from core.llm_input_framework import LLMInput, InputType

            # First, log some internal thinking
            thinking_input = LLMInput(
                type=InputType.THINKING,
                thinking=f"User request: '{user_input}'. This doesn't match any of my specific patterns. I'll provide a general response and offer more help.",
                parameters={"context_key": "last_thinking"},
            )

            # Process the thinking
            self.input_handler.process_input(thinking_input)

            # Provide a general response
            response = (
                "I'm not sure how to help with that specific request. "
                "You can ask me to capture the screen, speak text, click somewhere, "
                "type text, or check my status. What would you like me to do?"
            )

        # Add assistant response to conversation history
        self.conversation_history.append({"role": "assistant", "content": response})

        return response

    def _handle_command(self, command):
        """Handle special / commands"""
        cmd = command[1:].lower().strip()

        if cmd == "help":
            return self._generate_help_text()
        elif cmd == "status":
            # Create a function call to get system status
            from core.llm_input_framework import LLMInput, InputType

            status_input = LLMInput(type=InputType.ACTION, action="get_system_status")

            # Process the function call
            result = self.input_handler.process_input(status_input)

            response = "# Sabrina AI System Status\n\n"

            if result.status == "success" and result.data:
                response += f"**System State:** {result.data.get('state', 'Unknown')}\n"
                response += (
                    f"**Uptime:** {result.data.get('uptime', 0):.1f} seconds\n\n"
                )

                # Component statuses
                if "components" in result.data:
                    response += "## Active Components\n\n"
                    for component, status in result.data["components"].items():
                        component_status = status.get("status", "Unknown")
                        response += f"- **{component}:** {component_status}\n"

                # Event stats
                if "event_bus" in result.data:
                    event_stats = result.data["event_bus"]
                    response += "\n## Event System\n\n"
                    response += (
                        f"- Processed Events: {event_stats.get('processed_count', 0)}\n"
                    )
                    response += f"- Queue Size: {event_stats.get('queue_size', 0)}\n"
                    response += (
                        f"- Handler Count: {event_stats.get('handler_count', 0)}\n"
                    )
            else:
                response += "Error retrieving system status."

            return response
        elif cmd == "components":
            # Get available components
            from core.llm_input_framework import LLMInput, InputType

            query_input = LLMInput(type=InputType.QUERY, action="available_components")

            # Process the query
            result = self.input_handler.process_input(query_input)

            response = "# Available Components\n\n"

            if result.status == "success" and result.data:
                for component in result.data:
                    response += f"- {component}\n"
            else:
                response += "Error retrieving component list."

            return response
        elif cmd == "commands":
            # Get available commands
            from core.llm_input_framework import LLMInput, InputType

            query_input = LLMInput(type=InputType.QUERY, action="available_commands")

            # Process the query
            result = self.input_handler.process_input(query_input)

            response = "# Available Commands\n\n"

            if result.status == "success" and result.data:
                for command, details in result.data.items():
                    response += f"## {command}\n"
                    response += f"{details.get('description', '')}\n\n"

                    # Parameters
                    if "parameters" in details and details["parameters"]:
                        response += "**Parameters:**\n"
                        for param in details["parameters"]:
                            required = " (required)" if param.get("required") else ""
                            response += f"- `{param.get('name')}`{required}: {param.get('description')}\n"

                    response += "\n"
            else:
                response += "Error retrieving command list."

            return response
        elif cmd.startswith("state"):
            # Get current state
            from core.llm_input_framework import LLMInput, InputType

            state_input = LLMInput(type=InputType.QUERY, action="system_state")

            # Process the query
            result = self.input_handler.process_input(state_input)

            response = "# Current System State\n\n"

            if result.status == "success" and result.data:
                state_info = result.data
                response += (
                    f"**Current State:** {state_info.get('current_state', 'Unknown')}\n"
                )
                response += (
                    f"**Previous State:** {state_info.get('previous_state', 'None')}\n"
                )
                response += (
                    f"**Duration:** {state_info.get('duration', 0):.1f} seconds\n"
                )
                response += f"**Description:** {state_info.get('description', '')}\n"

                # Allowed transitions
                if "allowed_transitions" in state_info:
                    response += "\n**Allowed Transitions:**\n"
                    for transition in state_info["allowed_transitions"]:
                        response += f"- {transition}\n"
            else:
                response += "Error retrieving system state."

            return response
        else:
            return f"Unknown command: '{cmd}'. Type /help for a list of commands."

    def _generate_help_text(self):
        """Generate help text for Sabrina commands"""
        help_text = """
# Sabrina AI Help

You can interact with me using natural language or commands:

## Commands
- `/help` - Show this help message
- `/status` - Show system status
- `/components` - List available components
- `/commands` - List available commands
- `/state` - Show current system state

## Natural Language Examples
- "Hello" - Basic greeting
- "How are you?" - Check system status
- "Capture the screen" - Take a screenshot
- "Say hello world" - Speak text
- "Click at the center" - Automate mouse click
- "Type hello" - Automate keyboard input

I'm designed to assist with voice interaction, screen awareness, automation,
and smart home control. What would you like me to do?
"""
        return help_text


def simulate_conversation(llm, core):
    """Simulate a conversation with the LLM"""
    print("\n" + "=" * 60)
    print(" Sabrina AI - LLM Integration Test ".center(60))
    print("=" * 60 + "\n")

    # Test conversation flow
    test_inputs = [
        "Hello, Sabrina!",
        "How are you doing?",
        "Can you capture my screen?",
        "Say hello world!",
        "Can you click on the screen?",
        "Type a welcome message",
        "/status",
        "/components",
        "/state",
        "Thanks for your help!",
    ]

    for user_input in test_inputs:
        print(f"\n👤 User: {user_input}")

        # Get LLM response
        response = llm.generate_response(user_input)

        # Simulate processing time
        time.sleep(0.5)

        print(f"\n🤖 Sabrina: {response}\n")
        print("-" * 60)

        # Pause between interactions
        time.sleep(1.5)

    print("\n" + "=" * 60)
    print(" Integration Test Completed ".center(60))
    print("=" * 60 + "\n")


def run_test():
    """Run the LLM integration test"""
    try:
        # Import core components
        from core.core import SabrinaCore
        from core.llm_input_framework import LLMInputHandler

        # Create core system
        print("Initializing Sabrina AI Core System...")
        core = SabrinaCore("config/settings.yaml")

        # Initialize core system
        core.initialize_components()

        # Create LLM input handler
        input_handler = LLMInputHandler(core)

        # Create mock LLM
        llm = MockLLM(input_handler)

        # Start a background thread to listen for wake word
        def start_wake_word_listener():
            if "hearing" in core.components:
                hearing = core.components["hearing"]
                if hasattr(hearing, "listen_for_wake_word"):
                    print("Starting wake word listener...")
                    hearing.listen_for_wake_word()

        # Start wake word listener in background
        wake_thread = threading.Thread(target=start_wake_word_listener)
        wake_thread.daemon = True
        wake_thread.start()

        # Simulate a conversation
        simulate_conversation(llm, core)

        # Shutdown core system
        core.shutdown()

        return 0

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Error in LLM integration test: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(run_test())
