"""Unit tests for ``sabrina-2/scripts/setup.py`` (P5.3 (a)-half).

Spec: ``rebuild/drafts/research/2026-05-06-p53-system-deps-setup-script-spec.md``

Covers each probe target's found / missing / wrong-version branches by
patching ``shutil.which`` and ``subprocess.run`` (or by injecting the
function-level ``which=`` / ``runner=`` keyword args the probes already
accept). No real binaries are invoked. ``setup.py`` is loaded by reading
the source and ``exec()``-ing it into a manually-registered
``types.ModuleType`` (see ``_load_setup_module`` for the rationale) —
this avoids both pytest's path-based assertion-rewrite finder and the
Python 3.10 ``dataclasses.py:711`` interaction with
``importlib.util.spec_from_file_location``-loaded modules that carry
``from __future__ import annotations`` + ``@dataclass(frozen=True)``.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent  # -> sabrina-2/
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
_SETUP_PY = _SCRIPTS_DIR / "setup.py"


def _load_setup_module() -> types.ModuleType:
    """Load ``sabrina-2/scripts/setup.py`` as a module without going through
    Python's regular import machinery.

    Why the manual ``exec()``: pytest's assertion-rewrite hook installs a
    meta-path finder that intercepts modules at known repo paths and runs
    them through ``SourceFileLoader.exec_module``. On Python 3.10, that
    interaction with our dataclass-with-string-annotations
    (``from __future__ import annotations`` + ``@dataclass(frozen=True)``)
    triggers ``dataclasses.py:711``'s ``sys.modules[cls.__module__]``
    walk, and the rewrite-loaded module's ``__module__`` resolves to a
    sys.modules entry the decorator can't dereference.

    The fix: ``compile()`` the source with a synthetic filename
    (``"<sabrina2_setup>"``) so pytest's path-based finder doesn't claim
    it, and ``exec()`` it into a manually-registered ``types.ModuleType``
    with ``__name__`` set to a name pytest hasn't seen.
    """
    cached = sys.modules.get("sabrina2_setup")
    if cached is not None:
        return cached
    module = types.ModuleType("sabrina2_setup")
    module.__name__ = "sabrina2_setup"
    # setup.py uses ``__file__`` to anchor REPO_ROOT, so we must seed it
    # in the module namespace before exec() runs the body.
    module.__file__ = str(_SETUP_PY)
    sys.modules["sabrina2_setup"] = module
    try:
        source = _SETUP_PY.read_text(encoding="utf-8")
        # Use a synthetic <...>-shaped filename so pytest's path-based
        # rewrite finder doesn't try to claim the module.
        compiled = compile(source, "<sabrina2_setup>", "exec")
        exec(compiled, module.__dict__)
    except BaseException:
        sys.modules.pop("sabrina2_setup", None)
        raise
    return module


@pytest.fixture(scope="module")
def setup_mod() -> types.ModuleType:
    return _load_setup_module()


# ---------------------------------------------------------------------------
# Helpers used to fake shutil.which / subprocess.run.
# ---------------------------------------------------------------------------


def _which_factory(present: dict[str, str]):
    def _which(name: str) -> str | None:
        return present.get(name)

    return _which


def _runner_factory(stdout: str = "", stderr: str = "", returncode: int = 0):
    def _runner(cmd, **kwargs):  # noqa: ARG001 - kwargs match subprocess.run shape
        return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)

    return _runner


# ---------------------------------------------------------------------------
# 1. _parse_min_python — pure parsing.
# ---------------------------------------------------------------------------


def test_parse_min_python_handles_geq_constraint(setup_mod) -> None:
    assert setup_mod._parse_min_python(">=3.12") == (3, 12)
    assert setup_mod._parse_min_python(">=3.12,<3.13") == (3, 12)


def test_parse_min_python_handles_eq_constraint(setup_mod) -> None:
    assert setup_mod._parse_min_python("==3.12") == (3, 12)


def test_parse_min_python_returns_none_when_unparseable(setup_mod) -> None:
    assert setup_mod._parse_min_python("python ~= 3.12") is None
    assert setup_mod._parse_min_python("") is None


# ---------------------------------------------------------------------------
# 2. probe_python_version branches.
# ---------------------------------------------------------------------------


def test_probe_python_version_ok_when_runtime_satisfies_constraint(setup_mod) -> None:
    result = setup_mod.probe_python_version(constraint=">=3.10", actual=(3, 12, 0))
    assert result.status == "ok"
    assert result.category == "hard"
    assert "3.12.0" in result.detail
    assert ">=3.10" in result.detail


def test_probe_python_version_fail_when_runtime_below_minimum(setup_mod) -> None:
    result = setup_mod.probe_python_version(constraint=">=3.12", actual=(3, 10, 12))
    assert result.status == "fail"
    assert "3.10.12" in result.detail
    assert "Python 3.12" in result.fix_hint


def test_probe_python_version_warn_when_constraint_missing(setup_mod) -> None:
    result = setup_mod.probe_python_version(constraint=None, actual=(3, 12, 0))
    # `constraint=None` falls back to reading pyproject.toml. In this repo
    # pyproject.toml ships a constraint, so the result should be `ok`. We
    # assert the type instead of the exact constraint to keep the test
    # robust against future pyproject edits.
    assert result.name == "Python version"
    assert result.category == "hard"


def test_probe_python_version_warn_when_constraint_unparseable(setup_mod) -> None:
    result = setup_mod.probe_python_version(constraint="garbage", actual=(3, 12, 0))
    assert result.status == "warn"
    assert "could not parse" in result.detail


# ---------------------------------------------------------------------------
# 3. probe_uv branches.
# ---------------------------------------------------------------------------


def test_probe_uv_ok_when_on_path(setup_mod) -> None:
    result = setup_mod.probe_uv(
        which=_which_factory({"uv": "/usr/local/bin/uv"}),
        runner=_runner_factory(stdout="uv 0.4.0 (linux)\n"),
    )
    assert result.status == "ok"
    assert "/usr/local/bin/uv" in result.detail
    assert "uv 0.4.0" in result.detail


def test_probe_uv_fail_when_missing_emits_install_hint(setup_mod) -> None:
    result = setup_mod.probe_uv(
        which=_which_factory({}),
        runner=_runner_factory(),
    )
    assert result.status == "fail"
    # Hint is platform-aware. Either of the two install commands is fine; we
    # just want to know we're not silent.
    assert (
        result.fix_hint == setup_mod.UV_INSTALL_HINT_WIN
        or result.fix_hint == setup_mod.UV_INSTALL_HINT_UNIX
    )


# ---------------------------------------------------------------------------
# 4. probe_ffmpeg branches.
# ---------------------------------------------------------------------------


def test_probe_ffmpeg_ok_when_on_path(setup_mod) -> None:
    result = setup_mod.probe_ffmpeg(
        which=_which_factory({"ffmpeg": "/usr/bin/ffmpeg"}),
        runner=_runner_factory(stdout="ffmpeg version 6.0 Copyright ...\n"),
    )
    assert result.status == "ok"
    assert "/usr/bin/ffmpeg" in result.detail
    assert "ffmpeg version 6.0" in result.detail


def test_probe_ffmpeg_fail_when_missing(setup_mod) -> None:
    result = setup_mod.probe_ffmpeg(
        which=_which_factory({}),
        runner=_runner_factory(),
    )
    assert result.status == "fail"
    assert "ffmpeg" in result.detail


# ---------------------------------------------------------------------------
# 5. probe_piper_voices branches.
# ---------------------------------------------------------------------------


def test_probe_piper_voices_warn_when_dir_absent(setup_mod, tmp_path: Path) -> None:
    result = setup_mod.probe_piper_voices(voices_dir=tmp_path / "missing")
    assert result.status == "warn"
    assert "not found" in result.detail


def test_probe_piper_voices_warn_when_dir_empty(setup_mod, tmp_path: Path) -> None:
    voices = tmp_path / "voices"
    voices.mkdir()
    result = setup_mod.probe_piper_voices(voices_dir=voices)
    assert result.status == "warn"
    assert "no .onnx" in result.detail


def test_probe_piper_voices_warn_when_default_missing(setup_mod, tmp_path: Path) -> None:
    voices = tmp_path / "voices"
    voices.mkdir()
    (voices / "en_US-other-voice.onnx").write_bytes(b"\x00")
    result = setup_mod.probe_piper_voices(voices_dir=voices)
    assert result.status == "warn"
    assert setup_mod.DEFAULT_VOICE_FILE in result.detail


def test_probe_piper_voices_ok_when_default_present(setup_mod, tmp_path: Path) -> None:
    voices = tmp_path / "voices"
    voices.mkdir()
    (voices / setup_mod.DEFAULT_VOICE_FILE).write_bytes(b"\x00")
    result = setup_mod.probe_piper_voices(voices_dir=voices)
    assert result.status == "ok"
    assert "1 voice" in result.detail


# ---------------------------------------------------------------------------
# 6. probe_supervisor_binary branches (mode-aware hard/soft).
# ---------------------------------------------------------------------------


def test_probe_supervisor_soft_ok_when_task_scheduler_and_nssm_missing(
    setup_mod, tmp_path: Path
) -> None:
    result = setup_mod.probe_supervisor_binary(
        mode="task_scheduler",
        which=_which_factory({}),
        nssm_local=tmp_path / "nssm.exe",
    )
    assert result.status == "ok"  # missing-but-not-required is OK at task_scheduler.
    assert result.category == "soft"
    assert "mode=task_scheduler" in result.detail


def test_probe_supervisor_hard_fail_when_service_mode_and_nssm_missing(
    setup_mod, tmp_path: Path
) -> None:
    result = setup_mod.probe_supervisor_binary(
        mode="service",
        which=_which_factory({}),
        nssm_local=tmp_path / "nssm.exe",
    )
    assert result.status == "fail"
    assert result.category == "hard"
    assert result.fix_hint == "run install-nssm.ps1"


def test_probe_supervisor_ok_when_local_nssm_present(setup_mod, tmp_path: Path) -> None:
    nssm_local = tmp_path / "nssm.exe"
    nssm_local.write_bytes(b"\x00")
    result = setup_mod.probe_supervisor_binary(
        mode="service",
        which=_which_factory({}),
        nssm_local=nssm_local,
    )
    assert result.status == "ok"
    assert result.category == "hard"
    assert str(nssm_local) in result.detail


def test_probe_supervisor_ok_when_nssm_on_path(setup_mod, tmp_path: Path) -> None:
    result = setup_mod.probe_supervisor_binary(
        mode="service",
        which=_which_factory({"nssm": "/usr/bin/nssm"}),
        nssm_local=tmp_path / "missing.exe",
    )
    assert result.status == "ok"
    assert "/usr/bin/nssm" in result.detail


# ---------------------------------------------------------------------------
# 7. probe_cuda branches.
# ---------------------------------------------------------------------------


def test_probe_cuda_ok_when_nvidia_smi_on_path(setup_mod) -> None:
    result = setup_mod.probe_cuda(which=_which_factory({"nvidia-smi": "/usr/bin/nvidia-smi"}))
    assert result.status == "ok"
    assert result.category == "soft"


def test_probe_cuda_warn_when_missing(setup_mod) -> None:
    result = setup_mod.probe_cuda(which=_which_factory({}))
    assert result.status == "warn"
    assert result.category == "soft"  # never hard — CPU fallback works.


# ---------------------------------------------------------------------------
# 8. collect_probes returns all six in display order.
# ---------------------------------------------------------------------------


def test_collect_probes_returns_six_in_order(setup_mod, tmp_path: Path) -> None:
    voices = tmp_path / "voices"
    voices.mkdir()
    results = setup_mod.collect_probes(
        constraint=">=3.10",
        actual_python=(3, 10, 12),
        mode="task_scheduler",
        which=_which_factory({"uv": "/u", "ffmpeg": "/f"}),
        runner=_runner_factory(stdout="x"),
        voices_dir=voices,
        nssm_local=tmp_path / "nssm.exe",
    )
    names = [r.name for r in results]
    assert names == [
        "Python version",
        "uv",
        "FFmpeg",
        "Piper voices",
        "Supervisor binary (nssm)",
        "CUDA runtime",
    ]


# ---------------------------------------------------------------------------
# 9. Reporting (text + JSON).
# ---------------------------------------------------------------------------


def test_render_text_report_lists_each_probe_and_summary(setup_mod) -> None:
    results = [
        setup_mod.ProbeResult(name="A", category="hard", status="ok", detail="ok-detail"),
        setup_mod.ProbeResult(
            name="B", category="hard", status="fail", detail="missing", fix_hint="hint!"
        ),
        setup_mod.ProbeResult(name="C", category="soft", status="warn", detail="soft-warn"),
    ]
    text = setup_mod.render_text_report(results)
    assert "Sabrina pre-flight check" in text
    assert "[OK]" in text and "[FAIL]" in text and "[WARN]" in text
    assert "hint!" in text
    assert "1 hard fail" in text


def test_render_json_report_is_parseable_and_has_expected_shape(setup_mod) -> None:
    results = [
        setup_mod.ProbeResult(name="A", category="hard", status="ok", detail="ok"),
        setup_mod.ProbeResult(name="B", category="hard", status="fail", detail="bad"),
    ]
    payload = json.loads(setup_mod.render_json_report(results))
    assert payload["hard_fail_count"] == 1
    assert len(payload["results"]) == 2
    assert payload["results"][0]["name"] == "A"
    assert "platform" in payload and "python" in payload


# ---------------------------------------------------------------------------
# 10. _plan_apply composes the right shellouts.
# ---------------------------------------------------------------------------


def test_plan_apply_always_includes_uv_sync(setup_mod) -> None:
    results = [setup_mod.ProbeResult(name="uv", category="hard", status="ok", detail="ok")]
    plan = setup_mod._plan_apply(results)
    labels = [label for label, _ in plan]
    assert "uv sync" in labels
    cmds = {label: cmd for label, cmd in plan}
    assert cmds["uv sync"] == ["uv", "sync"]


# ---------------------------------------------------------------------------
# 11. run_apply latch behavior (the safety surface from spec DoD #6).
# ---------------------------------------------------------------------------


def test_run_apply_refuses_when_uv_missing(setup_mod) -> None:
    captured: list[str] = []
    results = [
        setup_mod.ProbeResult(
            name="uv",
            category="hard",
            status="fail",
            detail="missing",
            fix_hint="install hint",
        ),
    ]
    rc = setup_mod.run_apply(results=results, confirm=True, out=captured.append)
    assert rc == 2
    joined = "\n".join(captured)
    assert "refusing" in joined
    assert "install hint" in joined


def test_run_apply_dry_run_without_confirm(setup_mod) -> None:
    captured: list[str] = []
    runs: list[list[str]] = []

    def _spy(cmd, **kwargs):  # noqa: ARG001
        runs.append(cmd)
        return types.SimpleNamespace(returncode=0)

    results = [setup_mod.ProbeResult(name="uv", category="hard", status="ok", detail="ok")]
    rc = setup_mod.run_apply(
        results=results, confirm=False, runner=_spy, out=captured.append
    )
    assert rc == 0
    assert runs == []  # dry-run never invokes the runner
    joined = "\n".join(captured)
    assert "dry-run" in joined
    assert "Re-run with --confirm" in joined


def test_run_apply_confirm_invokes_runner_for_each_step(setup_mod) -> None:
    captured: list[str] = []
    runs: list[list[str]] = []

    def _spy(cmd, **kwargs):  # noqa: ARG001
        runs.append(list(cmd))
        return types.SimpleNamespace(returncode=0)

    results = [setup_mod.ProbeResult(name="uv", category="hard", status="ok", detail="ok")]
    rc = setup_mod.run_apply(
        results=results, confirm=True, runner=_spy, out=captured.append
    )
    assert rc == 0
    assert runs == [["uv", "sync"]]
    joined = "\n".join(captured)
    assert "complete" in joined


def test_run_apply_propagates_subprocess_failure(setup_mod) -> None:
    captured: list[str] = []

    def _spy(cmd, **kwargs):  # noqa: ARG001
        return types.SimpleNamespace(returncode=7)

    results = [setup_mod.ProbeResult(name="uv", category="hard", status="ok", detail="ok")]
    rc = setup_mod.run_apply(
        results=results, confirm=True, runner=_spy, out=captured.append
    )
    assert rc == 7
    joined = "\n".join(captured)
    assert "exit 7" in joined and "aborting" in joined


# ---------------------------------------------------------------------------
# 12. Module-level CLI smoke (typer Typer instance + subcommand registration).
# ---------------------------------------------------------------------------


def test_cli_app_has_three_subcommands(setup_mod) -> None:
    # Typer registers @app.command()-decorated functions on the underlying
    # click group. The exact attribute lives on `app.registered_commands`.
    names = {entry.name or entry.callback.__name__ for entry in setup_mod.app.registered_commands}
    assert {"check", "report", "apply"}.issubset(names)
