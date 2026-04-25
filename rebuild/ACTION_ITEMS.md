# Action items — overnight 2026-04-25 (consolidated)

**Owner:** code (this session is the consolidation pass).
**Scope:** merges Track A (personality), Track B (code from earlier
overnight), and tonight's deltas (ONNX embedder, deferred-item wiring,
MCP audit, file integrity inventory) into one canonical doc. Replaces
`ACTION_ITEMS_code.md` + `ACTION_ITEMS_personality.md`, both now
deleted.

**State:** everything in working tree, **uncommitted**. Eric reviews +
commits in the morning. Sandbox notes:
- The Edit/Write tools on this mount truncate large writes silently
  (tracked in `feedback_write_tool_also_truncates`). Tonight's session
  hit it again on `voice_loop.py`, `gui/settings.py`, `config.py`,
  `cli.py`, and `test_smoke.py`. All five reconstructed via
  bash heredocs / Python splices. **Phase-0 inventory below catalogues
  the prior-session reconstructions; the new diffs are surgical splices,
  much lower drift risk.**
- `.git/config` has trailing NUL-byte corruption (line 23). Inside the
  sandbox we worked around with a `/tmp` git overlay; on Eric's box this
  is unlikely to bite (Windows git has different parsing) but worth a
  glance: `git config --get lfs.repositoryformatversion` should return
  `0` cleanly. If it errors, `git config --remove-section lfs` clears it.

---

## Summary table

| # | Work unit | Status | Files touched | Blockers / notes |
|---|---|---|---|---|
| A | Personality finalization (Track A) | Awaiting Eric review | `rebuild/drafts/personality-plan.md`, `rebuild/decisions/drafts/010-personality-spec.md` | "Dry humor" remains assumed — calibrate at first dogfood pass |
| B0 | Step 0: cleanup (dedup decision file + write_test.txt + when-you-return refresh) | Eric morning | `rebuild/decisions/008-foundational-refactor-shipped.md`, `rebuild/when-you-return.md`, `write_test.txt` | `git rm` the stub + write_test.txt |
| B1 | Step 1: logging vocabulary completion | Tests gate | `listener/faster_whisper.py`, `listener/record.py`, `voice_loop.py`, +3 tests | None |
| B2 | Step 2: wake-word scaffolding (`openwakeword`, `hey_jarvis`) | Validate per `validate-wake-word.md` (TBD) | `listener/wake_word.py` (new), `pyproject.toml`, `sabrina.toml`, `config.py`, +5 tests | Voice-loop wake-word integration **NOW WIRED** (see C2) |
| B3 | Step 3: supervisor + autostart | Validate per `validate-supervisor-autostart.md` | `supervisor.py` (new), `cli.py`, `sabrina.toml`, `config.py`, +9 tests | nssm `status` action not implemented; intentional defer |
| B4 | Step 4: 007b semantic-memory GUI + auto-compaction | Tests gate | `memory/store.py`, `memory/compaction.py` (new), `gui/settings.py`, `sabrina.toml`, `config.py`, +10 tests | Brain-as-summarizer **NOW WIRED** (see C3); summary injection **NOW WIRED** (see C4); GUI shell-outs **NOW WIRED** (see C6) |
| C0 | Tonight: integrity inventory of 4 prior-session reconstructions | Done — defects flagged below | (no edits) | Two real bugs in `gui/settings.py` reconstruction; both **fixed** in C5 |
| C1 | Tonight: ONNX embedder swap (drop sentence-transformers from default install) | Tests gate | `memory/embed.py`, `pyproject.toml`, `sabrina.toml`, `config.py`, `cli.py`, `voice_loop.py`, +4 tests | `sabrina download-models embedder` first run on Windows; needs HF reachable |
| C2 | Tonight: voice-loop wake-word integration | Validate per `validate-wake-word.md` (TBD) | `voice_loop.py` | First real gate is "say 'hey jarvis' on Eric's box" |
| C3 | Tonight: `sabrina memory-compact` CLI verb + brain-as-summarizer adapter | Tests gate | `cli.py` | Eric should manually compact a real session before trusting auto |
| C4 | Tonight: voice-loop summary injection (`load_summaries` -> head of `_SYSTEM`) | Tests gate | `voice_loop.py` | None |
| C5 | Tonight: `gui/settings.py` Phase-0 fixes (`mainloop`, `_collect`, `PRESETS` drift) | Tests gate | `gui/settings.py` | None |
| C6 | Tonight: GUI Compact-now / Reindex buttons -> subprocess shell-out | Manual GUI smoke | `gui/settings.py` | Needs `sabrina` console script on PATH; works via `uv run` invocation if it isn't |
| C7 | Tonight: MCP-compatibility audit appended to `tool-use-plan.md` | Awaiting Eric review | `rebuild/drafts/tool-use-plan.md` | Plan-doc only; no code |
| C8 | Tonight: AudioMonitor / WakeWordMonitor unification | **Deferred again, intentionally** | (none) | See "Deliberately not done" below |

