# Thin-spot split plan — `cli.py` and `voice_loop.py`

**Date:** 2026-04-23
**Status:** Draft. Implementable in one session. No Eric blockers; this is
housekeeping the project's own guardrails call for. Ship when whichever
upcoming session would push one of these files past ~500 lines.
**Closes:** guardrail #3 drift flagged in `remaining-components-plan.md`.

## The one-liner

`cli.py` is 753 lines; `voice_loop.py` is 427. Guardrail #3 says "past
300, split or justify in the header." Neither file has a justification
header; both have grown naturally as shipped components added verbs
(memory-*, tts-*, look, settings) and as the voice loop grew retrieval
+ vision. Split `cli.py` into a `cli/` package with one module per
subsystem. Extract a `Turn` helper out of `voice_loop.py`. Do **not**
introduce protocol-level abstractions — no new `Command` base class, no
`TurnStage` interface. The cut is structural, not architectural.

## The two splits — what we do

### Split 1: `cli.py` → `cli/` package

New layout (only one new top-level package; each module stays under
200 lines by design):

```
sabrina-2/src/sabrina/cli/
├── __init__.py                # re-exports `app` + aggregates subcommands
├── app.py                     # `app = typer.Typer(...)` — the single root Typer
├── _common.py                 # _open_memory, _build_brain, _build_speaker,
│                              # _build_listener, _parse_device  (helpers,
│                              # shared only — not public API)
├── brain.py                   # version, chat, config-show, settings-gui
├── tts.py                     # tts, tts-voices, tts-download, tts-compare
├── asr.py                     # asr, asr-record, test-audio
├── voice.py                   # voice
├── vision.py                  # look
└── memory.py                  # memory-show, memory-clear, memory-stats,
                               # memory-reindex, memory-search
```

`__init__.py` imports each module for the side-effect of registering
its `@app.command`s against the shared `app` Typer instance. The user's
entry point (`sabrina = "sabrina.cli:app"` in `pyproject.toml`) keeps
working because `sabrina.cli.app` resolves via `__init__.py`.

Rationale, in order of importance:

1. **Every module sits under 200 lines.** Meaningfully under the 300
   threshold, room for the verbs each subsystem will gain next
   (`sabrina run`, `sabrina autostart`, `sabrina budget`,
   `sabrina memory-compact`, `sabrina wake-test` are all planned).
2. **Subsystem boundaries already exist.** The current `cli.py` has
   hand-drawn `# ---- tts ----` dividers separating the sections. The
   split follows those dividers exactly — no new taxonomy invented.
3. **Helpers go in `_common.py`, not a third-party location.** The
   underscore prefix tells readers (and future-Eric) that nothing
   outside `cli/` should import from it.

### Split 2: extract a `Turn` helper from `voice_loop.py`

New layout:

```
sabrina-2/src/sabrina/voice_loop.py         # ~180 lines — the main loop
sabrina-2/src/sabrina/voice_turn.py         # ~180 lines — one-turn state
```

`voice_loop.py` keeps:
- Outer setup (memory, embedder warmup, PTT start, vision hotkey start,
  console intro).
- The main `while True` loop with state transitions and per-turn calls
  into the helper.
- Shutdown cleanup.

`voice_turn.py` holds a single helper (kept deliberately procedural):

```python
@dataclass
class TurnContext:
    """Mutable-during-a-turn state. Reset per iteration. NOT a class
    hierarchy — just a bag that the helpers below pass around so the
    voice loop's `while True` body stays readable."""
    user_text: str
    user_msg_id: int | None
    user_embedding: list[float] | None
    turn_brain: Brain
    turn_system: str
    turn_system_suffix: str | None
    turn_user_msg: Message
    use_vision: bool

async def prepare_turn(
    user_text: str, *,
    history: list[Message],
    settings: Settings,
    base_brain: Brain,
    memory: MemoryStore | None,
    embedder: Embedder | None,
    session_id: str,
    vision_hotkey,               # VisionHotkey | None
    bus: EventBus,
    console: Console,
) -> TurnContext:
    """Resolve per-turn inputs: append user turn, maybe attach screenshot,
    build system prompt + optional retrieved-memory suffix. Does NOT call
    the brain."""
    ...
```

`run_voice_loop` then becomes:

