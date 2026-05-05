# Multi-surface identity architecture — keeping Sabrina one entity

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** How the voice loop, GUI, avatar, tray icon, and any future
companion surface stay perceptually one Sabrina rather than a
federation of components that happen to share a name. Implementation
recommendations grounded in the existing event bus + state machine,
plus 2026 evidence on what works and what kills the illusion.

**Anchor:** the rebuild already has a small, healthy spine — a typed
event bus and a 5-state machine ([decision 003](../../decisions/003-voice-loop-shipped.md)),
a barge-in cooperative-cancel pattern that threads through Brain and
Speaker ([decision 009](../../decisions/009-barge-in-shipped.md)), and
the avatar plan's "frameless presence reacting to bus events"
posture ([avatar-plan.md](../avatar-plan.md)). Nothing here proposes
ripping any of that out. The question is the layer *above* it: what
does it take to make Sabrina feel like one person across surfaces,
and which decisions get hard once there are three of them on screen.

**Audience:** Eric on Sunday morning. Implementation owner is a future
session.

---

## The problem, stated plainly

Today Sabrina is essentially one surface — voice — with a settings
GUI you only open occasionally. Once the avatar lands she is two
visible surfaces concurrently: the avatar reacting to state events
in one corner of the screen, and the customtkinter settings or
memory panel in another. A tray icon (likely behind
`hide_in_focus_assist`) is a third. A future companion / mobile
mode is a fourth. Each of these subscribes to the same bus today
and that is exactly the trap: pub/sub on its own gives you
*coordination*, not *identity*. Coordination means everyone
receives `StateChanged(speaking)`. Identity means only one of them
should *be* the answer to "where's Sabrina right now."

Symptoms of getting this wrong, observed in adjacent products:

- **Federated-feel.** Cortana on Windows 10 famously read as "the
  search bar at the bottom" and "the chat panel" simultaneously,
  with neither knowing what the other was doing. Users called it
  "two assistants" in usability work [4][9].
- **Conflicting affect.** A GUI memory panel that says "indexing"
  while the avatar smiles and lip-syncs feels uncanny. The Live2D
  + AI demos in the wild that don't synchronize the panel UI with
  the rig hit this immediately [10].
- **Lifecycle leaks.** Surfaces dying without telling the system
  leave orphan state — most visibly when the avatar process dies
  but the voice loop still publishes `SpeakStarted` to nobody, and
  the user can't tell whether Sabrina is broken or quiet. Rabbit
  R1 and Humane Pin both shipped with this exact failure class
  visible to end users [5][6].

These are not separate bugs. They are the same bug — *no canonical
home for "what Sabrina is right now"* — wearing different costumes.

---

## Identity continuity primitives

The set of facts every surface needs in agreement to read as one
entity. Smaller than it sounds.

**Mood.** The current emotion the avatar would express, the
register the GUI would tint with, the tone the voice loop would
choose. One enum, ~8 values, exactly the avatar-plan vocabulary
(`neutral, happy, sad, surprised, thinking, focused, concerned,
amused`). Cue-track tags drive transitions; surfaces read the
current value.

**Activity.** What Sabrina is *doing* — listening, thinking,
speaking, reading the screen, idle. The state machine already
publishes this. Activity is finer-grained than mood and changes
faster.

**Attention target.** Where Sabrina is "looking" — `user`, `away`,
`screen_capture`, `gui_panel_xyz`. The avatar uses this for
gaze; the GUI uses it to decide whether to surface a notification
or stay quiet. Today implicit; should be explicit.

**Recent context handle.** Not the full memory, just a short
"current topic" string and a turn counter. Lets a panel show
"working on the audio refactor" without re-querying memory.

**Active-surface set.** The list of surfaces that currently
exist. Which ones are visible, which are hidden, which ones own
input focus. Lets the avatar know whether to fade for the GUI;
lets the GUI know whether the avatar is reachable.

These five facts are the entire identity-continuity payload. Most
of it is a few bytes. None of it includes content (transcripts,
messages, embeddings) — that lives in memory and is queried as
needed.

The decision-doc voice in `decisions/008` and `010` already names
the principle without naming it: small, owned, justified. Identity
state should be the same.

---

## Cross-surface signal architecture

The current event bus is a fire-and-forget pubsub. Adding identity
on top of it doesn't require replacing it; it requires putting one
authoritative subscriber-and-publisher in front of it whose only
job is to own the five primitives above and broadcast deltas when
they change.

**Topology.**

```
voice_loop ──pub──┐
listener   ──pub──┤        ┌────────────────────┐
brain      ──pub──┼──> bus ─┤   Presence actor    ├──> bus ──sub──> avatar
speaker    ──pub──┤        │  (single owner of   │              ──sub──> gui
vision     ──pub──┘        │   identity state)   │              ──sub──> tray
                            └────────────────────┘
```

