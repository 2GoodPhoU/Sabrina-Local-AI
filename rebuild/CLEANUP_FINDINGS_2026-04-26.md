# Cleanup audit — 2026-04-26 (overnight)

**Owner:** code agent (autonomous overnight pass).
**Scope:** read-mostly audit across (G) `sabrina-2/src/sabrina/`,
(H) `sabrina-2/tests/test_smoke.py`, and (I) `rebuild/` decision docs +
ROADMAP. Did not run pytest; did not run `uv sync`. Phase-2 work is
already committed (see `dc730e3`); the focus here is post-commit
hygiene, not commit slicing.

## Executive summary

The pass-2 commit landed real features cleanly, but it landed a
**ship-blocker** in `config.py` (truncation residue introduced a
SyntaxError) plus a smaller dead-import in `listener/faster_whisper.py`.
Both were trivially fixable in place; both are now fixed. Beyond that,
the codebase is in healthy shape — no TODO/FIXME backlog, no stale
abstractions, no recurrence of the GUI-reconstruction defect class
that bit Phase 0. The bigger debt is in **rebuild/ docs**: ROADMAP,
sabrina-2/README, and three `validate-*.md` files reference the
*pre-implementation* drafts (file names like `memory/compact.py`,
`listener/wake.py`, `hey_sabrina.onnx`, `sabrina wake-test`) rather
than what actually shipped (`memory/compaction.py`, `listener/wake_word.py`,
`hey_jarvis`, no `wake-test` verb). Test coverage is decent on the new
code but lopsided — supervisor and compaction are well-covered, while
the wake-word *integration* (voice loop → race PTT vs. wake) and the
ONNX embedder *behaviour* (vs. the dim/factory smoke checks) lean on
"grep the source" tests that don't actually exercise behaviour.

**Counts:** 2 trivial fixes applied in-place; 23 findings (1 ship-blocker
just fixed, 0 currently open ship-blockers, 7 ship-soon, 11 nice-to-have,
4 informational). Codebase health: green; doc-coherence: yellow.

## Trivial fixes applied in-place

