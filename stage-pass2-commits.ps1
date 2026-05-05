# stage-pass2-commits.ps1
# -----------------------------------------------------------------------------
# Stages the Track-B + pass-2 working-tree changes into 3 atomic commits.
#
# Run from the Sabrina-Local-AI/ root:
#   pwsh -File .\stage-pass2-commits.ps1
# or just:
#   .\stage-pass2-commits.ps1
#
# The script:
#   1. Sanity-checks that you're in the right directory and on the expected branch
#   2. Optionally repairs the .git/config NUL-byte corruption (asks first)
#   3. Stages + commits 3 logical groups in order
#
# Each commit step prompts for [Y/n] before staging. You can skip any commit
# (saves the changes for later, doesn't lose them). To split commits further,
# `git reset --soft HEAD~1` after a commit and re-stage with `git add -p`.
#
# Designed by Claude after auditing the working tree on 2026-04-25.
# Audit findings worth knowing before running:
#   - 3 silent-truncation bugs in prior-session reconstructions were fixed
#     pre-commit: memory/__init__.py, listener/__init__.py, listener/record.py.
#     The fixes are in the working tree; they ride along with commit 2.
#   - config.py diff includes substantial INLINE-COMMENT removal beyond the
#     new feature additions. Likely an artifact of an earlier reconstruction
#     pass. Eyeball commit 2's config.py diff before signing off; you may
#     want to restore the comments via `git checkout -p HEAD -- sabrina-2/src/sabrina/config.py`.
#   - The 010 personality spec was promoted out of decisions/drafts/ in-session.
#     The original file in drafts/ couldn't be removed from the sandbox; this
#     script does the cleanup.
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

function Confirm($prompt) {
    $r = Read-Host "$prompt [Y/n]"
    return ($r -eq "" -or $r -eq "y" -or $r -eq "Y")
}

function Header($text) {
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor Cyan
    Write-Host $text -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor Cyan
}

# --- Sanity checks ---------------------------------------------------------
Header "Sanity checks"

if (-not (Test-Path "rebuild/ACTION_ITEMS.md")) {
    Write-Host "ERROR: run this from the Sabrina-Local-AI/ repo root." -ForegroundColor Red
    exit 1
}

$branch = (git rev-parse --abbrev-ref HEAD 2>$null).Trim()
Write-Host "Current branch: $branch"
if ($branch -ne "main" -and $branch -ne "Sabrina-AI-Presence") {
    if (-not (Confirm "On branch '$branch', not main. Continue?")) { exit 0 }
}

# .git/config NUL corruption (per ACTION_ITEMS.md)
$lfs = git config --get lfs.repositoryformatversion 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ".git/config has the [lfs] NUL-byte corruption noted in ACTION_ITEMS.md." -ForegroundColor Yellow
    if (Confirm "Fix it now (`git config --remove-section lfs`)?") {
        git config --remove-section lfs
        Write-Host "Fixed." -ForegroundColor Green
    }
}

git status --short | Select-Object -First 40
Write-Host ""

# --- Commit 1: cleanup ----------------------------------------------------
Header "Commit 1/3: chore(rebuild) - cleanup stubs + ACTION_ITEMS consolidation + 010 promotion"
Write-Host @"
Will:
  - git rm rebuild/decisions/008-foundational-refactor-shipped.md
  - git rm write_test.txt
  - rm rebuild/ACTION_ITEMS_code.md, rebuild/ACTION_ITEMS_personality.md (untracked)
  - rm rebuild/decisions/drafts/010-personality-spec.md (the original; promoted copy lives at decisions/010-personality-spec.md)
  - rmdir rebuild/decisions/drafts (now empty)
  - git add rebuild/ACTION_ITEMS.md, when-you-return.md, ROADMAP.md, decisions/010-personality-spec.md
  - git commit
"@
if (Confirm "Run commit 1?") {
    git rm rebuild/decisions/008-foundational-refactor-shipped.md
    git rm write_test.txt
    Remove-Item -Force rebuild/ACTION_ITEMS_code.md, rebuild/ACTION_ITEMS_personality.md -ErrorAction SilentlyContinue
    if (Test-Path "rebuild/decisions/drafts/010-personality-spec.md") {
        Remove-Item -Force rebuild/decisions/drafts/010-personality-spec.md
    }
    if ((Test-Path "rebuild/decisions/drafts") -and -not (Get-ChildItem rebuild/decisions/drafts)) {
        Remove-Item -Force rebuild/decisions/drafts
    }
    git add `
        rebuild/ACTION_ITEMS.md `
        rebuild/when-you-return.md `
        rebuild/ROADMAP.md `
        rebuild/decisions/010-personality-spec.md
    git commit -m @"
chore(rebuild): consolidate ACTION_ITEMS + cleanup stubs + promote 010 spec

Repo housekeeping for the Track-B / pass-2 overnight work.

- Remove tracked stubs:
    rebuild/decisions/008-foundational-refactor-shipped.md  (8-line redirect)
    write_test.txt                                          (sandbox artifact)
- Remove untracked redirect stubs that were merged into ACTION_ITEMS.md:
    rebuild/ACTION_ITEMS_code.md
    rebuild/ACTION_ITEMS_personality.md
- Promote rebuild/decisions/drafts/010-personality-spec.md to
  rebuild/decisions/010-personality-spec.md (drop DRAFT marker + Status line);
  remove the now-empty drafts/ subdirectory.
- Add rebuild/ACTION_ITEMS.md (consolidated punch list) and refresh
  rebuild/when-you-return.md + rebuild/ROADMAP.md to point at it.
"@
    Write-Host "Commit 1 done." -ForegroundColor Green
} else {
    Write-Host "Skipped commit 1." -ForegroundColor Yellow
}

