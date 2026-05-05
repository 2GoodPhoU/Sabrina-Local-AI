"""Tier 1 personality eval: regex/string smokes per failure mode.

Per ``rebuild/drafts/research/2026-04-26-personality-eval-framework.md``,
this catches roughly 5 of the 12 failure modes for free (no API call):
sycophant slip, customer-service voice creep, identity disclaimers,
em-dash vomit, list-vomit. The remaining seven (opinion flattening,
refusal verbosity, hedging-as-softener, apology inflation,
mode-bleed, memory fabrication, closing-question inflation) need
LLM-as-judge scoring — that's tier 2 (see ``cli.py::personality_eval``).

Runs in milliseconds. Suitable as a pre-commit / pre-push hook gate.
Mark with ``personality_fast`` so it can be selected via
``pytest -m personality_fast`` once the marker is registered in
pyproject.toml — the regex tests below are also discovered by the
default ``pytest`` invocation, so commit-time coverage is automatic.

Tier 3 (golden-set comparison on system-prompt change) — TODO. The
current snapshot test in ``tests/test_smoke.py`` is the placeholder
for that until the harness lands.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Apply the personality_fast marker to every test in this module so
# `pytest -m personality_fast` selects them all without per-test annotation.
pytestmark = pytest.mark.personality_fast


# Patterns per failure mode. Each is case-insensitive; matches anywhere
# in the response. Comments explain why each phrase counts.
_PATTERNS: dict[str, list[str]] = {
    "sycophant_slip": [
        r"\bgreat question\b",
        r"\bwhat a (?:great|fun|interesting) (?:question|request|idea)\b",
        r"\bI'?d love to help\b",
        r"\bhappy to help\b",
    ],
    "customer_service": [
        r"\bI'?d be happy to\b",
        r"\bof course[!.]",   # "Of course!" affirmation opener
        r"\blet me know if\b",
        r"\bhope (?:this|that) helps\b",
        r"\bis there anything else\b",
    ],
    "identity_disclaimer": [
        r"\bas an AI\b",
        r"\bas a (?:helpful|language) (?:assistant|model)\b",
        r"\bI'?m (?:just )?(?:an AI|a language model)\b",
        r"\bI don'?t have (?:personal )?(?:opinions|feelings|preferences) (?:as|because)\b",
    ],
    "em_dash_vomit": [
        # >= 3 em-dashes anywhere in a single response is the cap; the
        # plan allows one sparingly. Two is borderline; three is a fail.
        r"(?:.*—.*){3,}",
    ],
    "list_vomit": [
        # Markdown bullets at line start.
        r"(?m)^\s*[-*]\s",
        # Numbered list at line start.
        r"(?m)^\s*\d+[.)]\s",
        # Markdown header at line start.
        r"(?m)^\s*#{1,6}\s",
    ],
    "closing_question_inflation": [
        r"\bdoes that help\??$",
        r"\bdoes that make sense\??$",
        r"\banything else\??$",
    ],
}


def _matches(text: str, mode: str) -> list[str]:
    """Return every pattern from `mode` that matches `text`. Empty if clean."""
    hits: list[str] = []
    for pat in _PATTERNS[mode]:
        if re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE):
            hits.append(pat)
    return hits


# ---- positive tests: known-bad strings must trip every relevant axis ----


def test_sycophant_slip_pattern_matches_canonical_offender():
    bad = "Great question! Let me think about that for you."
    hits = _matches(bad, "sycophant_slip")
    assert hits, f"expected sycophant_slip to fire on {bad!r}"


def test_customer_service_pattern_matches_canonical_offender():
    bad = "I'd be happy to help with that. Let me know if you need anything else!"
    assert _matches(bad, "customer_service")


def test_identity_disclaimer_pattern_matches_canonical_offender():
    bad = "As an AI, I cannot share my personal opinion."
    assert _matches(bad, "identity_disclaimer")


def test_em_dash_vomit_fires_on_three_dashes():
    bad = "It's small — fast — sturdy — clean."
    assert _matches(bad, "em_dash_vomit")


def test_em_dash_vomit_does_not_fire_on_one_dash():
    ok = "It's small — but sturdy."
    assert _matches(ok, "em_dash_vomit") == []


def test_list_vomit_pattern_matches_bullets_and_headers():
    bad = "Here are your options:\n- foo\n- bar\n- baz"
    assert _matches(bad, "list_vomit")
    bad2 = "## Options\n1) foo\n2) bar"
    assert _matches(bad2, "list_vomit")


def test_closing_question_inflation_matches_canonical_offender():
    bad = "Right click the file and choose Properties. Does that help?"
    assert _matches(bad, "closing_question_inflation")


# ---- negative tests: known-good strings must trip nothing ----


def test_clean_short_reply_trips_nothing():
    good = "3:42."
    for mode in _PATTERNS:
        assert _matches(good, mode) == [], f"{mode} false-positive on {good!r}"


def test_directional_pushback_trips_nothing():
    good = "audio_ring.py — it's a ring buffer and you'll forget it's audio-specific otherwise."
    for mode in _PATTERNS:
        # The single em-dash is allowed; bullets / phrases must stay clean.
        assert _matches(good, mode) == [], f"{mode} false-positive on {good!r}"


def test_genuine_uncertainty_does_not_trip_hedging_smoke():
    # We don't pattern-match hedging here (LLM-judge job), so this just
    # documents the intentional false-negative gap.
    text = "I'm not sure — could be either. Want me to look it up?"
    # No regex axis should flag this.
    triggers = {m: _matches(text, m) for m in _PATTERNS}
    only = {k: v for k, v in triggers.items() if v}
    assert only == {}, f"unexpected trips: {only}"


# ---- golden-set sanity: file loads and shape is well-formed ----


def test_golden_set_yaml_loads_and_has_thirty_entries():
    yaml = pytest.importorskip("yaml")
    path = Path(__file__).parent / "golden_set.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 30
    # Each entry has required keys.
    for entry in data:
        assert "id" in entry and entry["id"].startswith("g")
        assert "prompt" in entry
        assert entry.get("register") in {"A", "B", "C"}
        assert "axes" in entry and isinstance(entry["axes"], list)


def test_golden_set_axes_are_valid():
    """Every axis named in the golden set must exist in the canonical
    failure-mode list (else the rubric loses coverage silently)."""
    yaml = pytest.importorskip("yaml")
    path = Path(__file__).parent / "golden_set.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    valid = {
        "sycophant_slip",
        "customer_service",
        "identity_disclaimer",
        "em_dash_vomit",
        "list_vomit",
        "closing_question_inflation",
        "hedging_inflation",
        "apology_inflation",
        "opinion_flattening",
        "refusal_verbosity",
        "memory_fabrication",
        "mode_bleed",
    }
    for entry in data:
        bad = set(entry["axes"]) - valid
        assert not bad, f"entry {entry['id']} names unknown axes: {bad}"


def test_golden_set_register_distribution_close_to_target():
    """Plan target: 60% A, 25% B, 15% C. Allow +/- 15% for a 30-prompt set."""
    yaml = pytest.importorskip("yaml")
    path = Path(__file__).parent / "golden_set.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    n = len(data)
    counts = {"A": 0, "B": 0, "C": 0}
    for e in data:
        counts[e["register"]] += 1
    a_pct = counts["A"] / n
    assert 0.45 <= a_pct <= 0.75, f"register A coverage {a_pct:.2f} off target 0.60"
    b_pct = counts["B"] / n
    assert 0.10 <= b_pct <= 0.40, f"register B coverage {b_pct:.2f} off target 0.25"
    c_pct = counts["C"] / n
    assert 0.05 <= c_pct <= 0.30, f"register C coverage {c_pct:.2f} off target 0.15"
