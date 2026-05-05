# Cleanup findings — 2026-04-26 night session

**Scope:** docs + repo hygiene only. The parallel session is doing
code work on `sabrina-2/src/sabrina/` and promoting decision 010
(personality spec) from draft to shipped; that's untouched here.

## Step-by-step record

### Step 1 — `compileall` pre-commit hook

**File:** `.pre-commit-config.yaml`
**Change:** appended a local hook that runs `python -m compileall -q
sabrina-2/src` before commit. Catches the SyntaxError-on-commit class
of bug — the kind that nearly shipped `config.py` in a previous pass.

- YAML validated with `python3 -c "import yaml; yaml.safe_load(...)"`
  → 4 repos parsed cleanly, local hook present.
- Command itself ran clean against current source tree:
  `python3 -m compileall -q sabrina-2/src` exited 0.
- Hook is `language: system`, `pass_filenames: false`,
  `types_or: [python]`, so it runs once per commit (not per file)
  whenever any `.py` is staged.

### Step 2 — Documentation drift

| Drift | Before | After | File |
|---|---|---|---|
| ROADMAP "Last updated" | 2026-04-25 | 2026-04-26 | `rebuild/ROADMAP.md` |
| ROADMAP heads-up: pass 2 "uncommitted" | yes | "landed 2026-04-25"; cross-link to `CLEANUP_FINDINGS_2026-04-26-night.md` and `LEGACY_REPLACEMENT_GATE.md` | `rebuild/ROADMAP.md` |
| ROADMAP status line: 59 tests | 59 | 96 | `rebuild/ROADMAP.md` |
| ROADMAP status line: missing 010 | absent | personality spec mention added | `rebuild/ROADMAP.md` |
| ROADMAP wake-word row | "⏭ replaced by PTT" | "🟡 scaffolded (2026-04-25)" | `rebuild/ROADMAP.md` |
| ROADMAP wake-word body section | "deferred" | "scaffolded; bundled `hey_jarvis` placeholder; awaiting validation" | `rebuild/ROADMAP.md` |
| ROADMAP decision log | 001-009 | + 010 personality spec | `rebuild/ROADMAP.md` |
| README test count | 57 | 96 | `sabrina-2/README.md` |
| README layout: `whisper.py` | `whisper.py` | `faster_whisper.py` | `sabrina-2/README.md` |
| README layout: missing `wake_word.py`, `compaction.py`, `supervisor.py` | absent | added | `sabrina-2/README.md` |
| README component table: wake-word "replaced by PTT" | yes | "🟡 scaffolded, awaiting Windows validation" | `sabrina-2/README.md` |
| README component table: 010 personality | absent | added | `sabrina-2/README.md` |
| `validate-007b-semantic-memory-gui.md` line 11 | `memory/compact.py` | `memory/compaction.py` | `rebuild/validate-007b-semantic-memory-gui.md` |
| `validate-wake-word.md` line 10 | `listener/wake.py` | `listener/wake_word.py` (+ surrounding prose rewrite for the bundled-id loading model) | `rebuild/validate-wake-word.md` |
| `validate-wake-word.md` model name | `hey_sabrina` (custom, untrained) | `hey_jarvis` (openWakeWord-bundled placeholder, matches `[wake_word].model` in `sabrina.toml`) | `rebuild/validate-wake-word.md` |
| `validate-wake-word.md` model loading | `voices/wake/hey_sabrina.onnx` (file path) | `wakeword_models=['hey_jarvis']` (bundled id, no path) | `rebuild/validate-wake-word.md` |
| `validate-wake-word.md` toml example | `model_path = "voices/wake/hey_sabrina.onnx"` | `model = "hey_jarvis"` (matches actual schema) | `rebuild/validate-wake-word.md` |
| `validate-wake-word.md` `auto_capture_s = 5.0` | present (not in current `[wake_word]` schema) | removed | `rebuild/validate-wake-word.md` |
| `validate-wake-word.md` triage row "git log -- voices/wake/" | present | "uv pip show openwakeword" | `rebuild/validate-wake-word.md` |
| `when-you-return.md` references to removed `ACTION_ITEMS_code.md`, `ACTION_ITEMS_personality.md`, and `008-foundational-refactor-shipped.md` redirect stub | live | reworked into a "these are gone, verified 2026-04-26" note | `rebuild/when-you-return.md` |
| `when-you-return.md` validate-memory-gui doc name | `validate-memory-gui.md` (doesn't exist) | `validate-007b-semantic-memory-gui.md` (actual filename) | `rebuild/when-you-return.md` |
| `when-you-return.md` test count | 59 → ~70 | 96 | `rebuild/when-you-return.md` |
| `when-you-return.md` "Date" header | 2026-04-25 | 2026-04-26 | `rebuild/when-you-return.md` |

**Highest-impact fix:** the `hey_sabrina` → `hey_jarvis` correction in
`validate-wake-word.md`. The doc was telling the reader to load a
custom-trained ONNX file at a path that doesn't exist (and was never
intended to exist at this stage); the actual scaffold uses the
bundled openWakeWord placeholder loaded by name. Anyone running
through the procedure pre-fix would have hit `FileNotFoundError` at
step 0 and burned an hour debugging a phantom missing-commit before
realizing the doc was stale.

