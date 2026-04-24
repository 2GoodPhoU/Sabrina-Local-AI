# Sabrina AI — Rebuild Roadmap (Component-First)

**Author:** Eric
**Started:** April 2026
**Last updated:** April 23, 2026
**Ambition:** Personal daily-driver. Windows. Local-first, Claude as the brain.
**Strategy:** Build and prove each component in isolation before integrating. Every component gets a working implementation, a benchmarked alternative set, and a "garbage-removal" pass on the old code.

> **Status:** MVP is alive. Voice loop with PTT + Claude/Ollama + sentence-streaming Piper TTS + SQLite memory (now with semantic retrieval) + vision attach + settings GUI. ~4,000 lines, 70+ tests. See [`decisions/007-semantic-memory-shipped.md`](decisions/007-semantic-memory-shipped.md) for the latest component; [`decisions/006-end-of-night-status.md`](decisions/006-end-of-night-status.md) is the previous end-of-night snapshot.

---

## Progress at a glance

| # | Component | Roadmap status | Reality | Notes |
|---|---|---|---|---|
| 0 | Foundation | planned | ✅ shipped | uv, pydantic-settings, structlog, typer. [decision 001] |
| 1 | TTS | planned | ✅ shipped | Piper (libritts_r-medium spk 0) + SAPI fallback. [decision 002] |
| 2 | ASR | planned | ✅ shipped | faster-whisper base.en. [decision 003] |
| 3 | Wake word | planned | ⏭ **replaced by PTT** | openWakeWord still a candidate; PTT is primary. |
| 4 | Brain | planned (with router) | ✅ **shipped, no router yet** | Claude + Ollama via `Brain` protocol. Router deferred. [decision 003] |
| 5 | Event bus + state machine | planned | ✅ shipped | ~100-line bus, ~80-line SM. [decision 003] |
| — | **MVP checkpoint** | planned | ✅ **hit** | Voice loop end-to-end, ~1.85s first-audio latency. |
| 5.5 | **Settings GUI** *(new)* | — | ✅ shipped | customtkinter + tomlkit. [decision 004] |
| 6 | Avatar | planned | ❌ not started | Deferred. |
| 7 | Memory | planned (semantic) | ✅ shipped | SQLite rolling context + sqlite-vec semantic retrieval via MiniLM-L6. [decisions 003, 007] |
| 8 | Vision | planned | ✅ shipped | mss + Claude vision via `Message.images`. Voice-phrase + hotkey triggers. [decision 005] |
| 9 | Automation | planned | ❌ not started | Deferred. |

Legend: ✅ shipped · 🟡 partial · ⏭ replaced · ❌ not started.

---

## The MVP, defined (revised)

Original MVP was "wake word → speak → think → reply → avatar reacts."
Actual MVP shipped is:

> **"Sabrina"** → hold PTT → I speak → she thinks (Claude or Ollama) → she replies sentence-by-sentence through Piper → memory persists → optionally she sees the screen.

The avatar stays deferred. PTT replaces wake word for now. Everything
else matches.

---

## The workflow for every component

Still the anti-sprawl protocol. Every completed component went through
the same nine boxes:

1. Extract → 2. Standalone harness → 3. Define "works" → 4. Benchmark
alternatives → 5. Pick winner → 6. Refactor → 7. Garbage pass →
8. Smoke test → 9. Bus contract documented.

For components 0–8 we ran this from scratch rather than mining the old
repo — the rebuild moved faster than archaeology would have.

---

## Shipped components — short form

Full write-ups live in `rebuild/decisions/`. The roadmap now just tracks
*what* shipped and *what's thin* per component. See decision 006 for the
comprehensive "what could still improve" list.

### 0. Foundation — ✅
`uv`, `pydantic-settings` + `sabrina.toml` + `.env`, `structlog`,
`typer`, `asyncio`. `sabrina --version` works; `sabrina chat` is a
text REPL through Claude with streaming.

### 1. TTS — ✅ [decision 002]
**Winner:** Piper, `libritts_r-medium` model, speaker 0.
**Fallback:** Windows SAPI, zero-dep.
**Thin spots:** only one voice tried seriously; no prosody knobs; no
streaming synth. Alternatives to revisit: Kokoro, XTTS v2, StyleTTS 2.

