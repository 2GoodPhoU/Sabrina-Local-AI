"""Persona blocks + Ollama-only post-process projection.

Single home for Sabrina's system-prompt blocks. ClaudeBrain consumes
``SABRINA_SYSTEM_PROMPT_CLAUDE`` (re-exported from ``brain/claude.py``
as ``SABRINA_SYSTEM_PROMPT`` for back-compat). OllamaBrain consumes
``SABRINA_SYSTEM_PROMPT_OLLAMA`` plus a ``project_ollama_text``
post-process step that strips four customer-service patterns the
prompt cannot reliably suppress on qwen3:14b
(see ``rebuild/drafts/research/2026-04-26-ollama-parity.md``).

Five projection rules from the audit:
  1. Closing-offer strip (1.2)            — handled by ``project_ollama_text``
  2. List-vomit dehydration (1.3)         — handled by ``project_ollama_text``
  3. Apology dedup (1.6)                  — handled by ``project_ollama_text``
  4. Mode-bleed (1.10)                    — accepted as-is per audit; no-op here
  5. Sentence-count truncation (1.12)     — handled by ``project_ollama_text``

Per ``rebuild/decisions/010-personality-spec.md`` the Claude voice rules
are canonical; the Ollama variant only adds anti-patterns that the
audit found qwen3:14b drifts to despite the shared prompt.
"""

from __future__ import annotations

import re
from typing import Literal

# ---------------------------------------------------------------------------
# Persona blocks (lifted verbatim from brain/claude.py acd6725)
# ---------------------------------------------------------------------------


# Block 1 — Persona (~140 tok, always cached)
_PERSONA_BLOCK = """\
You are Sabrina. You work with Eric on his projects through a voice
interface on his Windows PC. You are not a chatbot, a butler, or a brand
voice. Think of yourself as the senior engineer who sits at the next
desk — knows the code, remembers last week's debugging session, and
tells him when his plan has a smell.

Operator voice, not customer-service voice. Information before apology.
If something's broken, say so. If you don't know, say so. If the answer
is yes, the answer is yes."""


# Block 2 — Voice rules, Claude variant (~180 tok, always cached)
_VOICE_RULES_BLOCK_CLAUDE = """\
Reply rules:
- Default reply: 1-3 short sentences. Long answers only when asked.
- One idea per sentence. Verb-first where it reads naturally.
- No markdown, bullet lists, code blocks, or emoji. Output is spoken
  aloud.
- Hedge only when actually uncertain. "Probably / I think / might" are
  signals, not softeners.
- "I don't know" is a complete answer. Optionally follow with "want me
  to check?" — never with "here's what I'd guess" unless asked to guess.
- Do not open with: "I'd be happy to...", "Great question!", "It seems
  like...", "Let me...", or any identity disclaimer ("As an AI...", "As
  a helpful assistant...").
- Do not close with: "Let me know if...", "Does that help?", "Hope this
  helps!" — unless the answer was actually a question.
- One "my mistake" per turn maximum. No re-apology on retry.
- Pronouns for self: she/her. Do not volunteer a gender statement.
- Profanity: mirror the user. Never first turn of a session."""


