"""ToolSpec scaffold — ``noop_action`` for end-to-end dispatch tests.

The scaffold proves the Phase-4 dispatch path before any real action
ToolSpec rides it. ``noop_action`` is intentionally a real
``ToolSpec`` (round-trips through ``to_anthropic_dict()`` like any
other) but has no side effects — it just returns its content length.

Registry membership policy (spec Q3 (a)): NOT in ``BUILTIN_TOOLS`` by
default. Tests pass ``tools=[NOOP_ACTION_SPEC, *BUILTIN_TOOLS]`` to
``ClaudeBrain.chat`` directly; the brain at runtime never sees this
spec. "Leaks impossible by construction" outweighs "P4.B4 has to wait
for B2 for a real action to fire" since they're sequential in any case
(B4 closes the quartet).
"""

from __future__ import annotations

from typing import Any

from sabrina.tools import ToolSpec


async def noop_action(content: str) -> dict[str, Any]:
    """Pure-function scaffold handler. Returns the content length.

    Side-effect class: ``read-only / pure`` (no fs / no network /
    no clipboard). Same shape as the existing ``write_clipboard``
    handler — async function, kwargs-in / dict-out — so the dispatch
    loop in ``brain/claude.py`` calls it exactly the same way.
    """
    return {"ok": True, "content_length": len(content)}


# Module-level constant. Importable as
# ``from sabrina.automation.scaffold import NOOP_ACTION_SPEC``. The
# spec name doubles as the test-only registry key — ``find()`` in
# ``sabrina.tools`` will return None for ``"noop_action"`` because
# the spec isn't registered with ``BUILTIN_TOOLS``; tests build their
# own lookup over the spec list they pass to ``chat()``.
NOOP_ACTION_SPEC: ToolSpec = ToolSpec(
    name="noop_action",
    description=(
        "Test-only no-op action. Reports the length of the input content "
        "string without performing any side effect. Used to exercise the "
        "automation dispatch path under unit tests; intentionally not "
        "registered as a runtime tool."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": (
                    "Arbitrary text. The handler returns its length."
                ),
                "maxLength": 100000,
            },
        },
        "required": ["content"],
    },
    handler=noop_action,
)
