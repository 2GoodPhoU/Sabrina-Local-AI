# Sabrina-Local-AI — Roadmap to v1.0

**Author:** Eric
**Last updated:** 2026-05-04
**Audience:** Eric, future-Eric, future-Claude (interactive sessions and the
scheduled-task automation harness).

This is the master release-targeted plan. It composes the per-component
decomposition in [`rebuild/ROADMAP.md`](rebuild/ROADMAP.md), the daily-driver
readiness list (in that same doc, "Daily-driver readiness" section), and the
[`rebuild/LEGACY_REPLACEMENT_GATE.md`](rebuild/LEGACY_REPLACEMENT_GATE.md)
checklist into a single ladder ending at v1.0. It does not replace those
docs — they are the inputs.

If you are an automated role (planner / worker / researcher / night-auditor /
digest), read this for orientation only. Do not modify it as part of an
ordinary shift; treat it like `rebuild/decisions/` — change requires a
decision doc and an explicit Eric-approved diff.

---

## Vision

Personality-forward local-first voice assistant for daily-driver use on
Windows. Mic → STT → brain → TTS, with persistent semantic memory, barge-in,
wake-word, and a Live2D avatar layer. Cortana-style "with you, not toward
you" operator voice (canonical in
[`rebuild/decisions/010-personality-spec.md`](rebuild/decisions/010-personality-spec.md)).

The hardware tier is fixed: i7-13700K + RTX 4080 16GB + 32GB / Win11
([decision 001](rebuild/decisions/001-hardware-and-budget.md)). Daily-driver
means Eric uses `sabrina voice` as the primary assistant for normal work
without falling back to legacy or to typing-instead-of-speaking out of
frustration.

---

## Release target — v1.0

v1.0 is defined by three concentric gates. All three must hold. Failing any
one resets to "release-pending"; failing two resets to a phase below.

### Gate 1 — Component completeness (Full DoD on Windows)

All nine ROADMAP components in `rebuild/ROADMAP.md`'s "Progress at a glance"
table must be at Full DoD per CLAUDE.md (Windows-validated voice loop +
`pytest` pass + DECISIONS entry where applicable):

1. Foundation — shipped
2. TTS — shipped
3. ASR — shipped
4. Wake word — scaffolded (placeholder `hey_jarvis`); v1.0 requires custom
   "Hey Sabrina" model + Windows validation
5. Brain — shipped (router + tool-use wire-up still pending; see Phase 4
   below)
6. Event bus + state machine — shipped
7. Memory — shipped (semantic + ONNX embedder + Park-style scoring)
8. Vision — shipped
9. Avatar (Live2D) — not started
10. Automation — not started

Settings GUI (component 5.5) is a shipped bonus and is not a v1.0 gate.

Today's count is **eight Full-DoD components plus one scaffolded plus two
not-started**, with ten decision docs filed (001–010). Wake-word, Avatar,
and Automation are the three that move v1.0.

### Gate 2 — Daily-driver readiness

The daily-driver readiness list in `rebuild/ROADMAP.md` must be fully
checked. As of today:

- [ ] Wake word OR reliable global PTT hotkey
- [ ] Auto-start on login (OS-level, not Python)
- [ ] Crash-recovery supervisor
- [x] Barge-in (shipped 2026-04-24, Windows-validated 2026-04-25;
      [decision 009](rebuild/decisions/009-barge-in-shipped.md) +
      [009a thin-spots](rebuild/decisions/009-barge-in-shipped.md))
- [ ] Budget observability (`sabrina budget` command + monthly tracker per
      [decision 001](rebuild/decisions/001-hardware-and-budget.md):
      $0 target / $10 warn / $100 ceiling)

Avatar and Automation are listed as "nice-to-have" in the readiness list but
are v1.0 gates under Gate 1. The two views agree: v1.0 ships them.

### Gate 3 — Legacy replacement gate clear + bake-in + archive flip