---

## Per-unit detail

### A — Personality finalization

Track A's full report (now folded in here, file deleted):

- `rebuild/drafts/personality-plan.md` rewrote OPEN-QUESTIONS with
  recommendation + override knobs per question; refreshed "Where these
  signals came from"; added a concrete "System-prompt skeleton" section
  with token-budget table, cacheable-vs-dynamic markings, and per-backend
  differences.
- `rebuild/decisions/drafts/010-personality-spec.md` is a new ~1-page
  decision-doc draft in the voice of 002-006, citing back into the plan.
- Three recommendations to glance:
  | Q | Recommendation | Override |
  |---|---|---|
  | Profanity | Mirror Eric, never first turn | "never swear" / "always swear freely" |
  | Pronouns | she/her, no volunteered statement | they/them or no-pronoun |
  | Opinions | Hold technical, push back when load-bearing, non-committal on politics | stricter / looser |
- **One judgment call to sanity-check first:** "dry humor as default"
  remains assumed (extrapolation from terseness, not a demonstrated
  trait in 008/009/009a). Cheap to course-correct at first dogfood; the
  plan now flags it explicitly under "Still assumed." If wrong, fix is
  one line in voice rules + dialing back `amused`-leaning gestures.
- On sign-off: move `rebuild/decisions/drafts/010-personality-spec.md`
  to `rebuild/decisions/010-personality-spec.md`, drop `(DRAFT)` from
  title, drop `Status: Draft` line.
- Implementation (lifting the skeleton into `voice_loop._SYSTEM` /
  `chat._SYSTEM`) is a separate session — keeps the diff reviewable.

### B0 — Step 0 cleanup

- `rebuild/decisions/008-foundational-refactor-shipped.md` is an 8-line
  redirect stub. `git rm` it.
- `write_test.txt` at repo root needs `git rm`.
- `rebuild/when-you-return.md` is up-to-date with the overnight session
  table — no further action.

### B1 — Logging vocabulary

- `listener/faster_whisper.py`: `fw.loading` → `asr.loading`;
  `fw.loaded` → `asr.loaded`; `fw.cuda_detect_failed` → `asr.cuda_detect_failed`.
- `listener/record.py`: `rec.start` → `asr.rec.started`;
  `rec.done` → `asr.rec.done`.
- `voice_loop.py`: `embedder.ready` → `embed.ready`;
  `embedder.warmup_failed` → `embed.warmup_failed`. Plus `turn_id`
  contextvar binding per iteration; `turn.started`,
  `turn.first_audio_ms`, `turn.done` event names.
- 3 new tests in `tests/test_smoke.py` (`test_turn_id_binds_during_simulated_turn`,
  `test_voice_loop_imports_structlog_and_uuid_for_turn_correlation`,
  `test_logging_vocabulary_renames_landed`).
- Pre-declared event names for unshipped components (wake-word, supervisor,
  tools, automation, avatar, budget, compaction) live in the plan's table;
  call sites land alongside each component as it ships.

### B2 — Wake-word scaffolding

- **NEW** `listener/wake_word.py` (~270 lines). `WakeWordDetector`
  wraps openwakeword's `Model` with `feed(chunk)` returning the score on
  fire past cooldown. `WakeWordMonitor` opens a sounddevice
  `InputStream` during idle, ring-buffers the last 5 s, and invokes
  `on_detect(score)` from the audio thread.
- `pyproject.toml`: `openwakeword>=0.6` added to runtime deps.
- `config.py`: `WakeWordConfig(enabled=False, model="hey_jarvis",
  threshold=0.5, cooldown_ms=2000, device="")`.
- `sabrina.toml`: `[wake_word]` block.
- `listener/__init__.py`: re-exports `WakeWordDetector`, `WakeWordMonitor`.
- 5 tests using a stub openwakeword model (no real torch/onnx load).
- **Voice-loop wiring is now done** — see C2.