| # | File | Fix | Why trivial |
|---|---|---|---|
| F1 | `sabrina-2/src/sabrina/config.py` | Truncated lines 298–312 (a 15-line block of orphaned text that started mid-docstring `ings once (cached)...` plus a duplicated `def project_root()`). File was a SyntaxError; would have blown up `import sabrina.config` and therefore every test, every CLI verb, every voice-loop boot. After fix the file is 297 lines and parses cleanly; tail matches the previous-good version (`f22cd73:sabrina-2/src/sabrina/config.py`). | The committed-bad block was unreachable cruft from a heredoc reconstruction; deleting it restores the file to the pre-pass-2 shape with the new `apply_migrations` / `load_settings` body intact. |
| F2 | `sabrina-2/src/sabrina/listener/faster_whisper.py` | Removed `from typing import TYPE_CHECKING` + the `if TYPE_CHECKING: import numpy as np` block. `np` was never referenced in any annotation (the module's audio param is typed `Path \| object`, not `np.ndarray`). | Pure dead import; `from __future__ import annotations` is present so even forward references would have been strings. Cost: zero. |

> **Sandbox warning** — F2 hit the documented Edit/Write truncation
> hazard on the first attempt (file came back ~3.8 kB with a NUL-byte
> tail). Repaired via `git show HEAD:... > /tmp/orig.py && cp ...`
> followed by an in-place `sed -i` with no Edit tool involvement. Both
> fixes are byte-clean and AST-parsable; ran `python3 -c "import ast,
> os; [ast.parse(open(...).read()) ...]"` over the whole package — all
> 39 modules now parse. Recommend Eric `git diff sabrina-2/src/sabrina/`
> to confirm before committing.

## Findings to triage

### G — Existing-code audit

#### Ship-soon

| ID | File:line | Finding | Suggested resolution |
|---|---|---|---|
| G1 | `sabrina-2/src/sabrina/config.py` (recovered) | The truncation hazard hit `config.py` *in a committed file*. This means every reviewer who clones the repo currently has a broken `sabrina.config`. Auto-tests would not have caught it because the bash heredoc reconstruction happened *after* the test gates were claimed green. | Now patched (F1). Add a one-liner pre-commit / CI gate: `python -c "import compileall, sys; sys.exit(0 if compileall.compile_dir('sabrina-2/src', quiet=1) else 1)"`. Catches every future occurrence in seconds. |
| G2 | `sabrina-2/src/sabrina/cli.py` (1085 lines) | Past the 300-line guardrail by 3.6×. `voice_loop.py` (614) is also past. Both have header docstrings explaining why, but cli.py is now the sprawl candidate `thin-spot-split-plan.md` was written to address. | Time to ship `thin-spot-split-plan.md`. Most CLI verbs are independent — `memory_*`, `tts_*`, `vision`, `autostart` could each move to `sabrina/cli/<verb>.py` with no shared state. |
| G3 | `sabrina-2/src/sabrina/voice_loop.py:215-330` | Wake-word racing block in `run_voice_loop` is ~50 lines of inline orchestration with two `asyncio.create_task` + `asyncio.wait`. Hard to test in isolation; any future "wait for either A or B" needs to copy the pattern. | Lift `_listen_with_wake(ptt, wake_event, wake_monitor)` → `(audio, source)` helper. Second caller (e.g. push-to-yell or a third trigger) gets it for free; first caller is now testable. |
| G4 | `sabrina-2/src/sabrina/listener/wake_word.py` + `listener/vad.py` | The C8 deferred unification is a real ~30 LOC of duplicated `sd.InputStream` open/start/stop boilerplate across `WakeWordMonitor` and `AudioMonitor`. The cancel-token-vs-event divergence is real, but only ~10 of those 30 lines actually differ. | Defer per ACTION_ITEMS C8 (rule of three). But add a one-line doc cross-link in each file's header pointing at the other so the next person comparing them doesn't have to grep. |

#### Nice-to-have

| ID | File:line | Finding | Suggested resolution |
|---|---|---|---|
| G5 | `sabrina-2/src/sabrina/memory/embed.py:38` | `import os` is only used for `os.environ.get(...)` once in `_project_data_root`. Most of the rest of this codebase reaches for `os.environ` directly without aliasing. | Either inline as `import os` + `os.environ.get`, or move to `import os` style consistent with `cli.py:_open_memory`. Cosmetic. |
| G6 | `sabrina-2/src/sabrina/memory/embed.py:161-258` | `OnnxMiniLMEmbedder.embed_batch` does inline `import numpy as np` per call. This codebase top-level-imports numpy elsewhere (vad.py, wake_word.py, ptt.py). | Promote to a module-level import. The inline-import pattern was a deliberate choice for the legacy backend's torch import (it's actually expensive); numpy is unconditionally a top-level dep, so there's no payoff to lazy-loading it. |
| G7 | `sabrina-2/src/sabrina/voice_loop.py:42` | `WakeWordDetector` is imported but only referenced inside an `if settings.wake_word.enabled:` branch. When `enabled=False` (the default), opening voice_loop.py imports `wake_word.py` which imports `numpy` and `sounddevice` regardless. | Acceptable today (numpy + sounddevice are already loaded for ASR). Worth revisiting if startup latency regresses. |
| G8 | `sabrina-2/src/sabrina/memory/embed.py:_HF_RESOLVE_BASE` etc. | Three string templates + `_DownloadSpec` dataclass for what is currently *one* model download spec (MiniLM-L6-v2). Premature abstraction by anti-sprawl rule (no second model). | Inline the constants; delete `_DownloadSpec`. Or wait until a real second model lands and earn the dataclass. Not urgent. |
| G9 | Multiple modules | "Bare except + log.warning" pattern repeated ~12 times across `voice_loop.py`, `gui/settings.py`, `vad.py`, `wake_word.py`, `compaction.py`, all with `# noqa: BLE001`. | Pattern is correct (these guard sounddevice / GUI / SQLite paths where any exception means "fall back, don't kill the loop"), but the rationale is per-site. Consider a one-paragraph "exception discipline" note in `CLAUDE.md` so reviewers don't reflexively flag each one. |
| G10 | `sabrina-2/src/sabrina/supervisor.py:21` (header docstring) | "Why one file" justification is ~250 lines but actual file is 316 — already past the self-set 300 guard. | Trim or split. The autostart/{task,service}.py split called out in the docstring is now justified. |

#### Informational

| ID | Finding |
|---|---|
| G11 | No `TODO` / `FIXME` / `XXX` / `HACK` markers anywhere in `sabrina-2/src` or `sabrina-2/tests`. Healthy for a 4-month-old project. |
| G12 | All 39 source modules AST-parse after the F1 fix. No silent breakage from the heredoc reconstructions in `voice_loop.py`, `gui/settings.py`, `cli.py`, `test_smoke.py` (the four files Phase-0 audited). |
| G13 | Phase-0 GUI fixes (`mainloop`, `_collect`, `_preset_key_from_model_path`) are all in place and behave as documented. Verified by reading lines 407–472 of `gui/settings.py`; `_VOICE_PRESETS` is fully purged. |

