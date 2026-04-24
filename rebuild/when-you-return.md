# When you return — Sabrina rebuild quickstart

**Date:** 2026-04-23
**Purpose:** single entry-point for starting a new chat session. Read this
first. Then act.

## State of play

Decision 007 (semantic memory) is shipped in-tree but **awaiting Windows
validation** on Eric's box. Eight component plans are drafted and queued
behind that validation — none ship until 007 is green. Three cross-cutting
plans (privacy posture, config-schema audit, logging vocabulary) all
converge on the same ~150-line foundational refactor, which is the
highest-leverage next session once 007 clears. Ship-one-before-next
guardrail is in force.

## First-time-you-sit-down sequence

**Step 1 — Validate 007.** Run `rebuild/validate-007-windows.md`
top-to-bottom from `sabrina-2/`. If step 0 or step 4 fails
(`enable_load_extension` missing, or sqlite-vec load fails), fill in
`rebuild/drafts/008-sqlite-vec-on-windows.md` and promote to
`rebuild/decisions/008-*.md`. If it passes, delete or archive 008.

**Step 2 — Foundational refactor (~150 lines, 3 tests).** Land all three
of these in one session. Each plan below cross-references the bundle:

- `[schema] version = 1` block + empty migration chain in `config.py` /
  `sabrina.toml` — source: `rebuild/drafts/config-schema-audit.md`.
- Redacting structlog processor + 512-char value cap in
  `sabrina/logging.py` — source: `rebuild/drafts/privacy-posture-plan.md`
  (closes gap G1).
- Rotating file sink for `logs/sabrina.log` (5 MB × 3) — source:
  `rebuild/drafts/logging-vocabulary-plan.md` (closes gap G2).

Unlocks privacy/config/logging plans at once and removes the repeated
"…once the logging/config refactor happens" caveat from every downstream
draft.

**Step 3 — Pick next component.** Natural dependency ordering from the
master index:

- **Infra-first path:** barge-in → wake-word → supervisor+autostart.
  Shared `AudioMonitor` primitive between barge-in and wake-word is why
  they belong adjacent.
- **Character-first path:** personality → onboarding. Ship voice + first-run
  state machine before more infra if Eric wants character locked in before
  the avatar arc starts.

Don't prescribe. Ask Eric which path; both are ready.

## Decisions awaiting glance-and-approve

Recommendation blocks attached; Eric just needs to eyeball:

- `rebuild/drafts/router-plan.md` — brain router (3 questions).
- `rebuild/drafts/tool-use-plan.md` — Brain protocol tools (3 questions).
- `rebuild/drafts/asr-upgrade-plan.md` — `base.en` → `large-v3-turbo`
  (2 questions).
- `rebuild/drafts/local-vlm-plan.md` — Ollama-hosted VLM (2 questions).
- `rebuild/drafts/vision-polish-plan.md` — no-VLM capture polish
  (1 question).

## Personality plan — calibration callout

`rebuild/drafts/personality-plan.md` has a "Where these signals came from
— explicit vs. assumed" section (line 67). The voice was **inferred**
from anti-sprawl premise and decision-doc tone rather than stated by
Eric. Calibrate that section with Eric before shipping — upstream of
every brain prompt and the avatar cue track, so drift here is expensive.

## Where everything lives

```
rebuild/
├── ROADMAP.md                              # roadmap + progress-at-a-glance
├── decisions/001–007-*.md                  # shipped decisions
├── validate-*.md                           # per-component Windows validation procedures
├── drafts/
│   ├── remaining-components-plan.md        # master planning index — primary entry for all plans
│   ├── *-plan.md                           # per-component plans (supervisor, wake, barge, budget, etc.)
│   ├── avatar-animation-graph.svg          # presence animation graph
│   ├── 008-sqlite-vec-on-windows.md        # contingency stub for 007 fallback
│   └── old-repo-migration-audit.md         # pre-rebuild codebase audit
```

## If you're a new Claude assistant reading this

1. Read `/sessions/blissful-charming-galileo/mnt/.auto-memory/MEMORY.md`
   and the three linked files (user, feedback, project_sabrina,
   project_sabrina_architecture).
2. Read `rebuild/drafts/remaining-components-plan.md` — the master
   index. Everything component-shaped branches from there.
3. Follow Eric's working style below. Don't ask him to re-explain
   context that's in memory or the master index.

## Working-style reminders

- **Decision doc per shipped component.** Match the voice of 002–007:
  terse prose, bullets sparingly, "thin spots" section at end,
  alternatives-to-research list.
- **Anti-sprawl.** No new abstraction until the second caller exists.
  No module past 300 lines without justification in the header.
- **Ship-one-validate-next.** No component starts until the previous
  one is in main with a smoke test.
- **Validation procedure** (`validate-*.md`) ships with each component
  before Eric calls it done on Windows.
- **Recommendations-attached pattern** for drafts with open questions
  — rationale + override path makes review cheap.
- **Additive protocol extensions** over new protocols — `Message.images`
  and `system_suffix` are the patterns.
- **Memory guardrails.** Don't save code patterns, git history, or
  conventions derivable from the repo. Do save surprises, corrections,
  and validated non-obvious calls.
