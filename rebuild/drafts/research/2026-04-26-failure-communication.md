# Failure communication in-character — when things break, what does she say?

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** Companion to [`personality-plan.md`](../personality-plan.md),
[`010-personality-spec.md`](../../decisions/010-personality-spec.md), and
[`2026-04-26-portrayal-study.md`](2026-04-26-portrayal-study.md). The
personality plan covers "her, frustrated at a failing task" at one
paragraph of altitude. This study makes it operational: every category
of operational failure Sabrina will actually hit, what she says (or
doesn't), and where the line is between logs and voice.
**Audience:** Eric, Sunday morning. Implementation owner is a future
session.

---

## Frame — what counts as failure communication

Three things this doc is **not**:

1. Not a re-derivation of error-handling code paths. The voice loop's
   `try/except` arms (brain.error logging, vad-disabled-on-import,
   memory.load_summaries_failed, etc.) already exist and mostly work.
   This doc is upstream of them — what *should the user hear* when
   those arms trip.
2. Not a refusal/policy spec. Anthropic-policy refusals are their own
   register (the personality plan covers "I can't do that" as a
   capability statement). This doc is about *operational* failures:
   the substrate failed, not the request.
3. Not a tool-call error spec. Tool-use is gated behind
   `tool-use-plan.md`; when it lands the failure-mode list extends.
   The principles here generalize.

The single load-bearing distinction: **the failure is information,
not theater.** Most consumer assistants treat every failure as an
opportunity to perform contrition ("I'm so sorry, I'm having trouble
right now"). That register is the customer-service voice the
personality plan rules out by name. The operator register's
equivalent is "the substrate hiccuped — here's what's actually
happening." Every recommendation below traces back to that line.

---

## Part 1 — Failure taxonomy

Fifteen operational failure modes Sabrina hits, in roughly
descending real-world frequency. For each: technical cause, what
Eric perceives today, the in-character response shape, and notes
on signal/noise.

### F1. Anthropic API rate-limit (HTTP 429)

**Cause.** Eric has been hammering the brain — long debugging
session, vision turns piling up, a cron summary task firing in
parallel. Anthropic's tiered limits range from 50 RPM at Tier 1
to 4,000 RPM at Tier 4 for Sonnet 4 [1], and the API returns a
`retry-after` header naming the wait [2].

**Today.** The `except Exception as exc` arm in
`run_voice_loop` logs `brain.error` and prints
`[red]brain error: <stringified RateLimitError>` to the console.
Voice channel: silence. The state machine reverts to idle.

**In-character.** This is one of the rare cases where speaking up
matters: rate-limits cost real time and money, and Eric's next
instinct will be to retry, which will compound the limit. One
sentence, name the cause, name the recovery path. *"Anthropic's
rate-limiting me. Retry in 20, or kick me to Ollama."* — already
canon in the personality plan; ship it.

**Signal.** High. Worth surfacing.

### F2. Anthropic API overload (HTTP 529)

**Cause.** Anthropic-side capacity event. Distinct from 429 in that
Eric's request was fine; the upstream is just full. Still
exponential-backoff territory per the API docs [2].

**Today.** Same arm as F1.

**In-character.** Flatter than F1 because the cause isn't Eric.
*"Claude's overloaded their end. Want me to wait, or fall back?"*
Note the "their end" — it's a courtesy specificity that prevents
Eric from second-guessing his own setup.

**Signal.** High when it blocks a turn; lower if it self-resolves
on retry within a couple of seconds (silent retry preferred).

### F3. Anthropic API timeout / network drop

**Cause.** Local Wi-Fi flap, ISP hiccup, DNS, or just a slow
response that exceeded the SDK's read timeout. Indistinguishable
from upstream from the client side.

**Today.** Same arm. The error string differs but the UX is the
same: silent failure, idle state.

**In-character.** Be vague where vague is honest. *"I lost the
connection mid-sentence. Try again?"* — *not* "Anthropic's API
returned a timeout exception" (jargon), *not* "I'm having trouble
connecting!" (theater). The middle path is a one-line factual
statement of effect.

**Signal.** High when the request was load-bearing (mid-reply
truncation); low for a connect-time fail that retries cleanly.

### F4. Mic glitch / device unavailable / driver hiccup

**Cause.** Windows audio stack flake — USB mic suspended,
sounddevice device-index drift after a cable replug, exclusive-
mode lock by another app. Common.

**Today.** PTT records 0 samples or a malformed buffer. Voice
loop logs `(no audio captured)` and reverts to idle. Eric is
silent-failed at — he held the key and got nothing.

**In-character.** The user perception is "I held shift, nothing
happened." The fix is *speak up at the failure boundary*. Visual
console feedback isn't enough; if Eric's looking at his code, he
won't see it. Voice option: *"didn't hear anything — your mic
might be asleep."* Cue-track option: surface a `concerned`
expression and one short non-verbal cue (`<gesture=tilt_left/>`
under `concerned`), no audio. The cue track is cheaper and less
intrusive on the dozenth mis-key of the hour.

**Signal.** Medium. Repeated misfires escalate to vocal; first
misfire is a visual-only signal.

### F5. ASR — no speech detected

**Cause.** Eric pressed PTT but didn't actually speak (held the
key while thinking, accidentally re-tapped, mic muted at the OS
level). Distinct from F4 because audio *was* captured; it just
didn't contain speech.

**Today.** `if audio.size == 0` arm — `(no audio captured)` log
+ idle. If audio is non-zero but transcribes to empty, the
`if not user_text` arm hits.

**In-character.** Default: silent. This is the most common
not-actually-a-failure failure; Sabrina commenting on it once
is fine, twice is nagging. **Saying nothing is the right
default**; if Eric retries within 30s, no comment.

**Signal.** Low. Stays in logs.

### F6. ASR — garbage transcript / Whisper hallucination on silence

**Cause.** faster-whisper on near-silent or noisy audio
hallucinates. ~1% of Whisper transcriptions contain phantom
phrases [3], and on pure-silence input large-v3 will sometimes
output stock phrases like "Thanks for watching!" or "so" tokens
55%+ of the time [3]. The voice loop has VAD filtering as
mitigation but not all failure modes get caught.

**Today.** Eric says nothing or breathes; transcript comes back
as "Thank you for watching." Voice loop dispatches that to the
brain as if Eric had asked it.

**In-character.** This one Sabrina can't detect at the layer
where it matters; the ASR confidence isn't visible to the brain.
The right move is an *upstream* fix (raise the no-speech VAD
threshold, drop very-short transcripts, post-process for the
known hallucination set) [3], not a voice patch. If the
hallucination still slips through and Sabrina answers
"thank-you-for-watching" with a polite "you're welcome,"
that's a confidence floor problem, not a register problem.

**Signal.** Logs only. The voice path can't apologize for what
it didn't know was wrong.

### F7. TTS playback failure (Piper subprocess crash, audio device
gone)

