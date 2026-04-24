"""Structured logging setup.

Pretty console output via Rich; structured JSON-ish key=value pairs under the hood.
Call `setup_logging(level)` once at program start.
"""

from __future__ import annotations

import logging
import sys

import structlog
from rich.console import Console
from rich.logging import RichHandler


def setup_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Route stdlib logging through Rich for pretty dev output.
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=Console(stderr=True), rich_tracebacks=True, show_path=False
            )
        ],
    )

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
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
