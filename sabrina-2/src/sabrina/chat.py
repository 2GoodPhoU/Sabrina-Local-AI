"""Interactive REPL against a Brain.

Simple Rich-based loop: reads user input, streams the reply, prints token usage
and state-machine transitions along the way. All text I/O goes through the bus.
Persists messages to the memory store when one is supplied.
"""

from __future__ import annotations

import asyncio

from rich.console import Console

from sabrina.brain.protocol import Brain, Done, Message, TextDelta
from sabrina.bus import EventBus
from sabrina.events import (
    AssistantReply,
    ThinkingFinished,
    ThinkingStarted,
    UserMessage,
)
from sabrina.memory.store import MemoryStore, new_session_id
from sabrina.state import StateMachine


_SYSTEM = (
    "You are Sabrina, a helpful, concise personal assistant running locally on the "
    "user's Windows PC. Keep replies short and conversational unless the user asks "
    "for detail."
)


async def run_repl(
    brain: Brain,
    bus: EventBus,
    sm: StateMachine,
    console: Console,
    memory: MemoryStore | None = None,
    load_recent: int = 20,
) -> None:
    history: list[Message] = []
    session_id = new_session_id()

    if memory is not None and load_recent > 0:
        loaded = memory.load_recent(load_recent)
        history.extend(m.to_message() for m in loaded)
        if loaded:
            console.print(
                f"[dim](loaded {len(loaded)} message(s) from memory; "
                f"session={session_id})[/]"
            )

    console.print(
        f"[bold green]Sabrina[/] ready. Backend: [cyan]{brain.name}[/]. "
        "Ctrl+D (or type /quit) to exit."
    )

    while True:
        try:
            user_input = await asyncio.to_thread(console.input, "[bold cyan]you>[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye.[/]")
            return

        text = user_input.strip()
        if not text:
            continue
        if text.lower() in {"/quit", "/exit", "/bye"}:
            console.print("[dim]bye.[/]")
            return

        history.append(Message(role="user", content=text))
        if memory is not None:
            memory.append(session_id, "user", text)
        await bus.publish(UserMessage(text=text))

        await sm.transition("thinking", reason="user_message")
        await bus.publish(ThinkingStarted(tier=brain.name))

        console.print("[bold magenta]sabrina>[/] ", end="")
        reply_chunks: list[str] = []
        in_tok: int | None = None
        out_tok: int | None = None

        try:
            async for event in brain.chat(history, system=_SYSTEM):
                if isinstance(event, TextDelta):
                    console.print(event.text, end="", highlight=False, soft_wrap=True)
                    reply_chunks.append(event.text)
                elif isinstance(event, Done):
                    in_tok, out_tok = event.input_tokens, event.output_tokens
        except Exception as exc:  # noqa: BLE001 - REPL should never crash
            console.print(f"\n[red]brain error:[/] {exc}")
            await sm.transition("idle", reason="brain_error")
            continue

        console.print()  # newline after stream
        reply = "".join(reply_chunks)
        history.append(Message(role="assistant", content=reply))
        if memory is not None:
            memory.append(session_id, "assistant", reply)

        await bus.publish(AssistantReply(text=reply, tier=brain.name))
        await bus.publish(
            ThinkingFinished(
                tier=brain.name, input_tokens=in_tok, output_tokens=out_tok
            )
        )
        await sm.transition("idle", reason="reply_sent")

        if in_tok is not None or out_tok is not None:
            console.print(f"[dim](tokens in={in_tok} out={out_tok})[/]")