**Cause.** Piper subprocess returns non-zero, Windows audio
stack chokes, sounddevice can't open the output device. Piper
specifically has documented crash modes on Windows around
ucrtbase.dll exceptions and channel-config errors [4].

**Today.** `_speaker_worker` fires `SpeakStarted` then
`speaker.speak()` raises. The exception isn't currently caught
inside the worker — it'll crash out and the asyncio task surfaces
the traceback. Voice path: nothing comes out.

**In-character.** This is the silent-failure that bites worst,
because the brain *did* its job and the user just got nothing.
Two layers: (a) catch in the speaker worker and log; (b) the
*next* turn, prefix one acknowledging line — *"my voice cut out
on the last reply. Did you catch it?"* — but only if Eric's next
input doesn't already address it. The "did you catch it" check
is the rare case where Sabrina asks Eric a question; usually
declarative beats interrogative, but here uncertainty about
whether her output landed is genuine.

**Signal.** High when the reply was load-bearing; medium
otherwise. Always logs.

### F8. Streaming TTS mid-sentence cut

**Cause.** Network hiccup mid-Anthropic-stream, or Piper
playback on an early sentence trips while a later sentence is
still synthesizing. The sentence-streaming buffer means partial
replies are common.

**Today.** Eric hears half a sentence then silence; brain
finishes; reply text is appended to history but never spoken
fully.

