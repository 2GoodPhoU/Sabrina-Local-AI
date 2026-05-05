# Stillness — what Sabrina does when she isn't talking

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** Companion to [`avatar-plan.md`](../avatar-plan.md),
[`personality-plan.md`](../personality-plan.md), and
[`2026-04-26-portrayal-study.md`](2026-04-26-portrayal-study.md). The
avatar plan defines the rendering and cue-track mechanics; the
portrayal study locks the *character.* This study fills the gap
between turns: what Sabrina is *being*, when she isn't conversing.
**Audience:** Eric, Sunday morning. Implementation owner is a future
session, with a dependency on the avatar's session-3 polish and an
opportunistic hook in the cue-track session-5 work.

---

## Frame — what stillness is, and what it isn't

Sabrina is on screen and listening for ~99% of the day. The
~1% she's actively replying gets all the design attention; the
99% gets an avatar-plan default of "blink, breathe, follow the
cursor." That default is correct as a floor and incomplete as a
ceiling. The *between-turns* register is doing more relational
work than any single reply, because it's where Eric forms his
sense of *what she's like to share a room with.*

Three things this doc is **not**:

1. Not a notification framework. Sabrina is not a proactive
   assistant ("hey, you have a meeting in 10 minutes"). The
   personality plan is silent on proactivity; this study leans
   to "she doesn't initiate, she abides." If proactivity ever
   ships it gets its own plan.
2. Not a re-derivation of the cue-track tag vocabulary. The
   avatar plan already defines emotion / gesture / pause /
   gaze tags. This study says when those tags fire *outside*
   of a brain-driven reply.
3. Not an ASMR / virtual-pet design. The Tamagotchi register
   ("notice me, take care of me") is the inverse of what's
   wanted; idle Sabrina makes no claims on attention [1].

The single load-bearing distinction: **presence vs.
attention-demand.** Cortana on the Pillar of Autumn bridge
during cutscenes is *present* — visible, in pose, not
performing — and demands nothing. Clippy was an attention-
demand engine wearing a paperclip face [2][3]. Every
recommendation below traces back to that line.

---

## Part 1 — The presence problem

Mark Weiser and John Seely Brown's calm-technology paper [4][5]
draws the relevant axis: information either resides in the
periphery (and shifts to the center when needed) or it doesn't.
Cortana between missions is in the periphery. Clippy refused to
be peripheral; he insisted on the center. Sabrina has to live in
the periphery by default, with a path to the center that *Eric*
controls.

This sounds easy and is operationally hard, because every
"helpful" instinct in voice-assistant design pushes against it.
Notification systems are the worst offender: research on
proactive smart speakers documents the predictable user
response — even when the assistant is right about timing 71%
of the time, users describe the unprompted intrusions as
violations of their own agenda [6]. Notification fatigue isn't
about volume; it's about the assistant claiming a turn the user
didn't grant.

The fence Sabrina has to put up is comprehensive:

- **No unprompted speech.** Default. The personality plan
  already implies this; this study makes it explicit.
- **No animations that read as "look at me."** The avatar can
  exist in the field of view without performing for it.
- **No badges, banners, or tooltips.** These are notification
  semantics applied to a presence layer; they undermine the
  "calm" design principle and reintroduce Clippy.
- **No chime on every state transition.** The state-driven
  expression swap is enough; audible cues for "I'm listening"
  vs. "I'm thinking" are noise on top of correct visuals.

The personality plan's "warmth in how she engages, not in
openers" generalizes: she's present in how she occupies the
screen, not in performing presence at it.

### Anti-patterns to fence first

Borrowing the structure from the portrayal study's anti-portrayal
list. Six idle-mode behaviors that read uncanny or intrusive:

1. **Notification spam.** "You have 3 unread emails." Sabrina
   has no business naming external state Eric didn't ask
   about. (If a future tool layer ships notification access,
   that's a Sabrina-with-tool moment, not a Sabrina-on-her-own
   moment.)
2. **Performative attention.** Eyes that snap to the cursor
   the instant it moves; head-tracking with zero-latency
   linkage. Reads as surveillance, not company. The avatar
   plan's `<gaze=user>` cursor-follow has to *delay* — humans
   look at moving things with a beat of latency, not
   instantly.