### B3 — Supervisor + autostart

- **NEW** `supervisor.py` (~315 lines). `run_supervised(child_argv,
  cfg, *, spawner, sleeper)` with crash-budget loop and injectable
  spawner/sleeper. Task Scheduler XML generator (UTF-16 LE BOM,
  `validate-supervisor-autostart.md` flag) + nssm command builders +
  `find_nssm`.
- `cli.py`: `sabrina run` (spawns voice loop under supervisor) + `sabrina
  autostart {enable|disable|status}` verbs. Mode-aware: routes to Task
  Scheduler in `task_scheduler` mode, nssm shell-outs in `service` mode.
- `config.py`: `SupervisorConfig(mode="task_scheduler", task_name="SabrinaAI",
  restart_max=5, restart_window_s=300, nssm_binary="")`.
- `sabrina.toml`: `[supervisor]` block.
- 9 tests covering crash budget, backoff growth, user-interrupt fast-path,
  XML rendering, BOM-prefixed write, schtasks invocation, nssm command
  sequence shape, config round-trip.
- **Deviations:** single-file (~315 lines, just over 300 guard) with
  "Why one file" docstring; `sabrina autostart status` for nssm mode is
  not implemented (parsing `nssm status` output has multiple shapes).

### B4 — 007b semantic-memory GUI + auto-compaction

- `memory/store.py` migrated to schema v1 (`kind` + `summarized_at`
  columns + index on kind). Idempotent via `PRAGMA user_version`.
  Tolerates "duplicate column" if a previous run left columns mid-
  migration. New methods: `append_summary`, `mark_summarized`,
  `load_summaries`, `count_uncompacted`, `total_turn_chars`,
  `oldest_uncompacted_turns`, `count_summaries`. Existing `search()`
  filters `WHERE m.kind = 'turn'` so summaries don't surface as retrieval
  matches.
- **NEW** `memory/compaction.py` (~180 lines). Token-based threshold
  trigger via `should_compact()`; `compact()` is async, takes a
  `Summarizer` Protocol; module-level `SUMMARIZATION_SYSTEM_PROMPT`;
  `CompactionResult` dataclass with skip-reason for visibility;
  `make_callable_summarizer(fn)` adapter for bare async functions.
- `config.py`: `CompactionConfig(mode="auto", threshold_tokens=50000,
  batch_size=200, chars_per_token=4.0)` under `MemoryConfig.compaction`.
- `sabrina.toml`: `[memory.compaction]` block.
- `gui/settings.py`: extended `_build_memory_tab` with Semantic /
  Compaction sub-frames + Compact-now / Reindex buttons. **Buttons now
  shell out (C6).**
- 10 tests covering migration idempotence, load/store filtering, count/
  total/mark APIs, threshold gating, manual-mode never-auto, end-to-end
  `compact()` with stub summarizer, config round-trip.
- **All deferred bits are now wired tonight** — see C2-C6.

### C0 — Phase-0 integrity inventory (defects found in prior reconstructions)

Result: all 4 prior-session reconstructions parse and have no missing
top-level def/class names. Two real defects in `gui/settings.py` only:

1. **`SettingsWindow.mainloop()` method dropped.** `open_settings()`
   calls `app.mainloop()` at line 61 but the reconstructed class no
   longer has it — would `AttributeError` at runtime. **Fixed in C5.**
2. **`_collect()` doesn't translate `_piper_preset`** to
   `tts.piper.voice_model`. Old `_collect_updates` skipped underscore-
   prefix keys + resolved preset via `PRESETS[key].id`. New `_collect`
   wrote `_piper_preset` raw, which `_nest` would turn into a top-level
   `_piper_preset` TOML key. Voice-preset save was silently broken.
   **Fixed in C5.**
3. **`_preset_key_from_model_path`** was using a hardcoded
   `_VOICE_PRESETS` dict instead of the canonical `PRESETS` from
   `sabrina.speaker.voices`. Drift risk if someone added a voice.
   **Fixed in C5** (now drives off `PRESETS` directly).