```python
async for ev in turn_brain.chat(
    history, system=ctx.turn_system, system_suffix=ctx.turn_system_suffix
):
    ...
```

Rationale:

1. **Eliminates a 200-line middle.** The current `voice_loop.py` has
   ~200 lines between "got user text" and "speak the reply," and
   ~80% of those lines are per-turn setup (vision, memory, system
   prompt assembly). Extracting that band is the natural cut.
2. **Makes upcoming work easier, not harder.** Barge-in adds a
   `CancelToken`; `prepare_turn` can own the token creation and wire
   it into the `turn_brain.chat` call. Wake-word adds a capture-on-
   detection shortcut; the outer loop branches the source, but
   `prepare_turn` is the same.
3. **No new abstraction.** `TurnContext` is a dataclass, not a
   protocol. `prepare_turn` is a function, not a class. If it grows,
   it grows — guardrail #3 applies recursively.

## What NOT to split — and why

A deliberate short list. The motivation is anti-sprawl: splitting
these would be change for change's sake.

### Do not split `memory/store.py` (408 lines)

Over 300, but the header documents why: the store is "SQLite writes,
sqlite-vec reads, backfill, clear" — four of those four live in the
same class and share the connection. Splitting into `read.py` +
`write.py` + `index.py` would introduce three files that all import
from each other and gain nothing. The file is cohesive. Add a
header comment documenting the guardrail exception:

```python
"""Conversation-memory store ...

Note: this module is 400+ lines by design. Reads and writes share one
SQLite connection and one sqlite-vec virtual-table lifecycle — splitting
them would force a shared-state wrapper that is more complex than the
file is today. See guardrail #3.
"""
```

### Do not split `gui/settings.py` (386 lines)

Over 300, but the Tkinter idiom is "one window = one class." Every
tab builder is a method on the same `SettingsWindow`. A per-tab
module would require each to reach into the shared `_vars` dict and
`self.settings`, creating circular imports or a second shared-state
module. Add a header comment with the same disclaimer.

### Do not split `speaker/voices.py` (154 lines)

It's a data module — a dict of voice presets. Under 300, not a
split candidate at all. Listed here so it's explicitly off the
table.

### Do not extract `run_voice_loop`'s speaker-worker task into its
### own module

It's a 15-line closure that captures `speak_queue` and `speaker` from
the enclosing scope. Extracting it would force parameter-passing for
every capture, bloating the surface for zero gain. Keep it a closure.

### Do not split `brain/protocol.py` into a subpackage

It's 77 lines. Tempting to someday split `Role`, `Image`, `Message`,
`TextDelta`, `Done`, `Brain` into siblings. Resist. The whole protocol
is visible on one screen today — that's a *feature*, not a smell.

## Files to touch

### For split 1:

```
sabrina-2/src/sabrina/
├── cli/                         # NEW package
│   ├── __init__.py              # re-exports app
│   ├── app.py                   # Typer root
│   ├── _common.py               # helper lifters
│   ├── brain.py
│   ├── tts.py
│   ├── asr.py
│   ├── voice.py
│   ├── vision.py
│   └── memory.py
├── cli.py                       # DELETED (replaced by cli/ package)
└── tests/test_smoke.py          # a smoke test that `import sabrina.cli`
                                 # still exposes `app` and every verb
```

### For split 2:

```
sabrina-2/src/sabrina/
├── voice_loop.py                # slimmed to ~180 lines
└── voice_turn.py                # NEW, ~180 lines
```

### Not touched:

- `pyproject.toml` — entry point is `sabrina.cli:app`; still resolves.
- `sabrina.toml` — no config change.
- Any other source file — splits are intra-module only.

## Test strategy

- `test_cli_package_exposes_app_and_all_commands` — import `sabrina.cli`,
  introspect `app.registered_commands`, assert a list of verb names is
  complete (the list is a constant in the test). Catches "forgot to
  import a module in `__init__.py`."
- `test_cli_verb_entrypoints_still_callable` — use Typer's CliRunner
  against `sabrina version`, `sabrina config-show`, asserting exit code
  0. Two or three verbs is enough to prove the Typer wiring is intact;
  we don't need to re-test every verb's behavior.
- `test_voice_turn_prepare_builds_expected_context` — stub memory,
  stub embedder, stub vision, call `prepare_turn("hello")`; assert
  `TurnContext` fields are populated. No real brain call.