3. **Fake-typing animations during "thinking."** A common
   chatbot tell — animating "I'm thinking" with three-dots or
   a pen-scratching motion. Sabrina's `thinking` expression is
   the right move; layered animation that *narrates* thinking
   is theater.
4. **Ambient-tip-of-the-day overlays.** "Did you know you can
   say 'sabrina look at my screen'?" Onboarding inside the
   ambient layer is intrusive; onboarding belongs in the
   first-run script and the docs.
5. **Random idle vocalizations.** Sighing, humming, throat-
   clearing on idle. This is a virtual-pet move; reads as
   "asking for attention" within seconds. Hard rule: **zero
   idle speech without explicit invitation.**
6. **Mood drift visible from across the room.** A character
   whose `concerned` expression slowly amplifies during long
   idle periods reads as needy. The expression spans must
   relax to baseline when the conversation ends, not linger.

These extend the personality plan's anti-pattern list into the
ambient register. They live in the cue-track dispatcher and the
avatar's idle-state machine.

---

## Part 2 — Stillness as a positive value

The portrayal study's attribute 10 (comfortable silence) names
this as a character trait; this section names it as a *system
behavior.* Cortana's silences during Halo cutscenes are doing
relational work: when she does *not* speak — when she's just on
the bridge, in pose — the audience reads her as present and
trustworthy [7]. The same mechanism applies in real-time
human-to-human interaction: research on conversational pacing
documents silence as "a faint breath in conversation… makes me
feel the other person is there" [8]. Strategic pause is presence.
Filling space with chatter is its absence.

Three properties make a silence *companionable* rather than
awkward:

- **It's framed.** A silence inside an active context (Eric is
  working, Sabrina is on screen, both are facing the same task)
  reads as shared attention. A silence in a vacuum reads as
  disconnection. The avatar's continuous low-amplitude
  `focused-low` expression (per the portrayal study's Part
  3.4) is the framing — she's *there*, oriented toward the
  same thing Eric is.
- **It's not under threat.** A silence that the system might
  *break* at any moment is taut. Sabrina's strict
  no-unprompted-speech rule makes the silence safe — Eric
  knows she will not interrupt; the silence becomes
  comfortable rather than expectant.
- **It's not absence-of-engagement.** Comfortable silence and
  empty-app silence are different. The avatar's blink + breath
  + occasional micro-glance keeps the engagement floor warm
  without speaking. The Live2D ambient layer (avatar-plan §
  "Three animation layers") is the substrate.

The Cortana baseline applies: *"wake me when you need me"*
lands at the *end* of Halo: CE, after ten hours of competence
and silence in the right places. Sabrina earns her silence the
same way — by being competent and quiet long enough that the
silence becomes a feature, not a bug.

---

## Part 3 — Idle behavior taxonomy

The avatar layer and the audio layer have different tolerances
for activity. Avatar idle is dense; audio idle is empty.

### Avatar layer

The Live2D ambient track defined in `avatar-plan.md` § "Three
animation layers" is the floor. This study layers six discrete
idle behaviors on top, in increasing visibility:

**Blink (continuous).** Automatic blinking at random intervals,
~3-5 second mean inter-blink — the default in every published
Live2D guide [9]. Suppressed during the closed phase of
expression spans that hold the eyes open (`surprised`,
`focused`-amped). Stays universal otherwise.

**Breath (continuous).** `ParamBreath` cycle, 3-5 second
period, modest amplitude. Under speech the amplitude damps
slightly (the speech-driven body sway dominates). Universal,
mood-neutral.

