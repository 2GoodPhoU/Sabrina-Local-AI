# stage-pass2-commits-v2.ps1
# -----------------------------------------------------------------------------
# Stages the Track-B + pass-2 working-tree changes into 3 atomic commits.
# v2 fixes from v1 (which silently failed because pre-commit blocked it):
#   - Adds --no-verify to every git commit (pre-commit not installed in venv;
#     known thin spot per CLAUDE.md gotcha #2; documented workaround).
#   - Replaces multi-line PowerShell here-strings (@"..."@) with multiple
#     `-m` flags. Git joins them with blank lines, no shell-quoting drama.
#   - git rm -f on the 008 stub (local mods present, plain git rm refused).
#   - Checks $LASTEXITCODE after each git command. A failed git aborts the
#     script instead of marching on.
#   - git reset HEAD . at the start so re-running on a partially-staged tree
#     (e.g. after v1 left things half-staged) is safe and idempotent.
#
# Run from the Sabrina-Local-AI/ root:
#   .\stage-pass2-commits-v2.ps1
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

function CheckExit($what) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: $what failed with exit code $LASTEXITCODE. Aborting." -ForegroundColor Red
        exit 1
    }
}

# --- Sanity checks ---------------------------------------------------------
Header "Sanity checks"

if (-not (Test-Path "rebuild/ACTION_ITEMS.md")) {
    Write-Host "ERROR: run this from the Sabrina-Local-AI/ repo root." -ForegroundColor Red
    exit 1
}

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Host "Current branch: $branch"

# Idempotency: clear the staging area in case v1 left it half-staged.
# Working tree is untouched.
Write-Host "Resetting index to HEAD (working tree untouched)..."
git reset HEAD . | Out-Null
# git reset returns 1 when nothing to do — that's fine, swallow it.
$global:LASTEXITCODE = 0

git status --short | Select-Object -First 40
Write-Host ""

# --- Commit 1: cleanup ----------------------------------------------------
Header "Commit 1/3: chore(rebuild) - cleanup stubs + ACTION_ITEMS consolidation + 010 promotion"
Write-Host @"
Will:
  - git rm -f rebuild/decisions/008-foundational-refactor-shipped.md
  - git rm write_test.txt
  - rm rebuild/ACTION_ITEMS_code.md, rebuild/ACTION_ITEMS_personality.md (untracked)
  - rm rebuild/decisions/drafts/010-personality-spec.md (the original; promoted copy lives at decisions/010-personality-spec.md)
  - rmdir rebuild/decisions/drafts (now empty)
  - git add rebuild/ACTION_ITEMS.md, when-you-return.md, ROADMAP.md, decisions/010-personality-spec.md
  - git commit --no-verify
"@
if (Confirm "Run commit 1?") {
    # -f because the stub has local modifications (whitespace from prior session)
    git rm -f rebuild/decisions/008-foundational-refactor-shipped.md
    CheckExit "git rm 008 stub"
    if (Test-Path "write_test.txt") {
        git rm write_test.txt
        CheckExit "git rm write_test.txt"
    }
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
    CheckExit "git add (commit 1)"

    git commit --no-verify `
        -m "chore(rebuild): consolidate ACTION_ITEMS + cleanup stubs + promote 010 spec" `
        -m "Repo housekeeping for the Track-B / pass-2 overnight work." `
        -m "Remove tracked stubs: 008-foundational-refactor-shipped.md (8-line redirect) and write_test.txt (sandbox artifact)." `
        -m "Remove untracked redirect stubs that were merged into ACTION_ITEMS.md: ACTION_ITEMS_code.md, ACTION_ITEMS_personality.md." `
        -m "Promote rebuild/decisions/drafts/010-personality-spec.md to rebuild/decisions/010-personality-spec.md (drop DRAFT marker + Status line); remove the now-empty drafts/ subdirectory." `
        -m "Add rebuild/ACTION_ITEMS.md (consolidated punch list) and refresh rebuild/when-you-return.md + rebuild/ROADMAP.md to point at it."
    CheckExit "git commit (commit 1)"
    Write-Host "Commit 1 done." -ForegroundColor Green
} else {
    Write-Host "Skipped commit 1." -ForegroundColor Yellow
}

# --- Commit 2: code -------------------------------------------------------
Header "Commit 2/3: feat(sabrina-2) - pass-2 features"
Write-Host @"
Will stage all sabrina-2/ working-tree changes and commit them as one
unit. Per-component decision docs carry the per-component traceability;
this commit message lists the units.

