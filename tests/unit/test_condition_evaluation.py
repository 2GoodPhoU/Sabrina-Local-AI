#!/usr/bin/env python3
"""
Simplified test for condition evaluation in the state machine
"""

import os
import sys
import unittest
from unittest.mock import MagicMock
import logging
import time

# Import the components to test - directly from the core
from core.state_machine import SabrinaState, StateTransition

# Ensure the project root is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../.."))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_condition_evaluation")


class TestConditionEvaluation(unittest.TestCase):
    """Test case specifically for condition evaluation in StateTransition"""

    def test_state_transition_condition(self):
        """Test that StateTransition.can_transition evaluates conditions correctly"""
        # Create a condition function that tracks its calls
        calls = []

        def condition_func(ctx):
            # Log that the function was called and with what context
            calls.append(ctx.copy() if ctx else {})
            # Return True only if 'flag' is in context and is True
            return ctx and "flag" in ctx and ctx["flag"]

        # Create a transition with this condition
        transition = StateTransition(
            from_state=SabrinaState.READY,
            to_state=SabrinaState.PROCESSING,
            condition=condition_func,
            description="Test condition",
        )

        # Test with empty context - should return False
        context1 = {}
        result1 = transition.can_transition(context1)
        self.assertFalse(result1, "Should be False with empty context")

        # Test with context but no flag - should return False
        context2 = {"other_key": "value"}
        result2 = transition.can_transition(context2)
        self.assertFalse(result2, "Should be False with no flag")

        # Test with context and flag=False - should return False
        context3 = {"flag": False}
        result3 = transition.can_transition(context3)
        self.assertFalse(result3, "Should be False with flag=False")

        # Test with context and flag=True - should return True
        context4 = {"flag": True}
        result4 = transition.can_transition(context4)
        self.assertTrue(result4, "Should be True with flag=True")

        # Verify the function was called with the expected contexts
        self.assertEqual(len(calls), 4, "Condition function should be called 4 times")
        self.assertEqual(calls[0], {}, "First call should have empty context")
        self.assertEqual(
            calls[1], {"other_key": "value"}, "Second call context incorrect"
        )
        self.assertEqual(calls[2], {"flag": False}, "Third call context incorrect")
        self.assertEqual(calls[3], {"flag": True}, "Fourth call context incorrect")

    def test_transition_without_condition(self):
        """Test that transitions without conditions are always allowed"""
        # Create a transition with no condition
        transition = StateTransition(
            from_state=SabrinaState.READY, to_state=SabrinaState.PROCESSING
        )

        # Should return True regardless of context
        self.assertTrue(
            transition.can_transition({}), "Should be True with empty context"
        )
        self.assertTrue(
            transition.can_transition({"any": "value"}),
            "Should be True with any context",
        )
        self.assertTrue(
            transition.can_transition(None), "Should be True with None context"
        )


if __name__ == "__main__":
    unittest.main()