`voice_loop.py`, `config.py`, `memory/store.py` all clean — imports
preserved, all HEAD def/class names present in WT, AST-parses OK. No
behavior dropped. The `voice_loop.py` file shrank 533 → 515 (now 614
after tonight's C2/C4 splices) but the diff comparing line-by-line
function lists shows no missing methods.

### C1 — ONNX embedder swap

The highest-leverage change tonight per the survey's
"highest-leverage potential switch" callout.

- **`memory/embed.py` rewritten.** New `OnnxMiniLMEmbedder` class
  (default) implements the `Embedder` Protocol via `onnxruntime` +
  `tokenizers` (no torch). Mean-pooling + L2-normalize matches
  sentence-transformers' recipe for `all-MiniLM-L6-v2` exactly.
  `SentenceTransformerEmbedder` (the prior class) is kept as legacy
  fallback. `build_embedder(model_name, *, backend="onnx")` factory
  routes between them.
- **Lazy download to `<project_root>/data/embedder/<model_id>/`** on
  first `_ensure_loaded`. Override via `SABRINA_EMBEDDER_CACHE_DIR`
  env. Mirrors the `voices/` pattern so Windows `.gitignore` already
  excludes it (`data/` is gitignored).
- **`pyproject.toml`:** added `onnxruntime>=1.19` + `tokenizers>=0.20`
  to runtime deps. Moved `sentence-transformers>=3.0` to a new
  `[project.optional-dependencies] legacy-embedder` group. Default
  `uv sync` no longer pulls torch.
- **`config.py`:** new `EmbedderConfig(backend = "onnx" | "sentence-transformers")`
  nested under `SemanticMemoryConfig`. Default is "onnx".
- **`sabrina.toml`:** new `[memory.semantic.embedder]` block with
  `backend = "onnx"`.
- **`cli.py`:** `_open_memory()`, `memory_reindex`, `memory_search` all
  pass `backend=settings.memory.semantic.embedder.backend` to
  `build_embedder`. New `sabrina download-models [embedder|all]` verb
  pre-fetches assets so the first runtime turn isn't a blocking
  download. Verb is registered as a typer command.
- **`voice_loop.py`:** the lone `build_embedder(model_name)` call now
  forwards `backend=`. No other call-site change.
- **Tests added:**
  - `test_embedder_factory_routes_by_backend` — factory dispatch.
  - `test_embedder_dim_constant_is_384_for_default` — config plumbing.
  - `test_onnx_embedder_round_trip` — cosine sanity (synonyms beat
    unrelated by ≥ 0.10), asserts L2 normalization. Skips if onnxruntime
    or tokenizers missing or HF unreachable.
  - `test_embed_module_no_torch_import` — guard that `import sabrina.memory.embed`
    doesn't pull torch.

**Eric's first run on Windows:** `uv sync` to pull onnxruntime +
tokenizers + drop torch. Then `sabrina download-models embedder` to
fetch the ~80 MB ONNX file + tokenizer.json. Then `sabrina
memory-search "hello"` for a smoke test. Reverting if it goes sideways:
`uv sync --extra legacy-embedder`, then in `sabrina.toml` set
`[memory.semantic.embedder] backend = "sentence-transformers"`.

### C2 — Voice-loop wake-word integration

- `voice_loop.py` imports `WakeWordDetector`, `WakeWordMonitor`.
- New optional wiring: when `[wake_word].enabled`, builds detector +
  monitor with `_on_wake` callback that signals an `asyncio.Event` via
  `loop.call_soon_threadsafe`. Device falls back to `asr.input_device` /
  `input_device` when `[wake_word].device` is blank.
- Listen-step now races PTT vs. wake-event with `asyncio.wait(...,
  return_when=FIRST_COMPLETED)`. Whichever fires first wins; the loser
  task is cancelled.
- On wake fire, the monitor's ring buffer (last 5 s) is pulled and fed
  to ASR — no PTT needed. Logs `wake.handled` with sample count.
- Falls back gracefully when openwakeword can't load (yellow console
  warning, runs PTT-only).
- One regression test in `test_smoke.py` asserts
  `voice_loop.py` imports the wake-word classes (cheap
  read-source-and-grep style; the heavier behaviour test is an
  on-Windows manual smoke: enable in `sabrina.toml`, run `sabrina
  voice`, say "hey jarvis [pause] what time is it").

### C3 — `sabrina memory-compact` CLI verb

