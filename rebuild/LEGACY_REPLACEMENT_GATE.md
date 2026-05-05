# Legacy Replacement Gate

**Date opened:** 2026-04-26 (overnight cleanup pass)
**Audience:** Eric, future-Eric, future-Claude.
**Status:** open. Five port items + a bake-in window stand between
the rebuild and an `archive/` move for the legacy tree.

This doc is the gate. When every box below is checked, `core/`,
`services/`, `utilities/`, and friends move to `archive/` (or a
sibling repo — see disposition section), the rebuild becomes the
default daily driver, and the migration project formally closes.

---

## Honest assessment — where the rebuild stands

The rebuild has surpassed the legacy on the four axes we said it
needed to. Documenting plainly because it's easy to lose sight of:

- **Quality.** `voice_loop.py` is ~300 lines and does what
  `core/core.py` (815 lines) + `core/component_service_wrappers.py`
  (2,186 lines) tried to do, with cleaner state transitions and no
  hidden globals.
- **Architecture.** `Brain`, `Speaker`, `Listener` are 50-line
  protocols with two implementations each. `core/llm_input_framework.py`
  (1,151 lines of "universal LLM framework") is the foil — the rebuild
  decided Claude's native function-calls and instruction following
  are the right abstraction layer, not a JSON-schema registry.
- **Test discipline.** 96 tests, ~3 s wall, run on every change. Legacy
  has ~50 test files but they're tied to the old wrappers and event
  bus, so practical coverage is uneven. Not a fair like-for-like.
- **Documentation discipline.** Ten decision docs (`001-010`),
  per-component `validate-*.md` Windows procedures, an `ACTION_ITEMS.md`
  punch list, `when-you-return.md` for clean session restarts, a
  `CLAUDE.md` for AI assistants. Legacy `docs/` has four files with
  encoding issues that describe the architecture the rebuild
  rejected.

The remaining gap is **functional feature parity** in a few
specific areas, plus the **bake-in** that turns "it works on my box"
into "it's actually my daily driver."

---

## What's still uniquely in legacy

Cross-referenced against `rebuild/drafts/old-repo-migration-audit.md`
(2026-04-23). The audit identified five worth-porting items. Re-checked
2026-04-26 — none have been ported into `sabrina-2/` yet:

| # | Item | Legacy location | Rebuild destination | Est. hrs | Confirmed not-yet-ported (2026-04-26) |
|---|---|---|---|---|---|
| 1 | Audio device enumeration + Windows fallback (pyaudio loop with name matching when default device fails) | `services/hearing/hearing.py` | `sabrina-2/src/sabrina/listener/audio_utils.py` (new) | 2 | ✅ no `audio_utils.py` exists |
| 2 | Keyboard-shortcut dictionary (copy/paste/select-all/etc.) | `services/automation/automation.py` | `sabrina-2/data/shortcuts.yaml` or inline constant | 0.5 | ✅ no shortcut table in `sabrina-2/` |
| 3 | System dependency checks (Python ≥3.10, Tesseract, FFmpeg, GPU drivers, platform-specific install) | `scripts/sabrina_install.py` | `sabrina-2/scripts/setup.py` (new) | 4 | ✅ no `setup.py` in `sabrina-2/scripts/` |
| 4 | Test fixtures (`conversation_history.json`, `default_memory.json`) | `scripts/` | `sabrina-2/tests/data/` (new) | 1 | ✅ no `tests/data/` |
| 5 | `conftest.py` + `test_utils/` pytest scaffolding (path helpers, mock factories) | `tests/` | `sabrina-2/tests/conftest.py` | 2 | ✅ no `conftest.py` in `sabrina-2/tests/` |

**Total port effort:** ~9.5 hours, sequenceable in one focused
session. None are blocking — the rebuild functions today without
them — but each removes a daily-driver papercut.

Worth noting what's *not* on this list, by design: the event system,
state machine, LLM input framework, `utilities/` modules, GUI code,
smart-home client, presence/ animations, and the wholesale test suite
are all dead weight per the audit. Re-confirmed 2026-04-26: nothing
the rebuild lacks would be cheaper to port than to rewrite.

---

## Replacement gate — checklist

Each box must be true before the legacy directories move to `archive/`:

- [ ] **Migration-port complete (or explicit decisions to skip).** All
      five items above either land in `sabrina-2/` *or* get a one-line
      "decided not to port — rationale: ..." entry in `decisions/` (a
      single decision doc covering all skipped items is fine).
- [ ] **Daily-driver bake-in completed.** Defined as **7 consecutive
      days of normal use** with `sabrina voice` as Eric's primary
      assistant, no falling back to legacy or to typing-instead-of-
      speaking out of frustration. Bake-in starts the day after the
      last port lands. Reset on any day that produced a regression
      filed in `ACTION_ITEMS.md`.
