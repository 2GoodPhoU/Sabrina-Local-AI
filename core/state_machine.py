"""
Sabrina AI State Machine
=======================
A comprehensive state machine for managing Sabrina's operational states,
state transitions, and associated behaviors.
"""

import logging
import time
from enum import Enum, auto
from typing import Dict, Any, Optional, List, Callable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sabrina.state_machine")


class SabrinaState(Enum):
    """Core operational states for Sabrina AI"""

    # System states
    INITIALIZING = auto()  # Starting up, loading components
    READY = auto()  # Idle, waiting for interaction
    SHUTTING_DOWN = auto()  # Graceful shutdown in progress
    ERROR = auto()  # System error state

    # Interaction states
    LISTENING = auto()  # Actively listening for commands
    PROCESSING = auto()  # Processing a command/request
    RESPONDING = auto()  # Generating or delivering a response
    SPEAKING = auto()  # Actively speaking/responding via voice

    # Task states
    EXECUTING_TASK = auto()  # Running an automation task
    MONITORING = auto()  # Passively monitoring (screen, sound, etc.)
    WAITING = auto()  # Waiting for external input or event

    # Smart home states
    CONTROLLING_DEVICES = auto()  # Interacting with smart home devices

    # Special states
    LEARNING = auto()  # Learning from feedback or training
    PAUSED = auto()  # Temporarily paused operation


class StateTransition:
    """Defines a valid transition between states with conditions and actions"""

    def __init__(
        self,
        from_state: SabrinaState,
        to_state: SabrinaState,
        condition: Optional[Callable[..., bool]] = None,
        actions: Optional[List[Callable[..., None]]] = None,
        description: str = "",
    ):
        """Initialize a state transition"""
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition
        self.actions = actions or []
        self.description = description

    def can_transition(self, context: Dict[str, Any] = None) -> bool:
        """Check if transition is allowed based on condition"""
        if self.condition is None:
            return True

        try:
            context = context or {}
            # FIX: Ensure the condition function is properly evaluated
            result = self.condition(context)
            return bool(result)  # Ensure we return a boolean value
        except Exception as e:
            logger.error(f"Error evaluating transition condition: {str(e)}")
            return False

    def execute_actions(self, context: Dict[str, Any] = None):
        """Execute all actions associated with this transition"""
        if not self.actions:
            return

        context = context or {}
        for action in self.actions:
            try:
                action(context)
            except Exception as e:
                logger.error(f"Error executing transition action: {str(e)}")


