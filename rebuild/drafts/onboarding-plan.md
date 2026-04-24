# Onboarding plan — fresh-install first-run experience

**Date:** 2026-04-23
**Status:** Draft. Open-questions block below; everything under it is
settled pending review.
**Prerequisites (all drafted):** `wake-word-plan.md`, `supervisor-
autostart-plan.md`, `automation-plan.md`. Onboarding wraps their
individual setup CLIs into one coherent first-run flow; it does not
add new runtime capabilities.
**Closes:** the currently-implicit "user clones the repo, runs `uv
sync`, and then what?" gap. Makes the daily-driver story end-to-end
testable.

## Open questions

1. **Mic calibration threshold formula.** Plan uses `min_peak_score *
   0.8` (from wake-word-plan.md). If real-room data says that's too
   tight or too loose, adjust once and lock.
2. **Claude API key flow.** Plan asks for it in the TTS-and-brain
   step; alternative is to defer and run Ollama-only until Eric
   pastes a key. Default: ask, with `--skip-key` to defer.

## The one-liner

`sabrina setup` is a single typer-driven CLI command that walks a
fresh install through dependency check, audio setup, TTS voice pick,
wake-word download and calibration, allow-list bootstrap, and a
30-second first conversation — each step skippable with `--defer`,
each step re-runnable on its own (`sabrina setup audio`, `sabrina
setup wake`, …).

## Launch-sequence state machine

Eight steps, each its own function, each writes `sabrina.toml`
atomically via `settings_io`, each idempotent, each re-runnable as
`sabrina setup <step>`:

1. **deps** — Python 3.12 + uv; point at `install-piper.ps1` /
   `install-nssm.ps1` for missing native bits.
2. **config** — scaffold `sabrina.toml` from the packaged template
   (reuse existing unless `--reset`).
3. **audio** — enumerate mics + speakers, test-record, pin by
   substring (not index).
4. **brain + TTS** — API key prompt + one Haiku test call,
   optional `ollama pull`, Piper voice picked from audible previews.
5. **wake-word** — download openWakeWord model, 3× calibration,
   write threshold. Skippable; PTT works without it.
6. **allow-list** — empty by default; prompt to register the
   kill-switch hotkey.
7. **autostart** — `schtasks` register? yes/no/later.
8. **introduce** — launch voice loop, Sabrina speaks the first-run
   script, exit.

## Per-step UX

**CLI-led throughout, voice confirmation in step 8.** GUI is
deferred to after-setup (see GUI cross-ref). Justification:
first-run is the one moment the user is guaranteed at a terminal
(they just ran `sabrina setup`); a second UI modality is churn.
Steps that need audible feedback (voice preview, wake-word
calibration) drive the speaker from the CLI.

| Step | Interaction | Skip-for-now |
|---|---|---|
| 1 deps | Red ✗ per missing tool + install hint | hard gate |
| 2 config | Prints diff, asks y/n | file must exist |
| 3 audio | Plays tone, records 2 s | `--skip-audio`, warns |
| 4 brain+TTS | Plays 3 voice samples, one Haiku test | `--skip-key` → Ollama only |
| 5 wake | 3 × "Hey Sabrina" | `--skip-wake` (PTT only) |
| 6 allow-list | y/n | default = skip |
| 7 autostart | y/n | default = skip |
| 8 introduce | Voice; fallback prints the script | n/a |

## First conversation — the script

First public showing of the personality-plan voice. Delivered via
the voice loop with memory writes **off** (shouldn't bias
semantic retrieval). Lives in `sabrina/setup/intro.py` as
string constants for review.

> "Hi Eric. I'm Sabrina. Push-to-talk's on shift-right — hold,
> talk, let go. If wake-word's on, just say my name. I'll be
> quiet unless you ask. Anything you want to start with, or
> should I get out of your way?"

If Eric answers: one normal turn (memory off), then:

> "Got it. I'm running. Settings are in `sabrina settings`."

If he doesn't answer within 15 seconds:

> "I'll be here. Talk to you soon."

## Calibration flows

- **Mic gain.** 2 s ambient vs. 2 s "Hey Sabrina, testing" —
  compare RMS, flag if too hot or too low, point at the Windows
  sound panel. No auto-normalize.
- **Wake-word sensitivity.** Three samples → threshold = min
  peak × 0.8, clamped to [0.35, 0.75]. Logged to
  `logs/wake-cal.json` + `sabrina.toml`.
- **TTS speed.** Preview at `length_scale = 1.0, 0.9, 1.15`.
- **Microphone selection — critical.** Pin by **substring** of
  the device name, not integer index. Windows reassigns indices
  across reboots; a pinned index silently binds to the wrong
  device after any USB hub change. `test-audio` already supports
  substring lookup; onboarding writes the substring.

## Fail-recovery

Each failure has an explicit offramp; **no single step can
hard-fail onboarding** — the user ends up with *something that
speaks*, even if degraded.

- **Audio device disappears mid-flow:** re-enumerate, re-run step 3.
- **Claude key missing / 401:** fall back to Ollama-only;
  `[brain.claude] enabled = false`; intro script swaps to "I'm
  running locally on Ollama."
- **Cubism DLL fails (avatar):** `[avatar] enabled = false`;
  pointer at `sabrina avatar-setup`. Avatar isn't MVP onboarding.
- **openWakeWord download fails:** keep PTT; `[wake_word] enabled
  = false`; pointer at `sabrina setup wake`.
- **`schtasks` fails** (policy/AV): surface the one-line error,
  suggest `[supervisor] mode = "none"`, continue.
- **Piper voice download fails:** SAPI fallback in
  `speaker/sapi.py`; `[tts] engine = "sapi"`; warn, continue.

## Re-onboarding triggers

Sabrina nudges but never auto-re-runs onboarding:

- **New mic** not matching `input_device` substring → log on
  launch, suggest `sabrina setup audio`.
- **Wake-word false-positive rate > 5/hour** rolling 24 h →
  suggest `sabrina setup wake`. Never auto-recalibrates (would
  thrash on ambient noise).
- **Allow-list reset** → next tool turn falls through to the
  automation-plan's "I haven't done that before" confirmation.
  No onboarding rerun needed.
- **Major version bump** in `sabrina.toml` → print diff of
  required new keys, offer `sabrina setup --incremental`.

## Settings GUI cross-ref

Rule: anything that *records* or *downloads* lives in onboarding;
anything that *tunes* lives in the GUI.

- **Onboarding-only:** wake-word model download, calibration
  samples, initial API-key paste, first-conversation script,
  autostart registration, dependency installation.
- **Both:** audio device substring, TTS voice + speed, wake-word
  threshold, `[brain]` picks, `[memory.semantic]` toggle,
  `[avatar]` knobs.
- **GUI-only:** runtime-tunable preferences with visual feedback
  (opacity sliders, position presets). GUI already has these tabs
  (decision 004, avatar-plan).

## Test strategy

Onboarding is stateful and touches real audio / filesystem /
network. Approach:

- **Scratch-config-per-test.** Each integration test creates a
  scratch dir under `tmp_path`, runs `sabrina setup --config
  <tmp>/sabrina.toml` with stubs wired via env vars
  (`SABRINA_ONBOARDING_MOCK_AUDIO=1`, …), asserts TOML contents.
- **Mock audio.** `sounddevice.query_devices` monkeypatched to
  return a fixture; record/play loop through a numpy array.
  Pattern exists in `test_test_audio_*`.
- **Mock Claude.** Existing `test_claude_*` pattern.
- **openWakeWord stubbed** via a `detector_factory` parameter.
- **Idempotence:** each step run twice; second run is a no-op.
- **Fail-recovery paths:** each branch above asserts fallback TOML
  keys set + exit code 0 (degraded is allowed).
- **Manual smoke** in `validate-onboarding-windows.md`: one fresh-
  VM end-to-end, one re-run (idempotent), one wake-skipped, one
  no-Claude-key.

## Ship criterion

`sabrina setup` on a VM with `uv sync` done → operational voice
loop (PTT + Piper + Claude + memory, optional wake-word +
autostart) in under 10 min wall time. Every step idempotent.
Every failure path lands on a degraded-but-usable install, no
hard-exit. Unit tests cover each step's happy + primary-failure
branch; one integration test covers the end-to-end flow against
mocked audio/brain/wake.

## Not in this plan

TUI/GUI wizard (CLI is enough for first release); remote or
headless onboarding (Eric is at the machine); account/cloud sync
(local-first); profile switching (one user, one config).