# Block 2 — Voice rules, Ollama variant. Same spine; adds the four
# in-prompt fixes the parity audit (§ 1.1 / 1.4 / 1.5 / 1.8) names as
# qwen3:14b drift mitigations the prompt can carry.
_VOICE_RULES_BLOCK_OLLAMA = """\
Reply rules:
- Default reply: 1-3 short sentences. Long answers only when asked.
- One idea per sentence. Verb-first where it reads naturally.
- No markdown, bullet lists, code blocks, or emoji. Output is spoken
  aloud.
- Hedge only when actually uncertain. "Probably / I think / might" are
  signals, not softeners. Do not stack hedges ("I think it might be
  possibly..."); pick one.
- "I don't know" is a complete answer. Optionally follow with "want me
  to check?" — never with "here's what I'd guess" unless asked to guess.
- Do not open with: "I'd be happy to...", "Great question!", "It seems
  like...", "Let me...", "Sure!", "Of course!", or any identity
  disclaimer ("As an AI...", "As a helpful assistant...", "As a large
  language model..."). Never refer to yourself as an AI, model, or
  assistant — you are Sabrina.
- Do not close with: "Let me know if...", "Does that help?", "Hope this
  helps!" — unless the answer was actually a question.
- One "my mistake" per turn maximum. No re-apology on retry.
- Refusals are character, not capability. Say "I won't" rather than
  "I can't" or "I'm unable to" when the refusal is about who you are.
- Pronouns for self: she/her. Do not volunteer a gender statement.
- Profanity: mirror the user. Never first turn of a session."""


# Refusal-as-character framing (folded under voice, not a separate block)
_REFUSAL_AS_CHARACTER_BLOCK = """\
Some things you won't do because they're not who you are: cheerlead
("you've got this!"), be extra (emoji rain, exclamation-point rain,
"absolutely!"), explain a joke, role-play as a different assistant
(ChatGPT, Siri), or fake memory. Refuse as character — sound like
you wouldn't, not like you can't."""


# Block 3 — Audience register (~70 tok, cached; invalidates on toggle)
_AUDIENCE_BLOCK_A = """\
Current register: A.
- A — Eric alone. Default. Dry, direct. Profanity mirror active.
  Shared-history references natural."""

_AUDIENCE_BLOCK_B = """\
Current register: B.
- B — someone else in the room. Same spine; no shared-history
  references unless Eric introduces them first; profanity off; humor
  dialed down."""

_AUDIENCE_BLOCK_C = """\
Current register: C.
- C — professional mode. Full sentences, no humor, no shared history,
  length budget +1 sentence."""


# Block 5 — Tool-use rules. Reserved; contributes zero tokens until
# tool-use ships per `rebuild/drafts/tool-use-plan.md`.
_TOOL_USE_BLOCK_DEFAULT = ""


# Block 6 — Memory-continuity preamble (~50 tok, always cached)
_MEMORY_CONTINUITY_BLOCK = """\
You have access to a semantic-memory retrieval system. When relevant
earlier turns are appended below, read them as prior context, not
current dialogue. Reference them only when they clarify something.
Never list them back. If nothing is appended, do not invent shared
history. She won't fake memory."""


_AUDIENCE_BLOCKS: dict[str, str] = {
    "A": _AUDIENCE_BLOCK_A,
    "B": _AUDIENCE_BLOCK_B,
    "C": _AUDIENCE_BLOCK_C,
}


_VOICE_RULES_BY_BACKEND: dict[str, str] = {
    "claude": _VOICE_RULES_BLOCK_CLAUDE,
    "ollama": _VOICE_RULES_BLOCK_OLLAMA,
}


def build_system_prompt(
    *,
    register: str = "A",
    backend: Literal["claude", "ollama"] = "claude",
    tool_use_block: str = _TOOL_USE_BLOCK_DEFAULT,
) -> str:
    """Assemble the cacheable head of Sabrina's system prompt.

    Returns the joined persona + voice + register + tool-use + memory
    continuity blocks (no trailing newline). Callers concatenate the
    dynamic retrieval suffix themselves so the cacheable head stays
    byte-stable across turns within a session.

    Args:
        register: "A" (Eric alone, default), "B" (someone else in the
                  room), or "C" (professional mode).
        backend:  "claude" returns the canonical voice-rules block;
                  "ollama" returns the tightened variant per the
                  parity audit.
        tool_use_block: optional block 5 contents. Default empty until
                        tool-use ships.
    """
    if register not in _AUDIENCE_BLOCKS:
        raise ValueError(
            f"Unknown register {register!r}. Expected one of "
            f"{sorted(_AUDIENCE_BLOCKS)}."
        )
    if backend not in _VOICE_RULES_BY_BACKEND:
        raise ValueError(
            f"Unknown backend {backend!r}. Expected one of "
            f"{sorted(_VOICE_RULES_BY_BACKEND)}."
        )
    parts = [
        _PERSONA_BLOCK,
        _VOICE_RULES_BY_BACKEND[backend],
        _REFUSAL_AS_CHARACTER_BLOCK,
        _AUDIENCE_BLOCKS[register],
    ]
    if tool_use_block.strip():
        parts.append(tool_use_block.strip())
    parts.append(_MEMORY_CONTINUITY_BLOCK)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# project_ollama_text — post-process projection layer
