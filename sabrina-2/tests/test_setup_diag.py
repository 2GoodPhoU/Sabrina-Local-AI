"""Minimal fixture-based repro."""
import sys, types
from pathlib import Path
import pytest

_SETUP = Path("/sessions/ecstatic-lucid-archimedes/mnt/Sabrina-Local-AI/sabrina-2/scripts/setup.py")

def _load():
    if "sabrina2_setup_diag" in sys.modules:
        return sys.modules["sabrina2_setup_diag"]
    m = types.ModuleType("sabrina2_setup_diag")
    m.__file__ = str(_SETUP)
    sys.modules["sabrina2_setup_diag"] = m
    src = _SETUP.read_text(encoding="utf-8")
    exec(compile(src, str(_SETUP), "exec"), m.__dict__)
    return m

@pytest.fixture(scope="module")
def setup_mod():
    return _load()

def test_with_fixture(setup_mod):
    print("\nProbeResult.__module__ =", setup_mod.ProbeResult.__module__, file=sys.stderr)
    assert setup_mod.ProbeResult.__module__ == "sabrina2_setup_diag"
