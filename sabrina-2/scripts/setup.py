"""Pre-flight dependency probe + apply hook for the rebuild.

Usage:

    python sabrina-2/scripts/setup.py check
    python sabrina-2/scripts/setup.py check --json
    python sabrina-2/scripts/setup.py apply           # dry-run, no mutation
    python sabrina-2/scripts/setup.py apply --confirm # actually shell out
    python sabrina-2/scripts/setup.py report --json   # alias of `check --json`

Replaces the legacy ``scripts/sabrina_install.py`` for the rebuild. The legacy
script created the legacy directory tree, downloaded Vosk, and probed
Tesseract — all dead weight. This one probes only what the rebuild's voice
loop actually needs (Python, uv, FFmpeg, Piper voices, supervisor binary,
CUDA), prints a one-screen status report, and only mutates the system when
``apply --confirm`` is invoked. ``check`` is the load-bearing surface for
daily-driver readiness; ``apply`` is convenience tooling that composes the
existing ``install-piper.ps1`` / ``install-nssm.ps1`` / ``uv sync``.

Bootstrap-uv policy (per spec-writer 2026-05-06 06:50 NEEDS-INPUT
recommendation (a)): if ``uv`` is missing, ``apply --confirm`` refuses
loudly and prints the install-uv command. We do not auto-install uv —
chicken-and-egg, and Eric's machine already has it.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Literal

import typer

# tomllib ships with Python 3.11+. Fall back to tomli for the Cowork
# Linux/3.10 sandbox so the (a)-half tests can run there.
try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised only on Python <3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - both unavailable
        tomllib = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Paths (resolved relative to this file so the script works from any cwd).
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # -> sabrina-2/
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SABRINA_TOML_PATH = REPO_ROOT / "sabrina.toml"
VOICES_DIR = REPO_ROOT / "voices"
INSTALL_PIPER_PS1 = REPO_ROOT / "install-piper.ps1"
INSTALL_NSSM_PS1 = REPO_ROOT / "install-nssm.ps1"
TOOLS_DIR = REPO_ROOT / "tools"
NSSM_LOCAL = TOOLS_DIR / "nssm" / "nssm.exe"
PIPER_LOCAL = TOOLS_DIR / "piper" / "piper.exe"

DEFAULT_VOICE_FILE = "en_US-libritts_r-medium.onnx"
DEFAULT_SUPERVISOR_MODE = "task_scheduler"

UV_INSTALL_HINT_WIN = "winget install --id=astral-sh.uv -e"
UV_INSTALL_HINT_UNIX = "curl -LsSf https://astral.sh/uv/install.sh | sh"


# ---------------------------------------------------------------------------
# Result type.
# ---------------------------------------------------------------------------

ProbeStatus = Literal["ok", "warn", "fail"]
ProbeCategory = Literal["hard", "soft"]


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of a single probe target."""

    name: str
    category: ProbeCategory
    status: ProbeStatus
    detail: str
    fix_hint: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Config readers (kept dependency-free so this script doesn't import sabrina).
# ---------------------------------------------------------------------------


def _read_requires_python(path: Path = PYPROJECT_PATH) -> str | None:
    """Return the ``requires-python`` constraint string, or None on failure."""
    if tomllib is None or not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):  # type: ignore[union-attr]
        return None
    project = data.get("project", {})
    value = project.get("requires-python")
    return value if isinstance(value, str) else None


def _read_supervisor_mode(path: Path = SABRINA_TOML_PATH) -> str:
    """Return the configured ``[supervisor] mode``, or the default."""
    if tomllib is None or not path.exists():
        return DEFAULT_SUPERVISOR_MODE
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):  # type: ignore[union-attr]
        return DEFAULT_SUPERVISOR_MODE
    mode = data.get("supervisor", {}).get("mode", DEFAULT_SUPERVISOR_MODE)
    return mode if isinstance(mode, str) else DEFAULT_SUPERVISOR_MODE


def _parse_min_python(constraint: str) -> tuple[int, int] | None:
    """Parse ``>=3.12`` (or ``==3.12``) into ``(3, 12)``. None if unparseable."""
    for pattern in (r">=\s*(\d+)\.(\d+)", r"==\s*(\d+)\.(\d+)"):
        match = re.search(pattern, constraint)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