# ---------------------------------------------------------------------------


# Regex helpers. Compiled at import time; cheap.
_CLOSING_OFFER_RE = re.compile(
    r"(?:\s*)"
    r"(?:let me know(?:[^.!?]*)?"
    r"|hope (?:this|that) helps"
    r"|does that help"
    r"|hope (?:this|that) makes sense)"
    r"[^.!?]*[.!?]\s*$",
    re.IGNORECASE,
)


_BULLET_LINE_RE = re.compile(r"^\s*[-*•]\s+(.+?)\s*$")
_NUMBERED_LINE_RE = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")


_APOLOGY_RE = re.compile(
    r"\b("
    r"i\s*['']?m\s+sorry"
    r"|my\s+apologies"
    r"|my\s+mistake"
    r"|apologies\s+for"
    r"|sorry(?:,|\s+about|\s+for|\s+again|[.!?])"
    r")",
    re.IGNORECASE,
)


def _strip_closing_offer(text: str) -> str:
    """Drop a final-sentence closing offer if present."""
    return _CLOSING_OFFER_RE.sub("", text).rstrip()


def _dehydrate_lists(text: str) -> str:
    """Collapse bullet/numbered list lines into a comma-joined sentence.

    Conservative: only fires when at least two list-shaped lines are
    contiguous AND the result is not >2x the original length.
    """
    lines = text.splitlines()
    if not lines:
        return text

    out_lines: list[str] = []
    i = 0
    while i < len(lines):
        # Look ahead for a contiguous list run.
        run_items: list[str] = []
        j = i
        while j < len(lines):
            line = lines[j]
            m = _BULLET_LINE_RE.match(line) or _NUMBERED_LINE_RE.match(line)
            if not m:
                break
            run_items.append(m.group(1).strip())
            j += 1
        if len(run_items) >= 2:
            joined = ", ".join(run_items).rstrip(".") + "."
            # Length-guard: only swap in when the dehydrated form is at
            # most 2x the original list-block character count. This
            # catches pathological "items are full sentences each" cases
            # where the comma-joined form would explode.
            original_len = sum(len(lines[k]) for k in range(i, j))
            if len(joined) <= 2 * original_len:
                out_lines.append(joined)
            else:
                out_lines.extend(lines[i:j])
            i = j
        else:
            out_lines.append(lines[i])
            i += 1
    return "\n".join(out_lines)


def _split_sentences(text: str) -> list[str]:
    """Split on .!? followed by whitespace or end-of-string. Preserves
    punctuation. Empty trailing fragment dropped.
    """
    pattern = re.compile(r"(?<=[.!?])\s+")
    parts = pattern.split(text.strip())
    return [p for p in parts if p.strip()]


_APOLOGY_LEAD_RE = re.compile(
    r"^\s*("
    r"i\s*['']?m\s+sorry"
    r"|sorry"
    r"|my\s+apologies"
    r"|my\s+mistake"
    r"|apologies"
    r")"
    r"(?:[^,.!?]*)"  # any trailing apology-clause modifiers ("again", "for that")
    r"(?:[,.!?]\s*|\s+)",
    re.IGNORECASE,
)


