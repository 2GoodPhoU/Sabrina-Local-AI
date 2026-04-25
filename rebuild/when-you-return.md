# When you return — Sabrina rebuild quickstart

**Date:** 2026-04-24
**Purpose:** single entry-point for starting a new chat session. Read this
first. Then act.

## State of play

Decisions 007, 008, and 009 are committed on this branch:

- **007 (semantic memory)** — Windows-validated 2026-04-24, first-audio
  1.62 s warm.
- **008 (foundational refactor bundle)** — `[schema].version` hook +
  redacting structlog processor + rotating file sink. Tests green
  (52 passed); committed.
- **009 (barge-in)** — Silero VAD + `CancelToken` threading through
  `Brain.chat` and `Speaker.speak`, wired into the voice loop's
  speaking state with `pending_barge_audio` to hand the captured audio
  back to the next turn. Committed at `f22cd73`.
- **009a (barge-in thin-spot patches)** — four of the five thin spots
  from decision 009 closed in-tree per `rebuild/drafts/009a-thin-spots-plan.md`:
  graceful-degrade on Silero load (`_make_barge_in_vad` helper, logs
  `vad.unavailable`), trim-to-VAD-start in `AudioMonitor.stop()` with a
  150 ms pre-fire margin, per-frame `vad.prob` DEBUG log, and Piper
  cancel poll tightened 30 ms → 10 ms. 59 tests green (was 57).
  Footnoted on decision 009; no new decision doc. **Not yet committed**
  — Eric runs `pre-commit install` + `git commit` on his Windows box.

**Next up: validation.** Decision 009 (now including the 009a patches)
is not yet end-to-end validated on real hardware; `[barge_in].enabled`
ships as `false` until `rebuild/validate-barge-in.md` passes.

## First-time-you-sit-down sequence

**Step 1 — Smoke 009 + 009a in-repo.** From `sabrina-2/`:

```powershell
uv sync                        # picks up silero-vad>=5.1
uv run pytest -q               # expect 59 passed, 0 skipped (57 pre-009a)
```

If pytest passes, the code is sound. If anything fails, skip to the
"If 009 smoke fails" table at the bottom.

**Step 2 — Commit the 009a bundle.** Changes are already in the
working tree (see `git status`):

- `sabrina-2/src/sabrina/listener/vad.py` — `_PRE_FIRE_MARGIN_MS`
  constant, `SileroVAD.speech_window_samples` property, `vad.prob`
  DEBUG log, `AudioMonitor._fire_at_samples` + trimmed `stop()`.
- `sabrina-2/src/sabrina/voice_loop.py` — new `_make_barge_in_vad`
  module-level helper (graceful-degrade); inline wiring simplified to
  a one-liner.
- `sabrina-2/src/sabrina/speaker/piper.py` — poll `sleep(0.03)` →
  `sleep(0.01)`.
- `sabrina-2/tests/test_smoke.py` — `test_make_barge_in_vad_degrades_on_load_failure`
  + `test_audio_monitor_trims_capture_to_speech_onset`. 57 → 59.
- `rebuild/decisions/009-barge-in-shipped.md` — 009a footnote at the
  top of "Thin spots."
- `rebuild/when-you-return.md` — this file; state-of-play refreshed
  and the thin-spots section pruned.

Before committing, run from Eric's Windows box (pre-commit install was
deferred for this session — still need to `--no-verify`):

```powershell
cd sabrina-2
uv add --dev pre-commit
uv run pre-commit install   # unblocks normal `git commit` going forward
uv run pytest -q            # must report 59 passed
cd ..
git add sabrina-2/src/sabrina/listener/vad.py `
        sabrina-2/src/sabrina/voice_loop.py `
        sabrina-2/src/sabrina/speaker/piper.py `
        sabrina-2/tests/test_smoke.py `
        rebuild/decisions/009-barge-in-shipped.md `
        rebuild/when-you-return.md `
        rebuild/drafts/009a-thin-spots-plan.md
git commit -m "fix: barge-in thin-spots (graceful degrade, VAD log, trim, poll tighten) - 009a footnote"
```

(If `pre-commit install` is still deferred, swap the `git commit` for
`git commit --no-verify`.)

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

## If 009 smoke fails

| Symptom | Likely cause | What to check |
|---|---|---|
| `ImportError: silero_vad` during pytest collection | `uv sync` skipped the dep | `uv pip list \| findstr silero` |
| `test_cancel_token_*` fails | Protocol addition regressed | Diff `brain/protocol.py` against decision 009 doc |
| `test_vad_state_machine_ignores_below_min_speech_ms` fails | Speech-samples reset logic broken in `SileroVAD.feed` | Re-read `listener/vad.py:80-100` |
| Voice loop crashes on start with barge-in off | Import-time side effect in `listener/vad.py` | Lazy-load `silero_vad` inside `_ensure_loaded` only |
| `uv run pytest` uses wrong venv | Windows console-script stub baked in old path | `Remove-Item .venv -Recurse -Force; uv sync` |

## Sandbox-mount sanity check (do this BEFORE any code edits)

The Edit tool was observed silently failing to propagate file writes
on 2026-04-24 (memory: `feedback_edit_tool_propagation.md`). Before
trusting any in-session edits, from `Sabrina-Local-AI/`:

```powershell
git status   # expect: clean working tree, ?? rebuild/drafts/009a-thin-spots-plan.md
```

Then pick one tracked file and compare its line count to git:

```powershell
git show HEAD:rebuild/when-you-return.md | wc -l   # compare to actual file
```

If they match, the mount is healthy. If not, see
`memory/sabrina_repo_location_corruption.md` for the
`Move-Item`-out-of-`Documents\` remediation. **Use the `Write` tool,
not `Edit`, until you've confirmed the mount is healthy this session.**

## Where everything lives

```
rebuild/
├── ROADMAP.md                              # roadmap + progress-at-a-glance
├── decisions/001–009-*.md                  # shipped decisions
├── validate-*.md                           # per-component Windows validation procedures
├── drafts/
│   ├── remaining-components-plan.md        # master planning index
│   ├── 009a-thin-spots-plan.md             # CURRENT: signed-off, ready to implement
│   ├── *-plan.md                           # per-component plans
│   └── avatar-animation-graph.svg
sabri