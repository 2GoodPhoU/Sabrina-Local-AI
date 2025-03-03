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
            response += "System Status: " + result.data.get("status", "Unknown") + "\n"
            response += "Uptime: {result.data.get('uptime', 0):.1f} seconds\n"

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
                response = "I tried to capture the screen, but encountered an issue."

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
