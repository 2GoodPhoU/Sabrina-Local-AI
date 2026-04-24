# DRAFT — DO NOT FILE UNTIL STEP 0 OR STEP 4 OF `validate-007-windows.md` FAILS

> This stub is pre-written so the fix path is ready if the sqlite-vec
> load path breaks on Eric's Windows Python. If validation goes green,
> **delete this file** (or leave it archived; don't move it to
> `decisions/`). If it breaks, fill in the observed error below, move to
> `rebuild/decisions/008-sqlite-vec-on-windows.md`, and commit.

---

# Decision 008: sqlite-vec on a Python built without `enable_load_extension`

**Date:** 2026-04-23 *(fill in actual file date on move)*
**Status:** *(fill in: "Mitigated" / "Shipped")*

## The one-liner

sqlite-vec rides on `sqlite3.Connection.enable_load_extension`, which is
compiled out of several common Windows Python distributions (old
python.org installers, Microsoft-Store Python, some Conda layouts). When
that flag is missing, `MemoryStore._try_enable_vec` catches the
`AttributeError` and silently degrades to text-only memory, so the voice
loop keeps running but semantic retrieval is inert. The fix is to have
`uv` use its managed Python build (`python-build-standalone`), which is
compiled with extension loading on.

## What we observed

*(Fill in the exact symptom path. Example placeholder:)*

```
> uv run python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.enable_load_extension(True)"
AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'
```

or from `memory-stats`:

```
  vec table:   disabled (sqlite-vec unavailable or config off)
```

with the structlog warning `memory.vec_unavailable error=... dim=384`.

Python we were running: *(paste `python --version` and `sys.executable`)*.
sqlite-vec version: *(paste `uv pip show sqlite-vec`)*.

## Why this happens

CPython's `sqlite3` is built against whatever libsqlite3 ships with the
distribution. The `--enable-loadable-sqlite-extensions` build flag is on
by default in the upstream source, but a few Windows-specific builds
disable it (historically for sandboxing reasons). When disabled, the
`Connection.enable_load_extension` attribute is simply not compiled in
— you get an `AttributeError` at runtime.

sqlite-vec needs it to load its loadable extension (the `.dll` that
implements `vec0`). No extension loading ⇒ no sqlite-vec ⇒ no
semantic retrieval.

## The fix

Switch to uv's managed Python. `uv python install 3.12` fetches a
`python-build-standalone` interpreter that is compiled with extension
loading enabled, regardless of what the system Python does.

```powershell
uv python install 3.12
uv sync --python 3.12
```

`uv sync --python 3.12` pins the project to that interpreter; subsequent
`uv run ...` calls use it automatically. No code change to Sabrina
itself — the graceful-degrade path already exists for this failure mode.

Verify:
```powershell
uv run python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.enable_load_extension(True); print('ok')"
```
Expected: `ok`. Then re-run validation steps 4–7.

## Alternatives considered

1. **Ship sqlite-vec's SQLite build.** `apsw` or a vendored sqlite binary
   would sidestep the stdlib limitation entirely. Rejected: adds a
   binary dep just to paper over a Python-build mismatch we can fix upstream.
2. **Detect at install time and fail loudly.** A post-install hook
   could probe `enable_load_extension` and refuse to install. Rejected:
   degrade-gracefully is the right UX for a Sabrina that runs without
   semantic memory just fine.
3. **Hard-require uv-managed Python.** Pin `requires-python` to a narrow
   band and document it. Rejected: too aggressive. Most users' Pythons
   work; we only need the escape hatch when they don't.
4. **Swap sqlite-vec for an in-memory numpy index.** Listed in decision
   007's research list. A viable longer-term path if the extension
   problem turns out to be common, but overkill for a single failure.

## What shipped

- Documented the `uv python install 3.12` + `uv sync --python 3.12`
  fix in `rebuild/validate-007-windows.md`, step 0.
- *(If we ended up adding a `.python-version` file or similar, note here.)*
- No code change. `MemoryStore._try_enable_vec` already catches
  `AttributeError` and logs `memory.vec_unavailable`; the CLI surfaces
  the degrade in `memory-stats`.

## Thin spots

- **No proactive warning at voice-loop start.** The degrade log line is
  easy to miss if you're not running at DEBUG. A one-liner on stderr
  ("semantic memory requested but sqlite-vec unavailable; text-only mode")
  when `settings.memory.semantic.enabled=True` but `memory.vec_enabled=False`
  would be friendlier. Trivial follow-up; skipped for this decision.
- **Managed Python is another moving piece.** If Eric's `.python-version`
  drifts, a future `uv sync` might silently pick a different interpreter
  that re-introduces the issue. Worth pinning via `.python-version` in
  the repo if we commit to this path.

## Alternatives worth researching

1. Leaner embedder path (onnxruntime + tokenizers; no torch) that uses
   its own tiny vector index — kills both the torch dep and the
   sqlite-vec dep. On the decision-007 research list already.
2. A startup probe that logs a clear warning (instead of the low-key
   structlog message) when semantic is config-enabled but vec is off.

## Ship criterion check

Validation procedure in `rebuild/validate-007-windows.md` must go green
on the uv-managed Python after this fix. No regressions to the
text-only memory path (`test_memory_store_append_without_semantic_still_works`
stays passing).