All seven boxes in
[`rebuild/LEGACY_REPLACEMENT_GATE.md`](rebuild/LEGACY_REPLACEMENT_GATE.md)
must be checked:

- [ ] Migration-port complete (or explicit skip-decisions for the five
      audit items: audio device fallback, shortcut table, install-deps
      script, test fixtures, conftest scaffolding)
- [ ] Daily-driver bake-in: 7 consecutive days of `sabrina voice` as
      primary assistant, no regressions filed in `ACTION_ITEMS.md`
- [ ] No regression vs. legacy in the bake-in window
- [ ] All references to legacy paths in rebuild docs removed/redirected
- [ ] `archive/` directory created and populated (move, not delete) for
      `core/`, `services/`, `utilities/`, `scripts/`, legacy `tests/`,
      `docs/`, `models/`, `config/`
- [ ] Top-level `README.md` updated to point only at `sabrina-2/` and
      `rebuild/`
- [ ] `CLAUDE.md` "Where the code and docs live" section updated for the
      post-archive shape

Bake-in resets on any in-window regression. The realistic-median window in
`LEGACY_REPLACEMENT_GATE.md` lands the archive flip mid-May 2026; honest
worst case is late May with one or two regression resets.

---

## Phase ladder

Each phase has explicit entry/exit criteria. A phase exits only when its
exit row is fully true; the next phase's entry row is the same row by
construction.

### Phase 0 — Foundation (DONE)

**Exit criteria:** uv-managed Python 3.12 project; `sabrina --version` works;
`sabrina chat` is a streaming text REPL through Claude;
`pydantic-settings` + `sabrina.toml` + `.env` wired; structlog (with
`redact_secrets` processor) + rotating file sink; typer CLI;
[decision 001](rebuild/decisions/001-hardware-and-budget.md) filed.

**Status:** complete. Shipped April 2026. See
[decision 001](rebuild/decisions/001-hardware-and-budget.md) and
[decision 003](rebuild/decisions/003-voice-loop-shipped.md).

### Phase 1 — Subsystems (DONE)

**Entry:** Phase 0 exit met.
**Exit criteria:** TTS, ASR, Brain (no router), Event-bus + state machine,
Memory (semantic), Vision, Settings GUI all at Full DoD on Windows. MVP
voice loop runs end-to-end with PTT + Claude/Ollama + sentence-streaming
Piper + SQLite + sqlite-vec semantic memory + Claude-vision attach +
`customtkinter` settings shell. Personality spec
([decision 010](rebuild/decisions/010-personality-spec.md)) canonical.
Foundational refactor bundle landed
([decision 008](rebuild/decisions/008-foundational-refactor-bundle.md)):
schema-versioned config + memory migrations, log redaction, rotating file
sink. Barge-in shipped + validated
([decision 009](rebuild/decisions/009-barge-in-shipped.md) + 009a):
Silero VAD + `CancelToken` through `Brain.chat` / `Speaker.speak`,
264 ms cut latency, ~0 ms first-audio regression.

**Status:** complete. Decision docs 002–009 plus 010 cover the bundle.
Voice loop validated on i7-13700K/RTX 4080/Python 3.12 (2026-04-24 for
component bundle, 2026-04-25 for barge-in).

### Phase 2 — Daily-driver gaps (IN PROGRESS)

**Entry:** Phase 1 exit met.
**Exit criteria:** all five daily-driver readiness items checked. The
remaining four after barge-in are wake-word + autostart + supervisor +
budget. "Wake word" at this gate means either openWakeWord with a custom
"Hey Sabrina" model trained, packaged, and Windows-validated **or** a
reliable global PTT hotkey shipped and validated; the existing PTT path
satisfies the latter on a strict reading, but Eric's stated goal in
[`rebuild/ROADMAP.md`](rebuild/ROADMAP.md) is the wake-word path with PTT
as fallback.

