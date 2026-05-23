"""Brain router — Claude/Ollama dispatch with policy + budget gate.

Implements the ``Brain`` protocol; delegates each ``chat()`` call to a
leaf backend (``ClaudeBrain`` or ``OllamaBrain``) per a TOML-configured
policy. v1 ships three policies:

- ``force_local`` — always Ollama. Offline / privacy use.
- ``claude_default`` — always Claude. Today's behavior; the safe default.
- ``cost_aware`` — Claude until rolling MTD crosses the warn threshold,
  then Ollama for the rest of the month. The active enforcement decision
  001 names as observed-not-enforced today.

The router is a Linux-runnable structural surface; the Windows voice-loop
swap (``voice_loop.py`` instantiates ``make_router_from_settings`` instead
of ``ClaudeBrain``) + decision doc are P4.C3.

Per spec §"Open questions / spec recommendations":

- Q1 (b) — router reads ``[budget].warn_usd_monthly`` directly per Eric's
  2026-05-15 dashboard answer at NEEDS-INPUT.md:143. Single source of truth;
  routing logic flipping at a different number than the budget warning would
  surprise the user. The ``Router`` constructor still accepts an explicit
  ``warn_threshold_usd`` kwarg for direct-construction tests, but
  ``BrainRouterConfig`` no longer carries a per-router override field.
- Q2 (a) — ``cost_aware`` resolves the route per-call (instant transition
  the first turn after MTD crosses threshold). ``BudgetLog`` MTD is
  monotonic so this collapses to "ratchet" without an explicit ratchet.
- Q3 (a) — system-prompt swap reads ``SABRINA_SYSTEM_PROMPT_CLAUDE`` /
  ``SABRINA_SYSTEM_PROMPT_OLLAMA`` from ``brain/persona.py`` (a hard
  dependency on P4.C1's (a)-half).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Literal

from sabrina.brain.persona import (
    SABRINA_SYSTEM_PROMPT_CLAUDE,
    SABRINA_SYSTEM_PROMPT_OLLAMA,
)
from sabrina.brain.protocol import Brain, CancelToken, Message, StreamEvent
from sabrina.logging import get_logger

if TYPE_CHECKING:
    from sabrina.brain.claude import ClaudeBrain
    from sabrina.brain.ollama import OllamaBrain
    from sabrina.budget import BudgetLog
    from sabrina.config import Settings
    from sabrina.tools import ToolSpec

log = get_logger(__name__)


RouterPolicy = Literal["force_local", "claude_default", "cost_aware"]


class RouterMisconfigured(Exception):
    """The configured policy resolved to a backend that wasn't wired.

    Raised by ``Router.select_backend`` when e.g. ``policy="force_local"``
    was set but ``ollama=None`` was passed (Ollama disabled in config).
    Surfacing this loudly is preferable to silently degrading — Eric
    asked for ``force_local`` and got Claude is a privacy footgun.
    """


class Router:
    """A policy-driven dispatcher across Claude and Ollama backends.

    Implements the ``Brain`` protocol. Constructor wires backends + policy +
    optional budget telemetry; ``select_backend`` is the pure-fn resolver
    (testable without spinning up real backends); ``chat`` forwards to the
    selected backend with the per-backend persona prompt swapped in.

    Either ``claude`` or ``ollama`` may be ``None`` to disable that backend
    entirely. ``select_backend`` raises ``RouterMisconfigured`` if the
    chosen route resolves to a None backend.
    """

    def __init__(
        self,
        *,
        claude: ClaudeBrain | None,
        ollama: OllamaBrain | None,
        policy: RouterPolicy = "claude_default",
        budget_log: BudgetLog | None = None,
        warn_threshold_usd: float | None = None,
    ) -> None:
        self._claude = claude
        self._ollama = ollama
        self._policy: RouterPolicy = policy
        self._budget_log = budget_log
        self._warn_threshold_usd = warn_threshold_usd
        self.name = f"router:{policy}"

    # --- policy resolver -------------------------------------------------

    def select_backend(self) -> Brain:
        """Resolve a leaf backend for the upcoming turn.

        Pure of the chat surface — tests can call this directly without
        ever touching the backends' streams. Raises
        ``RouterMisconfigured`` rather than degrading silently.
        """
        if self._policy == "force_local":
            if self._ollama is None:
                raise RouterMisconfigured(
                    "policy='force_local' requires an Ollama backend; "
                    "got ollama=None"
                )
            return self._ollama
        if self._policy == "claude_default":
            if self._claude is None:
                raise RouterMisconfigured(
                    "policy='claude_default' requires a Claude backend; "
                    "got claude=None"
                )
            return self._claude
        if self._policy == "cost_aware":
            return self._select_cost_aware()
        raise RouterMisconfigured(
            f"unknown router policy: {self._policy!r}"
        )

    def _select_cost_aware(self) -> Brain:
        """Inner resolver for ``cost_aware`` policy.

        Reads ``BudgetLog.sum_month()`` if a log is wired; falls back to
        ``claude_default`` semantics if the log is missing (so ``cost_aware``
        in a fresh install with no log still routes sanely).
        """
        # No budget log => degrade to claude_default behavior.
        if self._budget_log is None:
            if self._claude is not None:
                return self._claude
            if self._ollama is not None:
                log.warning(
                    "router.degraded_open",
                    reason="no_budget_log_and_no_claude",
                    policy=self._policy,
                )
                return self._ollama
            raise RouterMisconfigured(
                "policy='cost_aware' with budget_log=None and both "
                "backends None — nothing to route to."
            )

        threshold = self._warn_threshold_usd
        if threshold is None:
            # Without a threshold the policy can't make a decision; degrade
            # to claude_default. The factory normally fills threshold from
            # [budget].warn_usd_monthly; explicit None here means a caller
            # constructed the router by hand without one.
            if self._claude is not None:
                return self._claude
            if self._ollama is not None:
                log.warning(
                    "router.degraded_open",
                    reason="no_threshold_and_no_claude",
                    policy=self._policy,
                )
                return self._ollama
            raise RouterMisconfigured(
                "policy='cost_aware' with no threshold and both "
                "backends None."
            )

        try:
            mtd = self._budget_log.sum_month()
        except Exception as exc:
            log.warning(
                "router.budget_read_failed",
                error=str(exc),
                policy=self._policy,
            )
            mtd = 0.0

        if mtd >= threshold:
            # Threshold crossed: prefer Ollama. If Ollama is missing,
            # log a degrade-open warning and stay on Claude — the user
            # asked for cost-aware behavior, but a missing local backend
            # is not a reason to refuse to answer.
            if self._ollama is not None:
                return self._ollama
            if self._claude is not None:
                log.warning(
                    "router.degraded_open",
                    reason="threshold_crossed_but_no_ollama",
                    policy=self._policy,
                    mtd=mtd,
                    threshold=threshold,
                )
                return self._claude
            raise RouterMisconfigured(
                "policy='cost_aware' threshold crossed and both "
                "backends None."
            )

        # Under threshold: prefer Claude.
        if self._claude is not None:
            return self._claude
        if self._ollama is not None:
            log.warning(
                "router.degraded_open",
                reason="under_threshold_but_no_claude",
                policy=self._policy,
                mtd=mtd,
                threshold=threshold,
            )
            return self._ollama
        raise RouterMisconfigured(
            "policy='cost_aware' under threshold and both backends None."
        )

    # --- chat surface (Brain protocol) ----------------------------------

    async def chat(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        cancel_token: CancelToken | None = None,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Forward to the policy-selected backend.

        - Picks a backend via ``select_backend()`` (per-turn resolution).
        - If ``system`` was None on entry, swaps in the per-backend
          persona prompt (Claude vs. Ollama) so each backend gets a
          voice-coherent system message. Explicit ``system="..."`` from
          the caller is passed through unchanged.
        - Drops ``tools`` to ``None`` if the selected backend doesn't
          support them (Ollama today raises NotImplementedError on
          non-empty tools). Logs ``router.tools_dropped`` at INFO so the
          conversion is debuggable mid-conversation.
        """
        backend = self.select_backend()

        # Per-backend persona prompt swap. Only applies when the caller
        # didn't pass an explicit system prompt — otherwise the caller
        # is asking for a specific shape and we honor that.
        resolved_system = system
        if resolved_system is None:
            resolved_system = _persona_for(backend)

        # Tools drop on backends that can't handle them. We rely on
        # Brain.name's "claude:" / "ollama:" prefix to identify the
        # backend kind without a hard runtime import on either class.
        forwarded_tools = tools
        if forwarded_tools and not _backend_supports_tools(backend):
            log.info(
                "router.tools_dropped",
                backend=backend.name,
                policy=self._policy,
                count=len(forwarded_tools),
            )
            forwarded_tools = None

        stream = backend.chat(
            messages,
            system=resolved_system,
            max_tokens=max_tokens,
            cancel_token=cancel_token,
            tools=forwarded_tools,
        )
        async for event in stream:
            yield event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _persona_for(backend: Brain) -> str:
    """Pick the per-backend persona prompt from ``brain/persona.py``."""
    name = getattr(backend, "name", "") or ""
    if name.startswith("ollama:"):
        return SABRINA_SYSTEM_PROMPT_OLLAMA
    # Default to Claude prompt for any non-Ollama backend (claude:* and
    # any future tier). Keeps the router usable with backends the
    # persona module hasn't been tuned for yet — they get the canonical
    # Claude voice rather than no system prompt.
    return SABRINA_SYSTEM_PROMPT_CLAUDE


