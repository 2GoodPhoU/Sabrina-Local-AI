"""Voice-phrase detection for vision turns.

Kept tiny on purpose: a short list of substring matches against the
lowercased transcript. We bias false-*negative* (miss a vision turn) over
false-*positive* (accidentally screenshot when the user didn't ask),
since the latter is creepy and eats API tokens.

A more serious detector (intent classifier / tool-call) can slot in later
behind the same `should_trigger_vision()` surface.
"""

from __future__ import annotations

# Phrases that unambiguously ask Sabrina to look at the screen.
# All lowercased; the matcher lowercases the transcript before checking.
VISION_TRIGGERS: tuple[str, ...] = (
    "look at my screen",
    "look at the screen",
    "look at this screen",
    "what's on my screen",
    "what is on my screen",
    "what's on the screen",
    "what is on the screen",
    "read my screen",
    "read this screen",
    "describe my screen",
    "describe the screen",
    "check my screen",
    "see my screen",
    "see the screen",
    "what do you see",
    # Common phrasings for quick help with whatever's on-screen right now.
    "what does this say",
    "what does this mean",
    "help me with this",
)


def should_trigger_vision(text: str) -> bool:
    """Return True if `text` contains a vision-trigger phrase."""
    if not text:
        return False
    lowered = text.lower()
    return any(t in lowered for t in VISION_TRIGGERS)