- [ ] **No regression vs. legacy in the bake-in window.** "Regression"
      means: a task Eric used legacy for that the rebuild can't do, or
      does worse. A regression resets the 7-day clock and gets a
      decision-doc footnote ("rebuild caught up to legacy on X
      because...").
- [ ] **All references to legacy paths in rebuild docs are removed or
      redirected.** Today, ROADMAP and decision docs mention `core/`,
      `services/`, `utilities/` in a "delete this" context — fine while
      they exist, confusing once they move. One `grep -rn 'core/\|services/\|utilities/'`
      pass through `rebuild/` before flipping the archive.
- [ ] **`archive/` directory created and populated.** Move (don't
      delete) `core/`, `services/`, `utilities/`, `scripts/`, `tests/`
      (legacy), `docs/`, `models/`, `config/`, plus any stragglers, to
      `archive/`. Add a one-page `archive/README.md` explaining what
      this is and why it's here.
- [ ] **Top-level `README.md` updated.** Currently this points at both
      legacy and rebuild. Post-archive, the top-level README is a
      pointer to `sabrina-2/` and `rebuild/`, with a single
      "What is `archive/`?" footnote.
- [ ] **`CLAUDE.md` updated.** The "Where the code and docs live"
      section currently lists legacy folders by name; post-archive it
      should describe `archive/` as a single fossil-cache and stop
      listing the individual subtrees.

---

## Realistic timeline

Velocity check, 2026-04-26: in the last 48 hours the rebuild absorbed
008 (foundational refactor: schema versioning, log redaction, rotating
file sink), 009 + 009a (barge-in: Silero VAD + `CancelToken` with the
thin-spots bundle), the ONNX embedder swap, supervisor + autostart
scaffolding, wake-word scaffold, memory compaction with token-budget
auto-trigger, and the cross-cutting overnight cleanup that produced
this doc. That's ~5–6 sizeable units in 2 days while also writing
matching `validate-*.md` procedures and decision docs.

At that velocity, the 9.5-hour port list is one well-rested Saturday.
Realistic calendar:

- **2026-04-27 to 2026-05-03** (week 1): port the five items into
  `sabrina-2/` over ~2 sessions. Stamp a single mini-decision doc
  ("legacy port complete"). Light validation; these are utilities, not
  components.
- **2026-05-04 to 2026-05-10** (week 2): bake-in week. `sabrina voice`
  is the daily driver. Any breakage gets logged in `ACTION_ITEMS.md`.
- **2026-05-11 onward**: if no regressions in week 2, flip the archive
  on or about **2026-05-11 to 2026-05-15** depending on how the
  bake-in actually goes.

**Worst case:** week 2 surfaces a regression that resets the clock
once, then a second regression after the fix-and-recheck, then a third
that turns out to require new component work. Add ~2 weeks per surprise.
Honest worst case is **late May 2026 (~30 days from today)**. Mid-May
is the realistic median.

---

## Post-archive disposition — what to do with the legacy code

Three options, ordered by recommendation:

1. **Same repo, `archive/` directory.** *(Recommended.)* git history
   stays intact, `archive/` is one `cd` away when Eric needs to
   remember how the old code did something, and the boundary is
   visually obvious from the top-level `ls`. The repo grows by ~50K
   LOC of read-only fossils, which `git clone` survives without
   complaint. CI / linting can be excluded with a one-line glob.

2. **Separate `Sabrina-Local-AI-Legacy` repo.** History is preserved,
   the main repo gets smaller, but cross-referencing means tab-switching
   and remembering which clone is which. Worth doing only if the
   archive grows past ~100K LOC or if Eric ever wants to make the main
   repo public — at which point the legacy code (with its `.env`
   examples, model paths, etc.) is the embarrassment to keep
   private-side.

3. **Delete entirely after a 90-day grace period.** git history still
   keeps it, but every reference becomes a `git log -p` exercise. Not
   recommended — disk is cheap, "I just need to peek at how the old
   wake-word fallback worked" comes up more than expected during
   bake-in.

**Default plan:** option 1. Re-evaluate at the public-repo decision
(if it ever happens) for a possible move to option 2.

---

## What this doc is *not*

This isn't a port plan — `rebuild/drafts/old-repo-migration-audit.md`
already is one, and it's the right doc to follow during week 1 above.
This isn't a roadmap entry either — `ROADMAP.md` tracks the rebuild's
forward motion; this gate is about what closes the rebuild project,
not what the rebuild does next. When this gate clears, this doc gets
a final commit ("legacy archived 2026-MM-DD") and stops being live.
