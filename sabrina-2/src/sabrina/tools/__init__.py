"""Tool registry — ToolSpec base class + BUILTIN_TOOLS list.

Anti-sprawl: this module exists because step 1 of the overnight tool-use
ship needs *some* canonical home for `ToolSpec`. Keeping it in
`tools/__init__.py` (rather than `brain/tools.py`) means handlers and
their registrations live next to the spec class — when `web_search` /
`append_note` land per the toolspec research doc, they slot in
alongside `clipboard.py` without a path change.

`ToolSpec` exposes two serializations:

  - `to_anthropic_dict()` — what the Anthropic SDK's `tools=` param
    expects: `{name, description, input_schema}`. Used today.
  - `to_mcp_dict()` — what an MCP server's `tools/list` advertises:
    `{name, description, inputSchema}`. Schema-shape only — not
    a runtime transport. Lets the same handler list power either
    surface when MCP migration lands per the audit in
    `rebuild/drafts/tool-use-plan.md`.

The handler is an async callable: `(input_dict) -> result_dict`. No
side-effect-class field yet — the side-effect taxonomy from the
research doc is documentation, not a runtime concern.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One tool's name, description, JSON Schema, and async handler.

    Serializes to either the Anthropic-native shape (`input_schema` key)
    or the MCP shape (`inputSchema` key). The two differ only in field
    naming — keeping both methods costs ~10 lines and lets the registry
    drive either transport.

    ``destructive`` (P4.B3) is a Sabrina-internal safety tag: True for
    tools whose effects are irreversible-ish (keyboard inputs, app
    launches, file writes). The runtime allow-list in
    ``sabrina.automation.allow_list`` consults this flag — destructive
    tools are blocked unless their name is in
    ``settings.automation.destructive_actions``. The field is NOT part
    of the Anthropic SDK or MCP wire format; ``to_anthropic_dict`` /
    ``to_mcp_dict`` omit it deliberately. Default False keeps existing
    ``write_clipboard`` registration unchanged.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    destructive: bool = False

    def to_anthropic_dict(self) -> dict[str, Any]:
        """Shape the Anthropic SDK's `messages.create(tools=[...])` expects."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def to_mcp_dict(self) -> dict[str, Any]:
        """Shape an MCP server's `tools/list` response advertises.

        The MCP tool schema (per modelcontextprotocol.io 2025-06 spec)
        names the schema field `inputSchema` (camelCase, not snake_case)
        and is otherwise identical at the top level. A handler isn't part
        of the MCP wire format — it's the server's private business — so
        only the three transport-visible fields ship.
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


# Lazy import inside the property so a teardown / partial install can't
# break `from sabrina.tools import ToolSpec` for callers that don't need
# the registry. The registry itself ships *populated* — empty registries
# are anti-sprawl bait ("we'll add tools later") and the toolspec
# research doc's first-three set is concrete.
#
# The optional ``settings`` parameter is a test-injection seam (P4.B2
# spec: ``test_send_hotkey_{not_,}in_builtin_tools_when_{disabled,enabled}``).
# Default = load via ``sabrina.config.load_settings()``; tests pass a
# constructed ``Settings`` instance to verify conditional registration
# without re-importing the module. Failures during the lazy settings
# load (e.g. a minimal stub test that hasn't built a Settings instance)
# fall through silently — gated tools simply don't register.
def _builtin_tools(settings: object | None = None) -> list[ToolSpec]:
    from sabrina.tools.clipboard import write_clipboard

    tools: list[ToolSpec] = [
        ToolSpec(
            name="write_clipboard",
            description=(
                "Place plain text on the user's system clipboard. "
                "Returns whether the write succeeded and the byte length."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Plain text to place on the clipboard.",
                        "maxLength": 100000,
                    },
                },
                "required": ["content"],
            },
            handler=write_clipboard,
            # P4.B3 Q3 (a): explicit ``destructive=False`` for documentation;
            # ``write_clipboard`` is non-destructive (clipboard contents are
            # easily overwritten; no keyboard input fires).
            destructive=False,
        ),
    ]

    # Conditional ``send_hotkey`` registration (P4.B2 (a)-half).
    # Off by default until P4.B4's Windows e2e validation lands —
    # ``sabrina.toml`` ships ``[tools] send_hotkey_enabled = false`` so a
    # fresh upgrade keeps the dangerous tool out of the registry.
    if settings is None:
        try:
            from sabrina.config import load_settings

            settings = load_settings()
        except Exception:  # noqa: BLE001 — minimal-stub tests; skip gated tools
            settings = None

    tools_section = getattr(settings, "tools", None) if settings is not None else None
    if getattr(tools_section, "send_hotkey_enabled", False):
        from sabrina.tools.hotkey import SEND_HOTKEY_SPEC

        tools.append(SEND_HOTKEY_SPEC)

    return tools


BUILTIN_TOOLS: list[ToolSpec] = _builtin_tools()


def find(name: str) -> ToolSpec | None:
    """Look a tool up by name. Returns None if not registered."""
    for spec in BUILTIN_TOOLS:
        if spec.name == name:
            return spec
    return None
