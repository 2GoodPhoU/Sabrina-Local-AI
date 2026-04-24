# Thin-spot split — Windows validation procedure

**Purpose:** confirm the `cli.py` → `cli/` package split and the
`voice_loop.py` → `voice_turn.py` extract work on Eric's Windows box
before we call the thin-spot-split decision validated. This is a
mostly-mechanical refactor; validation focuses on "nothing behaves
differently."
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from
`sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`. Split
has landed per `rebuild/drafts/thin-spot-split-plan.md`.

---

## Step 0 — Blow away stale `__pycache__`

The split deletes `cli.py` and replaces it with a `cli/` package. A
lingering `__pycache__/cli.cpython-312.pyc` on Windows can mask the
new package. Clear all pycache before anything else:

```powershell
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

**Success:** command completes silently. A second run shows nothing
(no pycache dirs left).

**Failure signal:** "access is denied" on a specific folder → some
process is holding files in that pycache. Close VS Code's Python
extension if it's running against this folder, then retry.

---

## Step 1 — `uv sync` (no-op expected)

```powershell
uv sync
```

**Success:** no-op or near-no-op; thin-spot-split adds no dependencies.

---

## Step 2 — `uv run pytest -q`

```powershell
uv run pytest -q
```

**Success — the pivotal step.** Test count is unchanged from pre-split
(70+ same tests, same names) plus ~5 new tests from the split itself:

- `test_cli_package_exposes_app_and_all_commands`
- `test_cli_verb_entrypoints_still_callable`
- `test_voice_turn_prepare_builds_expected_context`
- `test_voice_turn_prepare_handles_vision_trigger`
- `test_voice_turn_prepare_appends_retrieved_block`

**Failure signals:**
- **Test collection failure on `import sabrina.cli`.** Means
  `cli/__init__.py` didn't re-export `app`, or the subsystem-module
  side-effect imports weren't added. Capture the traceback:

  ```powershell
  uv run python -c "from sabrina.cli import app; print([c.name for c in app.registered_commands])"
  ```

  Should print a list of verb names. If it prints a shorter list than
  pre-split (say, `['version', 'chat']` instead of the full ~20+
  verbs), the missing verbs' modules aren't being imported in
  `__init__.py`.

- **One or more verb tests fail with `sabrina <verb>` not recognized.**
  A verb's `@app.command` decorator didn't register because its
  module wasn't imported. Check `cli/__init__.py` has one `from .
  import <module>` per file in the split.

- **Any pre-split test now fails.** Capture the name and traceback.
  Pre-existing tests must not regress; their behavior is the
  thin-spot-split's load-bearing invariant.

---

## Step 3 — `sabrina --help` verb inventory

```powershell
uv run sabrina --help
```

**Success:** every verb that existed pre-split is in the help output.
Cross-reference against what you remember, or grep the old `cli.py` from
git:

```powershell
git show HEAD~1:sabrina-2/src/sabrina/cli.py | Select-String "@app.command"
```

Every `@app.command` decorated function name should be a verb in the
new `--help` output.

**Failure signal:** verb missing → its module wasn't imported in
`cli/__init__.py`, or its decorator refers to a stale `app` instance
instead of the shared one in `cli/app.py`.

---

## Step 4 — Import-cycle check

A package split can accidentally introduce circular imports between
the new sub-modules and `_common.py`. Prove none exist:

```powershell
uv run python -c "import sabrina.cli; import sabrina.cli.brain; import sabrina.cli.tts; import sabrina.cli.asr; import sabrina.cli.voice; import sabrina.cli.vision; import sabrina.cli.memory; import sabrina.voice_loop; import sabrina.voice_turn; print('clean')"
```

**Success:** prints `clean` with no errors.

**Failure signal:** `ImportError: cannot import name X from partially
initialized module Y` → a circular import. Capture which two modules
are involved from the traceback.

---

## Step 5 — A few verbs, end-to-end

The fast unit tests covered the registration plumbing; these prove the
verbs still *do* the thing they used to do.

```powershell
uv run sabrina version
```

**Success:** prints the version banner.

```powershell
uv run sabrina config-show
```

**Success:** prints the full settings tree.

```powershell
uv run sabrina memory-stats
```

**Success:** same output as before the split (counts for messages,
embeddings, etc.).

```powershell
uv run sabrina test-audio
```

**Success:** lists audio devices as before.

**Failure signal for any:** `AttributeError` / `NameError` inside the
verb → a helper function was left behind in the old location. Check
`cli/_common.py` has all the private helpers the plan lists.

---

## Step 6 — `sabrina voice` — the one that exercises `voice_turn.py`

```powershell
uv run sabrina voice
```

Hold PTT, ask a simple question (*"what is 2 plus 2?"*), release. Let
the reply finish.

**Success:** behaves identically to pre-split. First-audio latency
within ~50 ms of baseline (the `prepare_turn` extraction adds nothing
meaningful to the critical path; if it adds 200+ ms, something is
wrong).

**Failure signal A:** crash mid-turn with `NameError: turn_brain` or
similar → `prepare_turn` returns a `TurnContext` that's missing a
field the outer loop uses. Check the dataclass definition against the
post-split `voice_loop.py`'s usages.
**Failure signal B:** vision trigger word in the question no longer
attaches a screenshot → the `use_vision` logic didn't make it into
`prepare_turn`. Retest with `"look at this for me"`.
**Failure signal C:** retrieved-memory block no longer surfaces in the
system prompt → `turn_system_suffix` not plumbed correctly from
`prepare_turn` to the brain call.

---

## Step 7 — Line-count targets per the plan

The split has specific line-count targets. Verify:

```powershell
Get-ChildItem src\sabrina\cli -Filter *.py | Select-Object Name, @{N='Lines';E={(Get-Content $_.FullName).Count}}
```

**Success:** every file in `cli/` is **< 200 lines**. None approach the
300 guardrail.

```powershell
(Get-Content src\sabrina\voice_loop.py).Count
(Get-Content src\sabrina\voice_turn.py).Count
```

**Success:** `voice_loop.py < 250` and `voice_turn.py < 250`.

**Failure signal:** a file bigger than its target → the split as
executed didn't match the plan. Capture the offender's line count. The
decision to adjust is either "further split" or "document the guardrail
exception" per the plan's stated pattern.

---

## Step 8 — Guardrail exception headers present

The plan says `memory/store.py` and `gui/settings.py` should gain a
header-comment guardrail exception (over 300 lines by design). Verify:

```powershell
Select-String -Path src\sabrina\memory\store.py -Pattern "guardrail" -SimpleMatch
Select-String -Path src\sabrina\gui\settings.py -Pattern "guardrail" -SimpleMatch
```

**Success:** each prints a line from the module docstring referencing
guardrail #3.

**Failure signal:** no match → the headers weren't added. Not a
blocker for the refactor's correctness but a plan deviation. File a
one-commit follow-up adding the headers.

---

## Step 9 — `pyproject.toml` entry point still resolves

The entry point is `sabrina = "sabrina.cli:app"`. Deleting `cli.py`
and replacing with `cli/` can break this if `__init__.py` doesn't
re-export `app`.

```powershell
sabrina version
```

**Success:** prints the version. (Using the entry-point directly, not
`uv run sabrina` which has its own resolution.)

**Failure signal:** `ModuleNotFoundError: sabrina.cli.app` or similar
→ `cli/__init__.py` must `from .app import app` for the entry point
to find it.

---

## Step 10 — Bonus smoke: settings GUI tab count unchanged

```powershell
uv run sabrina settings-gui
```

**Success:** same tab count as pre-split, each tab renders without
crash. GUI code isn't in scope of the split but relies on
`sabrina.cli`'s verbs being resolvable for its subprocess invocations.

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 0 | Access denied on pycache | IDE holding files | Which folder failed |
| 2 | `test_cli_package_exposes_app_and_all_commands` fails | Missing module import in cli/__init__.py | List from `app.registered_commands` |
| 2 | Pre-split test regresses | Helper not migrated into `_common.py` | Test name + traceback |
| 3 | Verb missing from --help | Same as above | Diff against `git show HEAD~1:.../cli.py` |
| 4 | Import cycle | `_common.py` importing a subsystem module that imports it back | Traceback's "partially initialized module" names |
| 5 | `AttributeError` in verb | Helper left behind | Which helper name |
| 6 | `NameError` in voice turn | TurnContext field missing | Which field |
| 6 | Vision trigger doesn't fire | `use_vision` logic not migrated | DEBUG log during the turn |
| 7 | File over line target | Plan-execution mismatch | Offending file + line count |
| 8 | No guardrail header | Plan skipped the header commit | — |
| 9 | Entry point broken | `cli/__init__.py` doesn't re-export | Traceback |

---

## Known risks from the pre-validation code audit

1. **Windows `__pycache__` staleness is the #1 gotcha.** Step 0 is
   non-optional. The pyc for the old `cli.py` will keep resolving as
   long as it exists — the Python module-finder finds `.pyc` first if
   the source `.py` is gone and `sys.dont_write_bytecode` isn't set.
   This is the most common cause of "the split worked for me but not
   for Eric."
2. **Typer's `@app.command` relies on module-import side effects.**
   Each subsystem module's commands only register with `app` when
   that module is imported. `cli/__init__.py` must explicitly import
   every subsystem file. A missing import is a silent partial break
   — `sabrina --help` shows fewer verbs, no error anywhere.
3. **`voice_turn.prepare_turn` is a pure function by design.** If
   tests pass but step 6 (the real voice loop) regresses, the bug is
   in how the outer loop consumes `TurnContext`, not in
   `prepare_turn` itself. Bisect by returning to pre-split `voice_loop.py`
   temporarily and confirming the pre-split turn still works.
4. **Line-count targets are loose.** "Every file < 200" is a guide,
   not a hard rule. A 210-line file isn't a blocker; a 310-line file
   is a re-split candidate. Step 7 surfaces the number; the decision
   to re-split happens separately.
5. **No protocol/behavior change in this work.** If any pre-split test
   fails, the refactor has a real bug, not a test flakiness issue —
   do not retry tests; investigate.

---

## If all green — the ROADMAP bump

Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line.
2. Append one line:

```
Thin-spot split validated on Windows (i7-13700K/4080, Python 3.12)
<YYYY-MM-DD>: cli.py → cli/ (<L1>..<L2> lines per module), voice_loop
<L3> + voice_turn <L4>, full test suite green, no behavior changes.
```

Fill in the line counts from step 7.

Commit with message:
```
validate: thin-spot split on Windows (no behavior change)
```

---

## If any step failed

1. Capture per the triage table.
2. For import-ordering or registration bugs (steps 2, 3, 4, 9): the
   fix is usually a single edit to `cli/__init__.py` — footnote on
   the shipped decision doc, no new numbered decision.
3. For `voice_turn.py` behavioral regressions (step 6): worth its own
   decision doc because the extraction touched the hottest path in
   the project; the doc captures what shape the `TurnContext`
   settled on and why.
4. For a line-count miss (step 7): neither a bug nor a decision doc;
   note in the ROADMAP bump and revisit at the next plan session.