- `test_voice_turn_prepare_handles_vision_trigger` — include a
  vision phrase in `user_text`; assert `use_vision=True` and
  `turn_user_msg.images` has one Image.
- `test_voice_turn_prepare_appends_retrieved_block` — stub memory
  with fake hits; assert `turn_system_suffix` is the expected format.

Existing tests that reference `voice_loop.run_voice_loop` continue
to work — the signature doesn't change.

Existing tests that import `from sabrina.cli import app` continue to
work — that line still resolves because `cli/__init__.py` re-exports.

## Step-ordered implementation outline

1. Create `cli/` package skeleton (`__init__.py` + `app.py` +
   `_common.py`), with `_common.py` lifted from the current
   `cli.py`'s private helpers. Empty `brain.py`, `tts.py`, etc.
   stubs. Tests for package import. One commit.
2. Move verbs into their subsystem modules in order of existing
   dividers: brain → tts → asr → voice → vision → memory. Each move
   is one commit, each time running `pytest -q` to confirm no verbs
   regressed.
3. Delete `cli.py`. One commit. Confirm `sabrina --help` still lists
   every verb.
4. Add header-comment guardrail exceptions to `memory/store.py` and
   `gui/settings.py`. One commit.
5. Extract `prepare_turn` + `TurnContext` into `voice_turn.py`; slim
   `voice_loop.py`. Tests for `prepare_turn`. One commit. Confirm
   `sabrina voice` still works end-to-end.

The split can be paused between commits without breaking main.

## Dependencies to add

None. Structural work only.

## Windows-specific concerns

- Python import caching on Windows: deleting `cli.py` and replacing
  it with a `cli/` package can trip `__pycache__` staleness if Eric
  has an existing `.pyc` for the old file. First step: add a
  `find . -name __pycache__ -type d | xargs rm -rf` line to the
  validation doc (PowerShell equivalent:
  `Get-ChildItem -Recurse -Directory __pycache__ | Remove-Item -Recurse -Force`).
- Typer/Click path-handling: none of the verbs pass Paths through
  the split; no Windows-path regressions expected.

## Open questions

None. The structure follows the existing section dividers; no design
calls required from Eric. If the final `memory.py` under `cli/` ends
up larger than expected (it has 5 verbs + a small shared `_open_memory`
call-site), it's still well under 200; not a blocker.

## Ship criterion

- `pytest -q` green (70+ tests; unchanged counts).
- `sabrina --help` lists the same verbs as before, same grouping shown
  in the help text.
- `sabrina version`, `sabrina voice`, `sabrina chat`, `sabrina memory-stats`
  all behave as before.
- Line counts:
  - Every new module under `cli/` < 200.
  - `voice_loop.py` < 250.
  - `voice_turn.py` < 250.
- Guardrail #3 exception headers on `memory/store.py` and
  `gui/settings.py`.

## Not in this plan (later)

- Splitting `gui/settings.py` when it passes ~500. The next GUI tab
  (Budget, Listen, Semantic sub-frames from 007b) may push it past
  that line. At that point, a per-tab helper-function pattern (not a
  per-tab class hierarchy) is the move.
- Extracting an `audio/` package for `listener/ptt.py`,
  `listener/record.py`, `listener/vad.py` (from barge-in), and
  `listener/wake.py` (from wake-word). Possible down the road but
  each file is currently small; guardrail #2 ("no new abstraction
  until the second caller exists") holds until one of them passes
  300 lines.
- Breaking out a `supervisor/` package if the autostart work ends up
  larger than the draft implies. Flagged in `supervisor-autostart-plan.md`;
  revisit there.

## The guardrail narrative, for the decision-doc-on-ship

When this lands as a numbered decision doc, the "why" paragraph is:

> Guardrail #3 drew a line at 300 lines. `cli.py` was at 753 and
> `voice_loop.py` at 427. Neither crossed because of a single big
> addition — both grew a little per shipped component. That's exactly
> the pattern anti-sprawl was supposed to catch: slow, justified growth
> that still ends up somewhere you wouldn't start from. The split
> respects the existing section dividers (for `cli.py`) and the
> existing per-turn state shape (for `voice_loop.py`). No new class
> hierarchies. Three files become eleven; total line count stays the
> same; the biggest resulting file is under 200 lines.
