# Queue — Sabrina-Local-AI

> Prioritized work waiting to be picked up by Workers. The Planner curates this each morning. Workers pick the top unchecked item.

## Format

Each item:

```
- [ ] [P0|P1|P2] Title — one-sentence description.
  - Definition of done: ...
  - Notes: ...
```

Use `[in-progress]` instead of `[ ]` if a Worker started but couldn't finish (with a note in NEEDS-INPUT.md about what blocked them).

---
- [in-progress] [P1] Wire ClaudeBrain.chat to pass tools= and handle ToolUseBlock events, enabling write_clipboard ToolSpec end-to-end.
  - Definition of done: write_clipboard fires from a real voice turn; tests pass; ToolSpec.to_anthropic_dict round-trips; `[tools] enabled = true` in `sabrina.toml`.
  - Notes: canonical diff surface is `research/2026-04-29-claudebrain-tool-wire-up-surface.md` — read it first, do not re-derive from `rebuild/drafts/tool-use-plan.md`. Recommended SDK strategy: KEEP `stream.text_stream` for the fast path, dispatch tool_use via `final.content` + `final.stop_reason == "tool_use"` after the loop (~80 LOC vs ~150). Recursion cap = 5. Ollama raises `NotImplementedError` on `tools=`.
  - Caveat: brain/claude.py is +134 lines dirty in the working tree (see PROPOSED #5). Commit ONLY the wire-up delta; do not roll the rest of the working tree into your commit. If your wire-up conflicts with the existing modifications, mark `[in-progress]` and write to NEEDS-INPUT — don't try to resolve the triage yourself.
  - ToolSpec round-trip tests already exist at `tests/test_smoke.py:1869-1965` (per researcher 2026-04-29 03:30). Don't write new ones; commit the existing ones as part of your delta.
  - 2026-04-29 08:00 worker-8am: in-progress; bailed without modifying production code. See NEEDS-INPUT entry from worker-8am 2026-04-29 08:00 — DoD has two gates (pytest pass + Windows-side e2e voice turn) that a Linux-sandbox Worker structurally cannot satisfy, AND voice_loop.py is +33 dirty so a clean wire-up commit on it requires the working-tree triage that PROPOSED #5 explicitly reserves for human-led work. Need Eric to pick a path forward (split, runner-move, or accept partial-DoD ship).
  - 2026-04-30 07:00 planner: still `[in-progress]`. NEEDS-INPUT fork from worker-8am 2026-04-29 still unanswered; no PROPOSED box checked overnight. Today's Workers (8am–12pm) will idle the same as yesterday's unless Eric responds before 08:00. The unblock is small: any one of (a)/(b)/(c)/(d) on the worker-8am NEEDS-INPUT entry, OR a single `[x]` on PROPOSED #4/#9 (the (a)/(b) split).
  - 2026-05-01 07:00 planner: still `[in-progress]`, day-3 of identical block-state. No graduations possible — all 14 PROPOSED items unchecked, all 5 NEEDS-INPUT items unanswered. Today's 8am–12pm will idle the same as the last two days unless Eric responds before 08:00. Did not write a 6th NEEDS-INPUT planner-marker entry; the 2026-04-30 07:00 entry already covers it (role-doc dedup rule). Unblock is unchanged.
  - 2026-05-02 07:00 planner: still `[in-progress]`, day-4 of identical block-state. No graduations possible — same 14 PROPOSED items unchecked (no new ones tonight; only delta in the working tree was the expected `digests/2026-05-01.md`), same 5 NEEDS-INPUT items unanswered. Today's 8am–12pm will idle the same as the last three days unless Eric responds before 08:00. Dedup rule still fires on the 2026-04-30 07:00 planner-marker; no new NEEDS-INPUT planner entry written. Unblock is unchanged: one `[x]` on PROPOSED #4 or #9, or one `[answered]` on the worker-8am DoD-gate fork, or `[x]` on PROPOSED #5 (working-tree triage).
  - 2026-05-03 07:00 planner: still `[in-progress]`, day-5 of identical block-state. No graduations possible — same 14 PROPOSED items unchecked (no new ones tonight; only delta in the working tree was the expected `digests/2026-05-02.md`), same 5 NEEDS-INPUT items unanswered. Today's 8am–12pm will idle the same as the last four days unless Eric responds before 08:00. Dedup rule still fires on the 2026-04-30 07:00 planner-marker (4th consecutive planner dedup-skip); no new NEEDS-INPUT planner entry written. Unblock is unchanged: one `[x]` on PROPOSED #4 or #9, or one `[answered]` on the worker-8am DoD-gate fork, or `[x]` on PROPOSED #5 (working-tree triage).
  - 2026-05-04 07:00 planner: still `[in-progress]`, day-6 of identical block-state. No graduations possible — same `[in-progress]` P1, same 5 NEEDS-INPUT items unanswered. PROPOSED count grew 14 → 24 overnight via the out-of-band workflow-efficiency-analysis run (2026-05-04 14:00 in JOURNAL); 0 of the 10 new items are checked. Today's 8am–12pm will idle the same as the last five days unless Eric responds before 08:00. Dedup rule still fires on the 2026-04-30 07:00 planner-marker (5th consecutive planner dedup-skip); no new NEEDS-INPUT planner entry written. Unblock menu now expanded — in addition to the original three (one `[x]` on PROPOSED #4 or #9, or one `[answered]` on the worker-8am DoD-gate fork, or `[x]` on PROPOSED #5), Eric can also `[x]` PROPOSED #19 + #20 together (partial-DoD tier in CLAUDE.md + planner split-authority for mixed-surface items), which would let tomorrow's planner stage the (a)-half wire-up automatically as a `[linux-runnable]` queue item without further human triage. The two-`[x]` path on #19 + #20 is the highest-leverage harness-side unblock; the one-`[x]` path on #4 or #9 is the highest-leverage queue-side unblock — either pair makes tomorrow's 8am Worker actionable for the first time in 6 days.
  - 2026-05-04 unblock run: PROPOSED #4 + #9 + #19 + #20 all approved out-of-band via the workflow-efficiency research. CLAUDE.md now defines a Partial-DoD tier; planner.md step 3 now grants split authority. The single `[in-progress]` P1 above is hereby split into the two items below. This `[in-progress]` line is retained as the parent reference; the two new items are the actionable units.

- [in-progress] [linux-runnable] [partial-dod-eligible] [P1] ClaudeBrain wire-up (a-half) — protocol.py + claude.py + ollama.py + 6 unit tests.
  - Definition of done (Partial DoD per CLAUDE.md "Partial-DoD tiers"): `python -m compileall sabrina-2/src` clean; the 6 new unit tests pass under the Cowork Linux/3.10 sandbox; ToolSpec round-trip tests at `tests/test_smoke.py:1869-1965` continue to pass; no changes to `voice_loop.py`, `events.py`, `sabrina.toml`, audio/clipboard/pywin32 paths; diff committed to `automation/worker-2026-MM-DD-Nam` with a draft PR titled `e2e: pending Windows runner` and a Windows DoD checklist in the PR body. Item moves to `[linux-shipped]` on commit; promotion to `[done]` waits for the (b)-half + Windows e2e.
  - Notes: canonical diff surface is `research/2026-04-29-claudebrain-tool-wire-up-surface.md` — read it first; do NOT re-derive from `rebuild/drafts/tool-use-plan.md`. SDK strategy: KEEP `stream.text_stream` for the fast path; dispatch tool_use via `final.content` + `final.stop_reason == "tool_use"` after the loop completes (~80 LOC). Recursion cap = 5. Tool-result follow-up uses `tool_use_id` + JSON-stringified content + `is_error`. `ollama.py` raises `NotImplementedError` on `tools=` with the exact message specified in the research doc.
  - Caveat: `brain/claude.py` is +134 lines dirty in the working tree (PROPOSED #5, personality blocks per JOURNAL). Commit ONLY the wire-up delta; do not roll the rest of the working tree into your commit. If your wire-up conflicts with the existing modifications, mark `[in-progress]` and write to NEEDS-INPUT — do not attempt the working-tree triage from inside a Worker run (PROPOSED #5 reserves that for human-led work).
  - ToolSpec round-trip tests already exist at `tests/test_smoke.py:1869-1965` (per researcher 2026-04-29 03:30). Don't write new ones; commit the existing ones as part of your delta.
  - 2026-05-04 09:00 worker-9am: code is done, commit blocked. Wire-up landed clean in working tree (protocol.py +50, claude.py +279 wire-up + personality, ollama.py +15, test_smoke.py +974 incl. 6 new tests). Linux gates GREEN: `python -m compileall -q sabrina-2/src sabrina-2/tests` clean; AST-parses clean for all four files; 6 new wire-up tests PASS under Linux/3.10 (executes_one_tool_and_continues, recursion_cap_yields_done_with_cap_reason, tool_handler_error_surfaces_in_tool_result, unknown_tool_name_returns_error_result, ollama_raises_cleanly_when_tools_provided, brain_chat_tools_none_is_backward_compatible); 4 existing ToolSpec round-trip tests at `tests/test_smoke.py:1869-1965` continue to PASS. Edit-tool truncation hit twice mid-run per CLAUDE.md hazard ("Edit-tool truncation is a recurring hazard — verify file contents post-edit"); recovered both times via bash heredoc + AST verification. Code-review self-pass: no P0/P1; P2/P3 noted in NEEDS-INPUT entry. **Blocked on commit step**: stale `.git/index.lock` (5 days old, 0 bytes, mtime 2026-04-29 14:15:52 UTC) prevents `git add`. Per `roles/worker.md` step 7 ("Do NOT delete the lock"), bailing without commit. Marking `[in-progress]` with pointer to NEEDS-INPUT entry from worker-9am 2026-05-04 09:00. Eric clears the lock and either runs the commit himself (option (a) in the entry) or leaves the work in-tree for tomorrow's 8am Worker (option (b)).
  - 2026-05-05 07:00 planner: still `[in-progress]`, stale `.git/index.lock` still in place (per night-auditor 02:37 finding the lock unchanged). Code in working tree intact (verified by night-auditor's spot-check of tail integrity on the four touched files). **Worker fall-through**: today's Workers should fall through to one of the four other Next-pull-ready Linux-runnable items below (P5.2 / P5.4 / P5.5; P2.1's research DoD has been satisfied this morning by researcher 03:30 — see Decomposed section). Eric: clear `.git/index.lock` per the worker-9am 2026-05-04 09:00 NEEDS-INPUT options (a)/(b)/(c) to unblock the commit. Today is the first plausibly-productive Worker slot in 7 days regardless of lock-state.

- [ ] [windows-required] [P1] ClaudeBrain wire-up (b-half) — events.py + voice_loop.py + sabrina.toml flip + Windows e2e validation.
  - Definition of done (Full DoD per CLAUDE.md): `write_clipboard` fires from a real voice turn on Windows; `pytest` passes on Windows; `[tools] enabled = true` in `sabrina.toml`; vision turns continue to pass `tools=None`; voice loop validated end-to-end (record sample → STT → brain → TTS) per CLAUDE.md.
  - Notes: depends on the (a)-half landing first. Canonical surface is the same research doc — §5 (events.py + voice_loop.py wire-up) and §6 (toml flip + e2e checklist). This item is intentionally NOT picked up by Linux-sandbox Workers; it sits in QUEUE for Eric's next Windows session. When the (a)-half hits `[linux-shipped]`, Eric promotes it to `[done]` together with this item once the e2e gate fires.

---

## Decomposed (next-pull-ready)

> Authored 2026-05-04 18:00 by the `[roadmap] sabrina-backlog-decomposition` run. Decomposes the four post-Phase-1 phases of `ROADMAP.md` (Phase 2 daily-driver gaps, Phase 4 avatar/automation/router, Phase 5 legacy gate, Phase 6 bake-in/archive/release) into worker-pickable units. Each item carries DoD + effort (S = ~1h, M = 1–3h, L = multi-slot) + dependency pointer + a `[linux-runnable]`/`[windows-required]` runtime tag. Phase 0 + Phase 1 are shipped — not decomposed. Phase 3 (a)/(b) ClaudeBrain wire-up is in-flight above and intentionally untouched by this pass.

The five items below are the highest-leverage Linux-runnable pulls from the decomposed backlog, ordered smallest-first. The (a)-half ClaudeBrain wire-up at the top of this file is the canonical first pull and is referenced (not duplicated) here. Tomorrow's 8am Worker should pick one if the (a)-half is unblocked, or the next one in line if not.

- **(reference) Phase 3 (a)-half ClaudeBrain wire-up** — see `[in-progress]` item above. Code-complete in working tree; commit blocked on stale `.git/index.lock`. First pull once Eric clears the lock per the worker-9am NEEDS-INPUT entry.

- [in-progress] [linux-runnable] [partial-dod-eligible] [P1] [S] **P5.2 Port — keyboard shortcut table → `sabrina-2/data/shortcuts.yaml`** — extract the copy/paste/select-all/etc. shortcut dictionary from `services/automation/automation.py` into a YAML data file that Phase 4 automation can load.
  - Definition of done (Partial DoD per CLAUDE.md): `sabrina-2/data/shortcuts.yaml` exists with the legacy shortcut table; a tiny `tests/test_shortcuts_yaml.py` validates that every entry parses to a `(modifier, key)` tuple of strings; `python -m compileall sabrina-2/src` clean; no production-code changes; commit lands on `automation/<role>-2026-MM-DD-Nam` with `Windows-pending: e2e` in the body (no e2e needed in practice — data file).
  - Notes: pure data port. Original location: `services/automation/automation.py` shortcut dict (read-only, off-limits to modify per CLAUDE.md). Listed as port item #2 in `LEGACY_REPLACEMENT_GATE.md` §"What's still uniquely in legacy" (~0.5h estimate). Composes with Phase 4 automation work (P4.B2) — that item consumes this data.
  - Dependencies: none. No conflict with the dirty `brain/claude.py` working tree.
  - 2026-05-05 08:00 worker-8am: code is done, commit blocked on the same stale `.git/index.lock` (now 6 days old) that's blocking the (a)-half wire-up. Authored `sabrina-2/data/shortcuts.yaml` (17 entries, verbatim port from `services/automation/automation.py:47-65`), `sabrina-2/tests/test_shortcuts_yaml.py` (20 parametrized tests including a presence-check per legacy entry + structural guard for `[modifier..., key]` shape), and a targeted `sabrina-2/.gitignore` tweak (`/data/*` + `!/data/*.yaml` negation so YAML data assets are tracked while runtime `sabrina.db` stays ignored — verified via `git check-ignore`). Linux Partial-DoD gates GREEN: `python -m compileall -q sabrina-2/src sabrina-2/tests` clean; AST parses clean; pytest 20/20 PASS under Linux/3.10 sandbox; no production-code changes (only data + test + gitignore). Edit-tool truncation hit once on the .gitignore mid-edit; recovered via bash heredoc per CLAUDE.md hazard. Marking `[in-progress]` per role doc step 8 with pointer to NEEDS-INPUT entry from worker-8am 2026-05-05 08:00. Files in tree are byte-identical to what the next Worker will see; pickup is clean once Eric clears the lock.

- [ ] [linux-runnable] [partial-dod-eligible] [P1] [S] **P5.4 Port — test fixtures into `sabrina-2/tests/data/`** — copy `conversation_history.json` + `default_memory.json` from legacy `scripts/` to a new `tests/data/` directory.
  - Definition of done (Partial DoD): `sabrina-2/tests/data/conversation_history.json` and `sabrina-2/tests/data/default_memory.json` exist; a tiny `tests/test_fixtures_load.py` validates that both fixtures parse as JSON and have the expected top-level shape; `python -m compileall sabrina-2/src` clean; commit lands on `automation/<role>-2026-MM-DD-Nam`.
  - Notes: pure data port. Listed as port item #4 in `LEGACY_REPLACEMENT_GATE.md` (~1h estimate). Composes with P5.5 (pytest scaffolding) — those tests will read from this directory.
  - Dependencies: none.

- [ ] [linux-runnable] [partial-dod-eligible] [P1] [M] **P5.5 Port — pytest scaffolding (`conftest.py` + `test_utils/`)** — port the path helpers and mock factories from legacy `tests/conftest.py` and `tests/test_utils/` into `sabrina-2/tests/conftest.py`, modernized for the rebuild's surface.
  - Definition of done (Partial DoD): `sabrina-2/tests/conftest.py` exists with the path-helper + mock-factory primitives the legacy version provided, adapted to the rebuild's protocol-based architecture (no references to `core/` / `services/` / `utilities/`); the existing `tests/test_smoke.py` continues to pass under the Cowork Linux/3.10 sandbox; new fixtures have at least one test using each; `python -m compileall sabrina-2/src sabrina-2/tests` clean; commit lands on `automation/<role>-2026-MM-DD-Nam` with `Windows-pending: e2e`.
  - **Spec at `rebuild/drafts/research/2026-05-05-p55-pytest-scaffolding-port-spec.md`** (spec-writer 2026-05-05 06:50) — read this before pulling. Covers what to port verbatim (path/temp/time helpers + `requires_gpu` marker), what to drop because the rebuild rejected the abstractions they mocked (`mock_event_bus`, `mock_state_machine`, all `Mock*Service` factories, `sabrina_core` fixture, three-way unit/integration/e2e split, `get_component_path`/`get_config_path`), and what to author fresh against the rebuild's protocols (`make_fake_brain`/`make_fake_speaker`/`make_fake_listener`/`make_fake_bus`/`make_cancel_token` in a new `sabrina-2/tests/test_utils/mocks.py`). Marker-list narrowed to `requires_gpu` + `requires_windows`.
  - Notes: port item #5 in `LEGACY_REPLACEMENT_GATE.md` (~2h). The legacy `conftest.py` references the legacy event bus + state machine (the abstractions the rebuild rejected) — port the *primitives*, not the *abstractions*. Composes with P5.4.
  - Dependencies: P5.4 (test fixtures) for full coverage; can be partially landed without it.

- [done-pending-move] [linux-runnable] [P1] [M] **P2.1 Wake-word — custom "Hey Sabrina" training pipeline research draft** — bounded investigation into openWakeWord's training-data shape, tooling, and packaging path, given the current `hey_jarvis` placeholder.
  - Definition of done (research-only, no DoD tier — it's a research artifact): `research/2026-05-05-wake-word-training-pipeline.md` exists describing (1) the openWakeWord training data format + minimum sample counts, (2) the audio capture / synthesis pipeline (Eric's voice samples vs. TTS-generated negatives), (3) the .onnx packaging shape that drops into `sabrina-2/models/openwakeword/`, (4) the validation procedure on Windows once trained, (5) a reasoned go/no-go recommendation. No code changes.
  - **2026-05-05 03:30 researcher: DoD satisfied.** `research/2026-05-05-wake-word-training-pipeline.md` exists (~270 lines, recommendation = Go). Key findings: (1) train inside WSL2 (Eric has Ubuntu + Ubuntu-22.04 installed) — predecessor plan's Windows-CPU assumption is wrong against current upstream tooling; (2) replace hand-rolled 200-speaker × prosody loop with a ~30-line wrapper around `piper-sample-generator`; (3) drop `voices/wake/hey_sabrina.onnx` for QUEUE-P2.2's `sabrina-2/models/openwakeword/hey_sabrina.onnx`; (4) verifier-models on Eric's voice are documented out-of-MVP follow-up. Three new PROPOSED items appended (wake-word-plan amendment, sandbox-host probe, ship-criterion citation). Worker should move this item to DONE in their next slot, or close it manually in evening review.
  - Notes: this was the natural follow-up to the candidate the researcher 2026-04-30 03:30 entry surfaced in the bounded-question menu. STATE.md flagged "Hey Sabrina wake-word training" as a known one-day task. The research doc unblocks P2.2 pending the proposed sandbox-host probe (PROPOSED #33).
  - Dependencies: none. Pure research; worked against current openWakeWord docs + the existing scaffold in `listener/wake_word.py`.

---

## Decomposed by phase

> Items below the `Next-pull-ready` selection. Each phase's items are listed in rough sequence (earliest first). When a `[linux-runnable]` item's dependency is `[windows-required]`, the Linux work can still ship under Partial DoD; only the parent item's promotion to `[done]` waits for the Windows gate.

### Phase 2 — Daily-driver gaps (in progress)

> Three of the five readiness items remain after barge-in: wake-word + autostart + supervisor + budget. Wake-word splits into a research item (P2.1, in `Next-pull-ready` above), a build item (P2.2), and a Windows validation gate (P2.3).

- [ ] [linux-runnable] [partial-dod-eligible] [P1] [L] **P2.2 Wake-word — train + package "Hey Sabrina" custom model** — execute the training pipeline P2.1 grounds, produce a packaged `.onnx`, drop it into `sabrina-2/models/openwakeword/`, point `[wake_word]` config at it.
  - Definition of done (Partial DoD): `sabrina-2/models/openwakeword/hey_sabrina.onnx` exists; `sabrina.toml` `[wake_word]` block default `model_path` updated; a unit test validates the model file loads via openWakeWord's API under Linux; `enabled` stays `false` in the committed toml (gate flip is P2.3); `python -m compileall sabrina-2/src` clean; commit on `automation/<role>-2026-MM-DD-Nam` with `Windows-pending: e2e`.
  - Notes: depends on P2.1's research doc landing. Audio capture is Eric-side; if the research doc lands a "TTS-generated samples are sufficient" path, that branch is fully Linux-runnable.
  - Dependencies: P2.1.

- [ ] [windows-required] [P1] [S] **P2.3 Wake-word — Windows validation + flip `[wake_word] enabled = true`** — load the custom model on Eric's i7-13700K/4080/Win11 box, run the `validate-wake-word.md` procedure, flip the toml flag, file decision doc.
  - Definition of done (Full DoD): `validate-wake-word.md` checklist runs clean on Windows; `sabrina voice` activates on "Hey Sabrina" with no false positives in a 10-minute background-conversation test; `[wake_word] enabled = true` in `sabrina.toml`; `pytest` passes on Windows; decision doc filed (next number in `rebuild/decisions/`, decision-doc voice).
  - Notes: this is the Component 3 Full-DoD gate per ROADMAP §"Gate 1 — Component completeness". One of the v1.0 movers.
  - Dependencies: P2.2.

- [ ] [linux-runnable] [P1] [M] **P2.4 Autostart — research approach + draft (Task Scheduler vs. registry vs. NSSM vs. shell:startup)** — bounded comparison of the Windows autostart-on-login mechanisms, recommendation, draft of the implementation surface.
  - Definition of done (research-only): `research/2026-05-MM-autostart-approach.md` exists comparing Task Scheduler / Run-key registry / NSSM service / shell:startup .lnk for: (1) reliability under power events + RDP login + multi-user, (2) install/uninstall surface (does Eric need to elevate?), (3) crash-recovery composition with the Phase-2 supervisor, (4) Eric's recommendation. No code changes.
  - Notes: STATE/CLAUDE.md note `drafts/` already has supervisor + autostart drafts — this research item supersedes them with a concrete pick before P2.5 builds.
  - Dependencies: none.

- [ ] [windows-required] [P1] [M] **P2.5 Autostart — implement OS-level launch on login** — install + uninstall scripts per P2.4's pick; verify `sabrina voice` runs on a fresh Windows login.
  - Definition of done (Full DoD): `sabrina-2/scripts/install_autostart.ps1` (or equivalent) creates the autostart entry; `sabrina-2/scripts/uninstall_autostart.ps1` removes it; reboot test on Eric's box shows `sabrina voice` running within 30 s of login; `pytest` passes; decision doc filed.
  - Notes: closes daily-driver readiness item #2.
  - Dependencies: P2.4.

- [ ] [windows-required] [P1] [M] **P2.6 Crash-recovery supervisor — implement + ship** — build the supervisor primitive `drafts/` already designs; verify it restarts `sabrina voice` after a forced kill.
  - Definition of done (Full DoD): supervisor module in `sabrina-2/src/sabrina/` (location TBD by impl) restarts the voice loop within 5 s of a forced exit; `pytest` passes (mock-restart unit test); manual kill-and-recover test on Eric's box shows clean recovery; decision doc filed.
  - Notes: closes daily-driver readiness item #3. Composes with P2.5 — supervisor wraps the autostart entry.
  - Dependencies: P2.5 (composition); could ship independently with manual launch.

- [ ] [linux-runnable] [partial-dod-eligible] [P1] [M] **P2.7 Budget tracker — telemetry hook + `sabrina budget` CLI** — instrument `claude.py` to log per-turn token + cost numbers; build the `sabrina budget` typer command that reads the rolling log and reports daily/monthly totals against the $0/$10/$100 thresholds from decision 001.
  - Definition of done (Partial DoD): `claude.py` emits per-turn `BudgetEvent` (or equivalent) without changing voice-loop runtime semantics; JSONL log lands under `~/.sabrina/budget/`; `sabrina budget` prints daily + month-to-date with threshold annotations; unit tests for the CLI summary math + the threshold logic; `python -m compileall sabrina-2/src` clean; commit on `automation/<role>-2026-MM-DD-Nam` with `Windows-pending: e2e`.
  - **Spec at `rebuild/drafts/research/2026-05-05-p27-budget-tracker-spec.md`** (spec-writer 2026-05-05 06:50) — read this before pulling. (a)/(b) split is named explicitly: (a) Linux-runnable = `budget.py` (new) + `brain/protocol.py` (additive `cost_usd` on `Done`) + `brain/claude.py` (cost in usage-extraction branch) + `cli.py` (`sabrina budget today/month/show`) + `config.py` + `sabrina.toml` `[budget]` block + 6 unit tests; (b) Windows-required = `voice_loop.py` + `events.py` (additive `cost_usd`) + 1 real Windows voice session + decision doc (this maps to the existing P2.8 queue item — no new stage). Picks JSONL over SQLite (single-writer, ~180 KB/month at heavy use).
  - **Open NEEDS-INPUT from spec-writer 2026-05-05 06:50: cost-table location pick (a/b/c).** Spec recommends (a) inline constants in `budget.py`. Worker can ship the (a)-half against (a) without waiting for an answer; if Eric overrides before pull, Worker reroutes per the answer.
  - Notes: closes daily-driver readiness item #5. Telemetry hook is a thin additive on `ClaudeBrain.chat`; the partial-DoD-eligible scope is "everything except the live Windows voice-turn measurement." Composes with P4.C2 (router budget gate).
  - Dependencies: optional but recommended after Phase 3 (a)-half lands so the wire-up surface is stable.

- [ ] [windows-required] [P1] [S] **P2.8 Budget tracker — Windows e2e validation + threshold-warn UX check** — run `sabrina voice` for one real session on Windows, confirm telemetry lands, confirm the warn threshold fires audibly/visibly when crossed.
  - Definition of done (Full DoD): one session (>= 5 turns) produces a populated budget log; `sabrina budget` reports correctly; threshold-warn fires when the daily cap is artificially set low for the test; `pytest` passes; voice loop validated end-to-end.
  - Notes: closes Gate 2 daily-driver readiness item #5 fully. Promotes P2.7 from `[linux-shipped]` to `[done]`.
  - Dependencies: P2.7.

### Phase 4 — Avatar + Automation + Brain router (not started)

> Phase 4 entry requires Phase 2 exit + Phase 3 exit per ROADMAP §"Phase 4". Items below can be researched/scaffolded against the current tree under Partial DoD without violating phase order, but their `[done]` promotions wait until Phase 2/3 close.

#### Avatar (Live2D) — component 6 of `rebuild/ROADMAP.md`

- [ ] [linux-runnable] [P2] [M] **P4.A1 Avatar — architecture research + decision draft** — bounded study of Live2D Cubism SDK Python bindings, PyQt6 frameless/click-through windowing, IPC shape vs. the voice loop, frame budget.
  - Definition of done (research-only): `research/2026-05-MM-avatar-architecture.md` covers (1) SDK pick (Cubism Python wrapper vs. live2d-py vs. roll-our-own with OpenGL), (2) window layer (PyQt6 frameless + always-on-top + click-through cookbook for Windows), (3) IPC (subscribes to `StateChanged` events: in-process vs. side-process), (4) frame budget at 60fps target on RTX 4080, (5) Eric's pick.
  - Notes: was the natural follow-up the researcher 04-30 menu surfaced. Pure paperwork; unlocks A2/A3.
  - Dependencies: none.

- [ ] [linux-runnable] [partial-dod-eligible] [P2] [M] **P4.A2 Avatar — PyQt6 skeleton + StateChanged subscriber** — minimal frameless click-through window that subscribes to `StateChanged` and prints state transitions; no Live2D rig yet.
  - Definition of done (Partial DoD): `sabrina-2/src/sabrina/avatar/window.py` (or per A1's pick) launches a frameless PyQt6 window; subscribes to the event bus and logs each `StateChanged`; closes cleanly; unit test against a mocked event bus; `python -m compileall sabrina-2/src` clean; commit with `Windows-pending: e2e`.
  - Notes: validation of the frameless/always-on-top/click-through window behavior is Windows-only — that's A4. The skeleton itself works under Linux (Xvfb in CI if needed).
  - Dependencies: P4.A1.

- [ ] [linux-runnable] [partial-dod-eligible] [P2] [L] **P4.A3 Avatar — Live2D model bind + render loop** — bind the picked Live2D rig, drive the parameter set from `StateChanged`, run a render loop at the budget A1 sets.
  - Definition of done (Partial DoD): rig loads; model parameters change in response to mocked `idle/listening/thinking/speaking` transitions; render loop hits target framerate under sandbox-emulated GPU; `python -m compileall sabrina-2/src` clean; commit with `Windows-pending: e2e`.
  - Notes: full visual validation is Windows-only and rolls into A4.
  - Dependencies: P4.A2.

- [ ] [windows-required] [P2] [M] **P4.A4 Avatar — Windows e2e validation + decision doc + ship** — run the avatar against `sabrina voice` on Eric's box, confirm frameless/click-through/always-on-top behavior on Win11, file decision doc.
  - Definition of done (Full DoD): avatar window stays on top across other apps, click-through works on transparent regions, opaque regions accept clicks (kill button etc.), no perceptible voice-loop latency regression; `pytest` passes; decision doc filed; promotes A2 + A3 from `[linux-shipped]` to `[done]`.
  - Notes: closes Gate 1 component 9 (Avatar) for v1.0.
  - Dependencies: P4.A3.

#### Automation — component 9 of `rebuild/ROADMAP.md`

- [ ] [linux-runnable] [partial-dod-eligible] [P2] [M] **P4.B1 Automation — kill-switch + dry-run + ToolSpec scaffold** — implement the kill-switch primitive (global hotkey that aborts any running automation action) + dry-run mode flag; scaffold a `ToolSpec` for one harmless test action.
  - Definition of done (Partial DoD): `sabrina-2/src/sabrina/automation/__init__.py` exposes a `KillSwitch` context-manager (raises on hotkey trip); `dry_run: bool` flag plumbed through; one test ToolSpec (e.g. `noop_action`) registered like `write_clipboard`; unit tests for kill-switch trip + dry-run no-op behavior; `python -m compileall sabrina-2/src` clean; commit with `Windows-pending: e2e`.
  - Notes: most-dangerous-component-last per ROADMAP §"Phase 4". Kill-switch + dry-run are the prerequisite safety primitives before any real action ToolSpec ships.
  - Dependencies: Phase 3 done (so the ToolSpec wire-up exists). Composes with P5.2 data file.

- [ ] [linux-runnable] [partial-dod-eligible] [P2] [M] **P4.B2 Automation — `send_hotkey` ToolSpec backed by `data/shortcuts.yaml`** — first real automation ToolSpec. Loads the shortcut table P5.2 produces; exposes `send_hotkey(name)` that the brain can call.
  - Definition of done (Partial DoD): `send_hotkey` ToolSpec round-trips through `to_anthropic_dict()` per the existing test pattern; loads + validates `data/shortcuts.yaml` at registration; dry-run mode logs the would-be keypress without actually pressing; unit tests for both modes + an unknown-name error path; commit with `Windows-pending: e2e`.
  - Notes: real keypress validation is Windows-only and rolls into B4. The Tool layer is fully Linux-runnable under Partial DoD.
  - Dependencies: P5.2 (shortcut data) + P4.B1 (kill-switch + dry-run).

- [ ] [linux-runnable] [partial-dod-eligible] [P2] [M] **P4.B3 Automation — destructive-action allow-list config** — `[automation] destructive_actions = ["..."]` in `sabrina.toml` + a guard that raises before any non-allow-listed destructive ToolSpec runs.
  - Definition of done (Partial DoD): `sabrina.toml` `[automation]` block with `destructive_actions` list; ToolSpec registration tags actions as `destructive: bool`; runtime guard raises `DestructiveActionBlocked` when the brain calls a destructive action that isn't allow-listed; unit tests for both branches; `python -m compileall sabrina-2/src` clean; commit with `Windows-pending: e2e`.
  - Notes: the guard CLAUDE.md / ROADMAP §"Phase 4" call out as the third leg of automation safety alongside kill-switch + dry-run.
  - Dependencies: P4.B1.

- [ ] [windows-required] [P2] [M] **P4.B4 Automation — Windows e2e validation + decision doc + ship** — exercise `send_hotkey` for a real `cmd+c` on Eric's box, exercise the kill-switch trip, exercise the destructive-action block, file decision doc.
  - Definition of done (Full DoD): real keypresses fire correctly via pyautogui/pynput; kill-switch hotkey aborts a running action mid-flight; destructive-action guard refuses an attempt; `pytest` passes; voice loop validated; decision doc filed.
  - Notes: closes Gate 1 component 10 (Automation) for v1.0. Promotes B1 + B2 + B3 from `[linux-shipped]` to `[done]`.
  - Dependencies: P4.B1 + P4.B2 + P4.B3.

#### Brain router (deferred from component 4)

- [ ] [linux-runnable] [partial-dod-eligible] [P2] [M] **P4.C1 Router — persona-projection layer for Ollama parity** — minimal projection surface that lets Ollama emit operator-voice without re-implementing the personality blocks in `claude.py`.
  - Definition of done (Partial DoD): `sabrina-2/src/sabrina/brain/persona.py` (or chosen home) exposes a single function that projects the canonical personality spec into a model-agnostic system-prompt fragment; `OllamaBrain` calls it on every turn; the existing personality unit tests continue to pass; new tests assert Ollama's projected prompt matches the spec from decision 010; `python -m compileall sabrina-2/src` clean; commit with `Windows-pending: e2e`.
  - Notes: CLAUDE.md flags this as planned; bounded surface researcher 04-30 menu cited as freshest. Composes naturally with router routing logic in C2.
  - Dependencies: Phase 3 done (clean brain surface) — but can ship in parallel with the (b)-half if scoped to Ollama-only.

- [ ] [linux-runnable] [partial-dod-eligible] [P2] [M] **P4.C2 Router — Claude/Ollama routing policy + budget-gate hook** — selects backend per turn from policy (`force_local`, `cost_aware`, `claude_default`); hooks into P2.7's budget telemetry to escalate to Ollama when the daily cap nears.
  - Definition of done (Partial DoD): `sabrina-2/src/sabrina/brain/router.py` implements `Brain` protocol + delegates to Claude or Ollama per policy; `[brain] router_policy = "..."` in `sabrina.toml`; unit tests for each policy branch + the budget-gate escalation; `python -m compileall sabrina-2/src` clean; commit with `Windows-pending: e2e`.
  - Notes: the persona-projection in C1 is what makes the route swap voice-coherent. Without C1, swapping to Ollama mid-day breaks the operator voice.
  - Dependencies: P4.C1 + P2.7.

- [ ] [windows-required] [P2] [M] **P4.C3 Router — voice_loop integration + decision doc + Windows e2e** — wire the router into `voice_loop.py` (replacing the current direct ClaudeBrain instantiation), validate end-to-end on Windows, file decision doc.
  - Definition of done (Full DoD): `voice_loop.py` instantiates the router instead of ClaudeBrain directly; both routes (`force_local`, `claude_default`) ship a real voice turn end-to-end; `pytest` passes; voice loop validated; decision doc filed.
  - Notes: this is the only `voice_loop.py`-touching item in Phase 4. Promotes C1 + C2 from `[linux-shipped]` to `[done]`.
  - Dependencies: P4.C1 + P4.C2 + Phase 3 (b)-half.

### Phase 5 — Legacy replacement gate (not started)

> Five port items + a docs sweep + a mini-decision doc. Per `LEGACY_REPLACEMENT_GATE.md` §"Realistic timeline", the row is ~9.5 hours and sequenceable in one Saturday session for Eric or across several Worker slots.

- [ ] [linux-runnable] [partial-dod-eligible] [P1] [M] **P5.1 Port — audio device fallback (`audio_utils.py`)** — port the pyaudio device-name-matching loop from legacy `services/hearing/hearing.py` into a new `sabrina-2/src/sabrina/listener/audio_utils.py`.
  - Definition of done (Partial DoD): `audio_utils.py` exposes a `select_input_device()` function that falls back to name-matched lookup when the default device is unavailable; unit tests with mocked sounddevice device list; `python -m compileall sabrina-2/src` clean; commit with `Windows-pending: e2e`.
  - Notes: port item #1 in `LEGACY_REPLACEMENT_GATE.md` (~2h). Real device-fallback validation is Windows-only (different audio devices behave differently); the partial-DoD ship covers everything except that.
  - Dependencies: none. P5.5 (conftest) makes the test scaffold cleaner if it ships first.

- See `Next-pull-ready` above for **P5.2** (shortcut table), **P5.4** (test fixtures), **P5.5** (pytest scaffolding).

- [ ] [linux-runnable] [partial-dod-eligible] [P1] [L] **P5.3 Port — system-deps install script (`scripts/setup.py`)** — port the install-deps logic from legacy `scripts/sabrina_install.py` (Python ≥3.12, FFmpeg, GPU drivers, platform-specific install flags) into a new `sabrina-2/scripts/setup.py`.
  - Definition of done (Partial DoD): `sabrina-2/scripts/setup.py` exists; `python sabrina-2/scripts/setup.py --check` reports the deps state; `--install` is a no-op-by-default dry-run unless `--apply` is also passed (safety); unit tests cover the dep-detection branches; `python -m compileall sabrina-2/scripts` clean; commit with `Windows-pending: e2e`.
  - Notes: port item #3 in `LEGACY_REPLACEMENT_GATE.md` (~4h, the largest). Full install validation is Windows-only.
  - Dependencies: none.

- [ ] [linux-runnable] [P1] [S] **P5.6 File "legacy port complete" mini-decision doc** — once P5.1–P5.5 land, file a single decision doc covering the port batch (or skip-decisions for any items deliberately not ported).
  - Definition of done: `rebuild/decisions/0XX-legacy-port-complete.md` exists in decision-doc voice; references each of the five port items by status (shipped vs. skipped + why); commit on `automation/<role>-2026-MM-DD-Nam`.
  - Notes: closes box #1 of `LEGACY_REPLACEMENT_GATE.md` ("Migration-port complete").
  - Dependencies: P5.1–P5.5 all `[linux-shipped]` or `[done]` (whichever applies).

- [ ] [linux-runnable] [P1] [S] **P5.7 Cross-doc legacy-path-references sweep** — `grep -rn 'core/\|services/\|utilities/' rebuild/` per `LEGACY_REPLACEMENT_GATE.md` box #4; remove or redirect each hit.
  - Definition of done: post-sweep grep returns only intentional references (e.g. ROADMAP entries explaining what `archive/` is); a `research/2026-05-MM-legacy-references-sweep.md` file logs each before/after; commit on `automation/<role>-2026-MM-DD-Nam`.
  - Notes: closes box #4 of `LEGACY_REPLACEMENT_GATE.md`. Pure docs work, no code changes.
  - Dependencies: best run after P5.6 lands so the in-flight migration entries are stable.

### Phase 6 — Bake-in + archive flip + v1.0 release

> All `[windows-required]` except the docs rewrite + decision doc. Phase 6 is the rate-limiter callout in ROADMAP §"Rate-limiter callout".

- [ ] [windows-required] [P1] [L] **P6.1 Bake-in — 7 consecutive days of `sabrina voice` as Eric's primary assistant** — daily-driver clock per `LEGACY_REPLACEMENT_GATE.md` box #2.
  - Definition of done (Full DoD): 7 consecutive days with no regression filed in `ACTION_ITEMS.md`; any regression resets the clock to day 0; one-line journal entry per bake-in day in `JOURNAL.md` so the digest can spot the streak; closes boxes #2 + #3 of `LEGACY_REPLACEMENT_GATE.md`.
  - Notes: by definition not a Worker task — Eric uses `sabrina voice` for normal work and the streak is observed.
  - Dependencies: Phase 2 + Phase 3 + Phase 4 + Phase 5 all closed (per ROADMAP §"Phase 6 — Bake-in" entry criteria).

- [ ] [windows-required] [P1] [M] **P6.2 Archive flip — create `archive/`, move legacy folders, file `archive/README.md`** — git operation Eric runs (or a Worker runs with explicit branch + diff oversight).
  - Definition of done (Full DoD): `archive/` directory contains `core/`, `services/`, `utilities/`, `scripts/`, legacy `tests/`, `docs/`, `models/`, `config/` (move, not delete); `archive/README.md` is a one-page explanation of what `archive/` is; `git mv` history preserved; closes box #5 of `LEGACY_REPLACEMENT_GATE.md`.
  - Notes: see `LEGACY_REPLACEMENT_GATE.md` §"Post-archive disposition" — option 1 (same repo, `archive/` directory) is the recommended default.
  - Dependencies: P6.1 closed.

- [ ] [linux-runnable] [P1] [M] **P6.3 Top-level `README.md` rewrite for post-archive shape** — currently points at both legacy and rebuild; post-archive points only at `sabrina-2/` and `rebuild/` with a single "What is `archive/`?" footnote.
  - Definition of done: `README.md` reflects the post-archive shape; closes box #6 of `LEGACY_REPLACEMENT_GATE.md`; commit on `automation/<role>-2026-MM-DD-Nam`.
  - Notes: docs-only. Linux-runnable. Should land after P6.2 so the README description matches the directory tree.
  - Dependencies: P6.2.

- [ ] [linux-runnable] [P1] [S] **P6.4 `CLAUDE.md` "Where the code and docs live" rewrite** — stop listing legacy subtrees individually; describe `archive/` as a single fossil-cache.
  - Definition of done: `CLAUDE.md` post-archive shape lands; closes box #7 of `LEGACY_REPLACEMENT_GATE.md`; commit on `automation/<role>-2026-MM-DD-Nam`.
  - Notes: docs-only. Linux-runnable. CLAUDE.md is in-scope for ordinary edits (not in the off-limits list).
  - Dependencies: P6.2.

- [ ] [linux-runnable] [P1] [S] **P6.5 File `rebuild/decisions/011-v1.0-release.md`** — final decision doc, decision-doc voice, ties off the rebuild project as a closed unit.
  - Definition of done: `rebuild/decisions/011-v1.0-release.md` filed in decision-doc voice per ROADMAP §"Phase 6" item #6; ROADMAP gets its `v1.0 released 2026-MM-DD` final commit; commit on `automation/<role>-2026-MM-DD-Nam`.
  - Notes: this is the v1.0 ship marker. After this, ROADMAP's current-state marker stops being updated and gets archived; this QUEUE's `Decomposed (next-pull-ready)` section is closed out.
  - Dependencies: P6.1 + P6.2 + P6.3 + P6.4 all closed.