def _backend_supports_tools(backend: Brain) -> bool:
    """Return True if the backend can accept a non-empty ``tools=`` list.

    Today: Claude yes, Ollama no. Future backends should advertise via a
    ``supports_tools: bool`` attribute; we read that if present, else
    fall back to the name-prefix heuristic.
    """
    flag = getattr(backend, "supports_tools", None)
    if flag is not None:
        return bool(flag)
    name = getattr(backend, "name", "") or ""
    return not name.startswith("ollama:")


# ---------------------------------------------------------------------------
# Factory — used by voice_loop.py / chat.py once P4.C3 wires the swap.
# ---------------------------------------------------------------------------


def make_router_from_settings(
    settings: Settings,
    *,
    budget_log: BudgetLog | None = None,
) -> Router:
    """Wire a Router from a loaded ``Settings`` instance.

    Mirrors the existing ``cli._build_brain`` factory pattern in shape:
    instantiates ``ClaudeBrain`` and/or ``OllamaBrain`` per the
    ``[brain.router] enable_*`` flags, reads policy + threshold from
    ``[brain.router]``, returns a wired ``Router``.

    ``warn_threshold_usd`` is sourced directly from
    ``[budget].warn_usd_monthly`` (Q1 (b) per Eric's 2026-05-15 dashboard
    answer at NEEDS-INPUT.md:143 — single source of truth; the
    ``[brain.router].warn_threshold_usd`` override field was removed to
    avoid two-knob drift between the budget warn line and the route swap).
    """
    # Imports kept inside the factory to keep ``router.py`` importable
    # without anthropic / ollama installed (test environments).
    from sabrina.brain.claude import ClaudeBrain
    from sabrina.brain.ollama import OllamaBrain

    router_cfg = settings.brain.router
    claude: ClaudeBrain | None = None
    if router_cfg.enable_claude:
        api_key = (
            settings.anthropic_api_key.get_secret_value()
            if settings.anthropic_api_key
            else ""
        )
        if api_key:
            claude = ClaudeBrain(
                api_key=api_key,
                model=settings.brain.claude.model,
                max_tokens=settings.brain.claude.max_tokens,
            )
        else:
            log.warning(
                "router.claude_disabled_no_api_key",
                hint="Set ANTHROPIC_API_KEY in .env or unset enable_claude.",
            )

    ollama: OllamaBrain | None = None
    if router_cfg.enable_ollama:
        ollama = OllamaBrain(
            host=settings.brain.ollama.host,
            model=settings.brain.ollama.model,
            strip_closing_offer=settings.brain.persona.ollama_strip_closing_offer,
            dehydrate_lists=settings.brain.persona.ollama_dehydrate_lists,
            dedup_apologies=settings.brain.persona.ollama_dedup_apologies,
            truncate_long_replies=settings.brain.persona.ollama_truncate_long_replies,
        )

    threshold = settings.budget.warn_usd_monthly

    return Router(
        claude=claude,
        ollama=ollama,
        policy=router_cfg.policy,
        budget_log=budget_log,
        warn_threshold_usd=threshold,
    )


__all__ = [
    "Router",
    "RouterMisconfigured",
    "RouterPolicy",
    "make_router_from_settings",
]
