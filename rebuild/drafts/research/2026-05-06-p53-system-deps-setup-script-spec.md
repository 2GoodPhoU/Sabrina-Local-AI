# P5.3 — System-deps install script (`sabrina-2/scripts/setup.py`) — spec

**Date:** 2026-05-06
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 5 → **P5.3 Port — system-deps install script (`scripts/setup.py`)** (`[linux-runnable] [partial-dod-eligible] [P1] [L]`).
**Predecessor:** legacy `scripts/sabrina_install.py` (~600 lines). Reference: `rebuild/drafts/old-repo-migration-audit.md` port item #3; closeout: `rebuild/LEGACY_REPLACEMENT_GATE.md` box #1 (~4h estimate).
**Scope:** mostly Linux-runnable (the dependency *probe* and the dry-run report). Names the (a) Linux-half / (b) Windows-half boundary so the Planner's split authority can stage the (a)-half cleanly. Off-limits: legacy `scripts/` (read-only), `rebuild/decisions/`.

---

## What this item is

The legacy `scripts/sabrina_install.py` does six things: (1) Python-version check, (2) system-binary probe (Tesseract, FFmpeg, PulseAudio), (3) virtualenv creation, (4) pip-install from `requirements.txt`, (5) directory-tree creation for the legacy architecture (`core/`, `services/voice|vision|hearing|automation|smart_home|presence/`, `models/`), (6) Vosk model download. **Five of the six are dead weight in the rebuild**: uv replaces (3) and (4); the rebuild has no `core/`/`services/`/`config/`/`models/` to create (5); Vosk is gone — faster-whisper handles ASR (6); Tesseract is gone — Claude vision handles screen reads. **Only the version-check + binary-probe surface (1) + (2) survives the port**, plus a thin wrapper that points at the right uv/Piper/NSSM follow-up commands. P5.3 ships a `sabrina-2/scripts/setup.py` that runs a *check-only-by-default* probe of the actual rebuild dependencies, prints a one-screen status report, and (only when `--apply` is passed) shells out to the existing `install-piper.ps1` / `install-nssm.ps1` and runs `uv sync`. The script is a pre-flight checklist for a fresh Windows clone, not an installer in the legacy sense — uv already does the heavy lifting.

## Proposed approach