`Presence` subscribes to the existing typed events
(`StateChanged`, `SpeakStarted`, `BargeInDetected`, vision-cue
events, future `MoodCue` from cue-track parsing) and reduces them
into the five primitives. It then publishes a single
`PresenceUpdated(snapshot)` event. Avatar, GUI, and tray subscribe
to *that* — not to the firehose.

**Why an actor, not a shared dataclass.** The actor model survey
results land on the same point that's load-bearing here: actors
"realize functionality by sending and receiving messages
asynchronously, communicate only by sending messages without
exposing internal state to other actors, each has an inbox queue
processing messages sequentially" [3]. The five primitives are a
miniature shared-state problem — race conditions on mood
transitions during a barge-in, attention-target flapping, the
avatar lerping toward stale snapshot — and a single-owner actor
is the boring well-known answer. ActressMAS and similar frameworks
exist for exactly this; we don't need them, we need the pattern
[3].

**Conflict resolution.** Two examples worth pinning down before
the avatar lands:

1. *GUI memory panel is open and Sabrina is speaking.* The avatar
   should keep speaking-affect and the panel should not steal
   gaze. `attention_target = user` while
   `activity = speaking`; the panel renders without announcing
   itself.
2. *Barge-in mid-reply with the avatar already showing `amused`.*
   Cue dispatcher already cancels queued cues and blends to
   `neutral-attentive` for 200 ms (avatar-plan §"parameter-conflict
   priority"). Presence's job is to publish the mood
   transition *once* so the GUI's "currently feels: amused" badge
   doesn't flash through.

The rule is: per-frame parameter conflicts stay inside the avatar
dispatcher (already designed). Per-second identity conflicts go
through Presence. Different timescales, different layers.

---

## Surface lifecycle

Each surface joins, lives, and leaves. Today none of these are
explicit; the avatar plan handwaves "supervisor restarts the
avatar independently." That works for *survival*; it does not
work for *coherence*. A surface that comes back from a restart
should not believe it's a different Sabrina.

**Join.** A surface starts and announces itself with a
`SurfaceJoined(name, capabilities)` event. Presence adds it to
the active-surface set, replies with a snapshot of the current
identity primitives so the surface can hydrate its initial render
without polling.

**Live.** Surface subscribes to `PresenceUpdated`. Updates a
heartbeat on every render; Presence drops surfaces whose
heartbeat lapses by > 5 s.

**Leave (graceful).** Surface publishes `SurfaceLeaving(name)`.
Presence removes from the set and broadcasts the new snapshot so
e.g. the avatar can reclaim "primary visible surface" if the GUI
just closed.

**Leave (crash).** Heartbeat lapse drops the surface; supervisor
restarts the process; on restart it `SurfaceJoined` again with a
new instance id so subscribers can distinguish "same surface,
fresh process" from "same surface, same process."

This is a tiny version of what supervisor architectures already
do for orchestration [7][8]; the value here isn't novelty, it's
that *every* surface lives in the same lifecycle vocabulary. No
ad-hoc avatar restart logic, no GUI-specific reconnection code.

---

## What does the user perceive as one Sabrina?

The literature on multi-surface assistant UX is thin — the four-way
Alexa/Siri/Google/Cortana studies focused on single-device usability
[9] — but four principles fall out of the failure-mode survey
consistently:

1. **One concurrent voice.** No matter how many surfaces are
   visible, only one of them is allowed to speak at a time. This
   is already the case (only Speaker emits TTS) but the principle
   generalizes: only one surface "answers" at a time. If the GUI
   and the avatar both want to surface a notification, Presence
   picks.

2. **Affect leads, content follows.** The Pi review writeups
   landed on this without naming it: "no difference in performance
   or tone between web and mobile" was load-bearing for users
   reading it as one Pi, even though session content differed
   somewhat across platforms [11]. Mood + activity (affect) is
   what makes "the same entity"; the exact words don't have to
   match — the shape of the engagement does.

3. **Continuity across pauses.** Apple's Continuity / Handoff is
   the largest deployed example of "keep working on the same
   thing across surfaces" — Mac to iPhone, iPhone to iPad, etc.
   [1][2] The user-visible behavior is that *the surface*
   changes but *the task* doesn't. Sabrina's analog: if Eric
   opens the memory panel mid-conversation, the conversation is
   still happening. The panel doesn't take over.

4. **Anti-pattern: stochastic personality.** The assistant
   research spans 2018-2025 and settles on the same finding —
   users can tolerate limited capability but not *inconsistent*
   capability or affect across access points [9]. The bar isn't
   "everywhere has every feature"; it's "everywhere feels like
   the same person." Cortana's federation feel was the
   counter-example.

What this means for Sabrina, concretely:

- The voice register, the avatar mood, and the GUI accent color
  are all derived from the same `mood` primitive.
- The avatar fading on cursor hover is fine; the avatar fading
  while still trying to *speak* would not be — visible-affect
  fade is a Presence-mediated decision.
- A GUI panel showing "indexing memories" while the avatar is
  showing `amused` because the brain just made a quip — that's
  the kind of split-personality moment a `Presence` actor
  prevents by making mood the avatar's source of truth and the
  GUI's at the same instant.

---

## Implementation pattern recommendation

**Build a `Presence` actor, ~150 lines, alongside the avatar
work — not before it.** The avatar lands first as drafted in
`avatar-plan.md`; while wiring the avatar's bus subscriber, that
subscriber gets factored *out* of `avatar/` and into a new
`presence/` package that the avatar then consumes. Same pattern
the rebuild has used elsewhere ([decision 003](../../decisions/003-voice-loop-shipped.md)
event bus extracted only when there were two callers).

```
sabrina-2/src/sabrina/presence/
├── __init__.py
├── actor.py        # Presence: subscribes to bus, owns state
├── primitives.py   # PresenceSnapshot, Mood, Activity, Attention
└── lifecycle.py    # SurfaceJoined / SurfaceLeaving / heartbeat
```

`actor.py` runs in `voice_loop`'s asyncio loop (no separate
process — process-isolation is for crashable surfaces, not for
the identity owner). It subscribes to `StateChanged`,
`SpeakStarted/Finished`, `BargeInDetected`, and (future)
`MoodCue` events. It publishes `PresenceUpdated(snapshot)` and
nothing else.