### H — Test-suite quality audit

#### Ship-soon

| ID | File:line | Finding | Suggested resolution |
|---|---|---|---|
| H1 | `tests/test_smoke.py:1813-1820` (`test_voice_loop_imports_wake_word_classes`) | Implementation-test, not behaviour-test — it greps `voice_loop.py` source for the string `WakeWordDetector`. A wrapper that imports under a different alias would slip through; a wrapper that calls but never imports the class wouldn't be caught. The wake-word integration **C2** has *no* behaviour test of the PTT-vs-wake race. | Add an `asyncio.run`-based test that fakes both a `record_while_held` coroutine and a wake `asyncio.Event`, and asserts (a) wake firing first cancels PTT and pulls from `wake_monitor.stop()`, (b) PTT firing first cancels the wake task. The pattern is in `test_compaction_*` already. |
| H2 | `tests/test_smoke.py:1293-1314` and 1315-1377 | Both `test_voice_loop_imports_structlog_*` and `test_logging_vocabulary_renames_landed` grep file source. Symbol-presence proxies for behaviour. | Replace with a smoke that runs `run_voice_loop` for one mocked turn and asserts `turn.started` / `turn.first_audio_ms` / `turn.done` events appear in a captured structlog ringbuffer. The setup exists in `test_turn_id_binds_during_simulated_turn` (line 1241) — extend it. |
| H3 | `tests/test_smoke.py:1838-1844` (`test_gui_settings_window_has_mainloop_method`) | Hasattr check only. Catches the Phase-0 deletion regression but not "mainloop exists but does nothing." | Suffices for the regression it was written for. Leave as-is; flag in audit only. |
| H4 | No test exists for the **rotating** behaviour of the structlog file sink (only that it writes). `test_logging_file_sink_writes` confirms wiring; the 5 MB × 3 backupCount setting is untested. | Optional. Real-world rotation is exercised by Eric's daily-driver loop within hours; adding a 6 MB synthetic-write test is feasible but slow. Defer until a rotation bug is hypothesised. |

#### Nice-to-have

| ID | File:line | Finding | Suggested resolution |
|---|---|---|---|
| H5 | `tests/test_smoke.py:560` (`test_onnx_embedder_round_trip`) | Network-dependent: pulls ~80 MB from HuggingFace. `pytest.skip` on failure, but on Eric's box the first run will be slow, and CI with no network always skips → coverage gap nobody notices. | Either (a) add a `@pytest.mark.network` marker + opt-in via `pytest -m network`, or (b) ship a tiny pre-cached fixture (random tokenizer + 4-token model) so the cosine sanity test runs offline. |
| H6 | `tests/test_smoke.py:1454-1527` | All four supervisor tests use `lambda _s: None` as the sleeper. Backoff growth is asserted by the `sleeps` list, which is good. But `test_supervisor_backoff_caps_at_60_seconds` runs `restart_max=12` against a constant-crash spawner — that's 13 spawns + 12 sleeps; the test is fast because the sleeper is a no-op, but it's the only one doing 13 iterations. | Cap `restart_max` lower (4 is enough to verify cap behaviour). Keeps the test cheap and removes any chance of a future timeout-related flake. |
| H7 | No test exercises the `_shell_out_async` thread + `root.after(0, ...)` glue in `gui/settings.py`. | Tk thread tests are notoriously flaky; defer until a concrete bug surfaces. The pattern is short and inspectable. |
| H8 | `tests/test_smoke.py:1641-1684` | Three `test_memory_store_*` tests for compaction-related store methods all open + close their own `MemoryStore`; no shared fixture. | Consider a `@pytest.fixture` for an empty MemoryStore to reduce repetition. Cosmetic. |

#### Informational

| ID | Finding |
|---|---|
| H9 | 96 tests in one `test_smoke.py` (1866 lines). Past the point a new feature can land without scrolling. Not urgent — the file is well-sectioned with `--- step N ---` separators — but a `tests/test_memory.py` / `tests/test_supervisor.py` split would mirror the source layout and make blame-bisect easier. |
| H10 | Coverage of 2026-04-25 pass-2 work, by module: ONNX embedder (4 tests, factory + dim + cosine), wake-word detector (4 tests, all behaviour), wake-word *integration* (1 grep test — see H1), supervisor (9 tests, all behaviour), schema migration (1 test, idempotency only — no test of multi-step migration chain), compaction (5 tests, including end-to-end), redacting processor (2 tests, redact + truncate), rotating sink (1 wiring test). Strongest area: supervisor. Weakest: wake-word integration + multi-step schema migration. |

