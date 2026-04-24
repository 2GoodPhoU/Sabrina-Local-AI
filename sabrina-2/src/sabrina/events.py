"""Typed event definitions for the Sabrina event bus.

Every event in the system is one of these. New subsystems add new event types
here. The Brain / voice / vision / automation components only depend on this
module, never on each other.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _EventBase(BaseModel):
    """Common base. Immutable; timestamped on creation."""

    model_config = ConfigDict(frozen=True)
    ts: datetime = Field(default_factory=_now)


# --- Conversation events ---


class UserMessage(_EventBase):
    kind: Literal["user_message"] = "user_message"
    text: str


class AssistantReply(_EventBase):
    kind: Literal["assistant_reply"] = "assistant_reply"
    text: str
    tier: str  # "claude:sonnet-4-6" | "ollama:qwen2.5:14b" | "fast_path" | ...


class ThinkingStarted(_EventBase):
    kind: Literal["thinking_started"] = "thinking_started"
    tier: str


class ThinkingFinished(_EventBase):
    kind: Literal["thinking_finished"] = "thinking_finished"
    tier: str
    input_tokens: int | None = None
    output_tokens: int | None = None


# --- State events ---


StateName = Literal["idle", "listening", "thinking", "speaking", "acting"]


class StateChanged(_EventBase):
    kind: Literal["state_changed"] = "state_changed"
    from_state: StateName
    to_state: StateName
    reason: str = ""


# --- Speaker events ---


class SpeakRequest(_EventBase):
    kind: Literal["speak_request"] = "speak_request"
    text: str
    voice: str | None = None


class SpeakStarted(_EventBase):
    kind: Literal["speak_started"] = "speak_started"
    engine: str  # "piper:amy-medium" | "sapi:Zira" | ...
    text: str


class SpeakFinished(_EventBase):
    kind: Literal["speak_finished"] = "speak_finished"
    engine: str
    duration_s: float


class SpeakAborted(_EventBase):
    kind: Literal["speak_aborted"] = "speak_aborted"
    engine: str
    reason: str


# --- Barge-in events ---


class BargeInDetected(_EventBase):
    """VAD fired during speaking; brain stream + TTS were cancelled."""

    kind: Literal["barge_in_detected"] = "barge_in_detected"


# Union of all events. Add to this list when adding an event type.
Event = (
    UserMessage
    | AssistantReply
    | ThinkingStarted
    | ThinkingFinished
    | StateChanged
    | SpeakRequest
    | SpeakStarted
    | SpeakFinished
    | SpeakAborted
    | BargeInDetected
)