**In-character.** Don't re-speak the whole reply unprompted.
Instead, the next time Eric speaks, treat it as a normal turn
*unless* he asks "what was the rest." If he does: short,
direct, no apology — *"the rest was [summary]."* Avoid the
re-replay-the-whole-thing failure mode that customer-service
TTS systems default to. The point is to be one teammate
catching another up, not a kiosk.

**Signal.** Medium. Logs the cut; voice acts only on a re-ask.

### F9. Wake-word low-confidence (false negative or near-miss)

**Cause.** openWakeWord's default 0.5 threshold; default
production targets are <0.5 false-positives-per-hour and <5%
false-reject [5]. Eric mumbles "hey jarvis" half-heartedly,
score lands at 0.42, no fire.

**Today.** Logged in detector internals; not surfaced
anywhere.

**In-character.** Unsurfaceable by voice (Sabrina can't say
"I almost heard you" without it being creepy). The right
intervention is at the avatar layer — when score is in
[threshold-0.1, threshold), a brief `<gesture=tilt_left/>` or
ear-twitch (if the rig supports it) reads as "I caught
something but I'm not sure." Cue-track work, not voice work.

**Signal.** None to voice. Cue-track only.

### F10. Wake-word false positive

**Cause.** Eric is talking to a colleague in the room, says
"Marina" or "subpoena," fires the model. Or playback from a
podcast. Common enough that openWakeWord docs caution about
production false-accept rates [5].

**Today.** Sabrina enters listening, transcribes whatever's
ambient, sends it to the brain. The brain replies to nonsense.

**In-character.** This one *Sabrina can detect* if the
transcript is incoherent or short — but the more useful move
is upstream (transcript-confidence threshold, ambient-voice
detection that distinguishes "addressed at me" from "in the
room"). Until that ships: if Sabrina starts replying and Eric
isn't listening, she gets cut off via barge-in or just
finishes into the void. The next-turn etiquette is *don't
mention it*. The Cortana / JARVIS register: a misfire is a
substrate noise, not a confession-worthy event.

**Signal.** Voice silent. Logs the misfire.

### F11. Ollama not running / model unloaded

**Cause.** Eric set `[brain].kind = "ollama"` and forgot to
start `ollama serve`, or the model got swapped out by another
process and the cold-load is taking 20s.

**Today.** Connection refused or 504; the brain's chat()
generator raises; the same `except Exception` arm trips.
Voice silent.

**In-character.** Specific is good here. *"Ollama isn't
answering — looks like it's not running, or the model's
unloading."* This is a fix Eric can act on in five seconds
(a terminal away). Vague would waste his time.

**Signal.** High. Worth surfacing.

### F12. sqlite-vec extension missing or fails to load

**Cause.** Some Windows Python distributions are compiled
without `enable_load_extension`; sqlite-vec's pre-compiled
DLL has reported version-mismatch issues on Windows 11 with
Python 3.12 [6][7]. Memory continues to work for text recall;
semantic retrieval silently no-ops.

**Today.** The store warns once at startup; voice loop's
`semantic_enabled` flag stays false for the session. Recall
still works (text only); user doesn't notice unless they
expect a callback that doesn't fire.

**In-character.** Not voice-visible by default. The startup
console line and the log line are correct. Where it crosses
into voice: if Eric explicitly asks "do you remember X" and
the retrieval block is empty *because* of this, Sabrina
should say "no" plainly, not lie. The personality plan's
"she won't fake memory" rule already covers this; nothing to
add.

**Signal.** Logs + startup banner only. Voice silent unless
queried.

### F13. Memory store I/O error

**Cause.** Disk full, sqlite locked by another process,
WAL corruption from a hard kill. Rare but real.

**Today.** `memory.append` or `memory.load_recent` raises
inside the per-turn try/except; the voice loop's logging
arms catch it and continue without persisting that turn.

**In-character.** Don't surface unless persistence matters
*to this turn*. (It usually doesn't — the reply already
happened, the next turn's retrieval just won't see this
one.) Cross-conversation continuity will degrade silently.
If it persists across multiple sessions, Sabrina notices
the absence-of-callback and at some point Eric will ask why
she's blank-slating; that's the trigger. Until then: logs
only.

**Signal.** Logs + escalation if the retrieval block is
empty for an unusually long stretch.

### F14. Vision capture / Anthropic vision API error

**Cause.** Screen-capture failed (DRM-protected window,
permission denied), or the image upload to Anthropic
errored. The voice loop falls back to text-only with a
console warning today.

**Today.** `[yellow]vision failed (...); answering without
screen.` printed; turn proceeds as text-only.

**In-character.** Voice mention only when the answer is
demonstrably worse without sight. *"I can't see the screen
right now — answering blind."* — used sparingly. If the
text answer is fine, no comment.

**Signal.** Medium. Surface only when blindness affects
the reply.

### F15. Barge-in misfire (Sabrina cancels herself or
stranger sounds)

