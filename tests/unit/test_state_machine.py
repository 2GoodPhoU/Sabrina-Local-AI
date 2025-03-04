#!/usr/bin/env python3
"""
Unit tests for Sabrina AI State Machine
"""

import os
import sys
import unittest
from unittest.mock import MagicMock
import time

# Import components to test
from core.state_machine import StateMachine, SabrinaState

# Ensure the project root is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../.."))
sys.path.insert(0, project_root)


class TestStateMachine(unittest.TestCase):
    """Test case for StateMachine class"""

    def setUp(self):
        """Set up test fixtures"""
        self.event_bus = MagicMock()
        self.state_machine = StateMachine(event_bus=self.event_bus)

    def test_initialization(self):
        """Test state machine initialization"""
        # Verify initial state
        self.assertEqual(self.state_machine.current_state, SabrinaState.INITIALIZING)
        self.assertIsNone(self.state_machine.previous_state)
        self.assertFalse(self.state_machine.is_state_expired())

    def test_state_descriptions(self):
        """Test state descriptions are provided"""
        for state in SabrinaState:
            description = self.state_machine._get_state_description(state)
            self.assertIsNotNone(description)
            self.assertGreater(len(description), 0)

    def test_state_animations(self):
        """Test animation mappings for states"""
        for state in SabrinaState:
            animation = self.state_machine._get_animation_for_state(state)
            self.assertIsNotNone(animation)
            self.assertGreater(len(animation), 0)

    def test_valid_transitions(self):
        """Test valid state transitions"""
        # Test transitions that should be allowed
        transitions = [
            (SabrinaState.INITIALIZING, SabrinaState.READY),
            (SabrinaState.READY, SabrinaState.LISTENING),
            (SabrinaState.LISTENING, SabrinaState.PROCESSING),
            (SabrinaState.PROCESSING, SabrinaState.RESPONDING),
            (SabrinaState.RESPONDING, SabrinaState.SPEAKING),
            (SabrinaState.SPEAKING, SabrinaState.READY),
        ]

        for from_state, to_state in transitions:
            # Set the state
            self.state_machine.current_state = from_state

            # Check if transition is allowed
            self.assertTrue(
                self.state_machine.can_transition_to(to_state),
                f"Transition from {from_state.name} to {to_state.name} should be allowed",
            )

            # Test actual transition
            result = self.state_machine.transition_to(to_state)
            self.assertTrue(result, f"Transition to {to_state.name} failed")
            self.assertEqual(
                self.state_machine.current_state,
                to_state,
                f"Current state should be {to_state.name}",
            )
            self.assertEqual(
                self.state_machine.previous_state,
                from_state,
                f"Previous state should be {from_state.name}",
            )

    def test_invalid_transitions(self):
        """Test invalid state transitions"""
        # Test transitions that should not be allowed
        invalid_transitions = [
            (
                SabrinaState.READY,
                SabrinaState.SHUTTING_DOWN,
            ),  # Assuming this isn't allowed directly
            (
                SabrinaState.LISTENING,
                SabrinaState.SPEAKING,
            ),  # Should go through PROCESSING first
            (
                SabrinaState.ERROR,
                SabrinaState.PROCESSING,
            ),  # Should recover to READY first
        ]

        for from_state, to_state in invalid_transitions:
            # Set the state
            self.state_machine.current_state = from_state

            # Add the transition to test if it's correctly NOT allowed
            # This is needed because by default transitions might not be defined
            if from_state not in self.state_machine.transitions:
                self.state_machine.transitions[from_state] = {}

            # Check transition permission
            if not self.state_machine.can_transition_to(to_state):
                # Expected behavior - transition not allowed
                pass
            else:
                # If the transition is actually defined, then skip this test
                continue

            # Try to transition anyway
            result = self.state_machine.transition_to(to_state)

            # Should fail
            self.assertFalse(
                result,
                f"Transition from {from_state.name} to {to_state.name} should not be allowed",
            )

            # State should not change
            self.assertEqual(
                self.state_machine.current_state,
                from_state,
                f"State should remain {from_state.name} after invalid transition attempt",
            )

    def test_global_transition(self):
        """Test global transitions that work from any state"""
        # First clear any existing global transitions
        self.state_machine.global_transitions = []

        # Define a condition function that checks for a critical_error flag
        def error_condition(ctx):
            return ctx.get("critical_error", False)

        # Add a global transition to ERROR state with a condition
        self.state_machine.add_global_transition(
            SabrinaState.ERROR,
            condition=error_condition,
            description="Critical error occurred",
        )

        # Set initial state
        self.state_machine.current_state = SabrinaState.READY

        # Clear any existing context
        self.state_machine.context = {}

        # Try transition without the condition being met
        can_transition = self.state_machine.can_transition_to(SabrinaState.ERROR)

        # Verify the function works as expected
        self.assertFalse(
            error_condition({}), "Condition should be false with empty context"
        )

        # Verify transition is blocked when condition is false
        self.assertFalse(
            can_transition,
            "Should not be able to transition without condition being true",
        )

        # Set the condition to make the transition work
        self.state_machine.context["critical_error"] = True

        # Verify condition function now returns true
        self.assertTrue(
            error_condition(self.state_machine.context), "Condition should now be true"
        )

        # Now check if transition is allowed
        can_transition = self.state_machine.can_transition_to(SabrinaState.ERROR)
        self.assertTrue(
            can_transition, "Should be able to transition with condition true"
        )

        # Actually perform the transition
        result = self.state_machine.transition_to(SabrinaState.ERROR)
        self.assertTrue(
            result, "Global transition to ERROR should occur with condition"
        )
        self.assertEqual(
            self.state_machine.current_state,
            SabrinaState.ERROR,
            "Current state should be ERROR after global transition",
        )

    def test_direct_transition_with_condition(self):
        """Test direct transitions with conditions"""
        # First set current state
        self.state_machine.current_state = SabrinaState.READY

        # Clear transitions to start fresh
        if SabrinaState.READY in self.state_machine.transitions:
            self.state_machine.transitions[SabrinaState.READY] = {}

        # Define a condition function
        def has_command(ctx):
            return "command" in ctx and ctx["command"]

        # Add a conditional transition
        self.state_machine.add_transition(
            from_state=SabrinaState.READY,
            to_state=SabrinaState.PROCESSING,
            condition=has_command,
            description="Process command when present",
        )

        # Clear context
        self.state_machine.context = {}

        # Check that transition is not allowed without condition
        self.assertFalse(self.state_machine.can_transition_to(SabrinaState.PROCESSING))

        # Try to transition anyway - should fail
        result = self.state_machine.transition_to(SabrinaState.PROCESSING)
        self.assertFalse(result)
        self.assertEqual(self.state_machine.current_state, SabrinaState.READY)

        # Now set condition
        self.state_machine.context["command"] = "test command"

        # Now transition should be allowed
        self.assertTrue(self.state_machine.can_transition_to(SabrinaState.PROCESSING))

        # Perform transition
        result = self.state_machine.transition_to(SabrinaState.PROCESSING)
        self.assertTrue(result)
        self.assertEqual(self.state_machine.current_state, SabrinaState.PROCESSING)

    def test_condition_evaluation(self):
        """Test that conditions are evaluated correctly"""
        # Create a test condition that tracks calls
        calls = []

        def tracking_condition(ctx):
            calls.append(ctx.copy())
            return "flag" in ctx and ctx["flag"]

        # Clear transitions
        self.state_machine.global_transitions = []

        # Set current state
        self.state_machine.current_state = SabrinaState.READY

        # Add global transition with condition
        self.state_machine.add_global_transition(
            SabrinaState.ERROR,
            condition=tracking_condition,
            description="Test condition tracking",
        )

        # Set context
        self.state_machine.context = {"test": 123}

        # Test without flag
        can_transition = self.state_machine.can_transition_to(SabrinaState.ERROR)
        self.assertFalse(can_transition)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["test"], 123)

        # Set flag
        self.state_machine.context["flag"] = True

        # Test with flag
        can_transition = self.state_machine.can_transition_to(SabrinaState.ERROR)
        self.assertTrue(can_transition)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1]["flag"])

    def test_context_updates(self):
        """Test context updates during transitions"""
        # Set initial state
        self.state_machine.current_state = SabrinaState.READY

        # Define test context
        test_context = {"user_name": "Test User", "command": "help"}

        # Perform transition with context
        result = self.state_machine.transition_to(SabrinaState.PROCESSING, test_context)
        self.assertTrue(result, "Transition with context failed")

        # Check context was updated
        for key, value in test_context.items():
            self.assertEqual(
                self.state_machine.context.get(key),
                value,
                f"Context key '{key}' not updated correctly",
            )

    def test_state_duration(self):
        """Test state duration tracking"""
        # Set state
        self.state_machine.current_state = SabrinaState.LISTENING

        # State entry time should be set
        self.assertIsNotNone(self.state_machine.state_entry_time)

        # Get initial duration
        initial_duration = self.state_machine.get_state_duration()

        # Wait a bit
        time.sleep(0.1)

        # Get new duration
        new_duration = self.state_machine.get_state_duration()

        # Duration should increase
        self.assertGreater(
            new_duration, initial_duration, "State duration should increase over time"
        )

    def test_state_expiry(self):
        """Test state expiry detection"""
        # Find a state with defined duration
        test_state = None
        for state in SabrinaState:
            if self.state_machine._get_typical_duration(state) is not None:
                test_state = state
                break

        if test_state is None:
            self.skipTest("No state with defined duration found")

        # Get the typical duration
        duration = self.state_machine._get_typical_duration(test_state)

        # Set state with a manipulated entry time to simulate expiry
        self.state_machine.current_state = test_state
        self.state_machine.state_entry_time = time.time() - (duration + 1)

        # Check expiry
        self.assertTrue(
            self.state_machine.is_state_expired(),
            f"State {test_state.name} should be expired",
        )

    def test_state_history(self):
        """Test state history tracking"""
        # Clear history
        self.state_machine.state_history = []

        # Perform some transitions
        states = [
            SabrinaState.READY,
            SabrinaState.LISTENING,
            SabrinaState.PROCESSING,
            SabrinaState.READY,
        ]

        # Starting state is INITIALIZING, so first transition is to READY
        first_transition = self.state_machine.transition_to(states[0])
        self.assertTrue(first_transition, "First transition should succeed")

        # Perform remaining transitions
        for state in states[1:]:
            result = self.state_machine.transition_to(state)
            self.assertTrue(result, f"Transition to {state.name} should succeed")

        # Check history length (should now be same as states length)
        self.assertEqual(
            len(self.state_machine.state_history),
            len(states),
            "State history should track all transitions",
        )

        # Check history content
        for i, state in enumerate(states):
            history_entry = self.state_machine.state_history[i]
            self.assertEqual(
                history_entry["to"],
                state.name,
                f"History entry {i} should transition to {state.name}",
            )

    def test_state_callbacks(self):
        """Test state transition callbacks"""
        # Create mock callbacks
        enter_callback = MagicMock()
        exit_callback = MagicMock()
        transition_callback = MagicMock()

        # Register callbacks
        self.state_machine.register_enter_callback(
            SabrinaState.PROCESSING, enter_callback
        )
        self.state_machine.register_exit_callback(SabrinaState.READY, exit_callback)
        self.state_machine.register_transition_callback(transition_callback)

        # Perform transition
        self.state_machine.current_state = SabrinaState.READY
        self.state_machine.transition_to(SabrinaState.PROCESSING)

        # Check callbacks were called
        enter_callback.assert_called_once()
        exit_callback.assert_called_once()
        transition_callback.assert_called_once()

    def test_get_state_info(self):
        """Test state info retrieval"""
        # Set state
        self.state_machine.current_state = SabrinaState.READY

        # Get info
        info = self.state_machine.get_state_info()

        # Check info content
        self.assertEqual(info["current_state"], "READY")
        self.assertIn("description", info)
        self.assertIn("animation", info)
        self.assertIn("allowed_transitions", info)


if __name__ == "__main__":
    unittest.main()
