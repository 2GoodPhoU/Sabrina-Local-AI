"""Pytest scaffolding for the Sabrina rebuild.

Ports the legacy `tests/conftest.py` primitives (path/temp/time fixtures, the
`pytest_configure` marker block, the `requires_gpu` skip-on-no-CUDA branch)
and drops the legacy abstractions the rebuild rejected (mock_event_bus,
mock_state_machine, Mock*Service factories, sabrina_core).

Marker list narrowed to the two that map onto the rebuild's actual posture:

* `requires_gpu`     -- skipped when torch.cuda is unavailable.
* `requires_windows` -- skipped when sys.platform != "win32". This is the
  marker every "Partial-DoD blocked, Windows-side e2e" path tags. It maps
  1:1 to the partial-DoD framing in CLAUDE.md ("touches voice-loop runtime,
  audio I/O, clipboard, mss/pynput/pyperclip paths, or pywin32-only
  modules").

Spec: rebuild/drafts/research/2026-05-05-p55-pytest-scaffolding-port-spec.md
"""

from __future__ import annotations

import sys
import tempfile
import time
import types
from pathlib import Path

import pytest

# Make `sabrina` importable from `src/sabrina` without an editable install.
# Mirrors the legacy `ensure_project_root_in_sys_path()` trick but targets
# the rebuild's src-layout root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC = _PROJECT_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# Sandbox guard: `sabrina.listener.__init__` eagerly imports `sounddevice`,
# which fails on Linux CI / Cowork sandboxes that don't have PortAudio. The
# real path is fine on Windows + Eric's daily-driver box; this stub is a
# Linux-only workaround so test collection survives without PortAudio. Real
# audio is exercised under the `requires_windows` marker, which skips on
# non-Windows platforms -- no audio behavior is mocked away by this stub.
def _install_sounddevice_stub_if_unavailable() -> None:
    try:
        import sounddevice  # noqa: F401
        return
    except (OSError, ImportError):
        pass

    stub = types.ModuleType("sounddevice")

    class _StubError(Exception):
        """Stub error class -- never raised in practice (no real audio in tests)."""

    stub.PortAudioError = _StubError  # type: ignore[attr-defined]
    stub.InputStream = None  # type: ignore[attr-defined]
    stub.OutputStream = None  # type: ignore[attr-defined]
    stub.RawInputStream = None  # type: ignore[attr-defined]
    stub.RawOutputStream = None  # type: ignore[attr-defined]
    stub.query_devices = lambda *a, **kw: []  # type: ignore[attr-defined]
    stub.default = types.SimpleNamespace(  # type: ignore[attr-defined]
        device=(None, None), samplerate=None, channels=(1, 1)
    )
    sys.modules["sounddevice"] = stub


_install_sounddevice_stub_if_unavailable()


# --- Path / temp / time fixtures (ported primitives) ---


@pytest.fixture
def project_root() -> Path:
    """Absolute path to the rebuild root (`sabrina-2/`)."""
    from tests.test_utils.paths import get_project_root

    return get_project_root()


@pytest.fixture
def test_dir() -> Path:
    """Absolute path to the test directory (`sabrina-2/tests/`)."""
    from tests.test_utils.paths import get_test_dir

    return get_test_dir()


@pytest.fixture
def data_dir() -> Path:
    """Absolute path to the test data directory (`sabrina-2/tests/data/`).

    Resolves to the directory P5.4 populates with `conversation_history.json`
    + `default_memory.json`. Without P5.4, the fixture still resolves but the
    directory may be empty.
    """
    from tests.test_utils.paths import get_test_data_dir

    return get_test_data_dir()


@pytest.fixture
def temp_dir():
    """Fresh temporary directory for the test; cleaned up automatically."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def current_time() -> float:
    """Wall-clock time at fixture-setup time. Useful for duration assertions."""
    return time.time()


# --- Pytest configuration ---


def pytest_configure(config):
    """Register the two markers the rebuild's partial-DoD posture needs."""
    config.addinivalue_line(
        "markers",
        "requires_gpu: mark tests that require a CUDA-capable GPU "
        "(skipped when torch is missing or torch.cuda is unavailable)",
    )
    config.addinivalue_line(
        "markers",
        "requires_windows: mark tests that require Windows-only deps "
        "(audio/clipboard/pywin32/etc.); skipped on non-Windows platforms",
    )


def pytest_collection_modifyitems(config, items):
    """Apply skip markers based on the run environment.

    `requires_gpu`     -- skip when torch is missing or no CUDA device.
    `requires_windows` -- skip when sys.platform != "win32".
    """
    no_gpu_marker = pytest.mark.skip(reason="No CUDA-capable GPU available")
    no_windows_marker = pytest.mark.skip(reason="Test requires Windows")

    for item in items:
        if "requires_gpu" in item.keywords:
            try:
                import torch

                if not torch.cuda.is_available():
                    item.add_marker(no_gpu_marker)
            except ImportError:
                item.add_marker(no_gpu_marker)

        if "requires_windows" in item.keywords and sys.platform != "win32":
            item.add_marker(no_windows_marker)