# ---------------------------------------------------------------------------
# Probes. Each probe is pure: takes injected dependencies, returns a result.
# Tests patch ``shutil.which`` / ``subprocess.run`` directly.
# ---------------------------------------------------------------------------


def probe_python_version(
    *,
    constraint: str | None = None,
    actual: tuple[int, int, int] | None = None,
) -> ProbeResult:
    """Compare ``platform.python_version()`` against ``requires-python``."""
    constraint_str = constraint if constraint is not None else _read_requires_python()
    runtime = actual if actual is not None else sys.version_info[:3]
    runtime_str = "{}.{}.{}".format(*runtime)
    if constraint_str is None:
        return ProbeResult(
            name="Python version",
            category="hard",
            status="warn",
            detail=f"requires-python missing from pyproject.toml; runtime is {runtime_str}",
            fix_hint="restore [project] requires-python in sabrina-2/pyproject.toml",
        )
    minimum = _parse_min_python(constraint_str)
    if minimum is None:
        return ProbeResult(
            name="Python version",
            category="hard",
            status="warn",
            detail=f"could not parse requires-python {constraint_str!r}; runtime is {runtime_str}",
            fix_hint="",
        )
    if (runtime[0], runtime[1]) >= minimum:
        return ProbeResult(
            name="Python version",
            category="hard",
            status="ok",
            detail=f"{runtime_str} satisfies {constraint_str}",
        )
    return ProbeResult(
        name="Python version",
        category="hard",
        status="fail",
        detail=f"{runtime_str} does not satisfy {constraint_str}",
        fix_hint=f"install Python {minimum[0]}.{minimum[1]} (winget install Python.Python.{minimum[0]}.{minimum[1]} on Windows)",
    )