- `cli.py`: `sabrina memory-compact [--force] [--brain claude|ollama]
  [--fast/--full]` runs `compaction.compact(...)` with a brain-backed
  `Summarizer` adapter built from `_make_brain_summarizer`. The adapter
  drives `brain.chat(...)` with `SUMMARIZATION_SYSTEM_PROMPT` and joins
  TextDelta events. Defaults: chosen brain = `settings.brain.default`,
  fast model = on (cheaper for compaction; --full overrides).
- `--force` bypasses the threshold check.
- Eric morning: `sabrina memory-compact --force` once on a real session
  to see the prompt + summary in action. Tune
  `[memory.compaction].batch_size` if summaries feel too coarse.

### C4 — Voice-loop summary injection

- `voice_loop.py` now defines `_summary_block(memory)` that returns
  `"Long-term memory (compacted summaries):\n- [date] body\n..."` or
  None.
- Per-turn: built once per iteration, prepended to `turn_system` before
  vision rewrites or retrieval block concat. Summaries appear at the top
  of the system prompt; brain sees compacted long-term context first.
- 2 unit tests: `test_voice_loop_summary_block_helper_returns_none_for_no_summaries`,
  `test_voice_loop_summary_block_renders_header_and_rows`.

### C5 — `gui/settings.py` Phase-0 fixes (Three real bugs)

- Restored `SettingsWindow.mainloop()` method.
- `_collect()` now skips underscore-prefix keys and translates
  `_piper_preset` via `PRESETS[key].id` to `tts.piper.voice_model`.
- `_preset_key_from_model_path` drops the hardcoded
  `_VOICE_PRESETS` dict and walks `PRESETS` from `sabrina.speaker.voices`.
- 2 regression tests: `test_gui_settings_window_has_mainloop_method`,
  `test_gui_collect_filters_underscore_keys_and_translates_preset`.

### C6 — GUI Compact-now / Reindex shell-outs

- `gui/settings.py` adds `_shell_out_async(argv, *, label)` helper that
  spawns a subprocess in a daemon thread, updates the status label
  pre-flight ("Compacting... (running `sabrina memory-compact --force`)"),
  and posts the result back via `self.root.after(0, ...)` for thread-
  safety.
- "Compact now" → `["sabrina", "memory-compact", "--force"]`.
- "Reindex"   → `["sabrina", "memory-reindex"]`.
- **If `sabrina` isn't on PATH** (e.g. when running the GUI from a venv
  where the console script wasn't installed), the status label says
  `Compacting failed: ...`. Run via `uv run sabrina ...` directly until
  the script is on PATH.

### C7 — MCP-compatibility audit (plan-doc only)

`rebuild/drafts/tool-use-plan.md` now ends with an "MCP compatibility"
section (~120 lines) summarizing what's already MCP-shape (JSON Schema
input, sequential dispatch, BUILTIN_TOOLS-as-list_tools,
`CancelToken` semantics), what diverges (snake_case vs. camelCase, free-
form result vs. typed content, error shape) plus a 30-line concrete
delta to the protocol (`ToolSpec.to_mcp_dict()` /
`to_anthropic_dict()`, `ToolUseDone.is_error` property, content-block
wrapping helper). No code touched. Migration cost from "Anthropic
native v1" → "MCP transport" is then ~50 lines of MCP-server boilerplate
+ moving handlers under `list_tools`; schemas stay put.

### C8 — Audio monitor unification (deferred — intentionally)

Prior session's Step 2 deviation: the wake-word monitor opens its own
sounddevice InputStream rather than sharing one with `AudioMonitor`
(barge-in). Tonight I reviewed `vad.py` (250 lines, load-bearing for
shipped 009/009a barge-in) and `wake_word.py` (270 lines). Unifying
would extract a `_MicMonitor` base that owns: device, stream open/close,
captured-buffer/ring-buffer trim, lazy detector load. Cost: ~50-60 net
lines, but requires touching the just-shipped `vad.py` again. Two
reasons to defer:

1. **Anti-sprawl rule: second caller before abstraction is permitted,
   but the caller semantics differ enough** (cancel-token vs. event,
   dead-zone vs. cooldown, trim-to-VAD-start vs. ring-buffer) that the
   base class would carry awkward "if/else by mode" branches. The
   duplication is mostly the 30-line "open InputStream + start +
   stop-and-close" boilerplate; that's small.
2. **The mount truncation budget tonight is already spent** on five
   files. A sixth (`vad.py`) reconstruction round is an unforced error.
   Two stable files getting a refactor at the same time as a freshly-
   landing feature is a recipe for diffing pain.