class StateMachine:
    """
    Enhanced state machine for Sabrina AI with comprehensive state management,
    validation, history tracking, and event integration.
    """

    def __init__(self, event_bus=None):
        """Initialize the state machine"""
        # Core state properties
        self.current_state = SabrinaState.INITIALIZING
        self.previous_state = None
        self.state_entry_time = time.time()
        self.state_history = []
        self.max_history = 20

        # Transition definitions
        self.transitions: Dict[SabrinaState, Dict[SabrinaState, StateTransition]] = {}
        self.global_transitions: List[StateTransition] = []

        # State callbacks
        self.on_enter_callbacks: Dict[SabrinaState, List[Callable]] = {}
        self.on_exit_callbacks: Dict[SabrinaState, List[Callable]] = {}
        self.on_any_transition: List[Callable] = []

        # State metadata
        self.state_data: Dict[SabrinaState, Dict[str, Any]] = {}
        self.context: Dict[str, Any] = {}

        # Integration
        self.event_bus = event_bus

        # Define default state metadata
        self._init_state_metadata()

        # Define allowed transitions
        self._init_transitions()

        logger.info(f"State machine initialized in state: {self.current_state.name}")

    def _init_state_metadata(self):
        """Initialize state properties and metadata"""
        # Define properties for each state
        for state in SabrinaState:
            self.state_data[state] = {
                "description": self._get_state_description(state),
                "can_interrupt": self._state_can_interrupt(state),
                "typical_duration": self._get_typical_duration(state),
                "animation": self._get_animation_for_state(state),
                "priority": self._get_state_priority(state),
            }

    def _get_state_description(self, state: SabrinaState) -> str:
        """Get human-readable description of a state"""
        descriptions = {
            SabrinaState.INITIALIZING: "Starting up and loading components",
            SabrinaState.READY: "Idle and waiting for commands",
            SabrinaState.SHUTTING_DOWN: "Shutting down gracefully",
            SabrinaState.ERROR: "Encountered an error",
            SabrinaState.LISTENING: "Actively listening for voice commands",
            SabrinaState.PROCESSING: "Processing a request or command",
            SabrinaState.RESPONDING: "Preparing a response",
            SabrinaState.SPEAKING: "Speaking a response",
            SabrinaState.EXECUTING_TASK: "Executing an automation task",
            SabrinaState.MONITORING: "Monitoring the environment",
            SabrinaState.WAITING: "Waiting for external input",
            SabrinaState.CONTROLLING_DEVICES: "Controlling smart home devices",
            SabrinaState.LEARNING: "Learning from feedback",
            SabrinaState.PAUSED: "Operation temporarily paused",
        }
        return descriptions.get(state, "Unknown state")

    def _state_can_interrupt(self, state: SabrinaState) -> bool:
        """Determine if a state can be interrupted by user input"""
        # States that should not be interrupted
        uninterruptible_states = {
            SabrinaState.INITIALIZING,
            SabrinaState.SHUTTING_DOWN,
            SabrinaState.ERROR,
        }
        return state not in uninterruptible_states

    def _get_typical_duration(self, state: SabrinaState) -> Optional[float]:
        """Get the typical duration of a state in seconds (None if indefinite)"""
        durations = {
            SabrinaState.INITIALIZING: 10.0,
            SabrinaState.LISTENING: 10.0,  # Timeout after listening for 10 seconds
            SabrinaState.PROCESSING: 5.0,
            SabrinaState.RESPONDING: 3.0,
            SabrinaState.SPEAKING: None,  # Depends on response length
            SabrinaState.WAITING: 30.0,  # Default timeout for waiting
            SabrinaState.READY: None,  # Indefinite
            SabrinaState.PAUSED: None,  # Indefinite
            SabrinaState.MONITORING: None,  # Indefinite
        }
        return durations.get(state)

    def _get_animation_for_state(self, state: SabrinaState) -> str:
        """Get the appropriate animation name for a state"""
        animations = {
            SabrinaState.INITIALIZING: "idle",
            SabrinaState.READY: "idle",
            SabrinaState.SHUTTING_DOWN: "idle",
            SabrinaState.ERROR: "error",
            SabrinaState.LISTENING: "listening",
            SabrinaState.PROCESSING: "thinking",
            SabrinaState.RESPONDING: "talking",
            SabrinaState.SPEAKING: "talking",
            SabrinaState.EXECUTING_TASK: "working",
            SabrinaState.MONITORING: "idle",
            SabrinaState.WAITING: "waiting",
            SabrinaState.CONTROLLING_DEVICES: "working",
            SabrinaState.LEARNING: "thinking",
            SabrinaState.PAUSED: "idle",
        }
        return animations.get(state, "idle")

    def _get_state_priority(self, state: SabrinaState) -> int:
        """Get the priority level of a state (higher number = higher priority)"""
        priorities = {
            SabrinaState.ERROR: 100,  # Highest priority
            SabrinaState.SHUTTING_DOWN: 90,
            SabrinaState.INITIALIZING: 80,
            SabrinaState.SPEAKING: 70,
            SabrinaState.RESPONDING: 60,
            SabrinaState.LISTENING: 50,
            SabrinaState.PROCESSING: 40,
            SabrinaState.EXECUTING_TASK: 30,
            SabrinaState.CONTROLLING_DEVICES: 25,
            SabrinaState.WAITING: 20,
            SabrinaState.LEARNING: 15,
            SabrinaState.MONITORING: 10,
            SabrinaState.READY: 5,  # Lowest priority
            SabrinaState.PAUSED: 1,
        }
        return priorities.get(state, 0)

    def _init_transitions(self):
        """Initialize the allowed state transitions"""
        # From INITIALIZING
        self.add_transition(SabrinaState.INITIALIZING, SabrinaState.READY)
        self.add_transition(SabrinaState.INITIALIZING, SabrinaState.ERROR)

        # From READY
        self.add_transition(SabrinaState.READY, SabrinaState.LISTENING)
        self.add_transition(SabrinaState.READY, SabrinaState.PROCESSING)
        self.add_transition(SabrinaState.READY, SabrinaState.MONITORING)
        self.add_transition(SabrinaState.READY, SabrinaState.PAUSED)
        self.add_transition(SabrinaState.READY, SabrinaState.SHUTTING_DOWN)
        self.add_transition(SabrinaState.READY, SabrinaState.ERROR)

        # From LISTENING
        self.add_transition(SabrinaState.LISTENING, SabrinaState.PROCESSING)
        self.add_transition(
            SabrinaState.LISTENING, SabrinaState.READY
        )  # Timeout or cancel
        self.add_transition(SabrinaState.LISTENING, SabrinaState.ERROR)

        # From PROCESSING
        self.add_transition(SabrinaState.PROCESSING, SabrinaState.RESPONDING)
        self.add_transition(SabrinaState.PROCESSING, SabrinaState.EXECUTING_TASK)
        self.add_transition(SabrinaState.PROCESSING, SabrinaState.WAITING)
        self.add_transition(SabrinaState.PROCESSING, SabrinaState.CONTROLLING_DEVICES)
        self.add_transition(
            SabrinaState.PROCESSING, SabrinaState.READY
        )  # No action needed
        self.add_transition(SabrinaState.PROCESSING, SabrinaState.ERROR)

        # From RESPONDING
        self.add_transition(SabrinaState.RESPONDING, SabrinaState.SPEAKING)
        self.add_transition(
            SabrinaState.RESPONDING, SabrinaState.READY
        )  # Text-only response
        self.add_transition(SabrinaState.RESPONDING, SabrinaState.ERROR)

        # From SPEAKING
        self.add_transition(SabrinaState.SPEAKING, SabrinaState.READY)
        self.add_transition(
            SabrinaState.SPEAKING, SabrinaState.LISTENING
        )  # Continue conversation
        self.add_transition(SabrinaState.SPEAKING, SabrinaState.ERROR)

        # From EXECUTING_TASK
        self.add_transition(SabrinaState.EXECUTING_TASK, SabrinaState.READY)
        self.add_transition(SabrinaState.EXECUTING_TASK, SabrinaState.RESPONDING)
        self.add_transition(SabrinaState.EXECUTING_TASK, SabrinaState.WAITING)
        self.add_transition(SabrinaState.EXECUTING_TASK, SabrinaState.ERROR)

        # From MONITORING
        self.add_transition(SabrinaState.MONITORING, SabrinaState.READY)
        self.add_transition(SabrinaState.MONITORING, SabrinaState.LISTENING)
        self.add_transition(SabrinaState.MONITORING, SabrinaState.PROCESSING)
        self.add_transition(SabrinaState.MONITORING, SabrinaState.ERROR)

        # From WAITING
        self.add_transition(SabrinaState.WAITING, SabrinaState.PROCESSING)
        self.add_transition(SabrinaState.WAITING, SabrinaState.READY)
        self.add_transition(SabrinaState.WAITING, SabrinaState.ERROR)

        # From CONTROLLING_DEVICES
        self.add_transition(SabrinaState.CONTROLLING_DEVICES, SabrinaState.RESPONDING)
        self.add_transition(SabrinaState.CONTROLLING_DEVICES, SabrinaState.READY)
        self.add_transition(SabrinaState.CONTROLLING_DEVICES, SabrinaState.ERROR)

        # From LEARNING
        self.add_transition(SabrinaState.LEARNING, SabrinaState.READY)
        self.add_transition(SabrinaState.LEARNING, SabrinaState.ERROR)

        # From PAUSED
        self.add_transition(SabrinaState.PAUSED, SabrinaState.READY)
        self.add_transition(SabrinaState.PAUSED, SabrinaState.SHUTTING_DOWN)
        self.add_transition(SabrinaState.PAUSED, SabrinaState.ERROR)

        # From ERROR
        self.add_transition(SabrinaState.ERROR, SabrinaState.READY)
        self.add_transition(SabrinaState.ERROR, SabrinaState.SHUTTING_DOWN)

        # From SHUTTING_DOWN - terminal state, no transitions out

        # Add global transitions (can happen from any state)
        self.add_global_transition(
            SabrinaState.ERROR,
            condition=lambda ctx: ctx.get("critical_error", False),
            description="Critical error occurred",
        )

    def add_transition(
        self,
        from_state: SabrinaState,
        to_state: SabrinaState,
        condition: Callable = None,
        actions: List[Callable] = None,
        description: str = "",
    ) -> None:
        """Add a transition between states"""
        if from_state not in self.transitions:
            self.transitions[from_state] = {}

        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            condition=condition,
            actions=actions,
            description=description,
        )

        self.transitions[from_state][to_state] = transition
        logger.debug(f"Added transition: {from_state.name} -> {to_state.name}")

    def add_global_transition(
        self,
        to_state: SabrinaState,
        condition: Callable = None,
        actions: List[Callable] = None,
        description: str = "",
    ) -> None:
        """Add a global transition that can happen from any state"""
        transition = StateTransition(
            from_state=None,  # None indicates any state
            to_state=to_state,
            condition=condition,
            actions=actions,
            description=description,
        )

        self.global_transitions.append(transition)
        logger.debug(f"Added global transition to: {to_state.name}")

    def get_allowed_transitions(self) -> List[SabrinaState]:
        """Get states that are valid transitions from the current state"""
        allowed = []

        # Check direct transitions
        if self.current_state in self.transitions:
            for to_state, transition in self.transitions[self.current_state].items():
                if transition.can_transition(self.context):
                    allowed.append(to_state)

        # Check global transitions
        for transition in self.global_transitions:
            if transition.can_transition(self.context):
                allowed.append(transition.to_state)

        return allowed

    def can_transition_to(self, target_state) -> bool:
        """
        Check if a transition to the target state is currently allowed

        Args:
            target_state: The state to transition to

        Returns:
            bool: True if the transition is allowed, False otherwise
        """
        # Check direct transitions
        if self.current_state in self.transitions:
            if target_state in self.transitions[self.current_state]:
                transition = self.transitions[self.current_state][target_state]
                # If there's a condition, evaluate it; otherwise transition is allowed
                if transition.condition:
                    return transition.can_transition(self.context)
                else:
                    return True

        # Check global transitions
        for transition in self.global_transitions:
            if transition.to_state == target_state:
                # If there's a condition, evaluate it; otherwise transition is allowed
                if transition.condition:
                    if transition.can_transition(self.context):
                        return True
                else:
                    return True

        # If we get here, no valid transition was found
        return False

    def transition_to(
        self, target_state: SabrinaState, context_updates: Dict[str, Any] = None
    ) -> bool:
        """
        Attempt to transition to the target state

        Args:
            target_state: The state to transition to
            context_updates: Updates to the context for this transition

        Returns:
            bool: True if transition succeeded, False otherwise
        """
        # Update context if provided
        if context_updates:
            self.context.update(context_updates)

        # Check if transition is allowed
        if not self.can_transition_to(target_state):
            logger.warning(
                f"Transition not allowed: {self.current_state.name} -> {target_state.name}"
            )
            return False

        # Get the transition object
        transition = None

        # Check direct transitions first
        if (
            self.current_state in self.transitions
            and target_state in self.transitions[self.current_state]
        ):
            transition = self.transitions[self.current_state][target_state]

        # Check global transitions if no direct transition found
        if transition is None:
            for global_transition in self.global_transitions:
                if (
                    global_transition.to_state == target_state
                    and global_transition.can_transition(self.context)
                ):
                    transition = global_transition
                    break

        if transition is None:
            logger.error(
                f"Transition not found: {self.current_state.name} -> {target_state.name}"
            )
            return False

        # Execute exit callbacks for current state
        self._execute_exit_callbacks(self.current_state)

        # Store previous state
        self.previous_state = self.current_state

        # Update current state
        self.current_state = target_state
        self.state_entry_time = time.time()

        # Add to history
        self._add_to_history(self.previous_state, self.current_state)

        # Execute transition actions
        transition.execute_actions(self.context)

        # Execute entry callbacks for new state
        self._execute_enter_callbacks(target_state)

        # Execute general transition callbacks
        self._execute_transition_callbacks(self.previous_state, target_state)

        # Fire event if event bus is available
        if self.event_bus:
            try:
                from .enhanced_event_system import Event, EventType, EventPriority

                event = Event(
                    event_type=EventType.STATE_CHANGE,
                    data={
                        "previous_state": self.previous_state.name,
                        "new_state": self.current_state.name,
                        "transition_time": self.state_entry_time,
                        "context": {
                            k: v
                            for k, v in self.context.items()
                            if isinstance(v, (str, int, float, bool, list, dict))
                        },
                    },
                    priority=EventPriority.NORMAL,
                    source="state_machine",
                )

                self.event_bus.post_event(event)
            except Exception as e:
                logger.error(f"Error posting state change event: {str(e)}")

        logger.info(
            f"State transition: {self.previous_state.name} -> {self.current_state.name}"
        )
        return True

    def _add_to_history(self, from_state: SabrinaState, to_state: SabrinaState):
        """Add a transition to the history"""
        entry = {
            "from": from_state.name,
            "to": to_state.name,
            "timestamp": time.time(),
            "context": self.context.copy(),
        }

        self.state_history.append(entry)

        # Trim history if needed
        if len(self.state_history) > self.max_history:
            self.state_history = self.state_history[-self.max_history :]

    def register_enter_callback(self, state: SabrinaState, callback: Callable) -> None:
        """Register a callback to be executed when entering a state"""
        if state not in self.on_enter_callbacks:
            self.on_enter_callbacks[state] = []

        self.on_enter_callbacks[state].append(callback)

    def register_exit_callback(self, state: SabrinaState, callback: Callable) -> None:
        """Register a callback to be executed when exiting a state"""
        if state not in self.on_exit_callbacks:
            self.on_exit_callbacks[state] = []

        self.on_exit_callbacks[state].append(callback)

    def register_transition_callback(self, callback: Callable) -> None:
        """Register a callback to be executed on any state transition"""
        self.on_any_transition.append(callback)

    def _execute_enter_callbacks(self, state: SabrinaState) -> None:
        """Execute all callbacks for entering a state"""
        if state in self.on_enter_callbacks:
            for callback in self.on_enter_callbacks[state]:
                try:
                    callback(state, self.context)
                except Exception as e:
                    logger.error(f"Error in state enter callback: {str(e)}")

    def _execute_exit_callbacks(self, state: SabrinaState) -> None:
        """Execute all callbacks for exiting a state"""
        if state in self.on_exit_callbacks:
            for callback in self.on_exit_callbacks[state]:
                try:
                    callback(state, self.context)
                except Exception as e:
                    logger.error(f"Error in state exit callback: {str(e)}")

    def _execute_transition_callbacks(
        self, from_state: SabrinaState, to_state: SabrinaState
    ) -> None:
        """Execute all callbacks registered for any transition"""
        for callback in self.on_any_transition:
            try:
                callback(from_state, to_state, self.context)
            except Exception as e:
                logger.error(f"Error in transition callback: {str(e)}")

    def get_state_duration(self) -> float:
        """Get the duration (in seconds) the system has been in the current state"""
        return time.time() - self.state_entry_time

    def is_state_expired(self) -> bool:
        """Check if the current state has exceeded its typical duration"""
        typical_duration = self._get_typical_duration(self.current_state)

        # If the state has no typical duration, it never expires
        if typical_duration is None:
            return False

        return self.get_state_duration() > typical_duration

    def get_animation_for_current_state(self) -> str:
        """Get the animation name for the current state"""
        return self._get_animation_for_state(self.current_state)

    def get_state_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the current state"""
        return {
            "current_state": self.current_state.name,
            "previous_state": self.previous_state.name if self.previous_state else None,
            "duration": self.get_state_duration(),
            "entry_time": self.state_entry_time,
            "is_expired": self.is_state_expired(),
            "description": self._get_state_description(self.current_state),
            "animation": self.get_animation_for_current_state(),
            "can_interrupt": self._state_can_interrupt(self.current_state),
            "allowed_transitions": [s.name for s in self.get_allowed_transitions()],
            "priority": self._get_state_priority(self.current_state),
        }