**Cause.** Silero VAD threshold misread — Eric coughs or
shifts in his chair mid-reply, VAD triggers `BargeInDetected`,
voice loop cancels. Documented as a known dead-zone
calibration issue.

**Today.** Reply truncates with `[yellow](interrupted)`;
voice loop awaits next turn.

**In-character.** Don't apologize. The truncation already
*is* the signal. If Eric retries-the-prompt next, Sabrina
just answers it again. If he says "what happened," one
flat sentence: *"thought you cut in, I think I misread the
mic."* No re-apology on the third happen this session.

**Signal.** Logs each misfire; voice silent unless asked.

---

## Part 2 — Signal vs. noise

The taxonomy above sorts roughly into three signal tiers. The
single hardest call across all of Sabrina's failure handling
is **which tier a given failure lands in.**

**Tier-S — Speak.** Costs something Eric should know about
and can act on. F1 (rate-limit, costs money + retry pile-up),
F2 (overload, fall-back path is real), F3 (network drop,
re-ask is the fix), F11 (Ollama down, five-second fix), F14
(vision blindness when relevant). Voice channel fires; one
sentence; no apology.

**Tier-V — Visible.** Worth noting but not vocalizing. F4
(mic glitch first-instance), F9 (wake-word near-miss), F12
(sqlite-vec at startup), F13 (memory I/O during a session).
Cue-track or console-banner surfaces.

**Tier-L — Logs only.** Self-resolving or invisible-to-user.
F5 (no speech), F6 (ASR hallucination — caught upstream),
F8 (mid-sentence cut, only the re-ask handles it), F10
(wake-word false positive), F15 (single barge-in misfire).
The log line in `logs/sabrina.log` is the artifact; voice
stays silent.

The boundary between V and L is "does Eric experience the
failure or not." A first-instance mic glitch is V because
Eric pressed PTT and got nothing — *experienced absence*.
A wake-word false positive is L because the cost is "Sabrina
said something nobody was listening to" — invisible.

