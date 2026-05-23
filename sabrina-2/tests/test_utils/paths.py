"""Path helpers for the Sabrina rebuild test scaffolding.

Ported subset of legacy `tests/test_utils/paths.py`. Drops the helpers tied
to the legacy directory layout (`get_component_path`, `get_config_path`,
`get_test_resource_path`, `get_test_unit_dir`/`integration_dir`/`e2e_dir`)
because the rebuild has neither a `config/` directory nor a unit/integration/
e2e split — `sabrina-2/tests/` is currently flat.

`get_project_root()` returns the rebuild root (`sabrina-2/`), not the
repo root. Indicators used to verify the resolution: `README.md`,
`pyproject.toml`, `src/sabrina`. The legacy indicators (`core/`,
`utilities/`, `services/`) are intentionally dropped — those folders live
at the repo root and are off-limits per CLAUDE.md.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Union


# Rebuild-root indicators. At least one must exist for `get_project_root` to
# return successfully. `src/sabrina` is the strongest signal — it's unique
# to the rebuild root and won't false-positive against legacy paths.
_KEY_INDICATORS = ("README.md", "pyproject.toml", "src/sabrina")


def get_project_root() -> Path:
    """Absolute path to the rebuild root (`sabrina-2/`).

    Resolves from this file's location: `paths.py` lives in
    `sabrina-2/tests/test_utils/`, so two `parent` hops land on
    `sabrina-2/`. Verifies the result by checking for at least one
    indicator from `_KEY_INDICATORS`.
    """
    here = Path(__file__).resolve()
    candidate = here.parent.parent.parent

    for indicator in _KEY_INDICATORS:
        if (candidate / indicator).exists():
            return candidate

    raise RuntimeError(
        f"Failed to locate rebuild root from {here}. "
        f"None of the expected indicators {_KEY_INDICATORS} were found "
        f"under {candidate}."
    )


def get_test_dir() -> Path:
    """Absolute path to `sabrina-2/tests/`."""
    return get_project_root() / "tests"


def get_test_data_dir() -> Path:
    """Absolute path to `sabrina-2/tests/data/`. Creates it if missing."""
    data = get_test_dir() / "data"
    data.mkdir(exist_ok=True)
    return data


def get_test_temp_dir() -> Path:
    """Absolute path to `sabrina-2/tests/temp/`. Creates it if missing.

    For tests that want a long-lived temp dir scoped to the project rather
    than per-test. Per-test scratch space should use the `temp_dir` fixture
    in `conftest.py`, which uses `tempfile.TemporaryDirectory`.
    """
    temp = get_test_dir() / "temp"
    temp.mkdir(exist_ok=True)
    return temp


def ensure_path_in_sys_path(path: Union[str, Path]) -> None:
    """Insert `path` at the head of `sys.path` if not already present."""
    p = str(path) if isinstance(path, Path) else path
    if p not in sys.path:
        sys.path.insert(0, p)


def ensure_project_root_in_sys_path() -> None:
    """Insert `sabrina-2/src/` into `sys.path` so `import sabrina` resolves.

    The legacy variant inserted the project root itself (legacy was a flat
    layout). The rebuild uses `src/`-layout (`pyproject.toml` says
    `packages = ["src/sabrina"]`), so the importable parent is `src/`,
    not the project root.
    """
    src = get_project_root() / "src"
    if src.is_dir():
        ensure_path_in_sys_path(src)


def create_test_file(dir_path: Path, filename: str, content: str = "") -> Path:
    """Create `dir_path/filename` with the given content; return the path.

    Creates parents if missing. Useful in tests that need a small fixture
    file inside a `temp_dir`.
    """
    dir_path.mkdir(exist_ok=True, parents=True)
    file_path = dir_path / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path
