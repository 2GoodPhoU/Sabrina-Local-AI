"""Personality eval substrate (decision 010 follow-up).

Three tiers, two of which ship here:

* Tier 1 — `test_regex_smokes.py`: pytest-marked `personality_fast` regex
  pattern checks per failure mode. Runs in seconds, no API call. Catches
  ~5 of the 12 documented failure modes (sycophant slip, customer-
  service voice, identity disclaimers, em-dash vomit, list-vomit).

* Tier 2 — invoked via `sabrina personality-eval` CLI verb. Plumbing is
  in place; the actual judge call is left as a TODO so Eric runs it
  manually with his API key (per the overnight-prompt's "wire the CLI
  plumbing + judge-prompt template + structured output parsing" scope).

* Tier 3 (golden-set comparison on system-prompt change) — TODO,
  documented in the test docstring; not implemented this session.

See `rebuild/drafts/research/2026-04-26-personality-eval-framework.md`.
"""