### I — Decision-doc / ROADMAP coherence audit

#### Ship-soon

| ID | File:line | Finding | Suggested resolution |
|---|---|---|---|
| I1 | `rebuild/ROADMAP.md` — Decision log section | 010 (Personality spec) is missing from the decision log even though `decisions/010-personality-spec.md` exists and was promoted out of `drafts/` per ACTION_ITEMS A. | Add `- [010 — Personality spec](decisions/010-personality-spec.md)` to the bullet list at the bottom of ROADMAP. |
| I2 | `rebuild/ROADMAP.md:8` | "Heads-up" warning still says "pass 2 work is uncommitted in the working tree." It's been committed since `dc730e3` (2026-04-25). | Delete the heads-up paragraph. Optionally replace with "Pass-2 features (wake-word scaffold, supervisor, ONNX embedder, compaction, GUI panel) committed `dc730e3`; Windows validation pending per `validate-*.md`." |
| I3 | `rebuild/ROADMAP.md` progress table, row 3 ("Wake word") | Marked `⏭ replaced by PTT`. Wake word is now scaffolded *and* wired into `voice_loop` (just `enabled=False` by default). | Update to `🟡 scaffolded (off by default)` with a footnote pointing at the validate doc. |
| I4 | `rebuild/ROADMAP.md` "Daily-driver readiness" checklist | Three of the four open boxes (wake word, autostart, crash recovery) are now scaffolded code, only awaiting validation. The checklist still shows them as fully open. | Convert to "[~] scaffolded; validation pending" so Eric sees the difference between "not built" and "built, awaiting Eric's mic." |
| I5 | `rebuild/ROADMAP.md` architecture diagram (lines ~270-290) | Shows `PTT ──▶ Listener` only. Wake-word path (`WakeWordMonitor → wake_event → race in voice_loop`) is not in the diagram. | Add a small wake-word lane to the diagram or footnote it. |
| I6 | `sabrina-2/README.md` status section | Says "57 tests running in ~3 s". Actual count: 96 (`grep -cE '^(def\|async def) test_' sabrina-2/tests/test_smoke.py`). Wake-word row still says "⏭ replaced by PTT". 010 personality not listed. ONNX embedder, compaction, supervisor not in the table. | Refresh the table after Eric runs the smoke pass. |
| I7 | `rebuild/validate-wake-word.md` | References the *pre-implementation* plan: `listener/wake.py` (singular), `voices/wake/hey_sabrina.onnx`, `sabrina wake-test` verb, `wake.model_loaded` log event. None of these exist. The actual implementation uses `listener/wake_word.py`, the bundled `hey_jarvis` openWakeWord model (no custom ONNX yet), no `wake-test` verb (manual smoke is `sabrina voice` with `enabled=true`), and `wake.loading` / `wake.ready` / `wake.detected` events. | Rewrite the validate doc to match the shipped surface. The existing doc is essentially unrunnable as-is. |
| I8 | `rebuild/validate-supervisor-autostart.md:9-11` | References `autostart/task_scheduler.py` and `autostart/service_nssm.py` as separate files. Implementation is single-file `supervisor.py` (intentional deviation per ACTION_ITEMS B3). Also names `test_supervisor_exits_on_child_clean_exit` but the actual test is `test_supervisor_exits_on_clean_child_exit`. | Update file paths in the prereq paragraph + fix the test name reference. |
| I9 | `rebuild/validate-007b-semantic-memory-gui.md:11` | References `memory/compact.py`. Actual file is `memory/compaction.py`. | One-token rename in the validate doc. Also: ACTION_ITEMS calls for a *new* `validate-memory-gui.md` to be written; the existing 007b doc may already cover everything intended for that. Reconcile. |

#### Nice-to-have

