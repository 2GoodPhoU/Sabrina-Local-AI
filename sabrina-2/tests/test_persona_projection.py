"""Unit tests for `brain/persona.py` and the OllamaBrain projection wrap.

Covers the (a)-half DoD points 6-7 from
`rebuild/drafts/research/2026-05-07-p4c1-persona-projection-layer-spec.md`.
Twelve tests across three groups:

  - build_system_prompt: golden parity + Ollama variant differentiation
    + register swap + tool-use block + invalid-input branches.
  - project_ollama_text: each rule fires; rule-disabled bypass works;
    the truncation rule gates on prior_user_chars correctly.
  - OllamaBrain projection wrap: project=True end-to-end yields the
    projected form; project=False passes through.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from sabrina.brain.persona import (
    SABRINA_SYSTEM_PROMPT_CLAUDE,
    build_system_prompt,
    project_ollama_text,
)
from sabrina.brain.protocol import Done, Message, TextDelta

# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------


def test_build_system_prompt_claude_matches_pre_lift_string() -> None:
    """The post-lift Claude prompt is the SABRINA_SYSTEM_PROMPT
    constant byte-for-byte. A snapshot in spirit; if a future edit to
    persona.py drifts the Claude variant, this fails first.
    """
    via_constant = SABRINA_SYSTEM_PROMPT_CLAUDE
    via_builder = build_system_prompt(register="A", backend="claude")
    assert via_constant == via_builder
    assert "You are Sabrina." in via_constant
    assert "Operator voice, not customer-service voice." in via_constant
    assert "Current register: A." in via_constant
    assert "Pronouns for self: she/her." in via_constant


def test_build_system_prompt_ollama_includes_extra_anti_patterns() -> None:
    """Ollama variant carries the four parity-audit in-prompt fixes
    (Sure!, Of course!, never-call-yourself-AI, hedge-stacking).
    """
    claude = build_system_prompt(register="A", backend="claude")
    ollama = build_system_prompt(register="A", backend="ollama")
    assert claude != ollama
    # Ollama-only anti-patterns
    assert '"Sure!"' in ollama
    assert '"Of course!"' in ollama
    assert "Never refer to yourself as an AI" in ollama
    assert "Do not stack hedges" in ollama
    # The Claude variant must NOT have these (drift guard)
    assert '"Sure!"' not in claude
    assert '"Of course!"' not in claude
    assert "Do not stack hedges" not in claude


def test_build_system_prompt_register_b_and_c_swap_audience_blocks() -> None:
    """Both backends emit the picked register block; the spine stays."""
    for backend in ("claude", "ollama"):
        a = build_system_prompt(register="A", backend=backend)
        b = build_system_prompt(register="B", backend=backend)
        c = build_system_prompt(register="C", backend=backend)
        assert "Current register: A." in a
        assert "Current register: B." in b
        assert "Current register: C." in c
        # Spine stays
        assert "You are Sabrina." in a
        assert "You are Sabrina." in b
        assert "You are Sabrina." in c


def test_build_system_prompt_invalid_register_or_backend_raises() -> None:
    with pytest.raises(ValueError, match="Unknown register"):
        build_system_prompt(register="Z", backend="claude")
    with pytest.raises(ValueError, match="Unknown backend"):
        build_system_prompt(register="A", backend="grok")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# project_ollama_text — per-rule
# ---------------------------------------------------------------------------


def test_project_ollama_text_strips_trailing_let_me_know() -> None:
    text = "That's how the cache works. Let me know if you need anything else."
    out = project_ollama_text(text)
    assert out == "That's how the cache works."


def test_project_ollama_text_strips_hope_this_helps() -> None:
    text = "Look at line 42. Hope this helps!"
    out = project_ollama_text(text)
    assert out == "Look at line 42."


def test_project_ollama_text_dehydrates_markdown_list() -> None:
    text = "- alpha\n- beta\n- gamma"
    out = project_ollama_text(text)
    assert out == "alpha, beta, gamma."


def test_project_ollama_text_dehydrates_numbered_list() -> None:
    text = "1) alpha\n2) beta"
    out = project_ollama_text(text)
    assert out == "alpha, beta."


def test_project_ollama_text_dedups_apology_stack() -> None:
    text = "I'm sorry. My apologies. Sorry again, here goes."
    out = project_ollama_text(text)
    # First apology kept; the second-apology sentence ("My apologies.")
    # is dropped entirely; the third-apology sentence has its apology
    # clause stripped + remainder capitalized ("Sorry again, here goes."
    # -> "Here goes."). Per spec § "Open question Q2 (a)": keep first.
    assert out == "I'm sorry. Here goes."


def test_project_ollama_text_sentence_count_truncation_kicks_in_on_short_user_prompt() -> None:
    six_sentence_reply = (
        "First. Second. Third. Fourth. Fifth. Sixth."
    )
    out = project_ollama_text(
        six_sentence_reply, prior_user_chars=30
    )
    assert "Want more?" in out
    # Should keep the first 3 sentences only.
    assert "First." in out
    assert "Second." in out
    assert "Third." in out
    assert "Fourth." not in out


def test_project_ollama_text_sentence_count_truncation_skipped_on_long_user_prompt() -> None:
    six_sentence_reply = "First. Second. Third. Fourth. Fifth. Sixth."
    out = project_ollama_text(six_sentence_reply, prior_user_chars=200)
    # Untouched: prior user prompt was long, so the user did ask for detail.
    assert out == six_sentence_reply


def test_project_ollama_text_disabled_rule_bypasses() -> None:
    """Each rule can be turned off independently."""
    closing_text = "Done. Let me know if you need anything else."
    assert project_ollama_text(closing_text, strip_closing_offer=False) == closing_text

    list_text = "- alpha\n- beta"
    assert project_ollama_text(list_text, dehydrate_lists=False) == list_text

    apol_text = "I'm sorry. My apologies. Sorry again, here goes."
    assert project_ollama_text(apol_text, dedup_apologies=False) == apol_text

    long_reply = "First. Second. Third. Fourth. Fifth. Sixth."
    assert (
        project_ollama_text(
            long_reply, prior_user_chars=10, truncate_long_replies=False
        )
        == long_reply
    )


# ---------------------------------------------------------------------------
# OllamaBrain projection wrap
# ---------------------------------------------------------------------------


class _FakeAsyncStream:
    """Mimics the Ollama AsyncClient stream: yields chunk dicts with a
    final ``done=True`` carrying token counts.
    """

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> _FakeAsyncStream:
        self._iter = iter(self._chunks)
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeAsyncClient:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks = chunks

    async def chat(self, **kwargs: Any) -> _FakeAsyncStream:
        return _FakeAsyncStream(self._chunks)


def _stream_chunks(text: str, *, in_tok: int = 5, out_tok: int = 7) -> list[dict[str, Any]]:
    """Split ``text`` into 3 chunks plus a final done chunk."""
    n = len(text)
    third = max(1, n // 3)
    return [
        {"message": {"content": text[:third]}, "done": False},
        {"message": {"content": text[third : 2 * third]}, "done": False},
        {"message": {"content": text[2 * third :]}, "done": False},
        {
            "message": {"content": ""},
            "done": True,
            "prompt_eval_count": in_tok,
            "eval_count": out_tok,
            "done_reason": "stop",
        },
    ]


async def _drain(it: AsyncIterator[Any]) -> list[Any]:
    return [event async for event in it]


@pytest.mark.asyncio
async def test_ollama_brain_streams_projected_text_when_default() -> None:
    """Default project=True yields a single projected TextDelta + Done."""
    from sabrina.brain.ollama import OllamaBrain

    brain = OllamaBrain(project=True)
    raw = "- alpha\n- beta\n- gamma"
    brain._client = _FakeAsyncClient(_stream_chunks(raw))  # type: ignore[assignment]

    events = await _drain(
        brain.chat([Message(role="user", content="list 'em")], system="x")
    )
    text_events = [e for e in events if isinstance(e, TextDelta)]
    done_events = [e for e in events if isinstance(e, Done)]
    assert len(text_events) == 1
    assert text_events[0].text == "alpha, beta, gamma."
    assert len(done_events) == 1
    assert done_events[0].input_tokens == 5
    assert done_events[0].output_tokens == 7


@pytest.mark.asyncio
async def test_ollama_brain_passes_through_when_project_false() -> None:
    """project=False yields raw text deltas as they arrive (no projection)."""
    from sabrina.brain.ollama import OllamaBrain

    brain = OllamaBrain(project=False)
    raw = "Done. Let me know if you need anything else."
    brain._client = _FakeAsyncClient(_stream_chunks(raw))  # type: ignore[assignment]

    events = await _drain(
        brain.chat([Message(role="user", content="ok?")], system="x")
    )
    text_events = [e for e in events if isinstance(e, TextDelta)]
    # Reassembling the chunked passthrough recovers the raw input.
    assert "".join(e.text for e in text_events) == raw
    # No projection: the cl