### 2. ASR — ✅ [decision 003]
**Winner:** faster-whisper `base.en`.
**Thin spots:** `medium.en` / `large-v3-turbo` likely worth the latency
hit; no VAD or streaming partials. Alternatives to revisit: Parakeet,
WhisperX, Distil-Whisper.

### 3. ~~Wake word~~ → PTT — ⏭
PTT works. Wake word is deferred. If Eric wants true hands-free,
**openWakeWord** is the top candidate (Apache license, ~30MB ONNX,
active maintenance). Porcupine has better accuracy but nasty licensing.

### 4. Brain — ✅ (no router) [decision 003]
**Shipped:** `Brain` protocol (50 lines), Claude backend, Ollama
backend. Streaming async iterator of `TextDelta`/`Done` events.
`Message.images` added (additive) for vision in decision 005.
**Not shipped:** router, budget tracker, tool use, prompt caching.
Router deferred until daily cost or offline pressure justifies it.

### 5. Event bus + state machine — ✅ [decision 003]
Hand-rolled pubsub on `asyncio.Queue` (~100 lines). Typed events in
`events.py`. State machine enforces transitions loudly. 5 states:
`idle`, `listening`, `thinking`, `speaking`, (`acting` reserved for
automation).

### 5.5. Settings GUI — ✅ (new, wasn't in original plan) [decision 004]
customtkinter settings window with tabs for Brain/TTS/ASR/Vision/
Memory. TOML round-trip preserves Eric's config comments via tomlkit.
Atomic writes. Launched with `sabrina settings`. Grew out of vision
work (lots of knobs) and pulled in the others for free.

### 6. Avatar — ❌
Deferred. The plan stands: PyQt6, frameless/always-on-top/click-
through, reacts to `StateChanged` events. Pure UX polish, zero
capability added.

### 7. Memory — ✅ [decisions 003, 007]
**Shipped:** SQLite rolling context (one message table, load-recent-N
on startup) *plus* semantic retrieval via sqlite-vec + sentence-
transformers `all-MiniLM-L6-v2` (384 dims). Per user turn Sabrina
embeds the query, pulls top-k relevant older turns, and appends an
"Earlier in our conversations..." block to the system prompt.
Assistant replies are indexed too. Off by default; opt in via
`[memory.semantic] enabled = true` + `sabrina memory-reindex`.
**Thin spots:** no summary compaction yet (long histories still grow
unbounded); one embedding model hardcoded; retrieval adds ~20-100 ms
to first-audio latency on CPU; reply is embedded synchronously.
**Alternatives to revisit:** cross-encoder reranker, leaner onnx-only
embedder (kills torch dep), per-session filter + time decay.

### 8. Vision — ✅ [decision 005]
mss capture → Pillow downscale to 1568px long-edge → PNG →
`Message.images` on a per-turn fresh ClaudeBrain. Two triggers:
voice phrase ("look at my screen…") or a global hotkey (default
Ctrl+Shift+V, arms the next turn). `sabrina look "..."` for
one-shot CLI use. Thin spots: whole-monitor only (no window/region),
no local VLM fallback, no image memory.

### 9. Automation — ❌
Deferred. Most dangerous component; last in order on purpose. Design
from original roadmap (pyautogui + pynput + kill-switch + dry-run +
destructive-action allow-list) still stands.

---

## Open questions, updated

| Question | Status |
|---|---|
| Custom "Sabrina" wake word? | Deferred with wake word itself. |
| Piper voice choice | `libritts_r-medium` spk 0 picked; could A/B more speakers. |
| PTT as fallback | ✅ Promoted to primary. |
| Monthly budget target | Decided: $0 target, $10 warn, $100 ceiling. Tracker **not built yet**. |
| Local-tier hardware | Decided: i7-13700K + RTX 4080 16GB + 32GB / Win11. [decision 001] |
| **Component 5 focus — wake word or local VLM?** | **New, unresolved.** Decide next session. |
| **Upgrade ASR to medium.en?** | **New, unresolved.** Trivial change, measurable impact. |
| **Build brain router or skip?** | **New, unresolved.** ~200 lines; delivers offline-first mode. |

---

## Next session — pick one

Semantic memory shipped in this session (decision 007). Revised menu:

1. **Barge-in (Silero VAD + cancellable TTS)** — closes the biggest
   daily-driver gap. Prerequisite: cancel-token in the Brain protocol.