**Status:** in progress. Wake-word scaffold landed in pass 2 (2026-04-25):
`listener/wake_word.py`, `[wake_word]` block in `sabrina.toml`,
`enabled = false` by default, bundled `hey_jarvis` placeholder.
Validation + custom model are pending Eric's Windows session. Autostart +
supervisor + budget tracker are designed in `drafts/` but not built. None
of these are blocked by automation; they are blocked on Eric picking the
infra-vs-character path from the
[`rebuild/ROADMAP.md`](rebuild/ROADMAP.md) "Open questions" table.

### Phase 3 — ClaudeBrain tool-use wire-up (MID-FLIGHT)

**Entry:** Phase 2 in progress is acceptable; this phase runs in parallel
because the diff surface does not collide with daily-driver work.
**Exit criteria:** `ClaudeBrain.chat` accepts `tools=` and dispatches
`ToolUseBlock` events; `write_clipboard` ToolSpec fires from a real voice
turn on Windows; `[tools] enabled = true` in `sabrina.toml`; recursion cap
of 5 enforced; `ollama.py` raises `NotImplementedError` cleanly;
`pytest` passes on Windows.

**Status:** mid-flight, split across two halves per the 2026-05-04 unblock
run.

- **(a)-half — `[linux-runnable] [partial-dod-eligible]`:** protocol.py +
  claude.py + ollama.py + 6 unit tests. Wire-up code landed in working
  tree by worker-9am 2026-05-04; Linux gates GREEN; **commit blocked on
  stale `.git/index.lock`** per
  [QUEUE.md](QUEUE.md) entry. Partial-DoD ship is one Eric-touch away
  (clear lock, run staged commit, mark `[linux-shipped]`).
- **(b)-half — `[windows-required]`:** events.py + voice_loop.py wire-up +
  `sabrina.toml` flag flip + Windows e2e voice-turn validation. Sits in
  QUEUE for Eric's next Windows session. Promotes the parent item to
  `[done]` only after the e2e gate fires.

The split, the partial-DoD tier in CLAUDE.md, and the planner split-authority
landed via the 2026-05-04 workflow-efficiency unblock run. Canonical diff
surface is `research/2026-04-29-claudebrain-tool-wire-up-surface.md`.

### Phase 4 — Avatar + Automation + Brain router (NOT STARTED)

**Entry:** Phase 2 exit met (daily-driver gaps closed) **and** Phase 3 exit
met (tool-use Full DoD).
**Exit criteria:**

- **Avatar (component 6):** Live2D layer shipped per
  `rebuild/ROADMAP.md` §6 design. PyQt6, frameless / always-on-top /
  click-through, reacts to `StateChanged` events from the event bus.
  Decision doc filed.
- **Automation (component 9):** pyautogui + pynput surface, kill-switch,
  dry-run mode, destructive-action allow-list. Shortcut table from the
  legacy port (item 2 of `LEGACY_REPLACEMENT_GATE.md` audit) lands here as
  data. Decision doc filed.
- **Brain router (deferred from component 4):** the
  Claude/Ollama-routing layer plus persona-projection for Ollama parity
  (CLAUDE.md flags both as planned). Build only when daily cost or offline
  pressure justifies; today the cost ceiling is unmonitored, which is its
  own Phase-2 gap (`sabrina budget`).

Automation is the most dangerous component and is intentionally last in the
phase order. Avatar is pure UX polish and adds zero capability — but is
gated as a v1.0 component because of Eric's stated daily-driver vision.

### Phase 5 — Legacy replacement gate (NOT STARTED)

**Entry:** Phases 2–4 exit met.
**Exit criteria:** all seven boxes in `LEGACY_REPLACEMENT_GATE.md` checked.
Five port items either land in `sabrina-2/` or get a one-line
"decided not to port" entry under `rebuild/decisions/`. Cross-doc
references-to-legacy-paths sweep complete.