**State shape (concrete):**

```python
@dataclass(frozen=True)
class PresenceSnapshot:
    mood: Mood            # 8-value enum from avatar-plan
    activity: Activity    # idle|listening|thinking|speaking|acting
    attention: Attention  # user|away|screen|gui|<surface_id>
    topic_handle: str     # short string, ~50 chars
    turn_id: str          # current voice-loop turn
    surfaces: frozenset[SurfaceId]
    revision: int         # monotonic; lets surfaces dedupe
```

**Why `frozen=True` and `revision`.** Frozen so subscribers can
trust the snapshot they got is the snapshot Presence published;
revision so a slow surface that re-renders against a stale
snapshot can detect the drift instead of writing back over a
newer one.

**Token-budget honesty.** Adding Presence costs maybe 10-20 ms
per state-change event (a small reduce + publish). Negligible
against the 1.85 s first-audio number. If it ever shows up, the
fix is moving the reducer off the hot path; the architectural
shape doesn't change.

**Anti-sprawl check.** A `Presence` actor is "a new abstraction"
in the rebuild's strict sense, which means it needs a second
caller before earning its file. The second caller is on the
roadmap by definition: the moment the avatar reads identity
state from somewhere, the GUI's mood-tinted accent and the
tray's current-status tooltip read it from the *same* place.
That's the second caller. Build the abstraction when the avatar
ships, not before.

---

## Comparable systems in 2026

**Apple Intelligence + Continuity.** Apple's working answer to
multi-surface identity is Handoff plus iCloud session state —
the surface changes, the task migrates, the user's identity (via
the Apple Account) is the canonical bind [1][2]. The lesson for
Sabrina: identity is *not* the union of what the surfaces think;
it's a separate thing that the surfaces query. Apple gets away
with it because the Apple Account is an obvious anchor; Sabrina
gets away with it because there's exactly one user and one
session at a time, so the actor *is* the anchor.

**Rabbit R1 / Humane AI Pin.** The teardown writeups converge on
two failure modes: "the gap between demo capability and shipped
capability" [5] and "the bar for standalone AI hardware is not
'better than nothing' but 'better than a smartphone'" [6]. The
second one is the cautionary tale for Sabrina-the-companion-app —
a future mobile surface can't justify itself by being merely
another way to reach Sabrina; it has to be *better* at something
the desktop surface isn't. The first is the cautionary tale for
the avatar — a half-shipped avatar that "sometimes" lip-syncs
will read as broken, not novel.

**Inflection Pi.** Pi's bet is "no difference in performance or
tone between web and mobile" [11], and the user reports back
"continues seamlessly regardless of device." Pi runs the same
fine-tuned model on every surface and stores conversation state
centrally — a much heavier-weight version of what we're sketching
with Presence + memory. The lesson: *consistency of voice* is
load-bearing for the perception of one entity; capability
parity is not.

