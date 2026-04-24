# Remaining components — planning doc (post-007, post-barge-in)

> **Starting a new session?** Read [`../when-you-return.md`](../when-you-return.md)
> first — it's the quickstart entry point (state of play, ordered action
> sequence, decisions awaiting approval, primer for fresh Claude instances).
> This file remains the master index for plan details.

**Date:** 2026-04-23 *(open questions resolved same day; drafts
written for every slot that can be drafted with current answers;
research briefs written for the two deferred items; all research-
drafted plans now carry Recommendation: blocks resolving their open
questions)*
**Status:** Index of ready-to-ship drafts, ready-pending-approve drafts
(recommendations attached, awaiting Eric's glance), and capability
briefs.

## Drafts index

### Ready to ship (no Eric blockers)

- Slot 1: [`supervisor-autostart-plan.md`](supervisor-autostart-plan.md) — validation: [`validate-supervisor-autostart.md`](../validate-supervisor-autostart.md)
- Slot 2: [`wake-word-plan.md`](wake-word-plan.md) — validation: [`validate-wake-word.md`](../validate-wake-word.md)
- Slot 3: [`budget-and-caching-plan.md`](budget-and-caching-plan.md) — validation: [`validate-budget-caching.md`](../validate-budget-caching.md)
- Slot 4: [`semantic-memory-gui-plan.md`](semantic-memory-gui-plan.md) (007b) — validation: [`validate-007b-semantic-memory-gui.md`](../validate-007b-semantic-memory-gui.md)
- Housekeeping: [`thin-spot-split-plan.md`](thin-spot-split-plan.md) (`cli.py`, `voice_loop.py` splits) — validation: [`validate-thin-spot-split.md`](../validate-thin-spot-split.md)

### Ready pending glance-and-approve — Recommendation: blocks attached; no remaining Eric blockers unless he overrides

- [`router-plan.md`](router-plan.md) — brain router (3 questions, all with Recommendation)
- [`tool-use-plan.md`](tool-use-plan.md) — Brain protocol tools (3 questions, all with Recommendation)
- [`asr-upgrade-plan.md`](asr-upgrade-plan.md) — `base.en` → `large-v3-turbo` (2 questions, all with Recommendation)
- [`local-vlm-plan.md`](local-vlm-plan.md) — Ollama-hosted VLM (2 questions, all with Recommendation)
- [`vision-polish-plan.md`](vision-polish-plan.md) — no-VLM capture polish (1 question, Recommendation attached)

### Promoted deferred items (drafts now exist; briefs are historical)

- [`avatar-plan.md`](avatar-plan.md) — Live2D native, 3-4 session arc, OC-art pipeline appendix — validation: [`validate-avatar.md`](../validate-avatar.md). Structural uncertainty **resolved**: IPC is localhost UDP (`127.0.0.1:<port>`), Cubism SDK license path documented. **New sections (2026-04-23):** presence-voice cue track, animation library scope, plus contracts diagrammed in [`avatar-animation-graph.svg`](avatar-animation-graph.svg).
- [`automation-plan.md`](automation-plan.md) — safety spine + first three tools, 2-3 session arc — validation: [`validate-automation.md`](../validate-automation.md). Structural uncertainty **resolved**: tomlkit append mitigation captured (restructured allow-list layout + canary test).
- [`avatar-brief.md`](avatar-brief.md) — original brief, **superseded by `avatar-plan.md`** (history only)
- [`automation-brief.md`](automation-brief.md) — original brief, **superseded by `automation-plan.md`** (history only)

### Cross-cutting / meta (not component-shaped)

Plans that govern conventions, posture, or first-run experience across the
whole project rather than shipping a new component.

- [`config-schema-audit.md`](config-schema-audit.md) — `sabrina.toml` governance ahead of the next five sections; ends in one concrete ~100-line refactor (add `[schema] version = 1` + empty migration chain, flip `extra = "allow"` with warn-log, contributor note). **Ready to ship.**
- [`logging-vocabulary-plan.md`](logging-vocabulary-plan.md) — canonical `component.action` event namespace, per-plan event pre-declaration table, `turn_id` contextvars bind, separate app/audit/supervisor sinks. One-session migration: four renames + one `log.error` call + the contextvars bind. **Ready to ship.**
- [`personality-plan.md`](personality-plan.md) — voice, registers (A/B/C), refusals, cue-track integration. Upstream of every brain prompt and the avatar cue track. 3 Eric-resolvable open questions (profanity register, pronouns, opinions) with plan's-call defaults. **Ready pending glance-and-approve.**
- [`onboarding-plan.md`](onboarding-plan.md) — `sabrina setup` first-run state machine (8 idempotent steps), wraps existing CLIs. Prereqs (wake-word, supervisor, automation) all drafted. 2 open questions (mic threshold formula, API key flow) with defaults. **Ready pending glance-and-approve.**
- [`privacy-posture-plan.md`](privacy-posture-plan.md) — local-first posture statement, per-category data table, retention rules, gap list G1-G6. Documents posture + surfaces remediation; remediation itself lives in `logging-vocabulary-plan.md` + `config-schema-audit.md`. **Research-only.**

### Audit

- [`old-repo-migration-audit.md`](old-repo-migration-audit.md) — per-subdirectory audit of the pre-rebuild codebase, identifying the ~150–250 hours of porting candidates vs. dead weight. Informs which old code is worth cherry-picking into future components (e.g. pyaudio device enumeration into wake-word / barge-in).

**Excludes** (already being handled elsewhere): barge-in
(`drafts/barge-in-plan.md` + [`validate-barge-in.md`](../validate-barge-in.md)),
sqlite-vec-on-Windows contingent fix
(`drafts/008-sqlite-vec-on-windows.md`), semantic-memory Windows
validation (`validate-007-windows.md`).

### Suggested pre-work — foundational refactor (~150 lines, one session)

`privacy-posture-plan.md`, `config-schema-audit.md`, and
`logging-vocabulary-plan.md` all converge on the same three-part
refactor. Landing it once unlocks everything above it:

1. **`[schema] version = 1` block + empty migration chain** in
   `config.py` / `sabrina.toml` (from `config-schema-audit.md`) —
   hooks config migrations before the first rename needs them.
2. **Redacting structlog processor + 512-char value cap** in
   `sabrina/logging.py` (closes privacy gap G1; prereq for
   tool-use / automation argument logging).
3. **Rotating file sink for `logs/sabrina.log`** (5 MB × 3, from
   `logging-vocabulary-plan.md`) — closes privacy gap G2; prereq
   for supervisor error trails.

All three plans cross-reference this bundle. Shipping it as one
session before the next component plan lands removes the repeated
"…once the logging/config refactor happens" caveat from every
downstream draft.

## Executive summary

Eight components shipped. Post-barge-in, twelve identifiable pieces of work
remain, split roughly into three buckets: (A) daily-driver gap items Eric
explicitly listed in decisions 006/007, (B) roadmap components we
deliberately deferred (avatar, automation), and (C) thin-spot follow-ups
enumerated in the decision log but never scoped.

Recommended order to reach "daily-driver" by guardrail logic:

1. **Supervisor + autostart** — closes two of the four stated daily-driver
   gaps. Small (~200 lines), no protocol changes, no deps. Ship first.
2. **Wake word (openWakeWord)** — closes the third daily-driver gap. Reuses
   the VAD + `AudioMonitor` we'll have built for barge-in; the marginal
   cost is meaningfully lower if we build it immediately after.
3. **Budget tracker + prompt caching** — closes the fourth cheap
   observability gap and drops cost by a large factor. Small (~200 lines),
   Anthropic-only scope.
4. **007b — semantic-memory GUI + summary compaction** — natural follow-ups
   to 007; un-pollutes long histories and exposes the new knobs.

Then, order-of-magnitude: tool use in `Brain` protocol (prereq for
automation; `CancelToken` from barge-in is the structural prerequisite),
brain router (~200 lines, unlocks offline-first; wants budget-tracker
cost data first), ASR upgrade (one config line + a bake-off — the
`asr-upgrade-plan.md` now recommends `large-v3-turbo` over `medium.en`),
local VLM fallback for vision, window/region capture for vision, and
finally the two big deferred items, avatar and automation.

Rough effort for items 1–4 on Eric's hardware, in one-session-each chunks:
~1–2 sessions each. Items 5–8 are larger (2–4 sessions). Avatar and
automation are open-ended and deliberately last.

---

## Component enumeration

Every remaining piece of work. "Scope" is a rough guess at LOC + files
touched + new deps. "Blocks/blocked-by" uses the numbering in this list.

### 1. Supervisor + autostart (daily-driver gap)

Combined because they're the same shape of work: keep Sabrina running
without Eric thinking about it. Supervisor restarts her when she crashes;
autostart brings her up on login.

- **Status:** not started. Called out in decision 006 daily-driver checklist.
- **Scope:** ~150–250 lines, one new module (`sabrina/supervisor.py` or a
  dedicated CLI entrypoint `sabrina run`), plus a Windows-specific
  registration script (Task Scheduler XML or a Startup-folder `.lnk`
  generator). No new runtime deps beyond stdlib; PowerShell for the
  scheduled-task import.
- **Dependency ordering:** blocks nothing structurally, but every other
  "daily-driver" claim rings hollow until this ships. Blocked by: none.
- **Risk:** low. Failure mode is "Sabrina doesn't come back after a crash"
  — same as today — plus a small new failure mode if the supervisor
  itself has a bug (double-logging, restart loop). Mitigated by a
  restart-budget window.

### 2. Wake word — openWakeWord (daily-driver gap)

- **Status:** not started. Deferred with the wake-word slot itself;
  promoted from "research" to "in scope" in decision 006/007 menus.
- **Scope:** ~200 lines. New `listener/wake.py` module, a new `listening`
  sub-mode ("armed" — passive, listening for the wake word but not yet
  recording a full utterance), a new `[wake_word]` config block, GUI tab
  additions, two new ONNX models bundled or downloaded (~30 MB).
- **Deps:** `openwakeword>=0.6`, `onnxruntime>=1.17`. We already pull
  onnxruntime transitively via sentence-transformers.
- **Dependency ordering:** naturally follows barge-in because the same
  `AudioMonitor`-style always-on input stream + VAD scaffold is the right
  place to add wake-word detection. If we build it immediately after
  barge-in, we share the input stream, dead-zone logic, and device
  selection. Blocked by: barge-in sign-off (for the shared stream
  primitive). Blocks: nothing.
- **Risk:** medium. False-positive rate in real rooms is the wildcard.
  Model choice (`alexa`, `hey_jarvis`, or a custom "sabrina" model) also
  open. Mitigation: keep PTT as a live alternative, not a fallback —
  "both work" should stay the durable configuration.

### 3. Budget tracker + prompt caching (daily-driver gap)

- **Status:** not started. `AssistantReply` event carries `tier` but not
  `cost_usd`. Prompt caching: Anthropic cache-control blocks, ~90%
  discount on cache hits.
- **Scope:** ~200 lines. New `sabrina/budget.py` (cost-per-model table,
  rolling day/month accumulator persisted to `data/budget.json`), one
  new field on `AssistantReply`/`ThinkingFinished`, new `[budget]` config
  block, new `sabrina budget` CLI verb, one GUI tab. Prompt caching is a
  ~20-line change in `brain/claude.py` (add `cache_control` to the
  system block + recent-history messages).
- **Deps:** none new.
- **Dependency ordering:** independent of everything else; cleanly slots
  anywhere. Blocked by: none. Blocks: router (#5) wants cost data to
  justify routing decisions, so build this first.
- **Risk:** low. Caching has a known edge-case: cache-controlled blocks
  must appear at the front of the system prompt; we need to stop
  appending the `_format_retrieved` block to the *end* of the system
  string and instead split it into a separate non-cached block. Doable,
  just needs attention.

### 4. 007b — semantic-memory GUI + summary compaction

- **Status:** flagged at end of decision 007. Partial: the memory tab
  exists; the semantic sub-frame does not.
- **Scope:** GUI piece is ~30 minutes (new sub-frame, "Reindex now"
  button shelling to `sabrina memory-reindex`, live progress via a
  subprocess reader). Summary compaction is the real work — ~150–200
  lines, a new `sabrina memory-compact` verb, a scheduled threshold
  trigger, and a new `role=system` summary row stored with its own
  embedding.
- **Deps:** none new. Summary generation uses the existing Brain.
- **Dependency ordering:** blocked by: nothing. Blocks: nothing structural.
- **Risk:** low for GUI, medium for compaction. The failure mode is
  "summarizer loses meaningful context" — same class of failure as any
  RAG eviction. Mitigation: never delete the original rows; compaction
  adds a summary row, the originals stay retrievable.

### 5. Brain router

- **Status:** roadmap design intact; not started. Deferred in decision 003
  and again in 006 because Haiku 4.5 is fast + cheap enough that routing
  hasn't justified complexity. Open question in the ROADMAP.
- **Scope:** ~200 lines. New `brain/router.py` implementing `Brain`
  with a "decide which backend" prelude step that itself streams through
  a fast local (`qwen2.5:7b`) prompt. New `[brain.router]` config.
- **Deps:** none new; Ollama already pinned.
- **Dependency ordering:** blocked by: budget tracker (#3) for the cost
  metrics that justify routing choices. Blocks: nothing; unblocks
  offline-first mode from decision 001.
- **Risk:** medium. Routing adds ~50–200 ms to every turn; if the decision
  is wrong, Eric pays latency for no reason. The project's prior history
  (old repo's `llm_input_framework.py` was ~1000 lines of similar logic
  that didn't survive the rebuild) is the cautionary tale.

### 6. Tool use in the Brain protocol

- **Status:** not started. Stub slot in original design, dropped from the
  shipped `Brain`. Prereq for automation.
- **Scope:** ~250–400 lines end-to-end. New event types in the
  `StreamEvent` union (`ToolCall`, `ToolResult`), schema propagation in
  `brain/claude.py` and `brain/ollama.py` (different wire formats),
  a `tools: list[ToolSpec]` kwarg on `chat()`. Tools themselves live
  in a new `sabrina/tools/` folder, each tool a small module.
- **Deps:** none new.
- **Dependency ordering:** blocked by: `CancelToken` landing from
  barge-in (#barge-in — already planned). Blocks: automation (#9).
- **Risk:** high, because tool use is the doorway to automation, and the
  old repo died of over-abstraction exactly in this area. Mitigation:
  ship with zero tools wired; the first tool is the second caller that
  justifies the protocol, per guardrail #2.

### 7. ASR upgrade (base.en → medium.en, maybe Parakeet)

- **Status:** one-line config change + a real bake-off. Open question in
  ROADMAP and in decision 006.
- **Scope:** ~20 lines of `sabrina asr-bench` script that loops 10 real
  clips through both models, prints WER + latency. Then flip the default.
  Optional: add `medium.en` to the download path so first run isn't slow.
- **Deps:** none new.
- **Dependency ordering:** blocked by: nothing. Blocks: nothing.
- **Risk:** low. `medium.en` is ~1.5 GB vs. ~140 MB; on the 4080 it runs
  well under 500 ms for typical clips.

### 8. Local VLM fallback for vision

- **Status:** flagged in decision 005, decision 006 thin spots, ROADMAP.
  Not started.
- **Scope:** ~150 lines. New `vision/local_vlm.py` that routes a
  `Message.images` turn through Ollama with a Qwen2.5-VL or Moondream
  model. One new `[vision.local]` config block. A `prefer_local` flag.
- **Deps:** none new runtime (Ollama already a dep); Eric pulls the
  model locally via `ollama pull qwen2.5vl:7b`.
- **Dependency ordering:** blocked by: nothing. Blocks: nothing.
- **Risk:** medium. Ollama's multimodal support is less stable than its
  text path; also the quality delta vs. Claude vision is large. Value
  is privacy/offline, not parity.

### 9. Vision: window/region capture + image-in-memory

- **Status:** thin spot in decision 005/006. Not started.
- **Scope:** ~80 lines for window capture (pygetwindow + mss rectangle),
  plus ~40 lines for short-retention image store (separate SQLite
  table, or filesystem-under-`data/screenshots/`). CLI verbs + one GUI
  option.
- **Deps:** `pygetwindow>=0.0.9` (Windows-supported).
- **Dependency ordering:** blocked by: nothing. Blocks: nothing.
- **Risk:** low.

### 10. Voice-loop polish — error surfacing + settings live-reload

- **Status:** thin spots in decision 006. Not started.
- **Scope:** ~60 lines. Wrap `brain.chat` errors and spend them
  through a `speaker.speak("I couldn't reach the model right now.")`.
  Add a `ConfigReloaded` event, have `voice_loop` re-read the settings
  handle on receipt. Both small.
- **Deps:** none new.
- **Dependency ordering:** blocked by: nothing. Blocks: nothing.
- **Risk:** low.

### 11. Avatar (component 6)

- **Status:** deferred in every decision doc so far. Still deferred.
- **Scope:** PyQt6 frameless/always-on-top/click-through window,
  reacts to `StateChanged` events, swaps sprites. ~300–500 lines; plus
  art assets. Pure UX.
- **Deps:** `PyQt6>=6.7`, plus sprite/animation assets (archived in
  the old repo's `services/presence/`).
- **Dependency ordering:** blocked by: nothing. Blocks: nothing.
- **Risk:** low-technical, high-scope-sprawl. Guardrail pressure is high
  here because it's the kind of component that grows unbounded.

### 12. Automation (component 9)

- **Status:** deferred; "most dangerous component, last on purpose."
- **Scope:** large. pyautogui/pynput driver + kill-switch + dry-run mode
  + destructive-action allow-list + the tool-use protocol (#6) to drive
  it. Plausibly ~600–1000 lines including the safety harness.
- **Deps:** `pyautogui>=0.9.54`, possibly `pygetwindow` shared with #9.
- **Dependency ordering:** blocked by: tool use (#6). Blocks: nothing.
- **Risk:** high. Destructive actions on the user's live machine. Every
  safety layer from the original roadmap should survive intact.

### Cross-cutting: module-size guardrail is starting to bite

Not a component, but calling it out because guardrail #3 is approaching
yellow. Current large files:

- `cli.py` — 753 lines. Past 300 with no header justification. Each
  `memory-*` and `tts-*` verb is small but they sum up. If we keep
  adding verbs (budget, memory-compact, asr-bench, etc.), a split
  into `cli/` package (one module per subsystem) becomes due.
- `voice_loop.py` — 427 lines. Also past 300. Barge-in will add ~80
  more. A refactor into a `Turn` helper (encapsulates the single-turn
  state: retrieval + vision + stream + speaker-queue) is the obvious
  cut if it goes past ~500.

No action today; flagging so whichever session hits ~500 on one of these
files considers the split as part of that session's work.

---

## Recommended ordering, with justification

Assume barge-in ships next (plan already drafted). Then:

**1. Supervisor + autostart.** Daily-driver gap #2 and #3 are free lunch.
No protocol changes, no deps, no coupling. The project's stated ambition
is daily-driver use; shipping a one-session supervisor delivers on it
more than any one new feature could.

**2. Wake word (openWakeWord).** Daily-driver gap #1. Ordered right after
barge-in specifically to reuse the `AudioMonitor` primitive we'll have
built. Guardrail #2 (no new abstraction until the second caller exists)
says building the second caller now is the right time. If we wait three
sessions, we'll end up with two near-identical input streams.

**3. Budget tracker + prompt caching.** Daily-driver gap #4, plus an
immediate cost reduction on Claude turns. Two weeks into daily-driver use
the token spend will have meaningful signal; having observability before
that window is better than after.

**4. 007b — semantic-memory GUI + summary compaction.** Natural
follow-up to 007. Keeps the "per component there's always a thin-spot
cleanup session" habit alive. Slots before anything larger because the
GUI half is a 30-minute win and the compaction half prevents unbounded
context growth we'll otherwise hit soon.

**5. Tool use in Brain protocol.** The prereq for automation; worth
landing before budget/router pressures force it. `CancelToken` from
barge-in is the structural prerequisite.

**6. Brain router.** Post-budget-tracker, because routing decisions
should be justified by real cost data from (#3).

**7. ASR upgrade.** Fast, cheap, high-value. Could bump earlier if Eric
is finding transcription errors in the daily-driver week.

**8. Local VLM fallback.** Lower-priority than the above because Claude
vision works and daily cost on vision is negligible (decision 006 note:
60c/month at 20 calls/day).

**9. Vision: window/region + image-in-memory.** Polish; ship when
window capture actually bites.

**10. Avatar (component 6).** Last of the "always planned" items;
deliberately low-priority because it's pure UX.

**11. Automation (component 9).** Intentionally last. Everything else
should be stable before we ship anything that moves the mouse.

---

## Deep plans (top 4)

Enough detail that one session after Eric's sign-off lands each in main.

---

## Plan A — Supervisor + autostart

### One-liner

`sabrina run` becomes the daily-driver entrypoint: a tiny supervisor that
spawns `sabrina voice` as a subprocess, watches it, and restarts it on
unhandled exit. Autostart is a one-command Windows Task Scheduler
registration that invokes `sabrina run` at login.

### Scope

In:
- New `sabrina/supervisor.py` (~120 lines): `run_supervised(argv)` that
  spawns, monitors, and restarts `sabrina voice`. Restart budget
  (configurable: default 5 restarts in 60 s before giving up — guard
  against tight crash loops). Structured log output.
- New CLI verb: `sabrina run` (wraps `sabrina voice` in the supervisor).
- New CLI verb: `sabrina autostart [--enable / --disable]` — writes or
  removes a Windows Task Scheduler entry that runs `sabrina run` at
  user logon.
- `[supervisor]` config block for the restart-budget knobs.
- Tests: supervisor-level unit tests with a stub subprocess.

Out:
- Real Windows Service install (requires admin + a service account).
  Task Scheduler at-logon is the right choice for a single-user daily
  driver.
- Crash telemetry (Sentry, etc.). Log lines are enough until they aren't.
- Health pings. The supervisor only responds to process-exit, not to
  hangs. A watchdog (ping the voice process every N seconds) is a
  follow-up if hang is observed in practice.

### Files to touch

```
sabrina-2/src/sabrina/
├── supervisor.py               # NEW, ~120 lines
├── cli.py                      # +2 verbs (run, autostart)
├── config.py                   # +SupervisorConfig
└── scripts/
    └── autostart.xml           # NEW: Task Scheduler template
sabrina-2/
├── sabrina.toml                # +[supervisor]
└── tests/test_smoke.py         # +supervisor tests (stub subprocess)
```

One new top-level file. Guardrail #3 comfortable.

### Protocol / API changes

None. Supervisor is a process-level concern; it doesn't touch Brain,
Listener, Speaker, Memory, or the event bus.

### Deps to add

None. `subprocess`, `time`, and `logging` are stdlib. Task Scheduler
integration uses `schtasks.exe` (built into Windows) — no Python library
dep needed.

### Test strategy

- `test_supervisor_restarts_on_exit` — stub `Popen` that exits fast,
  assert N restarts happen within the budget.
- `test_supervisor_respects_budget` — stub that keeps crashing, assert
  supervisor gives up after configured threshold and logs loudly.
- `test_supervisor_propagates_sigint` — stub that runs forever, send
  SIGINT to supervisor, assert child is signalled and reaped cleanly.
- `test_autostart_writes_xml_and_invokes_schtasks` — monkeypatch
  `subprocess.run` on the `schtasks` path; assert the XML file we
  write lines up with a known-good template.

No real process spawn in test suite. Manual smoke: `sabrina run`,
kill the voice process externally, watch it come back.

### Open questions

1. ~~Windows Task Scheduler vs. Windows Service?~~ **Resolved
   (2026-04-23):** both, behind `supervisor.mode`. Default
   `task_scheduler`; `service` mode uses nssm. See
   `supervisor-autostart-plan.md` for the full spec.
2. Restart budget values. 5 restarts in 60 s? More lenient?
3. Should the supervisor also own the avatar process (once that exists)
   as a sibling? Probably yes eventually, but not in this scope.
4. Logging: supervisor writes to `logs/supervisor.log`; voice loop keeps
   writing to stderr. OK?

### Windows-specific notes

- `schtasks /create /xml <path>` is the stable way to import a
  scheduled task. Build the XML from a template string that embeds the
  current Python path (resolved at runtime from `sys.executable`) plus
  `-m sabrina run`.
- Task should run "only when user is logged on" and "do not start if on
  battery" defaults off. Eric's on a desktop so battery doesn't apply.
- `sabrina autostart --disable` deletes the task by name.

---

## Plan B — Wake word (openWakeWord)

### One-liner

Add an optional always-on wake-word detector that fires a
`WakeWordDetected` event, which the voice loop treats identically to
PTT press. Both triggers coexist; wake-word defaults off until Eric
has tuned threshold.

### Scope

In:
- New `listener/wake.py` (~100 lines): `OpenWakeWordDetector` wrapping
  openWakeWord's `Model` class, frame-by-frame `feed(pcm_chunk) -> float`
  returning a confidence score.
- New always-on input stream manager (shared with the `AudioMonitor`
  from barge-in — see below) that runs during `idle` state.
- New event: `WakeWordDetected(word: str, score: float)`.
- Voice-loop change: `idle → listening` transition can now be triggered
  by either PTT press or `WakeWordDetected`.
- `[wake_word]` config block.
- GUI tab addition (sub-frame in ASR or a new "Listen" tab — Eric picks).

Out:
- Custom wake-word training ("sabrina"). Bundled `hey_jarvis` or
  `alexa` for initial validation. Custom model is a follow-up session
  using `piper-tts` to generate training data + openWakeWord's trainer.
- On-device VAD gating for wake-word. openWakeWord's own VAD is
  sufficient; we already have Silero from barge-in but wiring both is
  unnecessary.

### Files to touch

```
sabrina-2/src/sabrina/
├── listener/
│   ├── wake.py                 # NEW, ~100 lines
│   └── __init__.py             # export WakeWordDetector
├── listener/vad.py             # barge-in's AudioMonitor — extended to
│                               #  dispatch to both wake + barge consumers
├── voice_loop.py                # +wake path in idle state
├── events.py                   # +WakeWordDetected
├── config.py                   # +WakeWordConfig
├── gui/settings.py              # +wake-word controls on a tab
└── cli.py                      # +`sabrina wake-test` verb
sabrina-2/
├── pyproject.toml               # +openwakeword>=0.6
├── sabrina.toml                 # +[wake_word]
└── tests/test_smoke.py         # +wake-word tests (stub detector)
```

`AudioMonitor` extension is the key architectural move — we make it a
multi-consumer dispatcher during `idle` so wake-word AND barge-in share
one input stream, not fight over the device.

### Protocol / API changes

- `Listener` protocol unchanged (transcribe stays the same).
- `events.py` gains `WakeWordDetected`.
- `voice_loop` gains a wake-word detection branch at the top of the
  main loop.

### Deps to add

```toml
"openwakeword>=0.6",
```

onnxruntime already comes in transitively (sentence-transformers pulls
it on CPU/CUDA). No new large dep.

### Test strategy

- `test_wake_word_model_loads_and_reports_dim` — stub an ONNX model,
  confirm feed/score path.
- `test_wake_word_detector_fires_above_threshold` — synthesize a score
  sequence (0.1, 0.2, 0.8, 0.9), assert detection at the first >0.5.
- `test_voice_loop_idle_to_listening_on_wake_event` — stub detector
  that emits `WakeWordDetected` immediately; assert state transitions.
- Real-audio test stays manual, documented in a new
  `validate-wake-on-windows.md` when we ship.

### Open questions

1. ~~Which bundled wake word?~~ **Resolved (2026-04-23):** custom-trained
   "Hey Sabrina". Training pipeline + model placement in
   `wake-word-plan.md`. Bundled wake words not used.
2. PTT vs. wake-word primacy — kept PTT primary; wake defaults off.
   (Settled in plan.)
3. GUI tab — new "Listen" tab consolidating PTT + wake + barge-in.
   (Settled in plan.)
4. Model storage — committed to the repo at
   `voices/wake/hey_sabrina.onnx`. ~2-5 MB is acceptable for git.
   (Settled in plan — no download-on-first-use.)

### Windows-specific notes

- openWakeWord v0.6+ has Windows wheels on PyPI. Confirmed.
- onnxruntime's DirectML provider would let wake detection run on the
  iGPU (UHD 770) instead of the 4080; probably overkill, CPU inference
  per frame is ~1 ms on this hardware.
- Same input device selection as PTT — if Eric pinned a USB mic for PTT,
  wake-word uses the same device. No separate config.

---

## Plan C — Budget tracker + prompt caching

### One-liner

Every Anthropic response carries usage info; persist it, total it, and
expose via CLI + GUI. Same session adds cache-control blocks to Claude
calls so repeat system prompts cost 10% of their first use.

### Scope

In:
- New `sabrina/budget.py` (~120 lines): rolling counters per-day and
  per-month, persisted to `data/budget.json`. Cost table keyed by model
  string (Claude Sonnet 4.6, Haiku 4.5, plus openrouter-compatible
  lookup if we ever need it).
- Extend `AssistantReply`/`ThinkingFinished` with `cost_usd: float | None`.
- Hook `brain/claude.py` to publish the input_tokens/output_tokens →
  cost computation after each `Done`.
- Hook `brain/ollama.py` to publish `cost_usd=0.0` (local is free).
- New CLI verb: `sabrina budget` (today / this-month / by-model
  breakdowns).
- New GUI: a "Budget" tab with a 7-day spark + current-month total.
- Prompt caching: mark the system prompt as cacheable in
  `brain/claude.py`. The "Earlier in our conversations..." retrieved
  block does NOT go into the cached region (it changes every turn).
  Current voice-loop appends the retrieved block to `turn_system`; we
  split that into a cacheable base + a per-turn suffix for the Anthropic
  request shape.
- `[budget]` config block (daily warn, monthly warn, monthly ceiling —
  values from decision 001).
- Tests: cost computation, persistence round-trip, cache-control
  message shape.

Out:
- Cost tracking for Ollama (it's $0).
- Per-session cost breakdown in the GUI. Per-day is enough.
- Automatic kill-switch behavior at the monthly ceiling. Currently just
  logs loudly + surfaces in GUI. Hard router-level enforcement ships
  with the router (#5).

### Files to touch

```
sabrina-2/src/sabrina/
├── budget.py                   # NEW, ~120 lines
├── brain/claude.py              # +cache_control split, +cost calc on Done
├── brain/ollama.py              # +cost=0 on Done
├── events.py                   # +cost_usd on existing events
├── voice_loop.py                # +budget.record() call on ThinkingFinished
├── cli.py                      # +`sabrina budget` verb
├── gui/settings.py              # +"Budget" tab
└── config.py                   # +BudgetConfig
sabrina-2/
├── sabrina.toml                 # +[budget]
└── tests/test_smoke.py         # +budget tests
```

Budget is a plausibly-mid-sized file; keep it ≤200 lines. If it grows,
factor `budget/store.py` + `budget/costs.py`.

### Protocol / API changes

- `AssistantReply.cost_usd`, `ThinkingFinished.cost_usd` added (optional,
  defaults `None`). Existing subscribers unaffected.
- `brain.claude.chat` internals: the Anthropic `system` kwarg becomes
  a list of content blocks with `cache_control={"type":"ephemeral"}` on
  the stable head, not a bare string. The per-turn suffix (retrieved
  block) is a separate, non-cached block. `voice_loop` passes the two
  halves in separately, or alternatively we split inside `claude.py`
  at a well-known marker. Proposal: new signature
  `chat(messages, *, system, system_suffix=None, ...)` where
  `system_suffix` is the non-cached part. Minimal surface change.

### Deps to add

None.

### Test strategy

- `test_budget_cost_table_matches_published_prices` — pin Sonnet/Haiku
  per-million-token prices in the table, a test asserts the computation
  matches a known input/output token pair. (Hard-coding prices is fine;
  Anthropic updates them infrequently, and a stale price is obviously
  a testable bug.)
- `test_budget_persists_across_restarts` — write, re-open, assert totals.
- `test_budget_day_rollover` — simulate two timestamps across midnight.
- `test_claude_cache_control_shape` — stub the Anthropic client, capture
  the `system` kwarg, assert the cache-control block is present and the
  per-turn suffix is separate.

### Open questions

1. ~~`system_suffix` kwarg vs. magic string split?~~ **Resolved
   (2026-04-23):** explicit `system_suffix` kwarg on `Brain.chat`.
   Ollama concatenates. Full spec in `budget-and-caching-plan.md`.
2. Cost table — hard-coded constants in `budget.py`. (Settled in plan.)
3. Persistence cadence — every turn, atomic replace. (Settled in plan.)
4. GUI live-updates — deferred until voice-loop polish adds the event
   stream. Static-on-open with refresh button ships this session.
5. Retrieval-block placement — strictly after the cached head as a
   separate non-cached block. (Settled in plan.)

**One risk discovered while drafting:** Anthropic's cache has a ~1024-
token floor; our `_SYSTEM` constant is ~80 tokens, so caching is wired
but inert until system prompts grow (e.g. when tool-use schemas land).
Plan-of-record accepts that — the budget tracker half still ships
observable value. See the full discussion in `budget-and-caching-plan.md`.

### Windows-specific notes

- `data/budget.json` path — same resolution as `data/sabrina.db`.
- Atomic write pattern (tempfile + `os.replace`) for crash-safety.
  Windows requires the target file to not be held open by a reader at
  rename time; the GUI shouldn't hold a file handle.

---

## Plan D — Semantic memory GUI (007b) + summary compaction

### One-liner

Finish decision 007's loose ends: a Memory-tab sub-frame for
`[memory.semantic]` knobs and a "Reindex now" button; then a summary
compaction loop that rolls old turns into summary rows so context
doesn't grow unboundedly.

### Scope (two halves, ship as one)

**007b.1 — GUI (~30 min):**
- Memory tab gets a "Semantic retrieval" sub-frame: `enabled` checkbox,
  `top_k` spinner, `max_distance` slider, `min_age_turns` spinner,
  `embedding_model` entry (greyed unless advanced is toggled).
- "Reindex now" button: spawns `sabrina memory-reindex` as a subprocess,
  streams output into a modal progress window.
- "Drop + reindex" button (destructive, confirm dialog).
- `memory-stats` inline on the tab for operator visibility.

**007b.2 — Summary compaction (~150 lines):**
- New `memory/compact.py`: walk the oldest N messages (default: everything
  older than 1000 turns), group by session, summarize via fast brain
  (Haiku or local), insert a new `role=system` row with the summary, keep
  originals queryable but mark them `compacted=True` so retrieval can
  optionally skip them.
- New column `compacted INTEGER NOT NULL DEFAULT 0` on `messages` (one
  migration). `search()` gains an `include_compacted: bool = False` flag.
- New CLI verb `sabrina memory-compact [--session ID] [--older-than N]`.
- New `[memory.compaction]` config block.

### Files to touch

```
sabrina-2/src/sabrina/
├── gui/settings.py              # +semantic sub-frame + Reindex buttons
├── memory/compact.py            # NEW, ~150 lines
├── memory/store.py              # +compacted column, migration,
│                                #  +include_compacted kwarg on search()
├── cli.py                      # +`sabrina memory-compact` verb
└── config.py                   # +CompactionConfig under MemoryConfig
sabrina-2/
├── sabrina.toml                 # +[memory.compaction]
└── tests/test_smoke.py         # +compaction tests
```

### Protocol / API changes

- `MemoryStore.search()` — `include_compacted: bool = False` new kwarg.
- `MemoryStore` — new `.compact(session_id, older_than)` method.
- New brain-driven summary generation: `summarize(history, *, brain) -> str`.
  Could live in `memory/compact.py` to keep contract local.

### Deps to add

None.

### Test strategy

- `test_compaction_inserts_summary_row` — stub brain that returns a
  canned summary, verify row insertion + original rows marked compacted.
- `test_compaction_reindexes_summary_embedding` — verify the summary
  row is embedded and searchable.
- `test_search_excludes_compacted_by_default` — direct assertion.
- `test_gui_semantic_subframe_renders` — configure a stub settings
  object, build the frame, assert the widgets exist (matches existing
  GUI test pattern).

### Open questions

1. ~~Manual vs. automatic trigger?~~ **Resolved (2026-04-23):** setting-
   driven, default automatic at a startup threshold. Threshold pick
   (token count vs. turn count) goes in the per-component draft when
   that one ships.
2. Summary writer — Claude Haiku default, Ollama override. (Settled
   in plan; defer final pick to the draft.)
3. Summary granularity — per-session. (Settled in plan.)
4. Delete originals — mark only, never delete. (Settled in plan.)

### Windows-specific notes

- The subprocess spawn for "Reindex now" from the GUI must use
  `sys.executable + ["-m", "sabrina", "memory-reindex"]`, not a bare
  `sabrina` invocation — the latter may resolve to the wrong Python if
  the user launched the GUI from a different venv than the shell.

---

## What's missing from this plan (acknowledged)

- **Real WER numbers on base.en vs. medium.en.** Without measuring on
  Eric's voice + mic, the "upgrade is worth it" claim is a guess.
- **Specific router design.** I kept router at ordering position 6 with
  a "~200 lines" estimate because anything more detailed would be
  dishonest — decision 001's design (fast-path → local → Haiku → Sonnet)
  is a sketch, not a spec. A dedicated plan precedes implementation.
- **Avatar asset inventory.** Old repo's `services/presence/` supposedly
  has reusable assets; haven't verified what's actually there + how it
  packages. Needed before any avatar work starts.
- **Automation safety model.** Old roadmap's design (dry-run,
  allow-list, kill-switch) stands but hasn't been re-validated against
  the rebuild's current threat model. Needed before any automation
  work starts.
- **Confidence that openWakeWord works on Eric's USB mic + headset
  combo without VAD retraining.** Validation plan will include a real
  "hey_jarvis" trial in a noisy room before default-enabling.

---

## Anti-sprawl note

This is one planning doc. No per-component drafts have been written.
After Eric signs off on an ordering pick, the top item gets its own
draft in the barge-in-plan style; the rest stay in this doc until their
turn.
