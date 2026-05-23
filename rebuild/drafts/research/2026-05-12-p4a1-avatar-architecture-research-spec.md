# P4.A1 — Avatar architecture research + decision draft — spec

**Date:** 2026-05-12
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Avatar → **P4.A1 Avatar — architecture research + decision draft** (`[linux-runnable] [P2] [M]`).
**Predecessors / canon to consult:**
- `rebuild/ROADMAP.md` § 6 — Avatar "deferred. The plan stands: PyQt6, frameless/always-on-top/click-through, reacts to `StateChanged` events. Pure UX polish, zero capability added." This is the design statement P4.A1 grounds.
- `ROADMAP.md` § "Phase 4 — Avatar + Automation + Brain router" — entry requires Phase 2 exit + Phase 3 exit; P4.A1 itself can land earlier under research-only Partial DoD.
- `rebuild/decisions/006-state-machine.md` (referenced indirectly through `sabrina-2/src/sabrina/state.py`) — defines the five state names the avatar must react to: `idle`, `listening`, `thinking`, `speaking`, `acting`.
- `sabrina-2/src/sabrina/events.py:55-63` — `StateChanged` event shape (`from_state`, `to_state`, `reason`). The IPC contract the avatar subscribes against.
- `sabrina-2/src/sabrina/bus.py:31-83` — `EventBus.subscribe(*kinds, maxsize=1024)` async-iterator API + lossy-on-backpressure semantics. The IPC option-1 (in-process subscriber) attaches here.
- `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` — earlier cue-track research; not authoritative on architecture but lists the per-state expressive cues the rig will eventually drive. Treat as input, not constraint.
- `rebuild/decisions/001-hardware-and-budget.md` — target hardware (i7-13700K + RTX 4080 16GB). Frame-budget math is against this tier.

**Scope:** research-only. No code touched. Output is one research doc under `rebuild/drafts/research/2026-05-MM-avatar-architecture.md` plus any spec-writer NEEDS-INPUT entries surfaced. Off-limits: `rebuild/decisions/`, legacy root-level dirs, any code edits.

---

## What this item is