# --- Commit 2: code -------------------------------------------------------
Header "Commit 2/3: feat(sabrina-2) - pass-2 features"
Write-Host @"
Will stage all sabrina-2/ working-tree changes and commit them as one
unit. The decision docs (007/008/009 + the per-component drafts) carry
the per-component traceability; this commit message lists the units.

Files in scope:
  - listener/wake_word.py            (NEW, B2)
  - listener/__init__.py             (re-exports + truncation fix)
  - listener/faster_whisper.py       (logging vocab, B1)
  - listener/record.py               (logging vocab + truncation fix)
  - memory/store.py                  (schema v1: kind+summarized_at, B4)
  - memory/compaction.py             (NEW, B4)
  - memory/embed.py                  (ONNX backend swap, C1)
  - memory/__init__.py               (re-exports + truncation fix)
  - supervisor.py                    (NEW, B3)
  - voice_loop.py                    (turn_id, wake-word race, summary inject, ONNX backend kwarg)
  - cli.py                           (autostart verbs, memory-compact verb, download-models verb)
  - gui/settings.py                  (memory tab, shell-out buttons, Phase-0 fixes C5)
  - config.py                        (4 new Config classes + COMMENT REMOVAL - audit!)
  - sabrina.toml                     (4 new config blocks)
  - pyproject.toml                   (onnxruntime, tokenizers, openwakeword;
                                       sentence-transformers -> legacy-embedder extra)
  - tests/test_smoke.py              (~37 new tests)

