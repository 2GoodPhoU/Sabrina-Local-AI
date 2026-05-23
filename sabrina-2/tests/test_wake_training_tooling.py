"""Tests for the wake-training wrapper scripts (P2.2 (a)-half).

Pure-Linux tests with mocked openwakeword / piper-sample-generator. They
exercise the orchestration the wrapper scripts provide:

- ``synthesize_positives.py --dry-run`` prints the expected ``python -m
  piper_sample_generator ...`` argv and exits 0 without invoking subprocess.
- ``acceptance_check`` rejects sub-threshold recall + sub-threshold
  false-accept-rate metrics.
- ``train_hey_sabrina.main`` raises ``RuntimeError`` when the trained
  model fails the acceptance check.
- ``README.md`` references the canonical paths the runtime expects.

The tests mock ``train_hey_sabrina.train_model`` rather than letting the
real ``openwakeword.train`` import fire — the sandbox does not have
``openwakeword[training]`` installed and the heavy training path is
explicitly out-of-scope per the spec.
"""

from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

WAKE_TRAINING_DIR = (
    Path(__file__).resolve().parent.parent / "tools" / "wake-training"
)


def _import_module(name: str, file_path: Path):
    """Load a module from an arbitrary file path.

    The wake-training scripts live under ``sabrina-2/tools/wake-training/``
    which is not a Python package on the import path. We load the modules
    by file location so the tests don't depend on packaging.
    """

    spec = importlib.util.spec_from_file_location(name, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def synthesize_module():
    return _import_module(
        "wake_synthesize_positives",
        WAKE_TRAINING_DIR / "synthesize_positives.py",
    )


@pytest.fixture(scope="module")
def train_module():
    return _import_module(
        "wake_train_hey_sabrina",
        WAKE_TRAINING_DIR / "train_hey_sabrina.py",
    )


# ---------------------------------------------------------------------------
# synthesize_positives.py
# ---------------------------------------------------------------------------


def test_synthesize_build_command_includes_phrase_and_seed(synthesize_module):
    cmd = synthesize_module.build_command(
        phrase="Hey Sabrina",
        output_dir=Path("/tmp/positive"),
        max_samples=4000,
        seed=1337,
    )
    assert "piper_sample_generator" in cmd
    assert "Hey Sabrina" in cmd
    assert "--max-samples" in cmd
    assert "4000" in cmd
    assert "--seed" in cmd
    assert "1337" in cmd


def test_synthesize_dry_run_prints_command_and_exits_zero(synthesize_module):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = synthesize_module.main(["--dry-run"])
    assert rc == 0
    output = buf.getvalue()
    assert "piper_sample_generator" in output
    assert "Hey Sabrina" in output
    assert "--max-samples" in output


def test_synthesize_dry_run_does_not_invoke_subprocess(synthesize_module):
    """``--dry-run`` MUST NOT shell out — its purpose is preview-only."""
    with patch.object(synthesize_module.subprocess, "run") as run_mock:
        rc = synthesize_module.main(["--dry-run"])
    assert rc == 0
    run_mock.assert_not_called()


def test_synthesize_overrides_max_samples_and_seed(synthesize_module):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = synthesize_module.main(
            ["--dry-run", "--max-samples", "10", "--seed", "42"]
        )
    output = buf.getvalue()
    assert rc == 0
    assert " 10 " in output  # surrounded by spaces in the rendered argv
    assert " 42" in output


# ---------------------------------------------------------------------------
# train_hey_sabrina.py — acceptance check
# ---------------------------------------------------------------------------


def test_acceptance_check_passes_at_threshold(train_module):
    result = train_module.TrainingResult(
        model_path=Path("/tmp/hey_sabrina.onnx"),
        recall=0.5,
        false_accepts_per_hour=0.2,
    )
    ok, _reason = train_module.acceptance_check(result)
    assert ok is True


def test_acceptance_check_rejects_low_recall(train_module):
    result = train_module.TrainingResult(
        model_path=Path("/tmp/hey_sabrina.onnx"),
        recall=0.1,
        false_accepts_per_hour=0.0,
    )
    ok, reason = train_module.acceptance_check(result)
    assert ok is False
    assert "recall" in reason


def test_acceptance_check_rejects_high_false_accepts(train_module):
    result = train_module.TrainingResult(
        model_path=Path("/tmp/hey_sabrina.onnx"),
        recall=1.0,
        false_accepts_per_hour=5.0,
    )
    ok, reason = train_module.acceptance_check(result)
    assert ok is False
    assert "false-accepts" in reason


def test_train_main_raises_when_model_fails_acceptance(train_module, tmp_path):
    """``train_hey_sabrina.main`` MUST fail loud on a sub-threshold model."""
    positives = tmp_path / "positive"
    positives.mkdir()
    output = tmp_path / "output"
    bad_result = train_module.TrainingResult(
        model_path=output / "hey_sabrina.onnx",
        recall=0.05,
        false_accepts_per_hour=0.0,
    )
    with patch.object(train_module, "train_model", return_value=bad_result):
        with pytest.raises(RuntimeError) as excinfo:
            train_module.main(
                [
                    "--positives-dir",
                    str(positives),
                    "--output-dir",
                    str(output),
                ]
            )
    assert "acceptance" in str(excinfo.value).lower()


def test_train_main_no_strict_does_not_raise_on_subthreshold(train_module, tmp_path):
    """``--no-strict`` is a debugging escape hatch; document by test."""
    positives = tmp_path / "positive"
    positives.mkdir()
    output = tmp_path / "output"
    bad_result = train_module.TrainingResult(
        model_path=output / "hey_sabrina.onnx",
        recall=0.05,
        false_accepts_per_hour=0.0,
    )
    with patch.object(train_module, "train_model", return_value=bad_result):
        rc = train_module.main(
            [
                "--no-strict",
                "--positives-dir",
                str(positives),
                "--output-dir",
                str(output),
            ]
        )
    assert rc == 0


def test_train_main_returns_2_when_positives_missing(train_module, tmp_path):
    """If the operator forgets ``synthesize_positives.py``, fail with rc=2."""
    missing = tmp_path / "does_not_exist"
    rc = train_module.main(
        [
            "--positives-dir",
            str(missing),
        ]
    )
    assert rc == 2


# ---------------------------------------------------------------------------
# README.md path references
# ---------------------------------------------------------------------------


def test_readme_references_canonical_paths():
    readme = (WAKE_TRAINING_DIR / "README.md").read_text(encoding="utf-8")
    assert "tools/wake-training/data/positive" in readme
    assert "tools/wake-training/output/hey_sabrina.onnx" in readme
    assert "models/openwakeword/hey_sabrina.onnx" in readme
    assert "[wake_word].enabled" in readme
    assert "P2.3" in readme  # forward-pointer to the validation gate


def test_requirements_file_lists_training_extras():
    text = (WAKE_TRAINING_DIR / "requirements-training.txt").read_text(
        encoding="utf-8"
    )
    assert "openwakeword[training]" in text
    assert "piper-sample-generator" in text
    assert "audiomentations" in text
    assert "soundfile" in text