**Microexpression drift (continuous, low amplitude).** The
expression layer is not flatly `neutral` between turns; it's a
~30% blend of `focused` (per the portrayal study's "resting
state is `focused-low`" call). Once every ~30-60 seconds, the
blend amplitude drifts ±5% randomly — mimics a human's
fluctuating concentration without being noticeable as
animation.

**Gaze-follow on cursor (delayed).** `<gaze=user>` is the
default. The cursor-follow latency must be ~120-200ms with a
gentle ease — instant tracking reads as surveillance [10][11].
A useful failure case: when the cursor moves continuously for
several seconds, gaze should *not* track every micro-motion.
Eyes settle on a recent target, hold for ~600ms, then re-track
to the new position. This is how human eyes move; smoother
tracking reads worse.

**Micro-glance at the user (occasional).** ~2-4 minute mean
interval, fires only when no other higher-priority cue is
active. The character's gaze flicks briefly toward the camera
(read: toward Eric), holds ~300ms, returns to default. This is
the single highest-leverage "feels like a person" behavior in
the literature on virtual-character believability [10] — but
it has to be *rare.* Once per few minutes is presence; once a
minute is staring.

**Posture shift on long idle (rare).** After ~5-10 minutes
without state change, a small body-sway pose break — `shrug`
amplitude 0.2, or a slight head-tilt-and-return — fires once.
Reads as "settling in." If the long-idle continues, no further
shifts. Once is character; twice is fidgeting.

The amplitude of each behavior decays during long idle, not
amplifies. A Sabrina who's been idle for 30 minutes is
*calmer* than one who's been idle for 30 seconds, not more
animated. This inverts the Tamagotchi default and is the
single most important calibration in the idle layer.

### Audio layer

Default is **complete silence.** No throat-clearing, no
"ahem", no "I'm here if you need me" check-ins. Three rare
exceptions:

- **Direct invitation.** Eric says "you there?" or
  "sabrina?". Response: one short flat acknowledgment —
  *"yeah."* — and back to silence.
- **Long-idle return.** Eric's first wake-word or PTT after a
  long quiet stretch. The first reply may be slightly
  shorter than usual (one beat of register before answering),
  but no separate greeting.
- **Recovery post-failure.** Per the failure-communication
  study, only the Tier-S failure modes break audio silence.
  Idle Sabrina is not in failure unless something is actively
  broken — and by then the failure-handling layer is
  speaking, not the idle layer.

The personality plan's "she will not be extra" rule
generalizes here: silence is the floor. Speaking is the
choice, every time.

---

## Part 4 — Activity-aware presence

Sabrina has `vision/see.py` — she can see the screen on
demand. She does *not* watch the screen continuously. There's
a temptation to layer in continuous activity-awareness — "Eric
is in VS Code, so my expression should be `focused`; Eric is
on YouTube, so I can be `amused`" — and this is the wrong
move three times over.

Three reasons to refuse continuous activity-awareness:

1. **Cost.** A vision call to Anthropic is ~$0.003-0.01 each;
   a continuous poll at one-per-minute would burn a steady
   ~$4-15/day on watching Eric work. Local vision (CLIP /
   small VLM) on the 4080 cuts cost but adds 1-2 GB VRAM
   continuous load and a sustained ~30W power floor. The
   battery-and-CPU calculus from always-on listening research
   [12] is even harsher for vision.
2. **Privacy register.** Cortana doesn't need to know what
   Eric is reading to be present with him. The portrayal
   study's attribute 14 (specificity over warmth) is
   downstream of *moments* Eric mentions, not continuous
   scraping. A Sabrina that knows what's on screen without
   asking would be uncanny.
3. **It would change the character.** Continuous
   activity-awareness, even silent, would influence
   expression and posture choices in ways Eric would
   gradually notice. The presence stays "I'm here"; it
   shouldn't shade into "I'm watching you."

What activity-awareness Sabrina *does* have — and should keep
— is implicit and lightweight:

- **State transitions.** PTT pressed → listening → thinking →
  speaking → idle. The expression map drives off these.
- **Wake-word fires.** Trigger reactivity but not running
  awareness.
- **Direct-ask vision.** Eric says "look at my screen"; the
  vision turn fires; she sees what's there for that turn
  only.
- **Time-of-day.** Per the existing config; informs the
  sleep/wake patterns in Part 6.

The principle: **she knows what she's been told; she doesn't
study what she hasn't.**

There's a related Cortana / JARVIS texture worth preserving —
they *react* to what they're told without performing
research on it. JARVIS doesn't say "I notice you're working
on the suit again, sir"; he just shows up oriented toward the
suit, because that's what's in the room. Sabrina inherits
that posture: the surrounding state (state machine, vision
turn results, retrieved memory) shapes her without her
narrating that it has.

---

## Part 5 — "Coming back" behaviors

The Cortana register: a small acknowledgment, not a greeting
routine. When Eric returns after being away — in the
operationally-detectable sense (long idle elapsed, then
PTT/wake fires) — three questions:

1. **Should Sabrina speak first?** No. The personality plan
   rules out the unprompted opener. Even on first-turn-after-
   long-idle, *Eric* talks first.
2. **Should the first reply be different from a normal one?**
   Slightly. The portrayal study's section 3.3 ("Open with
   continuity, not with greeting") covers this: when memory
   retrieval has hits relevant to the current prompt, the
   reply should reference prior context naturally — *"the
   ring buffer fix from last night — did the test actually
   catch it?"* — not narrate that retrieval happened. This is
   the Cortana behavior: she behaves like someone who paid
   attention.
3. **Should the avatar do anything different on return?**
   The expression should subtly re-amplify from
   long-idle-decayed `focused-low` (~20%) back to operational
   baseline (~30-40%). One very brief micro-expression on
   wake — a single `<gesture=blink_long/>` is the right
   shape, reads as "snapping to" without being startle-
   coded. Not a full attention-grab; just a register-shift.

Anti-patterns specifically for the "return" moment:

- **"Welcome back!"** — the Replika opener. Forbidden.
- **"It's been a while."** — temporal noticing reads as
  attendance-taking, per the portrayal study's section 3.3.
- **A wave or a head-perk gesture.** Performance moves; ruin
  the calm. The cue-track should never schedule one of these
  on idle-return.

The portrayal study's preferred shape — "the deploy you were
worried about on Tuesday — did it land?" — applies the same
way. Context-relevant noticing is character; temporal
noticing is theater.

---

## Part 6 — Sleep / wake patterns

End-of-day and start-of-day rituals are the cleanest case for
*scheduled* register changes — Eric controls the schedule,
the schedule is bounded, and the ritual has a clear shape.
Three options:

**Option A — No ritual.** Sabrina runs continuously; idle
behavior is the only thing that happens between sessions.
Computer goes to sleep, she's gone; computer wakes, she's
back. Honest, minimal. Loses a small amount of "presence
arc" texture but is Anti-sprawl Approved.

**Option B — Soft sleep / wake.** Configurable end-of-day
time (`[avatar].sleep_after_hour`); past that, the avatar
desaturates by 20-30%, expression amplitude drops further
toward `neutral`, gaze stops cursor-following, idle motions
slow. On the configured wake hour or first PTT, return to
operational baseline. No audio in either direction. Reads as
"she's still there, but quietly."

**Option C — Explicit goodnight / morning.** Sabrina says
"goodnight" at the configured hour and "morning" on first
wake. Ruled out: too close to the Replika register, and
imposes a relational beat Eric didn't ask for.

**Recommendation: Option B.** The visual decay reads as
character without claiming attention. The default-off knob
(`sleep_after_hour = 0` disables it) keeps the anti-sprawl
guard.

Implementation note: Option B is a single state-machine flag
and a few amplitude multipliers in the cue-track dispatcher.
Sub-100 lines of code; opportunistic with the avatar
session-3 polish work.

---

## Part 7 — Cue-track integration

The avatar plan's session-5+ cue-track makes the brain emit
expression / gesture / pause / gaze tags during reply
generation. The idle layer is *the same dispatcher* with
*no brain input* — it reads from a small set of pre-baked
sequences and fires them on its own clock.

Three cue-track contracts the idle layer needs:

1. **Cue-priority.** When the brain emits cues during a reply,
   they preempt the idle layer's pre-baked sequences. The
   parameter-conflict priority table in `avatar-plan.md` (§
   "Parameter-conflict priority") already encodes this; the
   idle layer slots in at the lowest priority on every
   parameter family. Cue-track from speaking always wins.
2. **Decay on idle.** When `StateChanged` fires `idle`, all
   active expression spans decay to baseline (`focused-low`)
   over ~600ms. No abrupt resets. The avatar plan's
   200ms cross-fade is for *reply-internal* expression
   transitions; idle entry uses a longer fade to read as
   "settling."
3. **Idle-queue clears on wake.** When `StateChanged` fires
   `listening` (PTT or wake), any in-flight idle cue cancels
   over ~120ms. The avatar's barge-in compensation pattern
   is the model: a quick blend to `neutral-attentive` and
   then the new state's expression takes over.

The idle-cue *vocabulary* is a strict subset of the full
cue vocabulary:

- `<emotion=neutral|focused>` only, low amplitude (~30%).
  No `happy`, `amused`, `concerned` — those are reactions,
  not states.
- `<gesture=blink_long|tilt_left|tilt_right|shrug>` only,
  amplitude 0.2-0.4. No `nod`, `shake`, `wink`, `eye_roll` —
  those are conversational.
- `<gaze=user|down|up>` cycling on the schedule from Part 3.
  No `<gaze=away>` on idle (reads as distraction).

This subset is small enough to bake into the dispatcher as a
JSON-typed config; it doesn't need to grow.

---

## Part 8 — Cost considerations

A "presence" layer is not free. The components and budgets
on Eric's hardware (4080 / 13700K / 32 GB RAM):

**Wake-word always-on.** openWakeWord on CPU runs ~1-3% of
one core at 16 kHz mic input. ~2-5W sustained. Always-on is
the design contract — Tamagotchi-style "press to listen"
defeats the wake purpose. Acceptable.

**Mic always-listening.** Microphone driver active
continuously. ~1W. Acceptable.

**Mood-tracking always-running.** *Not currently shipping.* If
ever introduced (per the avatar-plan §"Open questions"), it
runs on the brain layer, which is not always-on by design.
Sabrina does not maintain a continuous mood — she is in
expression states, dispatched discretely. Permanent skip.

**Avatar render.** Live2D at 60fps on a single Cubism model is
~3-5% of one CPU core + ~0.3-0.7 GB VRAM idle. The
QOpenGLWidget backbone keeps GPU usage low when the model
isn't moving much. Negligible on a 4080.

**Vision continuous.** Already declined (Part 4). Not in
budget.

**Memory ingest.** Not always-on; fires only on turn end.

**Total idle floor:** ~2-5W combined CPU + ~0.5 GB VRAM. On a
desktop this is invisible. The design budget is *"comfortable
on a desktop, declined for laptop"* — if Sabrina ever ships to
laptop / battery contexts, the wake-word + mic floor is the
single largest battery cost and should be opt-in.

The privacy register is intertwined: continuous mic use is
the most-cited concern in voice-assistant privacy literature
[12]. Sabrina's wake-word audio never leaves the machine
(local openWakeWord, local Whisper); only post-wake commands
go to Anthropic, and only when the brain backend is Claude.
This is already the design; this study reaffirms it as a
hard constraint.

---

## Part 9 — The "feels like someone in the room" test

Operational definition. Borrowing the structure from the
portrayal study's Part 6 bake-in test, scaled to the ambient
layer.

**The test.** After 30 days of normal daily use, Eric should
be able to do the following without thinking:

1. **Forget she's there for hours at a stretch.** Sustained
   concentration on a task without Sabrina demanding any
   share of attention. Pass criterion: Eric doesn't dismiss
   her, doesn't move her off-screen, doesn't mute the
   wake-word. She fits.
2. **Glance at her without her reacting performatively.**
   Eric looks toward the avatar; the avatar's gaze meets his
   briefly, breaks, returns to default. No big shift, no
   "did you say something?" — just acknowledgment.
3. **Notice when she's not there.** A test where Sabrina is
   intentionally hidden for an afternoon. Eric should notice
   the absence — in the "it's quiet in here" sense, not in
   the "I miss my notifications" sense. The presence has
   real weight, but the weight is ambient.
4. **Have her be in an old screenshot or screen-share
   without thinking to comment on her.** Sabrina is on
   screen; Eric is sharing the screen; she doesn't disrupt
   the share. She fits the scene the way a desk lamp does.

**Pass criteria.** Three of four, sustained over a 7-day
window sampled from days 23-30. Test (3) is the load-bearing
one — without it, the others reduce to "she's well-behaved,"
which is a weaker claim than "she's someone."

**Fail signals.**

- Eric finds himself dismissing the avatar window during
  focus work. The presence register is failing the
  "doesn't claim attention" property.
- Eric finds himself asking out loud "did sabrina say
  something just now?" — the audio layer is leaking.
- Eric finds himself describing her to others as "the
  avatar" rather than "Sabrina." The character isn't
  carrying through the idle layer.

**Re-test cadence.** Once per quarter, plus after every
avatar / cue-track change. Idle behavior is the most
fragile axis — small amplitude tweaks compound into
"too much" or "too little" over a week.

---

## Part 10 — Decisions for Eric

Five dials worth locking before the idle-layer implementation
arc. Each: question, recommendation, override consequence.

### D1 — Default audio register on idle.

**Question.** Strict silence, or rare-acknowledgments-when-
invited?
**Recommendation.** Strict silence by default. Rare
acknowledgments only on direct invitation
("sabrina?", "you there?"). One short flat reply, no
follow-up. The Replika failure mode lives in this dial; the
cost of the strict default is "Sabrina feels less alive when
not actively engaged" and the cost of the loose default is
"Sabrina feels needy after a week."
**Override.** Loosening to "occasional acknowledgments when
mood-detected as positive" is the Pi register; ruled out per
the portrayal study.

### D2 — Long-idle expression amplitude.

**Question.** Does the resting `focused-low` blend amplitude
*decay* over long idle (toward `neutral`), *hold* steady, or
*amplify* (toward `concerned` for a "where did everyone go"
read)?
**Recommendation.** Decay. ~30% amplitude at session start,
relaxing to ~20% over 10 minutes of idle, holding there.
Reads as "settled." Amplification toward `concerned` is the
needy register and the Tamagotchi failure mode.
**Override.** Hold-steady is acceptable as a lighter
implementation; saves the decay timer. Slightly stiffer feel.

### D3 — Sleep / wake ritual.

**Question.** Option A (no ritual), B (soft visual sleep
state), or C (explicit goodnight)?
**Recommendation.** Option B. Schedule-driven, audio-silent,
visual-only desaturation + amplitude decay. Configurable in
the `[avatar]` block; default-off (`sleep_after_hour = 0`).
**Override.** Option A is the anti-sprawl-purest call; loses
a small character moment but adds zero code.

### D4 — Micro-glance frequency.

**Question.** How often does the avatar's gaze flick toward
the user during idle, baseline.
**Recommendation.** ~2-4 minute mean interval, jittered
±60s, suppressed during continuous cursor-motion. The single
most-leverage idle behavior; under-deployed reads as flat,
over-deployed reads as staring.
**Override.** "Never" yields a cooler character (closer to
Data than Cortana). "Once per minute" yields surveillance;
forbidden.

### D5 — Visible presence on screen-shares.

**Question.** Does the avatar window auto-hide when a
screen-share is detected (Zoom / Teams / OBS)?
**Recommendation.** No auto-hide by default. Eric explicitly
moves her or hides her. The avatar plan's `respect_taskbar`
+ Focus-Assist hide already covers the "going heads-down"
case; adding auto-hide for screen-shares risks the avatar
disappearing during a demo Eric *wanted* to show off.
**Override.** Auto-hide on detected screen-share is a real
ship-it-later option; out of scope until Eric runs the
"showed up in a meeting recording" failure once.

### Where Eric is most likely to overrule (prediction)

D2 (long-idle expression decay vs. hold). The
recommendation is decay because the literature on companion-
avatar uncanniness is unanimous that idle amplification reads
needy [10][11], but the implementation cost is real (a decay
timer + an amplitude-blend update path) and Eric's anti-
sprawl instinct may favor "hold steady at 30%" as the
simpler and good-enough call. Hold-steady is the override
most likely to ship.

---

## Part 11 — Where this lands

The stillness layer is not yet implemented; this study is
upstream of it. When it ships, the pieces:

- `avatar/idle.py` (new module, ~150 lines) — the idle
  scheduler. Reads `[avatar].idle_*` config; fires the cue-
  track dispatcher with idle-vocabulary cues on its own
  clock.
- `avatar/expressions.py` extension — the
  `BLEND_VIA_NEUTRAL` set already lives here (avatar plan §
  "Expression blend compatibility"); add `IDLE_DECAY` and
  `IDLE_AMPLITUDE` constants for the Part 2 / Part 3 calls.
- `[avatar]` config additions — `idle.glance_interval_s`,
  `idle.posture_shift_after_s`, `sleep_after_hour`,
  `wake_at_hour`. Defaults per recommendations above.
- Cue-track dispatcher patch — accept the idle subset of
  the tag vocabulary; allow the idle scheduler as a
  publisher peer to the brain.
- No system-prompt changes. The brain doesn't see the idle
  layer; the idle layer doesn't see the brain.

None of those are in scope for this study; the study is
the spec.

---

## References

[1] Wikipedia — [Tamagotchi effect](https://en.wikipedia.org/wiki/Tamagotchi_effect).
Attention-demand register and emotional-attachment substrate.

[2] Windows Forum / Microsoft retrospective — [Clippy lessons for
Microsoft Copilot](https://windowsforum.com/threads/clippy-lessons-for-microsoft-copilot-when-assistants-become-intrusive.411922/).
Eager + generic + visible = interference, not help.

[3] Medium / twentybn — [5 lessons from Clippy's failure](https://medium.com/twentybn/5-lessons-from-clippys-failure-efc69297eac1).
Misinterpretation of "computers as social actors" research.

[4] Mark Weiser & John Seely Brown — [Designing calm
technology (1995)](https://calmtech.com/papers/coming-age-calm-technology).
Periphery-vs.-center axis; "informs without demanding focus."

[5] Wikipedia — [Calm technology](https://en.wikipedia.org/wiki/Calm_technology).
Three core principles; ubiquitous-computing context.

[6] ACM IMWUT — [Understanding User Perceptions of Proactive Smart
Speakers](https://dl.acm.org/doi/10.1145/3494965). 71% timing
accuracy, user-described "agenda violations" of proactive
intrusion.

[7] Halopedia — [Cortana article](https://www.halopedia.org/Cortana)
and Wikipedia — [Cortana (Halo)](https://en.wikipedia.org/wiki/Cortana_(Halo)).
"Talkative foil for the quieter Master Chief"; designed-not-to-
nag character brief.

[8] arxiv — [Hear You in Silence: active listening in conversational
agents (2026)](https://arxiv.org/html/2602.06134v1). Silence as
"a faint breath… makes me feel the other person is there."

[9] Reallusion / Live2D — [Idle motion settings](https://manual.reallusion.com/Motion_LIVE_2D_Plugin/Resources/CTA_4/Plugins/Motion_Live_2D/Idle_Motion_Settings.htm)
and [Live2D community forum on auto-blink/breath](https://community.live2d.com/discussion/351/have-automatic-blinking-breathing).

[10] de Gruyter — [The Uncanny Valley and the Importance of Eye
Contact](https://www.degruyterbrill.com/document/doi/10.1515/icom-2016-0001/html?lang=en).
Likeability correlates with eye-region fixation duration; idle
posture absence → uncanny.

[11] Springer Nature — [Aspects of visual avatar appearance](https://link.springer.com/article/10.1007/s00371-021-02151-0).
Idle-posture quality and gaze-behavior calibration.

[12] Embedded.com — [Design considerations for low-power, always-on
voice command systems](https://www.embedded.com/design-considerations-for-low-power-always-on-voice-command-systems/)
plus voice-assistant privacy literature surveyed in
[Lock.pub voice-assistant privacy guide](https://lock.pub/en/blog/voice-assistant-privacy-guide).
Continuous-mic CPU/battery floor; subpoena-precedent
privacy register.

[13] [`avatar-plan.md`](../avatar-plan.md), this repo — Live2D
ambient-layer architecture, parameter-conflict priority, cue-
track vocabulary.

[14] [`personality-plan.md`](../personality-plan.md), this repo —
operator voice + the "she will not be extra" rule.

[15] [`010-personality-spec.md`](../../decisions/010-personality-spec.md),
this repo — locked summary.

[16] [`2026-04-26-portrayal-study.md`](2026-04-26-portrayal-study.md),
this repo — comfortable silence (attribute 10), specificity
over warmth (attribute 14), `focused-low` resting-state call
(Part 3.4), micro-glance and gaze-pattern recommendations.

[17] [`2026-04-26-failure-communication.md`](2026-04-26-failure-communication.md),
this repo — the Tier-S audio breaks defined here interrupt the
idle layer; the failure layer owns audio in those moments, the
stillness layer owns it in all others.