If you'd rather split this further, answer N here, then use
`git add -p` per-file to slice into commits like ACTION_ITEMS suggests.
"@
if (Confirm "Run commit 2 (the kitchen sink)?") {
    git add sabrina-2/
    git commit -m @"
feat(sabrina-2): pass-2 features (wake-word, supervisor, ONNX embedder, compaction, GUI panel)

Bundles the Track-B (B1-B4) + pass-2 (C1-C6) working-tree changes from
the 2026-04-25 overnight session. Per-component decision docs and
validate-*.md procedures are unchanged; this is the code landing.

Units included (see rebuild/ACTION_ITEMS.md for the full per-unit
detail and validate-*.md gating):

  B1 logging vocabulary completion
       - asr.* event renames in listener/faster_whisper.py + record.py
       - turn_id contextvar binding + turn.* events in voice_loop.py
       - +3 tests
  B2 wake-word scaffolding (openwakeword)
       - new listener/wake_word.py (~270L)
       - WakeWordDetector + WakeWordMonitor (mirrors AudioMonitor shape)
       - +5 tests
  B3 supervisor + autostart
       - new supervisor.py (~315L)
       - run_supervised + Task Scheduler XML + nssm command builders
       - cli.py: \`sabrina run\` + \`sabrina autostart {enable|disable|status}\`
       - +9 tests
  B4 semantic memory schema v1 + compaction algorithm
       - memory/store.py: schema v1 (kind, summarized_at) + new APIs
         (load_summaries, mark_summarized, count_uncompacted, ...)
       - new memory/compaction.py (~180L) with Summarizer protocol
       - gui/settings.py: memory tab + Semantic / Compaction frames
       - +10 tests
  C1 ONNX embedder swap (drops torch from default install)
       - memory/embed.py rewritten: OnnxMiniLMEmbedder default, legacy
         SentenceTransformerEmbedder kept as fallback
       - pyproject.toml: onnxruntime + tokenizers added; sentence-transformers
         moved to optional [legacy-embedder] extra
       - cli.py: new \`sabrina download-models [embedder|all]\` verb
       - voice_loop.py: forwards backend= to build_embedder
       - +4 tests
  C2 voice-loop wake-word integration
       - voice_loop.py: race PTT vs wake-event with asyncio.wait
       - graceful degrade on openwakeword load failure
       - import-presence regression test
  C3 \`sabrina memory-compact\` CLI verb + brain-backed summarizer
       - cli.py: brain-backed Summarizer adapter via brain.chat
  C4 voice-loop summary injection
       - voice_loop.py: _summary_block() at head of system prompt
       - +2 tests
  C5 gui/settings.py Phase-0 fixes (3 real bugs from prior reconstruction)
       - restore SettingsWindow.mainloop()
       - _collect filters underscore-prefix keys + translates _piper_preset
       - _preset_key_from_model_path drives off canonical PRESETS
       - +2 tests
  C6 GUI Compact-now / Reindex shell-out buttons
       - gui/settings.py: subprocess + status-label feedback

Also fixes silent-truncation drift from prior sandbox edits:
  - memory/__init__.py        (was cut at \"Se\"; restored \`__all__\`)
  - listener/__init__.py      (was cut at \"__al\"; restored \`__all__\`
                                with WakeWord re-exports)
  - listener/record.py        (was \`return audio.res\`; restored
                                \`return audio.reshape(-1)\`)

Audit notes for review:
  - config.py diff includes substantial inline-comment removal beyond
    the new Config classes. Likely artifact of an earlier reconstruction.
    Selectively restore via \`git checkout -p HEAD~1 -- sabrina-2/src/sabrina/config.py\`
    if the slimmer style isn't desired.
  - Imports require Windows test run: \`uv sync && uv run pytest -q\`
    Expect ~96 tests passing (was 59 pre-overnight).
  - Validate gates (Eric morning):
      - validate-wake-word.md         (TBD)
      - validate-supervisor-autostart.md
      - validate-memory-gui.md        (TBD)
"@
    Write-Host "Commit 2 done." -ForegroundColor Green
} else {
    Write-Host "Skipped commit 2." -ForegroundColor Yellow
}

# --- Commit 3: planning docs ---------------------------------------------
Header "Commit 3/3: docs(planning) - personality + tool-use MCP audit + research"
Write-Host @"
Will stage:
  - rebuild/drafts/personality-plan.md             (rewritten OPEN-QUESTIONS,
                                                     +System-prompt skeleton section)
  - rebuild/drafts/personality-lift-plan.md        (NEW: implementation plan for
                                                     lifting 010 spec into
                                                     voice_loop._SYSTEM + chat._SYSTEM;
                                                     4 open questions for glance-review)
  - rebuild/drafts/tool-use-plan.md                (+ MCP-compatibility audit, ~120L)
  - rebuild/drafts/research/                       (overnight survey notes)
"@
if (Confirm "Run commit 3?") {
    git add `
        rebuild/drafts/personality-plan.md `
        rebuild/drafts/personality-lift-plan.md `
        rebuild/drafts/tool-use-plan.md `
        rebuild/drafts/research/
    git commit -m @"
docs(planning): personality finalization + tool-use MCP audit + research notes

- rebuild/drafts/personality-plan.md: rewrite OPEN-QUESTIONS with
  recommendation + override knobs per question; refresh "Where these
  signals came from"; add concrete "System-prompt skeleton" section with
  per-block token-budget table and cacheable-vs-dynamic markings. (Also
  see decisions/010-personality-spec.md, promoted in the cleanup commit.)
- rebuild/drafts/personality-lift-plan.md: NEW. Implementation plan for
  lifting the 010 skeleton into voice_loop._SYSTEM + chat._SYSTEM. Adds
  a small new sabrina/personality.py module (anti-sprawl rule #2 holds:
  two callers exist before it ships). Four open questions awaiting Eric:
  chat._SYSTEM scope, system_suffix= plumbing, vision-turn integration,
  Ollama tightening + smoke test scope. Recommendations attached.
- rebuild/drafts/tool-use-plan.md: append "MCP compatibility" section
  summarizing what's already MCP-shape, what diverges, and a 30-line
  concrete delta to the protocol (ToolSpec.to_mcp_dict, ToolUseDone.is_error,
  content-block helpers). No code touched.
- rebuild/drafts/research/: Track-B overnight stack-alternatives survey
  + sources index. Background reading; cited from C1 (ONNX embedder)
  and the wake-word plan.
"@
    Write-Host "Commit 3 done." -ForegroundColor Green
} else {
    Write-Host "Skipped commit 3." -ForegroundColor Yellow
}

# --- Final state ----------------------------------------------------------
Header "Final state"
git log --oneline -10
Write-Host ""
git status --short
Write-Host ""
Write-Host "Done. Next steps (per ACTION_ITEMS.md):" -ForegroundColor Cyan
Write-Host "  1. cd sabrina-2 && uv sync && uv run pytest -q   (expect ~96 passing)"
Write-Host "  2. sabrina download-models embedder              (one-shot HF fetch ~80 MB)"
Write-Host "  3. Walk validate-*.md procedures (wake-word, supervisor, memory-gui)"
Write-Host "  4. Push when validation is green."
