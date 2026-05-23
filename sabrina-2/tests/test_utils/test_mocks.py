"""Tests for the rebuild test scaffolding (mocks + path helpers).

Spec: rebuild/drafts/research/2026-05-05-p55-pytest-scaffolding-port-spec.md
DoD point 5 — at least one test per mock factory and per path helper. This
is scaffolding, not a deep suite; one test per primitive is enough.

Single file (rather than test_mocks.py + test_paths.py) per the spec's
literal wording: "At least one new test in `sabrina-2/tests/test_utils/
test_mocks.py` exercises each ... and at least one new test exercises each
path helper."
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from sabrina.brain.protocol import Brain, CancelToken, Done, Message, TextDelta
from sabrina.events import UserMessage
from sabrina.listener.protocol import Listener, Transcript
from sabrina.speaker.protocol import Speaker, SpeakResult

from tests.test_utils import paths
from tests.test_utils.mocks import (
    make_cancel_token,
    make_fake_brain,
    make_fake_bus,
    make_fake_listener,
    make_fake_speaker,
)


# --- Mock factories --------------------------------------------------------


def test_make_fake_brain_satisfies_brain_protocol():
    brain = make_fake_brain(reply="hi")
    assert isinstance(brain, Brain)
    assert brain.name == "fake-brain"


def test_fake_brain_streams_reply_and_done():
    brain = make_fake_brain(reply="hello world")

    async def _drive() -> list:
        events = []
        stream = await brain.chat(
            messages=[Message(role="user", content="hi")]
        )
        async for ev in stream:
            events.append(ev)
        return events

    events = asyncio.run(_drive())
    text_events = [e for e in events if isinstance(e, TextDelta)]
    done_events = [e for e in events if isinstance(e, Done)]
    assert len(text_events) >= 1
    assert "".join(e.text for e in text_events) == "hello world"
    assert len(done_events) == 1
    assert done_events[0].stop_reason == "end_turn"
    assert len(brain.calls) == 1


def test_fake_brain_honors_cancel_token():
    brain = make_fake_brain(deltas=("a", "b", "c"))
    token = make_cancel_token()

    async def _drive() -> list:
        events = []
        stream = await brain.chat(
            messages=[Message(role="user", content="x")],
            cancel_token=token,
        )
        async for ev in stream:
            events.append(ev)
            if isinstance(ev, TextDelta) and ev.text == "a":
                token.cancel()
        return events

    events = asyncio.run(_drive())
    done_events = [e for e in events if isinstance(e, Done)]
    assert any(d.stop_reason == "cancelled" for d in done_events)


def test_make_fake_speaker_satisfies_speaker_protocol():
    speaker = make_fake_speaker()
    assert isinstance(speaker, Speaker)

    async def _drive() -> SpeakResult:
        return await speaker.speak("hello", voice="amy")

    result = asyncio.run(_drive())
    assert isinstance(result, SpeakResult)
    assert speaker.calls == [("hello", "amy")]


def test_make_fake_listener_satisfies_listener_protocol():
    listener = make_fake_listener(text="rebuild root")
    assert isinstance(listener, Listener)

    async def _drive() -> Transcript:
        return await listener.transcribe(Path("/dev/null"))

    transcript = asyncio.run(_drive())
    assert isinstance(transcript, Transcript)
    assert transcript.text == "rebuild root"
    assert listener.calls == [Path("/dev/null")]


def test_make_fake_bus_records_publishes_and_filters_subscribe():
    bus = make_fake_bus()

    async def _drive() -> None:
        await bus.publish(UserMessage(text="one"))
        await bus.publish(UserMessage(text="two"))

    asyncio.run(_drive())
    assert len(bus.events) == 2
    user_msgs = bus.subscribe("user_message")
    assert len(user_msgs) == 2
    assert bus.subscribers_called == 1
    nothing = bus.subscribe("assistant_reply")
    assert nothing == []


def test_make_cancel_token_returns_fresh_token():
    token = make_cancel_token()
    assert isinstance(token, CancelToken)
    assert token.cancelled is False
    token.cancel()
    assert token.cancelled is True


def test_make_cancel_token_pre_tripped():
    token = make_cancel_token(cancelled=True)
    assert token.cancelled is True


# --- Path helpers ---------------------------------------------------------


def test_get_project_root_resolves_to_sabrina_2():
    root = paths.get_project_root()
    assert root.is_dir()
    assert root.name == "sabrina-2"
    # Verify at least one rebuild-root indicator exists at the resolved path.
    assert (root / "pyproject.toml").exists()


def test_get_test_dir_resolves_under_project_root():
    root = paths.get_project_root()
    test_dir = paths.get_test_dir()
    assert test_dir == root / "tests"
    assert test_dir.is_dir()


def test_get_test_data_dir_creates_directory():
    data_dir = paths.get_test_data_dir()
    assert data_dir.is_dir()
    assert data_dir.name == "data"
    assert data_dir.parent == paths.get_test_dir()


def test_get_test_temp_dir_creates_directory():
    temp_dir = paths.get_test_temp_dir()
    assert temp_dir.is_dir()
    assert temp_dir.name == "temp"
    assert temp_dir.parent == paths.get_test_dir()


def test_create_test_file_writes_content(tmp_path: Path):
    p = paths.create_test_file(tmp_path / "sub", "hello.txt", "world")
    assert p.exists()
    assert p.read_text(encoding="utf-8") == "world"


def test_ensure_project_root_in_sys_path_inserts_src(monkeypatch):
    # Snapshot sys.path so we can detect insertion idempotently.
    monkeypatch.setattr(sys, "path", list(sys.path))
    src = paths.get_project_root() / "src"
    paths.ensure_project_root_in_sys_path()
    assert str(src) in sys.path
    # Calling again is a no-op (no duplicate insertion).
    before = list(sys.path)
    paths.ensure_project_root_in_sys_path()
    assert sys.path == before


# --- Markers ---------------------------------------------------------------


@pytest.mark.requires_windows
def test_requires_windows_marker_skips_off_windows():
    """If this body actually runs, the marker isn't being honored — fail."""
    if sys.platform != "win32":
        pytest.fail(
            "requires_windows marker should have skipped this test on non-Windows"
        )
