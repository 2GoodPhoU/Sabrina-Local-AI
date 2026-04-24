# Old Repo Migration Audit

**Date:** 2026-04-23
**Audit scope:** pre-rebuild codebase (root-level subtrees excluding `sabrina-2/`, `rebuild/`, `.venv/`, `.git/`)
**Decision context:** [002-tts-component-1-shipped.md](../decisions/002-tts-component-1-shipped.md) established deliberate rebuild from scratch; this audit cherry-picks specific assets/logic still worth porting.

## Executive Summary

**Worth migrating:** 4–5 self-contained items, roughly 150–250 hours of porting work if done incrementally.
**Worth documenting only:** 2–3 architectural decisions from old core/ framework; not worth code-porting.
**Dead weight:** Event system, old state machine, LLM input framework, everything in utilities/ (over-abstracted), most docs (encoding issues + stale).

Biggest findable candidate: **audio device enumeration + pyaudio stream setup** (services/hearing/) — non-trivial, handles edge cases in older code.
**Surprise:** Old repo built a "universal LLM framework" (core/llm_input_framework.py, 1151 lines) that sabrina-2 decided to handle _in the LLM call itself_ (much simpler, relies on Claude API function definitions). The rebuild validated the abstraction was premature.

---

## Per-Subdirectory Audit

### core/ (5 files, 5034 lines)

**What's there:**
- `core.py` (815 lines): Event-driven orchestration skeleton, ServiceComponent base class, placeholder LLM integration.
- `enhanced_event_system.py` (133 lines): Custom event bus (Enum-based event types, priority queuing).
- `state_machine.py` (620 lines): SabrinaState FSM (init → listening → processing → responding, etc.).
- `llm_input_framework.py` (1151 lines): Structured LLM I/O protocol (InputType/OutputType enums, LLMFunction dataclass, handler routing).
- `component_service_wrappers.py` (2186 lines): Heavy wrapper patterns for vision/hearing/automation components.

**Verdict:** Not worth porting code.

**Reasoning:**
The rebuild chose event-less design: components are tasks driven by explicit method calls, state is in pydantic dataclasses, no custom event bus. The old event system was over-engineered for what sabrina-2 actually needs (startup, dispatch commands, collect results). The state machine maps cleanly to sabrina-2's `state.py` but was refactored into simpler enums + condition checks; the old FSM structure doesn't add value.

The LLM framework is the most interesting conceptually (function registry, parameter validation, type safety) but sabrina-2 shipped without it—Claude's native function_calls and natural instruction-following handle the routing better than a JSON schema registry. Decision 007 may revisit if multi-model routing becomes necessary.

**Docs only:** Architecture intent in core_integration.py comments is worth reading for context on why each component exists, but no code extraction needed.

---

### services/ (11,484 lines across hearing/, vision/, automation/, presence/, voice/, smart_home/, data/)