2. **Wake word (openWakeWord)** — frees hands from PTT.
3. **Local VLM fallback** — llava / Qwen2.5-VL / Moondream behind
   the same `Message.images` interface. Privacy + offline.
4. **Budget tracker + prompt caching** — small lift, immediate cost
   reduction, observability win.
5. **Summary compaction + semantic-memory GUI (007b)** — natural
   follow-ups to this session. Long histories still grow unbounded;
   the GUI doesn't expose the new semantic knobs yet.

---

## Daily-driver readiness

Eric's stated goal is daily-driver. Honest gap list:

- [ ] Wake word OR reliable global PTT hotkey
- [ ] Auto-start on login (OS-level, not Python)
- [ ] Crash-recovery supervisor
- [ ] Barge-in (interrupt mid-reply)
- [ ] Budget observability (`sabrina budget` command)
- [ ] (nice-to-have) Avatar
- [ ] (nice-to-have) Automation

Four of those — wake-word/PTT, autostart, crash recovery, barge-in —
are the real gap. The rest is polish or scope expansion.

---

## The "remove garbage" scorecard

We never did the archaeology phase — the rebuild from scratch was
faster than extracting from the old repo. The scorecard below is
aspirational (if/when we delete the old repo, this is the ledger).

| From old repo | Lines | Fate |
|---|---|---|
| `core/core.py` | ~700 | Delete. Rebuild has no god object; voice_loop is ~300 lines. |
| `core/component_service_wrappers.py` | ~2000 | Delete entirely. |
| `core/llm_input_framework.py` | ~1000 | Delete. Rebuild `Brain` protocol is 50 lines. |
| `core/state_machine.py` | ~600 | Delete. Rebuild state machine is ~80 lines. |
| `services/voice/` (FastAPI + docker + own venv) | ~1500 | Delete. Rebuild TTS is one module, no HTTP layer. |
| `services/vision/vision_ai.py` + YOLO training | ~800 + weights | Delete. Claude vision replaces it. |
| `services/hearing/hearing.py` | ~300 | Rebuild splits wake word + ASR; ASR shipped, wake-word deferred. |
| `services/automation/automation.py` | ~700 | Keep shortcuts as data when we ship automation. |
| `services/smart_home/` | ~400 | Delete. |
| `services/presence/` | ~2000 (17 modules) | Keep assets + animation manager for future avatar. |
| Empty stubs + empty tests | 0 | Delete. |

Rebuild is currently ~3,500 lines (source + tests). Target was under
3K for MVP, under 6K for full feature parity. On track.

---

## Guardrails (still holding)

1. **No component starts until the previous one is in main with a
   smoke test.** ✅ Held.
2. **No new abstraction until the second caller exists.** ✅ Held —
   `Brain` has two backends; no premature factories.
3. **If a module grows past 300 lines, split or justify in the header.**
   ✅ Held; `voice_loop.py` is our longest at ~300 lines.
4. **Weekly dogfood.** 🟡 Just now started — dogfooding week begins.
5. **Commits are atomic per component step.** ✅ Held.
6. **Decisions log.** ✅ 001–006 written.

---

## Architecture — current shape

```
                       ┌──────────────┐
                       │  Settings    │  (customtkinter, writes
                       │  GUI         │   sabrina.toml via tomlkit)
                       └──────┬───────┘
                              │ config
                              ▼
  PTT ──▶ Listener ──▶ Voice Loop ──▶ Brain ─── Claude
  (pynput) (whisper)   (asyncio)      │     └── Ollama
                          │           │
             Vision ──────┤           └──▶ Memory (SQLite)
             (mss+Claude) │           │
                          ▼           ▼
                        Speaker ──▶ sounddevice
                        (Piper / SAPI, sentence-streaming)
                          │
                          ▼
                       Event Bus ──▶ State Machine
                       (typed events, enforced transitions)
```

---

## Decision log

- [001 — Hardware and budget](decisions/001-hardware-and-budget.md)
- [002 — TTS component shipped](decisions/002-tts-component-1-shipped.md)
- [003 — Voice loop shipped](decisions/003-voice-loop-shipped.md)
- [004 — Settings GUI shipped](decisions/004-settings-gui-shipped.md)
- [005 — Vision shipped](decisions/005-vision-shipped.md)
- [006 — End-of-night status](decisions/006-end-of-night-status.md)
- [007 — Semantic memory shipped](decisions/007-semantic-memory-shipped.md)