**Status:** not started. The five port items total ~9.5 hours and are
sequenceable in one Saturday session per
`LEGACY_REPLACEMENT_GATE.md` §"Realistic timeline".

### Phase 6 — Bake-in + archive flip + v1.0 release

**Entry:** Phase 5 port items complete.
**Exit criteria — and v1.0 ship:**

1. 7 consecutive days of `sabrina voice` as Eric's primary assistant,
   no regression filed in `ACTION_ITEMS.md`. Reset on any in-window
   regression.
2. `archive/` directory created; `core/`, `services/`, `utilities/`,
   `scripts/`, legacy `tests/`, `docs/`, `models/`, `config/` moved (not
   deleted); one-page `archive/README.md` filed.
3. Top-level `README.md` rewritten to point only at `sabrina-2/` and
   `rebuild/` with a single "What is `archive/`?" footnote.
4. `CLAUDE.md` "Where the code and docs live" rewritten for post-archive
   shape.
5. Final commit on `LEGACY_REPLACEMENT_GATE.md`: `legacy archived
   2026-MM-DD`. Doc stops being live.
6. `rebuild/decisions/011-v1.0-release.md` filed. Decision-doc voice. Ties
   off the rebuild project as a closed unit.

Realistic-median calendar per `LEGACY_REPLACEMENT_GATE.md`: archive flip
2026-05-11 to 2026-05-15 if Phase 5 port lands in week 1 and bake-in
completes clean. Honest worst case: late May 2026 with one or two
regression resets.

---

## Current-state marker

> **We are here:** end of Phase 1 + middle of Phase 2 + middle of Phase 3.

Weighted estimate to v1.0: **~70%**. Breakdown:

| Phase | Weight | Done | Contribution |
|---|---|---|---|
| 0 — Foundation | 5% | 100% | 5% |
| 1 — Subsystems | 45% | 100% | 45% |
| 2 — Daily-driver gaps | 15% | ~25% (1 of 5: barge-in only) | ~4% |
| 3 — Tool-use wire-up | 10% | ~80% ((a)-half code complete pending commit; (b)-half Windows-side untouched) | ~8% |
| 4 — Avatar + Automation + router | 15% | 0% | 0% |
| 5 — Legacy replacement gate | 5% | 0% | 0% |
| 6 — Bake-in + archive flip + release | 5% | 0% | 0% |
| **Total** | **100%** | — | **~62–70%** |

The 70% upper bound assumes the Phase-3 (a)-half lands as `[linux-shipped]`
this week and Eric runs the (b)-half Windows e2e the same week. The 62%
lower bound assumes Phase 3 stays mid-flight through May.

The dominant remaining work, by raw weight, is Phase 4 (Avatar + Automation
+ router) at 15%. By calendar drag, Phase 6 (bake-in) is the hardest to
compress because it's seven real days of daily-driver use, not engineering
hours.

---

## Partial-DoD bridge

The 2026-05-04 unblock run added a **Partial-DoD tier** to CLAUDE.md.
Linux-runnable diffs that don't touch voice-loop runtime, audio I/O,
clipboard, mss/pynput/pyperclip paths, or pywin32-only modules can ship
under Partial DoD:

- `python -m compileall sabrina-2/src` clean
- the new tests pass under the Cowork Linux/3.10 sandbox
- code-review approves the diff
- commit lands on `automation/<role>-<YYYY-MM-DD>-<slot>` with
  `Windows-pending: e2e` in the body and a Windows DoD checklist in JOURNAL

Such an item moves to `[linux-shipped]` in QUEUE/DONE. **It is "code
complete" but not v1.0-counted until Eric runs the Windows checklist and
promotes it to `[done]`.** The Phase-3 (a)-half is the first item to use
this tier; the precedent it sets is what makes the 62–70% weighting honest
rather than optimistic — Linux-shipped work is real but does not move v1.0
gates by itself.