The Avatar component (Component 6 of `rebuild/ROADMAP.md`; v1.0 Gate 1 mover #9 in `ROADMAP.md`) is the only `not-started` component of the nine-row component table aside from Automation. The QUEUE entry frames a five-section research deliverable, but the section topics are at title-only resolution: a Worker pulling A1 today would have to interpret what "SDK pick" means, how deep to go on PyQt6 patterns, what "frame budget" answers, and what counts as "Eric's pick." This spec sharpens each of the five sections into a concrete question, names the candidates the research should evaluate, and surfaces the sub-decisions that need Eric's call before code lands in A2/A3/A4.

The deliverable is a research doc — not code, not a decision doc. It is the input the eventual `rebuild/decisions/0XX-avatar-architecture.md` (filed under P4.A4 Full DoD) will cite. The research doc itself does not commit to anything; per role-doc step 6 it states a recommendation per section and a one-line "Eric's pick" placeholder that becomes the load-bearing answer once Eric checks the matching NEEDS-INPUT entry.

## Proposed approach

**Single output:** `rebuild/drafts/research/2026-05-MM-avatar-architecture.md` (replace `MM` with the actual day-of-month at write time; recommended slug `avatar-architecture`). Five sections, ~1500-2500 words total. No code in the doc — surfaces only.

**Section 1 — Live2D SDK pick.** Evaluate three candidates against four axes (license, maintenance posture, Windows-x64 install path, render path):

- `live2d-py` (community wrapper around Cubism Native SDK; pip-installable; GPL-flavored license inheritance). Bias: low-friction install, smaller scope.
- Cubism SDK Python wrapper (official; download-gated from Live2D Inc; their non-commercial / commercial license tiers apply). Bias: higher fidelity, license friction for a personal daily-driver is irrelevant but the SDK download isn't pip-able.
- Roll-our-own with OpenGL + texture-atlas + raw Cubism Moc3 parser (do-not-recommend baseline — included so the "buy vs build" delta is named explicitly).

Output: a side-by-side table + recommendation. The spec recommends `live2d-py` for v1 unless its render fidelity is materially worse than Cubism SDK; the daily-driver bar is "reacts to state, doesn't look broken" not "production VTuber app."

**Section 2 — PyQt6 frameless / always-on-top / click-through cookbook.** Document the exact Qt window flags + attributes needed on Windows 11 to achieve all three behaviors simultaneously. The canonical recipe is `Qt.WindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)` plus `setAttribute(Qt.WA_TranslucentBackground)` plus `setAttribute(Qt.WA_TransparentForMouseEvents)`. Click-through is the tricky one — `WA_TransparentForMouseEvents` is all-or-nothing; per-pixel transparency via Windows `SetWindowLong`/`WS_EX_LAYERED`+`WS_EX_TRANSPARENT` is the workaround when opaque-regions-accept-clicks is needed.

Output: a code-snippet-free description of the exact flag combination, the click-through gotcha (and how A2 will sidestep or solve it), and a pointer to the smallest known-working public reproduction (e.g. a Qt forum thread or a published recipe; cite the source). The spec recommends shipping A2 with **WA_TransparentForMouseEvents everywhere** (full click-through, no opaque regions, no kill-button on the avatar itself — kill-button lives elsewhere, e.g. the system tray) — this collapses the most fragile Windows path into a single flag.

**Section 3 — IPC: in-process subscriber vs. side-process subscriber.** The avatar subscribes to `StateChanged` events from the event bus. Two architectures:

- **In-process.** Avatar runs in the same process as the voice loop. Subscribes to `bus.subscribe("state_changed")` directly. Pro: zero IPC overhead, simple. Con: Qt event loop must co-exist with asyncio; PyQt6's `QApplication.exec()` is blocking, so we bridge via `qasync` (PyQt6+asyncio integration) or a `QTimer.singleShot` pump from a background asyncio thread.
- **Side-process.** Avatar runs in its own Python process. IPC via local TCP, named pipe, or stdin/stdout JSONL. Pro: crash isolation (avatar segfaults don't take down voice); independent restart story. Con: ~1ms-class IPC latency, additional process management, second venv-or-wheel deployment surface.

Output: side-by-side table, recommendation + dissent. The spec recommends **in-process with `qasync`** for v1 — crash isolation is solved cheaper by the supervisor (component already shipped in `acd6725`), and the daily-driver target machine (RTX 4080) has plenty of headroom for one extra Qt event loop. Side-process is the right answer if A3's render-loop research turns up a real risk of OpenGL-driver-crash bringing down the voice path.

**Section 4 — Frame budget at 60fps on RTX 4080.** Establish the per-frame budget (16.67 ms wall-clock at 60 Hz; 8.33 ms at 120 Hz aspirational) and how much of it the Live2D rig + Qt compositor will consume on the target hardware. Cite published benchmarks for the Cubism runtime on similar hardware; estimate the textures + parameter-update cost; flag the asyncio-bridge overhead. Output: a single number per stage (rig render, Qt compositor, asyncio-bridge wakeup) summing to a budget consumption percentage, plus the headroom that remains for the voice loop's own asyncio scheduling needs.

Spec stance: this section is informational, not gate-defining. If the budget is comfortable (< 30% of one core at 60 Hz), proceed; if it's tight (> 60%), reconsider side-process IPC. The recommendation defaults to "comfortable on RTX 4080" given community benchmarks for Live2D Cubism Native at this hardware tier.

**Section 5 — Eric's pick.** A one-line "Eric's pick" placeholder per section, plus a top-of-section summary. The research doc ships with the recommendations populated and the picks blank; Eric's `[x]` on the matching NEEDS-INPUT entries fills them in. Per role-doc step 6, this is the cleanest hand-off shape.

## Dependencies

- **Phase 4 entry criteria** (per `ROADMAP.md` §"Phase 4 — Avatar + Automation + Brain router"). The research itself can land independently; only the eventual code in A2/A3/A4 waits on the Phase 4 entry gate.
- **`sabrina-2/src/sabrina/bus.py` + `events.py`** are read-only inputs — the research cites the existing API surface but doesn't propose changes.
- **No other queue items.** A1 is the gate for A2; A2 is the gate for A3; A3 is the gate for A4. A1 itself has no upstream blockers.

## Concrete DoD

The fuzzy QUEUE DoD ("research-only: `research/2026-05-MM-avatar-architecture.md` covers ...") gets sharpened to:

1. **File exists** at `rebuild/drafts/research/2026-05-MM-avatar-architecture.md` (`MM` and `DD` match the writing date; slug `avatar-architecture`). Lives in `rebuild/drafts/research/`, not `research/` at project root — matches every other 2026-05-* spec/research doc in the repo per `rebuild/drafts/research/` glob.
2. **Five sections present** in order, each with a level-2 heading: §1 SDK pick, §2 PyQt6 window flags + click-through, §3 IPC architecture, §4 Frame budget, §5 Eric's pick.
3. **§1, §2, §3** each contain a per-axis comparison table + a recommendation line + an "Eric's pick" placeholder. §1 specifically names the three candidates (live2d-py, Cubism SDK Python, roll-our-own); §2 specifically names the canonical Qt-flag recipe + the click-through gotcha; §3 specifically names the in-process-via-qasync vs side-process trade-off.
4. **§4** contains at least one quantitative per-frame budget estimate (ms-per-stage) plus a headroom statement; cites at least one external source for the Cubism-on-Windows render cost.
5. **§5** is a checklist of the per-section picks; matches the NEEDS-INPUT entries 1:1.
6. **No code touched.** The Worker doing this research touches zero `.py` files. `python -m compileall sabrina-2/src` clean from before equals after.
7. **No new dependencies added.** No `pyproject.toml` edit, no `requirements*.txt` edit. The avatar dep additions (`PyQt6`, `live2d-py` or chosen SDK, `qasync`) land in P4.A2's spec, not here.
8. **NEEDS-INPUT entries filed** for §1, §2, §3 picks per the role-doc step 4 protocol. §4 is informational, §5 is the summary — neither needs a separate entry.
9. **Commit on `automation/<role>-2026-05-DD-<slot>` branch** with body `Windows-pending: e2e` omitted (this is research-only; no Windows path to validate). Pre-commit hook's `compileall` runs against `sabrina-2/src` and is unaffected.

The original 5-bullet QUEUE DoD ("(1) SDK pick, (2) window layer, (3) IPC, (4) frame budget, (5) Eric's pick") is preserved by construction — each bullet becomes a §-numbered section above with a sharpening clause.

## Open NEEDS-INPUT for Eric

Three picks the Worker can't make without an Eric call. Spec recommends an answer for each; Worker can ship the research draft against the recommendations without waiting, and Eric's override at any point before the matching code lands in A2 reroutes per the answer.

1. **§1 SDK pick** — live2d-py vs. Cubism SDK Python vs. roll-our-own. Spec recommends (a) live2d-py for the v1 daily-driver bar. Override (b) Cubism SDK if license posture for a personal-use binary is a concern Eric wants to vet upstream; (c) roll-our-own only if both candidates fail the install / fidelity bar.
2. **§2 click-through policy** — full click-through with kill-button elsewhere (a), or per-pixel opaque-regions-accept-clicks via Windows native flags (b). Spec recommends (a) for v1 — simplest path, smallest Windows-native surface. Override (b) if Eric wants the avatar window to be the kill-switch target.
3. **§3 IPC architecture** — in-process via qasync (a), or side-process via JSONL stdin/stdout (b). Spec recommends (a). Override (b) if Eric prioritizes crash isolation over IPC latency. Note: P4.A2's spec will be parameterized on this pick — if Eric picks (b), A2's file partition changes substantially.

---

## (a)/(b) split framing

P4.A1 is **not** mixed-surface. It is research-only — all output is markdown under `rebuild/drafts/research/`. There is no Linux/Windows split to name; both halves of the avatar component (A2 code under Partial DoD, A3 code under Partial DoD, A4 Windows e2e under Full DoD) are scoped to their own queue items.

The Planner does not need to split P4.A1 when promoting from `[ ]` to `[in-progress]`; the existing `[linux-runnable] [P2] [M]` tag is correct.

## Notes on what this spec deliberately is NOT

- **Not the research itself.** This spec names the questions; the Worker doing P4.A1 answers them.
- **Not a decision doc.** The decision doc lands later under P4.A4 Full DoD per `rebuild/decisions/` precedent. P4.A1 produces a `research/`-tier draft.
- **Not a P4.A2 / P4.A3 spec.** Those need P4.A1's answers as inputs and get their own specs after Eric's picks land. A2's spec can be parameterized on (a)/(a)/(a) recs and shipped speculatively — see the companion spec drafted in the same slot.
- **Not a `pyproject.toml` edit.** Dependency additions live in A2's spec/diff.

## Verification checklist (for the Worker pulling this)

- [ ] Read this spec end-to-end.
- [ ] Read `sabrina-2/src/sabrina/events.py:55-63` (StateChanged shape) and `bus.py:31-83` (subscribe API).
- [ ] Glob `rebuild/drafts/research/2026-04-26-avatar-*.md` for any earlier cue-track research (not authoritative, but cite if relevant).
- [ ] Draft the research doc against the five-section structure above.
- [ ] File three NEEDS-INPUT entries (one per Q1/Q2/Q3 above) with `[from: worker / 2026-05-DD HH:MM]` headers — Eric's reply lands inline per `NEEDS-INPUT.md` "How to respond" protocol.
- [ ] Append JOURNAL.md per the standard Worker JOURNAL shape; mark `[linux-shipped]` since this ships under Partial DoD with no Windows path.
