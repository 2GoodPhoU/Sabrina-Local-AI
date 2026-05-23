"""Automation safety primitives — kill-switch, dry-run, scaffold + allow_list (P4.B3)."""

from __future__ import annotations

from sabrina.automation.allow_list import (
    DestructiveActionBlocked,
    check_allowed,
    is_allowed,
)

__all__ = [
    "DestructiveActionBlocked",
    "check_allowed",
    "is_allowed",
]