Files in scope (pyproject.toml + sabrina.toml include the post-audit
truncation fixes from this session: pyproject.toml had lost
[build-system], [tool.ruff], [tool.uv]; sabrina.toml had an empty
[memory.compaction] block. Both reconstructed.)
"@
if (Confirm "Run commit 2 (the kitchen sink)?") {
    git add sabrina-2/
    CheckExit "git add sabrina-2/"

    git commit --no-verify `
        -m "feat(sabrina-2): pass-2 features (wake-word, supervisor, ONNX embedder, compaction, GUI panel)" `
        -m "Bundles the Track-B (B1-B4) + pass-2 (C1-C6) working-tree changes from the 2026-04-25 overnight session. Per-component decision docs and validate-*.md procedures are unchanged; this is the code landing." `
        -m "Units (see rebuild/ACTION_ITEMS.md for per-unit detail and validate-*.md gating):" `
        -m "B1 logging vocabulary completion: asr.* event renames in listener/faster_whisper.py + record.py; turn_id contextvar binding + turn.* events in voice_loop.py; +3 tests." `
        -m "B2 wake-word scaffolding (openwakeword): new listener/wake_word.py (~270L) with WakeWordDetector + WakeWordMonitor; +5 tests." `
        -m "B3 supervisor + autostart: new supervisor.py (~315L); run_supervised + Task Scheduler XML + nssm command builders; cli.py 'sabrina run' + 'sabrina autostart {enable|disable|status}'; +9 tests." `
        -m "B4 semantic memory schema v1 + compaction algorithm: memory/store.py schema v1 (kind, summarized_at) + new APIs (load_summaries, mark_summarized, count_uncompacted, ...); new memory/compaction.py (~180L) with Summarizer protocol; gui/settings.py memory tab + Semantic / Compaction frames; +10 tests." `
        -m "C1 ONNX embedder swap (drops torch from default install): memory/embed.py rewritten with OnnxMiniLMEmbedder default and legacy SentenceTransformerEmbedder fallback; pyproject.toml moves sentence-transformers to optional [legacy-embedder] extra; cli.py new 'sabrina download-models' verb; +4 tests." `
        -m "C2 voice-loop wake-word integration: race PTT vs wake-event with asyncio.wait; graceful degrade on openwakeword load failure; import-presence regression test." `
        -m "C3 'sabrina memory-compact' CLI verb + brain-backed Summarizer adapter via brain.chat." `
        -m "C4 voice-loop summary injection: _summary_block() at head of system prompt; +2 tests." `
        -m "C5 gui/settings.py Phase-0 fixes (3 real bugs from prior reconstruction): restore SettingsWindow.mainloop(); _collect filters underscore-prefix keys + translates _piper_preset; _preset_key_from_model_path drives off canonical PRESETS; +2 tests." `
        -m "C6 GUI Compact-now / Reindex shell-out buttons: subprocess + status-label feedback." `
        -m "Also fixes silent-truncation drift from prior sandbox edits: memory/__init__.py (was cut at 'Se'; restored __all__); listener/__init__.py (was cut at '__al'; restored __all__ with WakeWord re-exports); listener/record.py (was 'return audio.res'; restored 'return audio.reshape(-1)'); pyproject.toml (was cut at '# Only install if you'; restored full project metadata + added [tool.uv] environments=[\"sys_platform == 'win32'\"] to fix the openwakeword/cp312 resolver wedge); sabrina.toml ([memory.compaction] body was missing 4 fields; restored)." `
        -m "Audit notes for review: config.py diff includes substantial inline-comment removal beyond the new Config classes (likely artifact of an earlier reconstruction; selectively restore via 'git checkout -p HEAD~1 -- sabrina-2/src/sabrina/config.py' if desired)." `
        -m "Imports require Windows test run: 'uv sync && uv run pytest -q'. Expect ~96 tests passing (was 59 pre-overnight)."
    CheckExit "git commit (commit 2)"
    Write-Host "Commit 2 done." -ForegroundColor Green
} else {
    Write-Host "Skipped commit 2." -ForegroundColor Yellow
}

# --- Commit 3: planning docs ---------------------------------------------
Header "Commit 3/3: docs(planning) - personality + tool-use MCP audit + research"
Write-Host @"
Will stage:
  - rebuild/drafts/personality-plan.md       (rewritten OPEN-QUESTIONS,
                                                +System-prompt skeleton section)
  - rebuild/drafts/personality-lift-plan.md  (NEW: implementation plan;
                                                4 open questions for review)
  - rebuild/drafts/tool-use-plan.md          (+ MCP-compatibility audit)
  - rebuild/drafts/research/                 (overnight survey notes)
"@
if (Confirm "Run commit 3?") {
    git add `
        rebuild/drafts/personality-plan.md `
        rebuild/drafts/personality-lift-plan.md `
        rebuild/drafts/tool-use-plan.md `
        rebuild/drafts/research/
    CheckExit "git add (commit 3)"

    git commit --no-verify `
        -m "docs(planning): personality finalization + tool-use MCP audit + research notes" `
        -m "personality-plan.md: rewrite OPEN-QUESTIONS with recommendation + override knobs per question; refresh 'Where these signals came from'; add concrete 'System-prompt skeleton' section with per-block token-budget table and cacheable-vs-dynamic markings. (See decisions/010-personality-spec.md, promoted in the cleanup commit.)" `
        -m "personality-lift-plan.md: NEW. Implementation plan for lifting the 010 skeleton into voice_loop._SYSTEM + chat._SYSTEM. Adds a small new sabrina/personality.py module (anti-sprawl rule #2 holds: two callers exist before it ships). Four open questions awaiting Eric: chat._SYSTEM scope, system_suffix= plumbing, vision-turn integration, Ollama tightening + smoke test scope. Recommendations attached." `
        -m "tool-use-plan.md: append 'MCP compatibility' section summarizing what's already MCP-shape, what diverges, and a 30-line concrete delta to the protocol (ToolSpec.to_mcp_dict, ToolUseDone.is_error, content-block helpers). No code touched." `
        -m "drafts/research/: Track-B overnight stack-alternatives survey + sources index. Background reading; cited from C1 (ONNX embedder) and the wake-word plan."
    CheckExit "git commit (commit 3)"
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
Write-Host "Done. Next steps:" -ForegroundColor Cyan
Write-Host "  1. cd sabrina-2 && uv sync && uv run pytest -q   (expect ~96 passing)"
Write-Host "  2. sabrina download-models embedder              (one-shot HF fetch ~80 MB)"
Write-Host "  3. Walk validate-*.md procedures (wake-word, supervisor, memory-gui)"
Write-Host "  4. Push when validation is green."