The roadmap math counts a `[linux-shipped]` item at half-credit toward its
phase weight, with the other half deferred to the matching `[done]`
promotion. This is informal and not tracked numerically; the only place it
matters is in this current-state marker.

---

## Rate-limiter callout

**The roadmap cannot move past ~85% on automation alone.** The following
work units require Eric's Windows sessions and cannot be substituted by any
configuration of the scheduled-task harness:

- Promotion of every `[linux-shipped]` item to `[done]` (every Partial-DoD
  ship has a Windows e2e gate Eric runs).
- Wake-word validation (Phase 2) — model load + Windows validation pass
  per `rebuild/decisions/` precedent.
- Custom "Hey Sabrina" wake-word training (Phase 2) — known one-day task
  flagged in STATE.md "Open threads".
- Autostart + supervisor (Phase 2) — OS-level process management, not
  Python; can't be tested in a Linux sandbox.
- Budget observability `sabrina budget` end-to-end check (Phase 2).
- Avatar Live2D Windows runtime (Phase 4) — PyQt6 + frameless +
  click-through windowing only meaningfully validates on Windows.
- Automation pyautogui + pynput (Phase 4) — kill-switch + destructive-
  action allow-list need a Windows desktop to validate.
- Bake-in week (Phase 6) — by definition, seven days of Eric using
  `sabrina voice` as his primary assistant.
- Archive flip (Phase 6) — one git operation Eric runs (or approves a
  Worker to run with explicit branch + diff oversight).

Today's automation is producing legible state, surfacing decisions, and
landing Linux-runnable diffs. It cannot ship v1.0 on its own. Eric is the
rate-limiter from ~85% onward and the bake-in clock is the rate-limiter
on top of that.

---

## Cross-references

- [`rebuild/ROADMAP.md`](rebuild/ROADMAP.md) — per-component decomposition,
  the workflow protocol (extract → benchmark → ship), the architecture
  diagram, and the daily-driver readiness checklist. This top-level
  ROADMAP imports its component table; do not re-derive it.
- [`rebuild/LEGACY_REPLACEMENT_GATE.md`](rebuild/LEGACY_REPLACEMENT_GATE.md) —
  the seven-box close-out checklist, port audit, and realistic timeline
  for the archive flip.
- [`rebuild/decisions/`](rebuild/decisions/) — decision docs 001–010. Off-
  limits to ordinary-shift edits per CLAUDE.md.
- [`QUEUE.md`](QUEUE.md) — current Worker-actionable items. Phase-3
  (a)-half and (b)-half live here.
- [`PROPOSED.md`](PROPOSED.md) — items awaiting Eric's `[x]` approval
  before graduating to QUEUE.
- [`NEEDS-INPUT.md`](NEEDS-INPUT.md) — open questions and blockers (today:
  the stale-lock blocker on Phase 3 (a)-half is here).
- [`STATE.md`](STATE.md) — Planner-overwritten one-page snapshot of the
  current-day state.
- [`CLAUDE.md`](CLAUDE.md) — automation standing orders, off-limits list,
  Full DoD + Partial-DoD tiers, project-specific notes.
- `research/2026-04-29-claudebrain-tool-wire-up-surface.md` — canonical
  diff surface for Phase 3.

---

## What this doc is not

- **Not the workflow guide.** That's `rebuild/ROADMAP.md` "The workflow for
  every component".
- **Not a port plan.** That's `rebuild/drafts/old-repo-migration-audit.md`,
  consumed by `LEGACY_REPLACEMENT_GATE.md`.
- **Not a status report.** Status lives in STATE.md (today) and JOURNAL.md
  (history). This doc is the destination, not the position.
- **Not a per-component design doc.** Designs live in
  `rebuild/decisions/` (shipped) and `rebuild/drafts/` (proposals).

When v1.0 ships, this doc gets a final commit (`v1.0 released
2026-MM-DD`), the phase-ladder section gets a "shipped" stamp, and the
current-state marker gets archived rather than updated.