**hearing/** (heading.py, ~400 lines)
- Vosk wake-word + pyaudio stream, model download logic.
- **Verdict:** Port the **pyaudio stream initialization** (channel config, format constants, device enumeration).
- **Why:** sabrina-2 uses faster-whisper + sounddevice, but the old code's fallback device-list strategy (enumerate + pick by ID when default fails) is non-obvious and Windows-specific. `pyaudio.PyAudio().get_device_count()` loop with name matching is worth keeping as a utility function. ~2 hours to extract + test.

**vision/** (vision_core.py + vision_ocr.py, ~1500 lines)
- Screen capture (mss), OCR (pytesseract), YOLOv8 detection.
- **Verdict:** Not worth porting code; worth documenting the **OCR postprocessing regex patterns** in one decision doc.
- **Why:** sabrina-2 uses Claude's vision API instead (simpler, better accuracy, no model download). Old code's layout-aware text assembly (joining fragments by y-coordinate) is a solved problem in the new design. If needed, the regex patterns live in version control for reference.

**automation/** (automation.py, ~400 lines)
- PyAutoGUI wrapper, keyboard shortcuts (copy/paste/etc.), failsafe.
- **Verdict:** Port the **shortcut dictionary** (copy/paste/select-all/etc.) as a constant or config YAML.
- **Why:** sabrina-2's automation is not yet shipped; this mapping is just structured data, not tied to old architecture. ~0.5 hours.

**presence/** (gui/, animation/, run.py, ~2500 lines)
- PyQt5 GUI, GIF animation state machine, system tray.
- **Verdict:** Not worth porting; GIFs already confirmed as non-Live2D-compatible.
- **Why:** sabrina-2 GUI shipped as a separate PyQt5 system (May 2026 roadmap item); old presence/ system was tightly coupled to the old event bus. No code reuse; assets (GIFs) are already flagged as dead.

**voice/** (voice.py + wrapper for piper/SAPI)
- Piper subprocess + SAPI (win32com) fallback, model management.
- **Verdict:** Already ported; see [002-tts-component-1-shipped.md](../decisions/002-tts-component-1-shipped.md).
- **Why:** sabrina-2/src/sabrina/speaker/ is the direct port (voice_core logic → speaker/piper.py + speaker/sapi.py).

**smart_home/** (google_home_client.py, ~300 lines)
- Google Home API client, Home Assistant integration.
- **Verdict:** Not worth porting now; keep in backlog for future smart-home integration.
- **Why:** Not in MVP scope. The API wrapper is straightforward; when smart-home ships, write fresh against current Google Home API docs.

**data/, logs/, config/** (runtime directories)
- **Verdict:** Not worth porting; ephemeral.

---

### utilities/ (5 files, 61 KB)

**What's there:**
- config_manager.py (16 KB): Config file loading, env var interpolation, validation.
- event_system.py (18 KB): Another event bus (signals, listeners, fire/subscribe pattern).
- error_handler.py (17 KB): Logging wrapper, exception categorization.
- entry_point.py (6 KB): CLI entry point orchestration.
- service_starter.py (5 KB): Service subprocess management.

**Verdict:** Not worth porting.

**Reasoning:**
All exhibit over-abstraction. sabrina-2 uses pydantic-settings for config (simpler, more standard), logging module directly (no wrapper needed), and explicit task dispatch (no event listener pattern). The abstraction layers don't map to the rebuild's philosophy. Rewriting these pieces once, cleanly, saves more time than porting + refactoring.

---

### scripts/ (10 files)

**What's there:**
- sabrina_install.py (20 KB): System dependency checks (Python 3.10+, Tesseract, FFmpeg, GPU drivers), venv setup, pip install.
- sabrina_ai_launcher.sh / .bat: Shell wrappers for starting services.
- start_sabrina.py, sabrina_local_ai.py, sabrina_ai.py, sabrina_tts.py: Entry points (mostly stubs or launcher code).
- conversation_history.json, default_memory.json, voice_settings.json: Test fixtures.

**Verdict:** Port **sabrina_install.py** system-check logic as a utility module; JSON fixtures to tests/.

**Why:** The dependency checks are platform-specific (Linux apt, macOS brew, Windows direct). Not worth reimplementing; sabrina-2 should inherit this. The fixtures (conversation_history.json, default_memory.json) seed the test suite. ~4 hours to extract install checks into sabrina-2/src/sabrina/setup.py + port fixtures.

---

### tests/ (full test suite, ~50 test files)

**What's there:**
- unit/ (10 files): test_automation.py, test_config_manager.py, test_core.py, test_state_machine.py, test_hearing.py, etc.
- integration/ (partial): service-level tests.
- e2e/ (partial): end-to-end workflows.

**Verdict:** Not worth porting wholesale; port **conftest.py + test_utils/ fixtures** and rewrite test cases for new architecture.

**Why:** The test structure is tied to old component wrappers and event system. sabrina-2's test suite (70+ tests, already in place) covers current functionality. Old unit tests would need rewrite to match new class signatures. Fixtures (mocking strategies, paths helpers) are reusable; test cases are not.

---

### docs/ (4 files, encoding issues present)

**What's there:**
- "Sabrina AI - LLM Integration Guide.md" (13 KB): Old LLM framework walkthrough.
- "Sabrina AI Core Integration System.mermaid": Architecture diagram (mermaid syntax).
- architecture.md: High-level system design.
- project_roadmap.md: Pre-rebuild roadmap.

**Verdict:** Read for context only; do not migrate.

**Reasoning:**
Most docs describe the old event-driven architecture or the LLM framework that the rebuild rejected. The mermaid diagram is outdated (doesn't reflect sabrina-2's simpler topology). Files have encoding issues (can't be read via normal tools), suggesting bit rot. New decision docs ([002–007](../decisions/)) supersede all architectural guidance.

---

### Root README.md

**Verdict:** Not worth migrating; it's a stub.

Describes old feature roadmap (vision, automation, presence) with emoji headers. sabrina-2 README lives in sabrina-2/ and is the source of truth.

---

## Recommended Migration Plan

**Ordered by value/effort ratio. Each entry: item, sabrina-2 destination, est. hours, one-line justification.**

1. **Audio device enumeration utility** → `sabrina-2/src/sabrina/listener/audio_utils.py` | 2 hrs | Non-trivial fallback logic for Windows audio input device selection; avoids re-learning the edge cases.

2. **Keyboard shortcuts dictionary** → `sabrina-2/src/sabrina/config.py` (inline constant) or `sabrina-2/data/shortcuts.yaml` | 0.5 hrs | Pure structured data (copy/paste/undo/etc.); reusable across automation components.

3. **System dependency checks** → `sabrina-2/scripts/setup.py` | 4 hrs | Platform-specific logic (apt/brew/choco, Tesseract, FFmpeg, CUDA) saves future debugging; low risk to port.

4. **Test fixtures (conversation_history.json, default_memory.json)** → `sabrina-2/tests/data/` | 1 hr | Seed integration tests; no code changes needed, just copy + validate format.

5. **conftest.py + test_utils/ utilities** → `sabrina-2/tests/` (merge into existing conftest.py) | 2 hrs | Path helpers, mock factories reusable; avoids duplicating pytest scaffolding.

**Do not attempt:**
- Event system, state machine code, LLM framework, utilities/ modules, GUI code, smart-home client, old tests (cases only; fixtures OK).

---

## Open Questions

- **GPU driver detection** (sabrina_install.py checks CUDA, cuDNN): Should this move to a separate `setup.py` or stay in docs as "prerequisites"?
- **Piper model cache** (models/piper/): No files present in current checkout. Confirm whether model weights are Git-LFS tracked or downloaded on-demand. Current sabrina-2 downloads on first use; old code also did this. No change needed.
- **Vosk model download fallback** (services/hearing/): Old code had logic to auto-download if missing. Current sabrina-2 uses faster-whisper (no Vosk); if we ever add wake-word detection back, revisit this code.

---

## Conclusion

Migration effort is modest and front-loaded: the ~10 hrs of extraction (audio utils, shortcuts, setup checks, test fixtures) pays dividends in test coverage + Windows robustness. Everything else is architectural debt that the rebuild correctly chose to leave behind.