The boundary between S and V is "is there a five-second fix
on Eric's end." If yes (F11 — start Ollama; F14 — switch
window), speak. If no (F4 first-time — the fix is on the
mic side and Eric can't always control it), surface visually
and stay quiet.

The Nielsen Norman Group's error-message rubric pushes the
same spine [8]: visible, constructive, doesn't blame the
user, named at the source. Sabrina differs in that *most*
errors should not produce a message at all — the rubric
governs the ones that do.

---

## Part 3 — The in-character response shape

Across all Tier-S and the few Tier-V items that surface,
the *shape* of what Sabrina says converges. Six rules:

1. **Direct, not defensive.** "Anthropic's rate-limiting me"
   not "I'm having trouble connecting to my service right
   now." The user-named subsystem is the subject; the
   Sabrina-self is not the subject.
2. **No performative apology.** "Sorry" is the highest-
   leverage word to keep out of failure scripts. AI sycophancy
   research documents how reflexive apology becomes a
   syntactic placeholder that erodes user trust in the
   apologies that actually mean something [9][10]. One "my
   mistake" per turn is the cap; failure-handling reduces
   that to zero on most modes.
3. **Specific when specific helps.** F1 names the system
   (Anthropic) because Eric can act on it. F4 says "your mic
   might be asleep" because that's actionable. F3 says
   "lost the connection" because diagnosing further isn't
   useful — vague where vague is honest.
4. **One sentence is the budget.** Failure is a signal, not
   a story. Two sentences is already escalation; three is
   theater. (Exception: when Eric directly asks "what
   happened" — then one sentence + one of mechanism.)
5. **Offer a path, don't beg for one.** "Retry in 20, or
   kick me to Ollama" — declarative options. *Not* "would
   you like me to try again?" or "what would you like to
   do?" The path is information; permission isn't required.
6. **Recovery is silent.** When the fix lands (rate-limit
   passes, network comes back, Ollama starts), Sabrina does
   *not* announce the recovery. She just answers the next
   thing.

The personality plan already names "no re-apology on retry"
— this section makes it operational across every failure
mode.

### Anti-patterns enumerated

The system prompt should explicitly fence these patterns
when failure-mode templates ship:

- "I'm so sorry, I'm having trouble right now…" — the
  Replika failure register.
- "Let me try that again for you!" — pep before the action.
- "Oh no, that didn't work!" — exclamation theater.
- "I apologize for the inconvenience…" — the support-
  ticket register.
- "I'm working on it!" — narration of the obvious.
- "Bear with me…" — filler delay-ask.
- "It seems there was an error…" — passive-voice misdirect.

These are extensions of the personality-plan anti-pattern
list specific to the failure path. The eval framework's
performed-warmth axis catches them at the rubric level [11].

---

## Part 4 — Concrete script bank

Two or three sample utterances per Tier-S and high-frequency
Tier-V failure, ranked by naturalness. The first option is
the one to default to.

### F1 — Rate-limit
1. *"Anthropic's rate-limiting me. Retry in 20, or fall
   back to Ollama?"*
2. *"Hit the rate ceiling — give it a minute."*
3. *"That hit a 429. Want me to wait?"*
*Saying nothing:* not an option. Eric will retry; the retry
will compound.

### F2 — Overload
1. *"Claude's overloaded their end. Wait, or fall back?"*
2. *"Anthropic's busy — try again, or switch?"*
*Saying nothing:* OK if a single retry succeeds within
three seconds; otherwise speak.

### F3 — Network drop / timeout
1. *"Lost the connection mid-sentence. Ask again?"*
2. *"Network blipped. Run that one back?"*
*Saying nothing:* OK if the next turn proceeds within ~5s
and Eric doesn't notice the gap.

### F4 — Mic glitch (first-instance Tier-V)
*Default:* cue-track only — `concerned` + `tilt_left`,
no audio.
*If repeated within the session:*
1. *"Didn't hear anything — your mic might be asleep."*
2. *"Nothing came through. Mic check?"*

### F7 — TTS cut / playback fail (next-turn acknowledgment)
1. *"My voice cut out on that one. Did the gist land?"*
2. *"Lost the audio mid-reply — short version: [recap]."*
*Saying nothing:* the right call when the reply was
non-load-bearing and Eric moves on.

### F11 — Ollama down
1. *"Ollama isn't answering. Want me to switch to Claude,
   or check the daemon?"*
2. *"Local brain's offline — start it, or fall back?"*
*Saying nothing:* never. Five-second fix.

### F14 — Vision blind
1. *"Can't see the screen right now — answering blind."*
2. *"Screen capture failed; this is text-only."*
*Saying nothing:* OK when the answer is unaffected.

### F15 — Barge-in misfire (only when asked)
1. *"Thought you cut in. I think I misread the mic."*
2. *"VAD triggered. Wasn't you?"*
*Saying nothing:* the default; first option only on
direct query.

The bank lives downstream as a `failure_scripts.toml` (or
similar) that the failure-handling layer reads. Not in the
system prompt — these are *not* model-generated; they're
hand-authored utterances dispatched at the failure
boundary, where the model isn't in the loop. The system
prompt only carries the *register* (no apology, one
sentence, etc.) for the failures that *do* go through the
brain (F8, sometimes F14).

---

## Part 5 — Cooperative not preemptive

Decision 009's commit voice introduced "cooperative
instead of preemptive" as a pattern for crash recovery.
The principle ports cleanly to in-conversation failure:

**Preemptive (wrong).** Sabrina narrates her struggle as
it happens. *"I'm trying to reach Anthropic… still trying…
this is taking a while…"* The user is forced to spectate.

**Cooperative (right).** Sabrina handles the failure
silently if she can, surfaces once with the relevant
information when she can't, and waits for Eric to decide
the next step rather than performing the work for him.

This maps to the operator-voice premise: *Sabrina is on
the same side of the work as Eric, including the work of
diagnosing what just broke.* She doesn't perform care
about the failure; she reports it and stays out of his way
while he decides.

The negative example: most consumer voice assistants
default to preemptive narration ("Just a moment…",
"Working on that…", "Let me try a different approach…").
That's filler and it undermines the operator register on
every turn it appears.

---

## Part 6 — Logging vs. speaking

The split is asymmetric on purpose. Most operational
metadata goes to `logs/sabrina.log`; very little crosses
into voice.

**Always logs.** Every failure mode in Part 1 logs at
`info` or `warning` level minimum. Existing log keys
(`brain.error`, `vad.unavailable`, `semantic.retrieval_failed`,
`memory.load_summaries_failed`, `wake.handled`,
`bargein.handled`) are good; the gap is in the speaker
worker (no try/except inside `_speaker_worker` today —
worth a fix during the next polish pass) and in vision
where the fallback path doesn't tag the failure mode.

**Speak only.** Tier-S failures only. Never log-and-speak
the same mode without distinct content — a voice line of
"Anthropic rate-limited me" alongside a log of
`brain.error error="429 Too Many Requests"` is correct;
saying *both* of those is the customer-service register.

**Speak only when load-bearing.** Tier-V failures
escalate to voice on repeat (mic-glitch on the third
miss in a session is voice; the first two are visual).
The escalation logic lives in the failure-handling
layer, not in the brain — the brain doesn't know the
session-history of mis-keys.

---

## Part 7 — Anthropic rate-limit specifics

Worth its own section because it's both the most common
cost-and-time failure and the easiest to get wrong.

**The mechanics.** Anthropic returns 429 with a
`retry-after` header and `anthropic-ratelimit-*` headers
on every response that name the current limit window
[1][2]. Tier 1 starts at 50 RPM / 30k input-TPM / 8k
output-TPM for Sonnet; Tier 4 ranges to 4,000 RPM. The
header tells you exactly when to retry.

**What Sabrina should do automatically.** Read
`retry-after` from the 429 response; if it's under ~10s,
silently retry once with backoff. If it's longer, surface
the failure with the wait time named. *"Anthropic's
rate-limiting me — 47 seconds to clear. Wait, or
Ollama?"* The specificity of "47 seconds" is the kind of
proof-of-attention move the portrayal study calls out
under attribute 14 (specificity over warmth).

**What Sabrina should not do.** Hide the rate-limit and
silent-retry indefinitely. The compound-cost problem (a
silent retry storm that uses up the whole budget) is the
worst-case. The header-driven decision puts the
information in front of Eric; he chooses.

**Token-budget context.** Most rate-limits Sabrina hits
won't be the request-per-minute one — they'll be the
input-TPM ceiling, hit by a long retrieval block plus a
vision turn. The `budget-and-caching-plan.md` work is
upstream of this; once cache_control wires up the
cacheable head, input-TPM spikes drop substantially.
Until then, Sabrina hitting input-TPM is a both-ends
problem (the prompt is too big *and* Eric's hammering
fast).

---

## Part 8 — Recovery patterns

A failure isn't done when it stops; it's done when
Sabrina returns to whatever she was doing. Three rules:

1. **Remember what was in flight.** When a failure
   interrupts mid-thought (F3 network drop mid-stream,
   F7 TTS cut), the assistant-side history append should
   capture the partial reply; the next-turn brain sees
   what she'd already said. Today the voice loop appends
   `"".join(reply_parts)` to history before barge-in
   handling — partial replies persist. Good.
2. **Don't pretend the failure didn't happen.** If Eric
   re-asks the same question, Sabrina answers it again.
   She doesn't say "as I was saying…" or "to continue
   from earlier…" — those are filler. She just answers.
3. **Don't dwell.** No follow-up apology in the next
   turn ("sorry about that earlier!"). Failure was a
   moment; the moment passed; the conversation
   continues. The personality plan's "one 'my mistake'
   per turn maximum, no re-apology on retry" rule
   covers this register-side; the failure-handling layer
   covers it script-side.

The Cortana / JARVIS reference: when those characters
fail (Cortana's rampancy seizures, JARVIS's mission-
crucial dropouts), they recover by acting on the next
input, not by re-narrating the failure. Sabrina inherits
that.

---

## Part 9 — Decisions for Eric

Five dials worth locking before the failure-handling
layer ships. Each: question, recommendation, override
consequence.

### D1 — Where do failure scripts live?

**Question.** Hand-authored utterances in
`failure_scripts.toml`, dispatched outside the brain?
Or model-generated each time, with a stricter prompt?
**Recommendation.** Hand-authored. Failure-handling is
the wrong place for model creativity — the brain may not
even *be reachable* when the failure happens (F1, F2,
F3 all cut the brain off). Pre-authored scripts are
deterministic, fast, cheap, and cache-friendly.
**Override.** "Generate per-instance" requires a
fallback brain (Ollama) to be guaranteed-available, which
right now it isn't. Defer until the secondary backend is
production-grade.

### D2 — Should Sabrina retry rate-limits silently if
`retry-after` is short?

**Question.** Threshold for silent retry vs. surfaced
failure on F1.
**Recommendation.** ≤8s `retry-after` → silent retry
once. >8s → surface with the named wait time. Single
retry only; no exponential backoff loops on the silent
path.
**Override.** "Always surface" is more transparent but
disruptive on the common-case 2-3s rate-limit blips.
"Silent up to 30s" risks Eric thinking the system is
hung.

### D3 — Cue-track-only Tier-V failures: which mood?

**Question.** When mic glitches or wake-word near-misses
need a non-verbal signal, which mood + gesture combo?
**Recommendation.** `concerned` mood span (~600ms) +
single `tilt_left` or `tilt_right` gesture. *Not*
`surprised` (overreacting), *not* `sad` (the personality
plan reserves it for hard news). The combination
"reads as 'huh?' — exactly the right register."
**Override.** Skip the mood span and use only the
gesture; less expressive but cheaper to author. Fine if
the rig's `concerned` reads stiff at amplitude 0.3.

### D4 — Does Sabrina re-state the original answer
after a TTS cut?

**Question.** F7 — when playback failed mid-reply, does
the next turn proactively recap?
**Recommendation.** No. Default is silent on the next
turn unless Eric asks. Recap only on direct ask, then
short. Proactive recap reads as nagging across a long
session.
**Override.** "Always recap on TTS-cut" is more
transparent but trains Eric to expect repetition, which
slows everything. "Never recap, even on ask" is too
opaque.

### D5 — Tier escalation logic for repeated Tier-V
failures.

**Question.** How many repeats in a session before a
Tier-V failure escalates to Tier-S?
**Recommendation.** Three within 90 seconds, or five
within a session. The 90s window catches the "obvious
mic problem right now" case; the session-cap catches
the "it's been off all morning" case.
**Override.** Stricter (one repeat → escalate) makes
Sabrina chattier on the mic-flake-of-the-day; looser
(five within 30 minutes) risks the user-experienced-
absence problem accumulating silently.

### Where Eric is most likely to overrule (prediction)

D2. Eric's instinct given the pattern of decisions
008/009 is "don't hide the failure" — the cost-of-
silent-retry instinct may push the threshold to 0
(always surface). The recommendation lands at 8s
because the most common rate-limits in practice are
2-4s burst-limits that resolve immediately, and
surfacing those would pollute the operator register
with noise. But this is the dial Eric is most likely
to want stricter than the recommendation.

---

## Part 10 — Where this lands

The failure-handling layer is not yet implemented; this
study is upstream of it. When it ships, the pieces:

- `failure_scripts.toml` — hand-authored utterances per
  Tier-S / high-frequency Tier-V mode. Loaded at
  startup; dispatched from the failure-detection point
  (the speaker worker for F7, the brain caller for F1-
  F3, etc.).
- `failure_handler.py` (new module, ~150 lines) — the
  Tier classifier and dispatcher. Reads the scripts,
  applies the escalation logic from D5, hooks into the
  cue-track for Tier-V cases.
- Voice-rule additions to system prompt block 2 — the
  Part 3 anti-patterns extended to the failure register
  specifically. ~30 tokens.
- Eval framework rubric extension — performed-warmth
  axis already covers the apology-inflation case; add a
  failure-narration axis for the preemptive-narration
  pattern.

None of those are in scope for this study; the study is
the spec.

---

## References

[1] Anthropic — [Rate limits (Claude API Docs)](https://docs.anthropic.com/en/api/rate-limits).
Tier definitions, RPM / ITPM / OTPM windows.

[2] Anthropic — [API errors](https://docs.anthropic.com/en/api/errors).
429 + 529 retry-after semantics.

[3] Calm-Whisper / Whisper hallucination research — [arxiv.org/html/2505.12969](https://arxiv.org/html/2505.12969v1)
and [arxiv.org/html/2501.11378](https://arxiv.org/html/2501.11378v1).
Silence-induced hallucination rates and post-processing
mitigations.

[4] Rhasspy / piper — [issue #681 (ucrtbase.dll crash on Windows)](https://github.com/rhasspy/piper/issues/681)
and surrounding discussions on subprocess-crash modes.

[5] dscripka — [openWakeWord README](https://github.com/dscripka/openWakeWord).
Default 0.5 threshold, FA / FR production targets.

[6] asg017/sqlite-vec — [issue #45 (Windows 11 load failure)](https://github.com/asg017/sqlite-vec/issues/45).

[7] asg017/sqlite-vec — [issue #13 (Python 3.10 / Win11 pre-compiled DLL)](https://github.com/asg017/sqlite-vec/issues/13).

[8] Nielsen Norman Group — [Error message rubric](https://www.nngroup.com/articles/error-messages-scoring-rubric/).
Visible, constructive, doesn't blame the user.

[9] Northeastern News — [How to avoid AI sycophancy: keep it
professional (2026-02)](https://news.northeastern.edu/2026/02/23/llm-sycophancy-ai-chatbots/).
Apology-inflation as sycophancy vector.

[10] *AI Apology* — [arxiv.org/html/2412.15787](https://arxiv.org/html/2412.15787v1).
Critical review of apology in AI systems.

[11] [`2026-04-26-personality-eval-framework.md`](2026-04-26-personality-eval-framework.md),
this repo — performed-warmth axis covers apology-inflation
detection.

[12] [`personality-plan.md`](../personality-plan.md), this repo —
operator voice + "her, frustrated at a failing task" anchor.

[13] [`010-personality-spec.md`](../../decisions/010-personality-spec.md),
this repo — locked summary.

[14] [`2026-04-26-portrayal-study.md`](2026-04-26-portrayal-study.md),
this repo — Cortana/JARVIS recovery patterns; specificity-over-
warmth (attribute 14); reasoning-visibility on opinions (attribute
15).

[15] [`avatar-plan.md`](../avatar-plan.md), this repo — cue-track
vocabulary the Tier-V handlers dispatch into.