| ID | File:line | Finding | Suggested resolution |
|---|---|---|---|
| I10 | `rebuild/drafts/remaining-components-plan.md` "Ready to ship" list | Slots 1, 2, and 4 (supervisor, wake-word, semantic-memory-GUI) are listed as "Ready to ship (no Eric blockers)". All three are now scaffolded + committed. | Move them to a new "Shipped, awaiting validation" section so the index reflects code reality. |
| I11 | `rebuild/ACTION_ITEMS.md` | Entire doc framed as "everything in working tree, uncommitted." Pass-2 commit `dc730e3` landed all of B1-B4 + C1-C7. The "Eric morning todo" suggested-commit-slicing list is now historical. | Add a one-paragraph postscript at the top: "Pass-2 landed as a single commit (`dc730e3`) on 2026-04-25; commit-slicing recommendations below are historical. Outstanding items: per-component validation walks + the doc fixes in `CLEANUP_FINDINGS_2026-04-26.md`." |
| I12 | `rebuild/decisions/010-personality-spec.md` | Has no "Status:" line. All other shipped decisions (007, 008, 009) have `**Status:** Shipped.` near the top. | Add `**Status:** Spec accepted; lift into voice_loop._SYSTEM is its own session.` Mirrors 008's tone. |
| I13 | Two top-level `stage-pass2-commits*.ps1` scripts (untracked) | `stage-pass2-commits.ps1` and `stage-pass2-commits-v2.ps1` are both at repo root, untracked. v2's docstring says "v1 silently failed because pre-commit blocked it." Now that the commit landed, both are dead one-shots. | `Remove-Item stage-pass2-commits*.ps1`. They served their purpose. |

#### Informational

| ID | Finding |
|---|---|
| I14 | `rebuild/decisions/008-foundational-refactor-shipped.md` (the dedup stub from ACTION_ITEMS B0) is **not** present in HEAD. It was never committed in the first place — `git ls-files rebuild/decisions/` shows only the canonical `008-foundational-refactor-bundle.md`. ACTION_ITEMS B0's "git rm the stub" instruction is satisfied a priori. |
| I15 | `write_test.txt` was deleted in the working tree (`D` in `git status`); commit pending per ACTION_ITEMS. Nothing else to do beyond `git add -u && git commit`. |

## Footprint snapshot

```
sabrina-2/src/sabrina/  — 39 .py modules, 6,717 lines (incl. tests)
                         — production source: ~4,851 lines (excluding tests)
                         — largest module: cli.py (1,085) — over 300-line guard
                         — second largest: voice_loop.py (614)
                         — third largest: gui/settings.py (529)
sabrina-2/tests/        — 1 test file, 1,866 lines, 96 test functions
                         — sync: 85, async: 11
                         — coverage hot spots: supervisor (9), compaction (5)
                         — coverage thin spots: wake-word integration (1 grep),
                           multi-step schema migration (0)
sabrina-2/pyproject.toml — 24 runtime deps, 2 optional groups (dev,
                           legacy-embedder), 1 lockfile-pending change
                           (uv.lock dirty in working tree)
rebuild/                — 9 decision docs (001–009 plus 010 promoted)
                         — 9 validate-*.md procedures (3 with file-path drift)
                         — 27 .md drafts (incl. research/)
```

Codebase health read: **green-yellow.** The pass-2 commit is meaty
and well-tested for its supervisor + compaction surfaces. The
ship-blocker in `config.py` was a sandbox-tool failure, not a design
failure, and the codebase has zero TODO/FIXME debt and no recurrence
of the GUI-class reconstruction defects. The yellow is that
**rebuild/ doc state lags code state by one session** — ROADMAP,
README, and three validate-*.md files all reference pre-shipping
plans rather than what shipped. None of those drift items will break
on Eric's box; all of them slow down the "what state is this in"
read at the top of the next session.

## Suggested resolution sequence (for Eric, in priority order)

1. `git diff sabrina-2/src/sabrina/` to confirm F1 + F2; commit with
   `fix(config): drop truncation residue + dead numpy import`.
2. Add the `compileall`-based syntax gate to `.pre-commit-config.yaml`
   (G1). One line; catches the next truncation in seconds.
3. Refresh ROADMAP per I1–I5; refresh README per I6. Mostly find-and-
   replace + decision-log append.
4. Rewrite `validate-wake-word.md` to match shipped surface (I7).
   This is the validate doc most likely to actually be run next.
5. Repoint `validate-supervisor-autostart.md` and
   `validate-007b-semantic-memory-gui.md` (I8, I9). Token-level edits.
6. Cleanup: delete `stage-pass2-commits*.ps1` (I13); commit
   `write_test.txt` deletion (I15).
7. *(Optional, next session)* Land `thin-spot-split-plan.md` to
   address `cli.py` sprawl (G2) and supervisor.py header-vs-actual
   drift (G10).