- **(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**
  - `sabrina-2/scripts/setup.py` (new, ~250 lines) — a typer-shaped CLI with three subcommands: `check` (default; prints status report and exits 0 even if deps are missing), `apply` (the destructive path; shells to `install-piper.ps1`/`install-nssm.ps1`/`uv sync` only when explicitly invoked), and `report --json` (machine-readable status output for CI / future supervisor health checks). The `check` command is the sole load-bearing surface for daily-driver readiness; `apply` is convenience tooling. Probe targets, listed in priority order:
    - **Hard requirements:** Python `>=3.12,<3.13` (per `sabrina-2/pyproject.toml`'s `requires-python`); `uv` on PATH (`uv --version` exit 0); FFmpeg on PATH (`ffmpeg -version` exit 0 — required by faster-whisper for non-WAV inputs).
    - **Soft requirements (warn, don't fail):** Piper voice files present at `sabrina-2/voices/libritts_r-medium/` (download path is `install-piper.ps1`); NSSM binary present (only required when `[supervisor] mode = "service"`; the default `task_scheduler` mode does not need it); CUDA runtime detectable via `nvidia-smi` exit 0 (only matters for embedder + future torch paths; CPU fallback works).
    - **Out of scope:** Tesseract (vision uses Claude), Vosk (ASR uses faster-whisper), pulseaudio (Windows daily-driver), the legacy `requirements.txt` flow (replaced by uv).
  - `sabrina-2/scripts/__init__.py` (new, empty marker) — needed for `python -m compileall sabrina-2/scripts` to recognise the directory as a package; matches the pattern P5.5 set with `tests/test_utils/__init__.py`.
  - `sabrina-2/tests/test_setup_script.py` (new, ~150 lines) — unit tests for the dep-detection branches: each probe target has a fake-PATH test (binary-found case + binary-missing case + wrong-version case where applicable). Mock `shutil.which` / `subprocess.run` directly; do not actually invoke the real binaries (those are e2e gates handled by the (b)-half).
  - **No production-code changes.** No edits to `sabrina-2/src/sabrina/**`, no edits to `sabrina-2/sabrina.toml`, no edits to `sabrina-2/pyproject.toml`. The script is self-contained tooling.
- **(b)-half — `[windows-required]` (file separately if Eric wants a tracked promotion gate; no e2e is strictly required for the script's correctness):**
  - One real Windows session that runs `python sabrina-2/scripts/setup.py check` on a fresh clone of Eric's box and confirms the report matches reality (Python 3.12, uv installed, FFmpeg installed, Piper voices present, supervisor binary present per `[supervisor] mode`). The dry-run nature of `check` makes this gate cheap — no system mutation, no rollback risk.
  - One real Windows session that runs `python sabrina-2/scripts/setup.py apply` on a clean machine to verify the install-piper / install-nssm / `uv sync` shellouts compose without the manual ordering Eric currently runs from memory. This is genuinely Windows-required because PowerShell exec policy + admin elevation behaves differently per machine; can be folded into Eric's next fresh-box rebuild rather than blocking P5.3's Linux ship.
- **What's deliberately NOT in scope.**
  - Legacy directory creation (`core/`, `services/`, `config/`, `models/`, `data/captures/`, `logs/`). The rebuild's directory tree is `sabrina-2/src/sabrina/`, `sabrina-2/voices/`, `sabrina-2/tests/`, plus runtime-created `~/.sabrina/` for memory + budget logs. None require pre-creation.
  - Virtualenv creation. uv handles `.venv` automatically on `uv sync`.
  - `pip install -r requirements.txt`. The rebuild uses `pyproject.toml` + uv lockfile.
  - Vosk download, Tesseract install, the `--gpu`/`--full` flag splits, the `download_vosk.py`/`paddleocr` paths. All target legacy components.
  - Tesseract probing on Windows (the legacy script's `where tesseract` shellout). Vision runs through Claude; no OCR binary needed.
  - Bootstrapping uv itself. If `uv` is missing, `check` prints the install-uv command (`winget install --id=astral-sh.uv -e` or the `pip install uv` fallback) and exits non-zero on `apply`. We do not auto-install uv — chicken-and-egg, and Eric's machine already has it.

## Dependencies

- **`sabrina-2/pyproject.toml`** — source of truth for `requires-python`. The probe reads the constraint string and compares against `platform.python_version()`; do not hardcode `3.12` in the script (drift hazard).
- **`sabrina-2/install-piper.ps1`** + **`sabrina-2/install-nssm.ps1`** — the `apply` path shells to these. Both already exist in HEAD and are the canonical Piper / NSSM fetchers. The script does not duplicate their logic; it composes them.
- **`sabrina-2/sabrina.toml`** `[supervisor]` block — read by `check` to decide whether NSSM is a hard or soft requirement. `mode = "task_scheduler"` (the default, per the 2026-05-06 autostart research) makes NSSM optional; `mode = "service"` makes it required.
- **`sabrina-2/voices/`** — soft-required directory. The probe checks for the libritts_r-medium voice file presence; absence routes the user to `install-piper.ps1`.
- **CLAUDE.md "Partial-DoD tiers"** — defines the (a)/(b) seam. The `check` command is pure-Linux-runnable (it reads PATH and file presence, no Windows-specific surface); the `apply` command shells PowerShell, so its e2e is Windows-only. Tests cover both code paths under Linux by mocking subprocess.
- **P5.5 (pytest scaffolding)** — `[in-progress]` per QUEUE; once committed, the `tests/test_setup_script.py` author can use `make_fake_*` factories for any future composition with brain/listener probes. Not a hard dep — the test file uses standard `unittest.mock` patterns directly.
- **P5.4 (test fixtures)** — not a dep. The setup-script tests don't read JSON fixtures.

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable checklist)

**(a)-half DoD (Partial DoD, Linux-runnable, this spec's deliverable):**

1. Three files exist with the contents described above: `sabrina-2/scripts/setup.py`, `sabrina-2/scripts/__init__.py`, `sabrina-2/tests/test_setup_script.py`.
2. `python -m compileall sabrina-2/scripts sabrina-2/tests` is clean.
3. `python sabrina-2/scripts/setup.py check` exits 0 inside the Cowork Linux/3.10 sandbox and prints a status report. (Sandbox is Python 3.10, not 3.12 — the report will flag the Python-version mismatch as a "would fail on apply" warning, which is correct behaviour. This is not a bug; the test asserts the warning fires.) `python sabrina-2/scripts/setup.py check --json` exits 0 and emits parseable JSON.
4. `pytest sabrina-2/tests/test_setup_script.py -v` passes under Linux/3.10 (≥ 12 tests covering the probe targets above × found/missing/wrong-version branches; mock `shutil.which` and `subprocess.run` so no real binaries are invoked).
5. Pre-existing tests still pass: `pytest sabrina-2/tests/test_smoke.py sabrina-2/tests/test_shortcuts_yaml.py sabrina-2/tests/test_fixtures_load.py sabrina-2/tests/test_audio_utils.py sabrina-2/tests/test_utils/test_mocks.py` shows no regression vs. worker-11am 2026-05-05's baseline (the 4 ToolSpec round-trip tests at `test_smoke.py:1869-1965` + the 6 (a)-half wire-up tests + the four prior P5 ports).
6. `sabrina-2/scripts/setup.py apply` is a strict no-op when run without `--confirm` (prints what it *would* do and exits 0); only `setup.py apply --confirm` actually shells out. This is the safety latch the queue note flagged ("`--install` is a no-op-by-default dry-run unless `--apply` is also passed (safety)" — spec collapses this to one verb with a `--confirm` flag, simpler surface).
7. Diff is committed to `automation/<role>-2026-05-MM-Nam` with `Windows-pending: e2e` in the body. Body lists the (b)-half checklist verbatim from this spec's bullets above. Item moves to `[linux-shipped]` in QUEUE/DONE.

**(b)-half DoD (Full DoD per CLAUDE.md, optional gate — only required if Eric wants a tracked `[done]` promotion separate from the (a)-half):**

1. `python sabrina-2/scripts/setup.py check` on Eric's i7-13700K/4080/Win11 box reports green for all hard requirements (Python 3.12, uv, FFmpeg) and matches the actual configured state for soft requirements (Piper voices, supervisor binary).
2. `python sabrina-2/scripts/setup.py apply --confirm` on a fresh clone successfully composes `install-piper.ps1` + `install-nssm.ps1` + `uv sync` without manual ordering. (Acceptable to defer this gate to Eric's next fresh-box session — the script's correctness on a working install is verified by `check`.)
3. `pytest` passes on Windows.
4. (If Eric files a decision doc) `rebuild/decisions/0XX-setup-script.md` lands in decision-doc voice, references this spec, and notes the legacy → uv transition explicitly. Likely bundled into the P5.6 mini-decision-doc rather than its own.

## Open questions for NEEDS-INPUT

Two open questions worth raising before a Worker picks up the (a)-half. Filed today as `[from: spec-writer / 2026-05-06 06:50]` entries in NEEDS-INPUT.md.

- **Bootstrap-uv policy.** If the probe finds `uv` missing, should `apply --confirm` (a) refuse and print the install-uv instruction, (b) auto-install via `pip install uv` (assumes `pip` is present, which is not guaranteed on a fresh Win11 box), or (c) auto-install via `winget install --id=astral-sh.uv -e` (Windows-only, requires recent winget). **Spec recommends (a)** — chicken-and-egg avoidance, fail-loud over fail-magic. Worker can ship (a) without waiting; Eric can override before merge.
- **Whether to ship `apply` at all in the (a)-half.** A more conservative read of the queue note is "ship `check` only as the (a)-half; ship `apply` in a follow-up after the (b)-half Windows e2e proves out." This narrows the (a)-half to ~150 LOC and removes the only Windows-specific code path from the Linux ship. **Spec recommends shipping both** — `apply` is well-mocked under tests and the `--confirm` latch makes accidental destructive runs nearly impossible. But if Eric prefers the conservative split, the Worker can drop `apply` and re-spec it as P5.3b in a follow-up.

One non-blocking judgment call a Worker can decide in-line:

- **Subcommand vs. flags.** `setup.py check` / `setup.py apply` (two typer subcommands) vs. `setup.py --check` / `setup.py --apply` (flags on a single command). Spec picks subcommands because the surfaces diverge enough (`check` has `--json`, `apply` has `--confirm`) that flags would crowd. Worker can override; either reads cleanly.