Recommend revisit when a *third* mic-driven monitor type lands (e.g. a
"keyword-spotter" continuous-listen mode); at that point the base class
has its second caller and earns its keep.

---

## Eric's morning todo (in suggested order)

1. **Sandbox-cleanup commits** (one each):
   - `git rm rebuild/decisions/008-foundational-refactor-shipped.md`
   - `git rm write_test.txt`

2. **Smoke** (from `sabrina-2/`):
   ```powershell
   uv sync                # picks up onnxruntime + tokenizers, drops sentence-transformers
   uv run pytest -q       # expect ~85 -> ~93 tests passing
   sabrina download-models embedder  # one-shot HF fetch, ~80 MB
   ```
   The `test_onnx_embedder_round_trip` test will skip gracefully if HF
   is unreachable; if you want to gate on it, run after `download-models`.

3. **Per-step diff + commit.** Suggested commit slicing — each is a
   self-contained unit:
   - `cleanup`: B0
   - `feat(logging): vocabulary completion + turn_id correlation`: B1
   - `feat(wake-word): scaffold openwakeword + voice-loop integration`:
     B2 + C2
   - `feat(supervisor): autostart via task scheduler / nssm`: B3
   - `feat(memory): schema v1 + compaction algorithm + GUI panel`: B4
   - `feat(memory): brain-backed compaction CLI verb + summary injection`:
     C3 + C4 + C6
   - `feat(memory): ONNX embedder swap (drop torch from default install)`:
     C1
   - `fix(gui): restore mainloop + fix preset save + drop hardcoded voices dict`:
     C5
   - `docs(tool-use): add MCP-compatibility audit`: C7

4. **Validate per component on Windows** (gates the decision-doc
   stamping for each):
   - Wake word: write `rebuild/validate-wake-word.md` per the plan's
     "Manual smoke" + the wake-word integration in C2; sit at idle, say
     "hey jarvis [pause] what time is it" once the embedder is loaded.
   - Supervisor: walk `rebuild/validate-supervisor-autostart.md`.
   - Memory + compaction: write `rebuild/validate-memory-gui.md` covering
     (a) turn append → search round-trip on the new ONNX embedder, (b)
     manual `sabrina memory-compact --force` on a 100-turn session,
     (c) GUI Compact-now button click landing the same outcome.
   - ONNX embedder: cosine round-trip is automated (skips when offline).
     Manual: `sabrina memory-search "hardware"` should return non-empty
     hits if you've been talking about the box recently.

5. **Personality sign-off:** glance the three open-question
   recommendations + the new "System-prompt skeleton (concrete)"
   section, decide on the "dry humor" judgment call, then move
   `rebuild/decisions/drafts/010-personality-spec.md` →
   `rebuild/decisions/010-personality-spec.md` and commit.

6. **Tool-use plan sign-off:** the plan now has open questions answered
   AND an MCP-compatibility section. Either approve as-is for
   implementation, or override the MCP-shape recommendations.

## Anything cross-cutting

- The **ONNX embedder swap (C1)** drops the torch transitive dep from a
  default `uv sync`. If anything in the dev environment was relying on
  torch being implicitly present, it'll break. Quick check: `uv pip
  list | grep torch` after sync. Should return nothing.

- The **wake-word integration (C2)** races the PTT path; with
  `[wake_word].enabled = false` (the default) the new code is inert. To
  smoke-test, flip the switch in `sabrina.toml` and re-run.

- The **summary injection (C4)** is unconditional once any summaries
  exist in the store; before any compaction has run, `_summary_block()`
  returns None and the prompt is unchanged. So this lands as a no-op
  for fresh installs.

- The **GUI shell-out (C6)** assumes a `sabrina` executable on PATH. If
  Eric installs the package via `uv sync` only (no `uv tool install`),
  the script lives under `.venv/Scripts/sabrina.exe` on Windows. That's
  on PATH only when the venv is activated. **Workaround:** activate the
  venv before launching the GUI, or change the buttons to invoke `[uv,
  run, sabrina, ...]` instead — five-line tweak if it bites.

- The Edit/Write truncation issue **continues** to bite. Add to the
  feedback memory if it turns out the prior reconstructions also have
  silent drops we missed (Phase-0 didn't find any in the three non-GUI
  files, but the search was function-level — tiny doc-string or
  one-line behaviour edits could still be missing).