def _binary_version(
    name: str,
    flag: str,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> str:
    """Best-effort one-line version string for a binary on PATH."""
    run = runner if runner is not None else subprocess.run
    try:
        completed = run(
            [name, flag],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    output = (completed.stdout or completed.stderr or "").strip()
    return output.splitlines()[0] if output else ""


def probe_uv(
    *,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> ProbeResult:
    """uv on PATH (hard requirement; replaces virtualenv + pip flows)."""
    location = which("uv")
    if not location:
        hint = UV_INSTALL_HINT_WIN if platform.system() == "Windows" else UV_INSTALL_HINT_UNIX
        return ProbeResult(
            name="uv",
            category="hard",
            status="fail",
            detail="uv not on PATH",
            fix_hint=hint,
        )
    version = _binary_version("uv", "--version", runner=runner)
    return ProbeResult(
        name="uv",
        category="hard",
        status="ok",
        detail=f"{location} ({version})" if version else location,
    )


def probe_ffmpeg(
    *,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> ProbeResult:
    """FFmpeg on PATH (hard; faster-whisper needs it for non-WAV inputs)."""
    location = which("ffmpeg")
    if not location:
        return ProbeResult(
            name="FFmpeg",
            category="hard",
            status="fail",
            detail="ffmpeg not on PATH",
            fix_hint="winget install Gyan.FFmpeg (Windows) / apt install ffmpeg (Linux)",
        )
    version = _binary_version("ffmpeg", "-version", runner=runner)
    return ProbeResult(
        name="FFmpeg",
        category="hard",
        status="ok",
        detail=f"{location} ({version})" if version else location,
    )


def probe_piper_voices(*, voices_dir: Path = VOICES_DIR) -> ProbeResult:
    """At least one .onnx voice present; warn if the daily-driver default is missing."""
    if not voices_dir.exists():
        return ProbeResult(
            name="Piper voices",
            category="soft",
            status="warn",
            detail=f"{voices_dir} not found",
            fix_hint="run install-piper.ps1, then `uv run sabrina tts-download libritts_r-medium`",
        )
    onnx = sorted(voices_dir.glob("*.onnx"))
    if not onnx:
        return ProbeResult(
            name="Piper voices",
            category="soft",
            status="warn",
            detail=f"no .onnx voices in {voices_dir}",
            fix_hint="run `uv run sabrina tts-download libritts_r-medium`",
        )
    has_default = any(p.name == DEFAULT_VOICE_FILE for p in onnx)
    detail = f"{len(onnx)} voice(s) under {voices_dir}"
    if not has_default:
        return ProbeResult(
            name="Piper voices",
            category="soft",
            status="warn",
            detail=f"{detail}; daily-driver default {DEFAULT_VOICE_FILE} missing",
            fix_hint="run `uv run sabrina tts-download libritts_r-medium`",
        )
    return ProbeResult(name="Piper voices", category="soft", status="ok", detail=detail)


def probe_supervisor_binary(
    *,
    mode: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    nssm_local: Path = NSSM_LOCAL,
) -> ProbeResult:
    """NSSM presence (hard if mode=service, soft otherwise)."""
    resolved_mode = mode if mode is not None else _read_supervisor_mode()
    is_required = resolved_mode == "service"
    category: ProbeCategory = "hard" if is_required else "soft"
    if nssm_local.exists():
        return ProbeResult(
            name="Supervisor binary (nssm)",
            category=category,
            status="ok",
            detail=f"{nssm_local} (mode={resolved_mode})",
        )
    on_path = which("nssm")
    if on_path:
        return ProbeResult(
            name="Supervisor binary (nssm)",
            category=category,
            status="ok",
            detail=f"{on_path} (mode={resolved_mode})",
        )
    if not is_required:
        return ProbeResult(
            name="Supervisor binary (nssm)",
            category=category,
            status="ok",
            detail=f"not present (mode={resolved_mode}; only required when mode=service)",
        )
    return ProbeResult(
        name="Supervisor binary (nssm)",
        category=category,
        status="fail",
        detail=f"nssm not found (mode={resolved_mode} requires it)",
        fix_hint="run install-nssm.ps1",
    )


def probe_cuda(
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> ProbeResult:
    """nvidia-smi presence (soft; embedder + future torch paths benefit)."""
    location = which("nvidia-smi")
    if location:
        return ProbeResult(
            name="CUDA runtime",
            category="soft",
            status="ok",
            detail=location,
        )
    return ProbeResult(
        name="CUDA runtime",
        category="soft",
        status="warn",
        detail="nvidia-smi not on PATH; CPU fallback paths still work",
        fix_hint="install NVIDIA driver if a GPU is attached",
    )


def collect_probes(
    *,
    constraint: str | None = None,
    actual_python: tuple[int, int, int] | None = None,
    mode: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
    voices_dir: Path = VOICES_DIR,
    nssm_local: Path = NSSM_LOCAL,
) -> list[ProbeResult]:
    """Run all probes and return results in display order."""
    return [
        probe_python_version(constraint=constraint, actual=actual_python),
        probe_uv(which=which, runner=runner),
        probe_ffmpeg(which=which, runner=runner),
        probe_piper_voices(voices_dir=voices_dir),
        probe_supervisor_binary(mode=mode, which=which, nssm_local=nssm_local),
        probe_cuda(which=which),
    ]


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------

_STATUS_GLYPH = {"ok": "[OK]  ", "warn": "[WARN]", "fail": "[FAIL]"}


def render_text_report(results: list[ProbeResult]) -> str:
    """Format the probe results as a one-screen status table."""
    lines = ["Sabrina pre-flight check", "=" * 40]
    for r in results:
        glyph = _STATUS_GLYPH[r.status]
        lines.append(f"{glyph} {r.name} ({r.category}): {r.detail}")
        if r.fix_hint and r.status != "ok":
            lines.append(f"        -> {r.fix_hint}")
    failures = sum(1 for r in results if r.status == "fail" and r.category == "hard")
    warnings = sum(1 for r in results if r.status in ("warn", "fail") and r.category == "soft")
    soft_fails = sum(1 for r in results if r.status == "fail" and r.category == "soft")
    lines.append("")
    lines.append(
        f"summary: {failures} hard fail(s), {warnings + soft_fails} soft warning(s)/fail(s)"
    )
    return "\n".join(lines)


def render_json_report(results: list[ProbeResult]) -> str:
    """Format the probe results as machine-readable JSON."""
    payload = {
        "results": [r.as_dict() for r in results],
        "hard_fail_count": sum(1 for r in results if r.status == "fail" and r.category == "hard"),
        "platform": platform.system(),
        "python": "{}.{}.{}".format(*sys.version_info[:3]),
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# Apply path. ``--confirm`` is the destructive latch. Without it, this prints
# what it would do and exits 0. With it, shells out to the existing scripts.
# ---------------------------------------------------------------------------


def _plan_apply(results: list[ProbeResult]) -> list[tuple[str, list[str]]]:
    """Return ordered (label, command) pairs the apply path would run."""
    plan: list[tuple[str, list[str]]] = []
    by_name = {r.name: r for r in results}
    is_windows = platform.system() == "Windows"

    if by_name.get("Piper voices", None) and by_name["Piper voices"].status != "ok" and is_windows:
        if INSTALL_PIPER_PS1.exists():
            plan.append(
                (
                    "install Piper",
                    [
                        "powershell",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(INSTALL_PIPER_PS1),
                    ],
                )
            )

    nssm_probe = by_name.get("Supervisor binary (nssm)")
    if nssm_probe and nssm_probe.status == "fail" and is_windows:
        if INSTALL_NSSM_PS1.exists():
            plan.append(
                (
                    "install NSSM",
                    [
                        "powershell",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(INSTALL_NSSM_PS1),
                    ],
                )
            )

    plan.append(("uv sync", ["uv", "sync"]))
    return plan


def run_apply(
    *,
    results: list[ProbeResult],
    confirm: bool,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
    out: Callable[[str], None] = print,
) -> int:
    """Execute (or dry-run) the apply plan. Return process exit code."""
    uv_probe = next((r for r in results if r.name == "uv"), None)
    if uv_probe is not None and uv_probe.status == "fail":
        out("uv is missing — refusing to proceed (per spec NEEDS-INPUT (a)).")
        out(f"install uv first: {uv_probe.fix_hint}")
        return 2

    plan = _plan_apply(results)
    if not plan:
        out("apply: nothing to do.")
        return 0
    out("apply plan:")
    for label, cmd in plan:
        out(f"  - {label}: {' '.join(cmd)}")
    if not confirm:
        out("")
        out("dry-run only. Re-run with --confirm to actually execute the plan.")
        return 0

    run = runner if runner is not None else subprocess.run
    for label, cmd in plan:
        out(f"running: {label} ...")
        try:
            completed = run(cmd, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            out(f"  failed to launch: {exc}")
            return 1
        rc = getattr(completed, "returncode", 0) or 0
        if rc != 0:
            out(f"  exit {rc} -- aborting plan")
            return rc
    out("apply: complete.")
    return 0


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="sabrina-setup",
    help="Pre-flight dependency probe + apply hook for the rebuild.",
    no_args_is_help=True,
    add_completion=False,
)


def _emit_report(json_output: bool) -> int:
    results = collect_probes()
    if json_output:
        typer.echo(render_json_report(results))
    else:
        typer.echo(render_text_report(results))
    # `check` and `report` exit 0 even on hard failures so they remain
    # composable in CI / supervisor health checks. Callers wanting an
    # exit-code gate should run `apply` (which refuses without uv) or
    # parse the JSON report's hard_fail_count.
    return 0


@app.command()
def check(
    json_output: bool = typer.Option(
        False, "--json", help="Emit JSON instead of the text report."
    ),
) -> None:
    """Probe deps and print a status report (read-only, exits 0)."""
    raise typer.Exit(_emit_report(json_output))


@app.command()
def report(
    json_output: bool = typer.Option(True, "--json/--text", help="Output format."),
) -> None:
    """Alias of ``check`` defaulting to JSON for CI consumers."""
    raise typer.Exit(_emit_report(json_output))


@app.command()
def apply(
    confirm: bool = typer.Option(
        False, "--confirm", help="Actually execute the plan (default: dry-run only)."
    ),
) -> None:
    """Compose install-piper / install-nssm / uv sync (Windows-only mutators)."""
    results = collect_probes()
    raise typer.Exit(run_apply(results=results, confirm=confirm))


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    app()