### Step 3 — Decision-doc cleanup audit

- **`008-foundational-refactor-shipped.md` redirect stub:** verified
  absent. Per `CLEANUP_FINDINGS_2026-04-26.md` line 137, this file was
  never committed to HEAD in the first place; the `git rm` instruction
  in `ACTION_ITEMS.md` B0 is moot. No action.
- **`ACTION_ITEMS_code.md` and `ACTION_ITEMS_personality.md`:**
  verified absent from `rebuild/`. The consolidated `ACTION_ITEMS.md`
  is the only punch list in the directory. Lingering references in
  `when-you-return.md` were rewritten (see Step 2). Lingering
  references in `ACTION_ITEMS.md` itself are historical context for
  the B0 row — left as-is; not confusing in context.
- **`decisions/` index:** files sort `001-010` cleanly in `ls` order.
  No `INDEX.md` needed; the `ROADMAP.md` decision-log section is the
  canonical index.

### Step 4 — Legacy Replacement Gate

**New file:** `rebuild/LEGACY_REPLACEMENT_GATE.md` (~1,300 words,
180 lines).

Sections: honest assessment of where the rebuild has surpassed
legacy; per-subdirectory walk of what's still uniquely in legacy
cross-referenced against `rebuild/drafts/old-repo-migration-audit.md`
(2026-04-23); replacement-gate checklist with a 7-day daily-driver
bake-in window; calendar timeline (mid- to late-May 2026 realistic);
post-archive disposition options.

**Headline finding (worst case):** ~30 days from 2026-04-26 to legacy
archive — 9.5 hours of port work + 7-day bake-in + budget for two
regression resets in the bake-in window. Mid-May is the realistic
median; late May is the worst case.

**Migration audit re-validation:** all five worth-porting items
(audio device enumeration, keyboard shortcuts, system dependency
checks, test fixtures, conftest scaffolding) confirmed **not yet
ported** as of 2026-04-26. None blocking; each removes a daily-driver
papercut.

### Step 5 — `ACTION_ITEMS.md` deltas

Appended a dated section. See that file for the punch-list entry; the
section header (`## 2026-04-26 night cleanup — docs + hygiene`) is
chosen so the parallel code-task's contribution can sit alongside
without conflict.

## Cross-cutting

- All work uncommitted in working tree. Recommended commit slicing
  (Eric's morning):
  1. `.pre-commit-config.yaml` — chore: add compileall hook.
  2. `rebuild/ROADMAP.md`, `sabrina-2/README.md` — docs: update
     status, test count, wake-word row, 010 entry.
  3. `rebuild/validate-wake-word.md`,
     `rebuild/validate-007b-semantic-memory-gui.md` — docs: fix
     stale filename references in validation procedures.
  4. `rebuild/when-you-return.md` — docs: drop references to removed
     redirect stubs.
  5. `rebuild/LEGACY_REPLACEMENT_GATE.md`,
     `rebuild/CLEANUP_FINDINGS_2026-04-26-night.md`,
     `rebuild/ACTION_ITEMS.md` — docs: legacy-archive gate +
     overnight-cleanup record.
- Anti-truncation discipline: every file edit went through
  `bash + python3` heredoc or the `Edit` tool with explicit Read+Edit
  pairs; large rewrites (the validate-wake-word.md sweep) used
  `python3` `.replace()` chains with byte-count assertions.
- **Untouched** (per cross-task contract): `sabrina-2/src/sabrina/`,
  `sabrina-2/sabrina.toml`, `sabrina-2/pyproject.toml`,
  `sabrina-2/tests/`, `rebuild/decisions/drafts/010-personality-spec.md`.

## Open follow-ups (none blocking)

- The wake-word `validate-*.md` rewrite kept the doc structure intact
  but swapped the model identity from `hey_sabrina` (custom, future)
  to `hey_jarvis` (placeholder, current). When a real custom "Hey
  Sabrina" model lands, the doc gets one more pass to swap back.
- `ROADMAP.md` "remove garbage scorecard" still describes the legacy
  delete plan in the present tense. Once legacy moves to `archive/`
  per `LEGACY_REPLACEMENT_GATE.md`, that table updates to past-tense
  ("archived 2026-MM-DD") in the same commit that flips the archive.
- `CLAUDE.md`'s "Where the code and docs live" lists legacy folders
  by name. Same trigger — update when legacy moves.
