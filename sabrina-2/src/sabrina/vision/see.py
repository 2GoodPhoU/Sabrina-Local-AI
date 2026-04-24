"""Run a one-shot "describe/answer about the screen" turn.

Glue layer: grab screenshot -> build a Message with one Image attachment ->
stream a reply from a Claude brain. The caller gets an async iterator of
TextDelta + final Done, exactly like a normal brain.chat() stream, so
sentence-streaming TTS works unchanged.

Why this lives outside voice_loop: `sabrina look "..."` wants the same
plumbing without touching the voice-loop state machine. Keeping the
capture-and-ask logic here makes both call sites use the same code path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sabrina.brain.claude import ClaudeBrain
from sabrina.brain.protocol import Image, Message, StreamEvent
from sabrina.config import Settings, load_settings
from sabrina.logging import get_logger
from sabrina.vision.capture import Screenshot, grab

log = get_logger(__name__)


DEFAULT_VISION_SYSTEM_PROMPT = (
    "You are Sabrina, a voice-first desktop assistant. The user has just "
    "attached a screenshot of their screen. Answer their question directly "
    "and briefly based on what you can see. Describe what's visible only as "
    "much as the question requires — do not narrate the whole screen unless "
    "asked. Keep the reply to 1-3 sentences unless the user asks for detail."
)


def capture(settings: Settings | None = None) -> Screenshot:
    """Capture a screenshot using the settings in sabrina.toml."""
    settings = settings or load_settings()
    v = settings.vision
    return grab(monitor=v.monitor, max_edge_px=v.max_edge_px)


async def see(
    question: str,
    *,
    history: list[Message] | None = None,
    settings: Settings | None = None,
    screenshot: Screenshot | None = None,
) -> AsyncIterator[StreamEvent]:
    """Stream a reply about the current screen.

    Args:
        question: What the user wants to know. Empty string gets a generic
                  "what's on the screen?" treatment.
        history: Prior conversation to include as context. System turns in
                 here are ignored — vision uses its own system prompt.
        settings: Override config. Mostly useful for tests.
        screenshot: Pre-captured image. If None, we grab one here. Passing
                  it in from the caller lets `sabrina look` report the
                  capture timing separately from the brain latency.
    """
    settings = settings or load_settings()
    shot = screenshot if screenshot is not None else capture(settings)

    api_key = (
        settings.anthropic_api_key.get_secret_value()
        if settings.anthropic_api_key
        else ""
    )
    if not api_key:
        raise ValueError(
            "Vision requires an Anthropic API key. Set ANTHROPIC_API_KEY in "
            ".env or your shell."
        )

    model = settings.vision.model or settings.brain.claude.fast_model
    brain = ClaudeBrain(
        api_key=api_key,
        model=model,
        max_tokens=settings.brain.claude.max_tokens,
    )
    log.info(
        "vision.see",
        model=model,
        source=f"{shot.source_width}x{shot.source_height}",
        sent=f"{shot.width}x{shot.height}",
        bytes=len(shot.data),
        capture_s=round(shot.capture_duration_s, 3),
    )

    user_msg = Message(
        role="user",
        content=question or "What's on my screen right now?",
        images=(Image(data=shot.data, media_type=shot.media_type),),
    )
    messages = [*(history or []), user_msg]

    async for event in brain.chat(
        messages,
        system=DEFAULT_VISION_SYSTEM_PROMPT,
        max_tokens=settings.brain.claude.max_tokens,
    ):
        yield event