**Generative agents (Park et al.).** The 2023 Stanford simulacra
paper formalized the recency / importance / relevance memory
stream that's still the dominant retrieval model in 2026 [12].
Less obviously, it gave us "one stream, one identity": the
agent's behavior across reflections, plans, and dialogue all
reduce through the same memory and the same self-summary. That's
the architecture analog to what Presence is doing at the surface
layer.

**Multi-agent reference architectures.** Microsoft's reference
architecture and Databricks' supervisor-agent patterns both name
the same shape: a central orchestrator that owns task state,
specialists that own capability state [7][8]. Sabrina's not
multi-agent in their sense, but the structural lesson — one
owner per identity-relevant fact — is the same.

---

## Decisions Eric needs to lock

1. **Build Presence as a single in-process actor, not a separate
   service. (Recommended.)** Identity is small, hot, and ordered;
   process isolation buys nothing here and costs the IPC the
   avatar already pays for amplitude. *Override:* if a future
   mobile companion needs to read identity over the network, lift
   Presence into a tiny WebSocket-fronted server *then*. Not now.

2. **Mood vocabulary = avatar's 8-value enum, single source of
   truth. (Recommended.)** Don't grow a separate "voice mood"
   alongside the avatar mood — drift is guaranteed and the
   personality plan already commits to the 8 values. *Override:*
   if the cue track grows past 8, Presence is the place to
   accept the wider vocabulary and downconvert for surfaces that
   only know 8.

3. **`SurfaceJoined / SurfaceLeaving` lifecycle events from day
   one. (Recommended.)** Even if the avatar is the only
   non-voice-loop surface for months, the GUI lifecycle events
   start paying for themselves the moment the memory panel grows
   "show me what Sabrina is doing right now" badges. *Override:*
   start with avatar-only, add GUI later — but commit to the
   event names *now* so future code doesn't have to translate.

4. **Presence is publish-only after construction; surfaces never
   write back. (Recommended.)** A surface that wants to change
   identity (e.g., GUI's "Professional Mode" toggle) publishes a
   *request* event; Presence reduces it. Otherwise three surfaces
   with three opinions about mood is a real possibility, and the
   actor model loses its point. *Override:* none worth taking.

5. **Defer mobile / companion surface entirely until the desktop
   triad (voice + avatar + GUI) is dogfooded. (Recommended.)**
   The Rabbit / Humane lesson is that "another surface" is dead
   weight if the existing one isn't loved. Same for a phone
   Sabrina that doesn't beat the desktop one at anything in
   particular. *Override:* if mobile becomes the daily driver,
   the desktop is the companion, and the calculus inverts. Not
   today.

---

## Sources

[1] Apple — [Continuity features and requirements](https://support.apple.com/en-us/108046).
[2] Apple — [Use Handoff to continue tasks on your other Apple devices](https://support.apple.com/en-us/102426).
[3] Roznovat et al. — [ActressMAS: A .NET Multi-Agent Framework Inspired by the Actor Model](https://www.mdpi.com/2227-7390/10/3/382).
[4] Berdasco et al. — [User Experience Comparison of Intelligent Personal Assistants: Alexa, Google Assistant, Siri and Cortana](https://www.mdpi.com/2504-3900/31/1/51).
[5] Digital Applied — [AI Product Failures 2026: Sora, Humane & Rabbit R1](https://www.digitalapplied.com/blog/ai-product-failures-2026-sora-humane-rabbit-lessons).
[6] TechRadar — [With the Humane AI Pin now dead, what does the Rabbit R1 need to do to survive?](https://www.techradar.com/computing/artificial-intelligence/with-the-humane-ai-pin-now-dead-what-does-the-rabbit-r1-need-to-do-to-survive).
[7] Microsoft — [Multi-agent Reference Architecture](https://microsoft.github.io/multi-agent-reference-architecture/docs/reference-architecture/Reference-Architecture.html).
[8] Databricks — [Supervisor Agent Architecture: Orchestrating Enterprise AI at Scale](https://www.databricks.com/blog/multi-agent-supervisor-architecture-orchestrating-enterprise-ai-scale).
[9] VAEXPERIENCE — [The UX Fails of AI Tech: Rabbit R1 & Humane AI Pin](https://blog.vaexperience.com/the-ux-fails-of-ai-tech-rabbit-r1-humane-ai-pin/).
[10] Marko0Marky — [Live2d-Avatar-Ai (PyTorch + PyQt5 chat-driven Live2D)](https://github.com/Marko0Marky/Live2d-Avatar-Ai).
[11] DataStudios — [Pi AI mobile vs web: features, differences, and performance in 2025](https://www.datastudios.org/post/pi-ai-mobile-vs-web-features-differences-and-performance-in-2025).
[12] Park et al. — [Generative Agents: Interactive Simulacra of Human Behavior (memory stream / recency·importance·relevance)](https://dl.acm.org/doi/10.1145/3586183.3606763).
