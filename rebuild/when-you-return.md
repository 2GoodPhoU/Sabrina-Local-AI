# When you return — Sabrina rebuild quickstart

**Date:** 2026-04-25 (refreshed end-of-day after pass 2)
**Purpose:** single entry-point for starting a new chat session. Read this
first. Then act.

> **Open [`rebuild/ACTION_ITEMS.md`](ACTION_ITEMS.md) right after this doc** —
> it's the consolidated punch list for everything in the working tree
> (Tracks A + B + tonight's pass 2). One file, one source of truth.

## State of play

Decisions 007, 008, 009, and the 009a thin-spots bundle are committed.
Barge-in is `enabled = true` in `sabrina.toml`.

- **007 (semantic memory)** — Windows-validated 2026-04-24, first-audio
  1.62 s warm.
- **008 (foundational refactor bundle)** — `[schema].version` hook +
  redacting structlog processor + rotating file sink. Tests green.
- **009 (barge-in)** — Silero VAD + `CancelToken` threading through
  `Brain.chat` and `Speaker.speak`, wired into the voice loop's
  speaking state with `pending_barge_audio` to hand the captured audio
  back to the next turn. **Validated 2026-04-25** on the
  i7-13700K/4080: 264 ms cut latency, threshold 0.5 holds against
  keyboard/mouse noise, no first-audio regression.
- **009a (barge-in thin-spots)** — graceful-degrade on Silero load
  failure, trim-to-VAD-start in `AudioMonitor.stop()`, per-frame
  `vad.prob` DEBUG log, Piper cancel poll tightened to 10 ms.
  Footnoted on decision 009; 59 tests green pre-overnight.

## Working tree — uncommitted (Track B + pass 2)

Track B ran four steps sequentially while Eric slept (2026-04-25).
Pass 2 (later same day) added the ONNX embedder swap, voice-loop
wake-word + summary-injection wiring, brain-backed `memory-compact`
CLI verb, GUI shell-out buttons, GUI Phase-0 fixes, and an
MCP-compatibility audit. Everything is in the working tree,
**uncommitted** — see `ACTION_ITEMS.md` for the per-unit table (B0-B4
+ C0-C8) and suggested commit slicing.

| Step | What landed | Files |
|---|---|---|
| 0 | Cleanup: deduped 008 decision file + refreshed this doc | `rebuild/decisions/008-foundational-refactor-shipped.md` (now a redirect stub — `git rm` it), `rebuild/when-you-return.md` |
| 1 | Logging-vocabulary completion: canonical `component.action[.detail]`, `turn_id` contextvar correlation, pre-declared event names in plan | `sabrina-2/src/sabrina/listener/faster_whisper.py`, `sabrina-2/src/sabrina/listener/record.py`, `sabrina-2/src/sabrina/voice_loop.py`, `sabrina-2/tests/test_smoke.py` |
| 2 | Wake-word scaffolding (openWakeWord placeholder model `hey_jarvis`) reusing `AudioMonitor` primitive | `sabrina-2/src/sabrina/listener/wake_word.py` (new), `sabrina-2/sabrina.toml`, `sabrina-2/src/sabrina/config.py`, `sabrina-2/pyproject.toml`, `sabrina-2/tests/test_smoke.py` |
| 3 | Supervisor + autostart: Task Scheduler XML generator + nssm service path + crash-budget restart loop | `sabrina-2/src/sabrina/supervisor.py` (new), `sabrina-2/src/sabrina/cli.py`, `sabrina-2/sabrina.toml`, `sabrina-2/src/sabrina/config.py`, `sabrina-2/tests/test_smoke.py` |
| 4 | 007b: semantic-memory GUI panel + token-based auto-compaction with summary-skip flag | `sabrina-2/src/sabrina/memory/store.py`, `sabrina-2/src/sabrina/memory/compaction.py` (new), `sabrina-2/src/sabrina/gui/settings.py`, `sabrina-2/sabrina.toml`, `sabrina-2/src/sabrina/config.py`, `sabrina-2/tests/test_smoke.py` |

Full per-unit detail + Eric's morning todo list (in suggested order):
[`rebuild/ACTION_ITEMS.md`](ACTION_ITEMS.md). The earlier
`ACTION_ITEMS_code.md` and `ACTION_ITEMS_personality.md` files are
now redirect stubs — `git rm` both during cleanup.

## First-time-you-sit-down sequence

**Step 1 — Sanity-check the overnight diffs.** From `Sabrina-Local-AI/`:

```powershell
git status
git diff --stat
```

Expect a substantial working-tree delta across `sabrina-2/` plus
`rebuild/decisions/008-foundational-refactor-shipped.md` (the dedup
stub) and the new `rebuild/ACTION_ITEMS_code.md`. The duplicate decision
file should also be `git rm`-ed during your first commit.

**Step 2 — Run tests per step.** From `sabrina-2/`:

```powershell
uv sync                # picks up openwakeword>=0.6
uv run pytest -q
```

Expected: 59 → ~70 tests passing. Per-step failure modes are catalogued
in `ACTION_ITEMS_code.md`.

**Step 3 — Commit per step.** Each step is a self-contained
commit-equivalent unit. Recommended order:

1. Step 0 cleanup commit — dedup file + this doc.
2. Step 1 logging-vocabulary commit.
3. Step 2 wake-word commit.
4. Step 3 supervisor commit.
5. Step 4 memory-GUI + auto-compaction commit.

**Step 4 — Validate per component.** Each step's `validate-*.md` doc
is the gating procedure for stamping its decision doc:

- Step 2: `rebuild/validate-wake-word.md` (see `wake-word-plan.md`).
- Step 3: `rebuild/validate-supervisor-autostart.md`.
- Step 4: `rebuild/validate-memory-gui.md` (see
  `semantic-memory-gui-plan.md`).

Step 1 has no validate doc — it's a refactor; the test suite gates it.

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

`rebuild/drafts/personality-plan.md` has a "Where these signals came
from — explicit vs. assumed" section. Track A may have rewritten parts
of this overnight; check `rebuild/ACTION_ITEMS_personality.md` first.
Voice was **inferred** rather than stated — calibrate before shipping.

## Sandbox-mount sanity check (do this BEFORE any code edits)

Edit and Write tools have been observed silently truncating large
files on this mount (memory: `feedback_write_tool_also_truncates.md`).
Before trusting any in-session edits, from `Sabrina-Local-AI/`:

```powershell
git status
git show HEAD:rebuild/when-you-return.md | wc -l   # compare to actual file
```

If they match, the mount is healthy. **Use bash + python3 heredocs for
any non-trivial edit (>1 KB) instead of Edit/Write.**

## Where everything lives

```
rebuild/
├── ROADMAP.md                              # roadmap + progress-at-a-glance
├── ACTION_ITEMS.md                         # consolidated punch list (Tracks A+B + pass 2)
├── decisions/001-009-*.md                  # shipped decisions
├── validate-*.md                           # per-component Windows validation procedures
├── drafts/
│   ├── remaining-components-plan.md        # master planning index
│   ├── *-plan.md                           # per-component plans
│   └── avatar-animation-graph.svg
sabrina-2/                                  # the code
└── src/sabrina/                            # brain/, listener/, speaker/, memory/,
                                            # vision/, gui/, voice_loop.py, supervisor.py
```
