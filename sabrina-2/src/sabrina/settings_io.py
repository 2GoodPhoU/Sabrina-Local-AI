"""Comment-preserving read/write for sabrina.toml.

Pydantic-settings is great for *loading* layered config, but it throws away
comments and ordering. The settings GUI needs to round-trip user edits back
into sabrina.toml without nuking the documentation comments the user reads
when tweaking by hand. tomlkit keeps the file exactly as-authored and only
touches the bytes of keys we update.

Path resolution: mirrors config.project_root() — looks upward from cwd for
the nearest sabrina.toml. Writes happen atomically via temp-file + replace
so a crash can never leave a half-written config.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import Table

from sabrina.config import project_root


def toml_path() -> Path:
    """Return the absolute path to sabrina.toml (may or may not exist)."""
    return project_root() / "sabrina.toml"


def load_document(path: Path | None = None) -> TOMLDocument:
    """Parse sabrina.toml preserving comments and formatting.

    If the file is missing, returns an empty document — caller can still
    write into it; save_document() will create the file on first save.
    """
    path = path or toml_path()
    if not path.is_file():
        return tomlkit.document()
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def save_document(doc: TOMLDocument, path: Path | None = None) -> None:
    """Atomically write `doc` to sabrina.toml."""
    path = path or toml_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = tomlkit.dumps(doc)
    # Write next to target, then rename — avoids a partial file on crash.
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=".sabrina.toml.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def apply_updates(doc: TOMLDocument, updates: dict[str, Any]) -> None:
    """Apply a nested-dict of updates into `doc` in place.

    Dotted keys are NOT supported — use nested dicts:
        {"tts": {"piper": {"speaker_id": 3}}, "brain": {"default": "ollama"}}

    Creates missing tables as needed. Preserves existing comments and the
    document's structural ordering (new tables are appended; existing keys
    keep their line position).
    """
    _apply(doc, updates)


def _apply(node: TOMLDocument | Table, updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict):
            child = node.get(key)
            if not isinstance(child, Table):
                child = tomlkit.table()
                node[key] = child
            _apply(child, value)
        else:
            node[key] = value


def save_with_updates(updates: dict[str, Any], path: Path | None = None) -> None:
    """Convenience: load → apply updates → save. Returns nothing on success."""
    doc = load_document(path)
    apply_updates(doc, updates)
    save_document(doc, path)
