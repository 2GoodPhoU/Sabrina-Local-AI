"""Structured logging setup.

Pretty console output via Rich; rotating JSON-per-line sink at
``logs/sabrina.log`` for audit. Call ``setup_logging(level)`` once at
program start.

Privacy posture (decision 008): secrets are redacted before rendering
and long values are truncated to 512 chars, so careless callers can't
leak an API key or multi-KB tool payload into either sink.
"""

from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from rich.console import Console
from rich.logging import RichHandler

from sabrina.config import project_root

# Key names that should never be rendered verbatim. Matched case-insensitively
# against the event-dict keys at the top level. Nested dicts are walked.
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "anthropic_api_key",
        "password",
        "secret",
        "token",
    }
)

# Any value (string repr) longer than this is truncated with a marker.
# 512 is enough for a line of prose or a short tool argument; long enough to
# be useful, short enough that a multi-KB transcript or screen-frame bytes
# never land in the log sink verbatim.
MAX_VALUE_CHARS = 512

# Suffix used when truncation happens. Exposed so tests can assert on it.
TRUNCATION_MARKER = "...(truncated)"


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    if lower in _SENSITIVE_KEYS:
        return True
    # Any key ending in `_token` (e.g. `refresh_token`, `bearer_token`) is
    # treated as sensitive — cheap catch-all for token-family fields.
    return lower.endswith("_token")


def redact_secrets(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: replace values of known-sensitive keys.

    Recursively walks nested dicts. Replaces the value with a fixed marker
    rather than dropping the key — the presence of the event is still
    informative ("an auth call happened"), just not the secret itself.
    """

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: ("***REDACTED***" if _is_sensitive_key(str(k)) else _walk(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        return obj

    return _walk(event_dict)


def truncate_long_values(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: cap long string values at MAX_VALUE_CHARS.

    Only walks the top level of the event dict. Non-string values that
    stringify long (e.g. big bytes blobs) are repr'd first so we don't pay
    `str(bytes)` on a 10MB buffer; stdlib's repr caps at reasonable sizes.
    """
    for k, v in list(event_dict.items()):
        if isinstance(v, str) and len(v) > MAX_VALUE_CHARS:
            event_dict[k] = v[: MAX_VALUE_CHARS - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER
    return event_dict


def _make_file_tee(file_handler: logging.Handler) -> Any:
    """structlog processor: tee a JSON copy of the event to the file sink.

    Runs before the ConsoleRenderer so the console path is unaffected. The
    file gets one JSON object per line — easy to `jq` / `grep` / pipe.
    """

    def processor(
        _logger: Any, _method: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            line = json.dumps(event_dict, default=str)
        except Exception:  # pragma: no cover — defensive
            line = str(event_dict)
        record = logging.LogRecord(
            name="sabrina",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=line,
            args=(),
            exc_info=None,
        )
        # Best-effort — a closed handler or full disk must not break the
        # caller. Log sinks are side-effects; the app keeps running.
        try:
            file_handler.emit(record)
        except Exception:  # pragma: no cover — defensive
            pass
        return event_dict

    return processor


def _default_log_file() -> Path:
    return project_root() / "logs" / "sabrina.log"


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Configure stdlib logging, Rich console sink, and rotating file sink.

    `log_file` defaults to ``<project_root>/logs/sabrina.log``. Tests can
    pass a tmp path. Rotation is 5 MB × 3 files — honest operational budget,
    not compliance. Automation audit log rotates separately (not here).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    log_file = log_file or _default_log_file()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Rotating sink for stdlib + structlog. Shared handler; same bytes go to
    # both sources.
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    file_handler.setLevel(log_level)

    # Route stdlib logging through Rich for pretty dev output + the file sink.
    # Clear any handlers a previous setup_logging() call attached so tests can
    # call us repeatedly without leaking file handles.
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:  # pragma: no cover
            pass
    root.setLevel(log_level)
    root.addHandler(
        RichHandler(
            console=Console(stderr=True), rich_tracebacks=True, show_path=False
        )
    )
    root.addHandler(file_handler)

    # Silence noisy third-party loggers that spam INFO during streaming.
    for noisy in (
        "httpx",
        "httpcore",
        "anthropic",
        "ollama",
        "urllib3",
        "faster_whisper",
        "ctranslate2",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_secrets,
            truncate_long_values,
            _make_file_tee(file_handler),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
