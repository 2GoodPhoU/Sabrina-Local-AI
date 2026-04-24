# When you return — Sabrina rebuild quickstart

**Date:** 2026-04-24
**Purpose:** single entry-point for starting a new chat session. Read this
first. Then act.

## State of play

Decisions 007 and 008 are validated and committed on this branch:

- **007 (semantic memory)** — Windows-validated 2026-04-24, first-audio
  1.62 s warm.
- **008 (foundational refactor bundle)** — `[schema].version` hook +
  redacting structlog processor + rotating file sink. Tests green
  (52 passed); committed.

**Decision 009 (barge-in)** is the current tip. Silero VAD + a
`CancelToken` threading through `Brain.chat` and `Speaker.speak`,
wired into the voice loop's speaking state with `pending_barge_audio`
to hand the captured audio back to the next turn. Five new unit tests
(57 total; suite green in ~3 s). **Not yet end-to-end validated on
real hardware** — `[barge_in].enabled` ships as `false` until the
`rebuild/validate-barge-in.md` procedure passes.

## First-time-you-sit-down sequence

**Step 1 — Smoke 009 in-repo.** From `sabrina-2/`:

```powershell
uv sync                        # picks up silero-vad>=5.1
uv run pytest -q               # expect 57 passed, 0 skipped
```

If pytest passes, the code is sound. If anything fails, skip to the
"If 009 smoke fails" table at the bottom.

**Step 2 — Commit 009.** Bundle the barge-in files + the doc updates:

```powershell
git add src/sabrina/brain/protocol.py src/sabrina/brain/claude.py src/sabrina/brain/ollama.py `
        src/sabrina/speaker/protocol.py src/sabrina/speaker/piper.py src/sabrina/speaker/sapi.py `
        src/sabrina/listener/vad.py src/sabrina/listener/__init__.py `
        src/sabrina/voice_loop.py src/sabrina/events.py src/sabrina/config.py `
        sabrina.toml pyproject.toml uv.lock tests/test_smoke.py `
        ..\rebuild\decisions\009-barge-in-shipped.md ..\rebuild\ROADMAP.md ..\rebuild\when-you-return.md
git status   # verify — nothing else unexpected
git commit --no-verify -m "feat: barge-in (Silero VAD + CancelToken through Brain/Speaker) — decision 009"
```

**Step 3 — Validate 009 on real hardware.** Run
`rebuild/validate-barge-in.md` top-to-bottom. Nine steps, each with a
success signal and a failure-triage row. If all green, bump the
`ROADMAP.md` "Status" line per the doc's final section and commit
(`validate: barge-in on Windows (M ms cut, T threshold)`).

If validation uncovers a bug that's not worth its own decision (e.g.
cancel-token check too coarse in Piper), fix in-place and annotate the
decision 009 doc with a "validation revealed X, fixed in commit Y"
footnote. Anti-sprawl.

**Step 4 — Pick next component.** Menu from decision 009's tail:

- **Infra-first path:** wake-word → supervisor+autostart. Wake-word
  reuses the `AudioMonitor` primitive shipped this session; supervisor
  is OS-level, no audio.
- **Character-first path:** personality → onboarding. Lock voice before
  the avatar arc. Personality plan's "inferred vs. stated" section
  needs Eric input before any code lands.

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

`rebuild/drafts/personality-plan.md` has a "Where these signals came
from — explicit vs. assumed" section. The voice was **inferred** from
anti-sprawl premise and decision-doc tone rather than stated by Eric.
Calibrate that section with Eric before shipping — upstream of every
brain prompt and the avatar cue track, so drift here is expensive.

## Thin spots from decision 009 worth tracking

- **No log-and-degrade for silero-vad import.** A broken install crashes
  the voice loop on first speaking phase. Mirror semantic memory's
  `_try_enable_vec` graceful-degrade pattern.
- **`AudioMonitor` captures TTS bleed before user speech.** On
  `continue_on_interrupt`, whatever audio was buffered (potentially
  including Sabrina's own voice) gets re-transcribed. Whisper usually
  handles it, but on a speakerphone setup it's garbage. Trim-to-VAD-start
  or document "headset required" based on what validation shows.
- **No per-frame VAD probability logging.** Tuning `threshold` during
  step 7 of the validation is blind without a DEBUG path that logs
  `vad.prob`. Trivial addition.
- **Speaker cancellation granularity is per-sentence.** If Piper is mid-
  synth on a long sentence, the cancel has to wait for synth to finish
  before stop() can interrupt playback. ~1 s worst case.
- `pre-commit` hook not installed in venv (still bypassed with
  `--no-verify`). Cheap fix: `uv add --dev pre-commit && uv run
  pre-commit install`.

## If 009 smoke fails

| Symptom | Likely cause | What to check |
|---|---|---|
| `ImportError: silero_vad` during pytest collection | `uv sync` skipped the dep | `uv pip list \| findstr silero` |
| `test_cancel_token_*` fails | Protocol addition regressed | Diff `brain/protocol.py` against decision 009 doc |
| `test_vad_state_machine_ignores_below_min_speech_ms` fails | Speech-samples reset logic broken in `SileroVAD.feed` | Re-read `listener/vad.py:80-100` |
| Voice loop crashes on start with barge-in off | Import-time side effect in `listener/vad.py` | Lazy-load `silero_vad` inside `_ensure_loaded` only |
| `uv run pytest` uses wrong venv | Windows console-script stub baked in old path | `Remove-Item .venv -Recurse -Force; uv sync` |

## Where everything lives

```
rebuild/
├── ROADMAP.md                              # roadmap + progress-at-a-glance
├── decisions/001–009-*.md                  # shipped decisions
├── validate-*.md                           # per-component Windows validation procedures
├── drafts/
│   ├── remaining-components-plan.md        # master planning index
│   ├── *-plan.md                           # per-component plans
│   └── avatar-animation-graph.svg
sabrina-2/
├── README.md                               # current-state README (read this before diving)
├── src/sabrina/                            # the code
└── tests/test_smoke.py                     # all 57 tests
CLAUDE.md                                   # Claude-agent bootstrap (repo root)
```

## If you're a new Claude assistant reading this

1. Read `CLAUDE.md` at the repo root first — it has the short-form
   bootstrap, working-style cues, and pointers to everything else.
2. Read the memory index (`MEMORY.md`) and the files it links.
3. Read `sabrina-2/README.md` for the current-state component snapshot.
4. Read `rebuild/drafts/remaining-components-plan.md` for the master
   planning index.
5. Don't ask Eric to re-explain context that's in memory, `CLAUDE.md`,
   or the master index.

## Working-style reminders

- **Decision doc per shipped component.** Match the voice of 002–009:
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
- **Additive protocol extensions** over new protocols — `Message.images`,
  `system_suffix`, and now `cancel_token` are the patterns.
- **Memory guardrails.** Don't save code patterns, git history, or
  conventions derivable from the repo. Do save surprises, corrections,
  and validated non-obvious calls.