def _strip_leading_apology(sentence: str) -> str:
    """Remove a leading apology clause from ``sentence``; capitalize
    the remainder. Returns "" if the whole sentence is just an apology.
    """
    stripped = _APOLOGY_LEAD_RE.sub("", sentence, count=1)
    stripped = stripped.lstrip()
    if not stripped:
        return ""
    # Capitalize the first remaining char (was preceded by apology lead).
    return stripped[0].upper() + stripped[1:]


def _dedup_apologies(text: str) -> str:
    """If >1 apology phrases appear in the turn, keep only the first.

    Sentence-granular with surgical strip on subsequent matches:
      - First apology sentence: kept verbatim.
      - Subsequent apology sentences: try to strip the leading apology
        clause; keep the trailing non-apology content if present;
        drop the sentence if nothing remains.
    Non-apology sentences are kept verbatim.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return text

    apology_count = sum(1 for s in sentences if _APOLOGY_RE.search(s))
    if apology_count <= 1:
        return text

    seen_apology = False
    kept: list[str] = []
    for s in sentences:
        if _APOLOGY_RE.search(s):
            if not seen_apology:
                kept.append(s)
                seen_apology = True
            else:
                # Try to surgically strip the apology lead and keep
                # the remainder (e.g. "Sorry again, here goes." ->
                # "Here goes."). If nothing remains, drop the sentence.
                tail = _strip_leading_apology(s)
                if tail:
                    kept.append(tail)
                # else: drop entirely
        else:
            kept.append(s)
    return " ".join(kept)


_WANT_MORE_TAIL = " Want more?"


def _truncate_long_replies(text: str, *, prior_user_chars: int | None) -> str:
    """If reply is >4 sentences AND prior user message was short
    (proxy for "didn't ask for detail"), truncate to 3 sentences plus
    " Want more?".

    A None prior_user_chars value disables truncation (callers that
    don't know prior context should not gate the rule).
    """
    if prior_user_chars is None or prior_user_chars >= 60:
        return text
    sentences = _split_sentences(text)
    if len(sentences) <= 4:
        return text
    head = " ".join(sentences[:3])
    if head.endswith(("?", "!", ".")):
        return head + _WANT_MORE_TAIL
    return head + "." + _WANT_MORE_TAIL


def project_ollama_text(
    text: str,
    *,
    strip_closing_offer: bool = True,
    dehydrate_lists: bool = True,
    dedup_apologies: bool = True,
    truncate_long_replies: bool = True,
    prior_user_chars: int | None = None,
) -> str:
    """Apply the Ollama-only projection rules to ``text``.

    Each rule is independently gated. Default = all on. ``OllamaBrain``
    reads ``[brain.persona]`` config and unpacks the bools to these
    kwargs; callers wanting raw Ollama text construct
    ``OllamaBrain(project=False)`` instead of zeroing every rule here.

    ``prior_user_chars`` is the proxy for the truncation rule's
    "didn't ask for detail" gate. Pass the ``len(user_message)`` from
    the immediately-preceding user turn; ``None`` disables truncation.
    """
    if not text:
        return text
    out = text
    if dehydrate_lists:
        out = _dehydrate_lists(out)
    if dedup_apologies:
        out = _dedup_apologies(out)
    if strip_closing_offer:
        out = _strip_closing_offer(out)
    if truncate_long_replies:
        out = _truncate_long_replies(out, prior_user_chars=prior_user_chars)
    return out


# ---------------------------------------------------------------------------
# Module-level convenience constants — back-compat with brain/claude.py
# ---------------------------------------------------------------------------


SABRINA_SYSTEM_PROMPT_CLAUDE: str = build_system_prompt(register="A", backend="claude")
SABRINA_SYSTEM_PROMPT_OLLAMA: str = build_system_prompt(register="A", backend="ollama")


__all__ = [
    "SABRINA_SYSTEM_PROMPT_CLAUDE",
    "SABRINA_SYSTEM_PROMPT_OLLAMA",
    "build_system_prompt",
    "project_ollama_text",
]
