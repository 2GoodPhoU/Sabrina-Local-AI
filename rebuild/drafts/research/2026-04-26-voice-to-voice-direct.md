# Voice-to-voice direct architecture — April 2026

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** Should Sabrina's voice loop ever skip the brain-LLM-text
round-trip in favor of an audio-token-in / audio-token-out model? In
April 2026 the V2V landscape has matured enough — OpenAI's Realtime
API, Kyutai's Moshi, Sesame's CSM, Pocket TTS — that a real comparison
is possible. This doc names the trade-offs and proposes how (and
whether) to bolt V2V into a system that already exists.

**Anchor:** Sabrina's current pipeline is mic → faster-whisper STT →
Claude/Ollama text → Piper TTS. Decision 002 picked Piper for
sub-second TTFA on CPU; decision 003 picked faster-whisper for
~4× speedup over reference Whisper; decision 010 anchored the
personality on a brain-side system prompt. Pass-1 validation hits
~1.6s warm first-audio. The
[stack-alternatives survey](2026-04-25-stack-alternatives-survey.md)
covered TTS / ASR / brain alternatives within the cascade; this doc
asks the upstream question.

**Audience:** Eric, Sunday morning.

---

## What "voice-to-voice direct" means in 2026

Two architectures, and a hybrid that is increasingly real.

**Cascade (current Sabrina).** Audio → STT → text-LLM → TTS → audio.
Four hops, each with its own latency floor and quality ceiling.
The text-LLM step is where reasoning, tool use, and memory retrieval
live. The TTS step is where prosody and timbre live. They are
independent, debuggable, swappable.

**Voice-to-voice direct (V2V).** Audio is encoded into discrete
audio tokens via a streaming neural codec (Mimi for Moshi, RVQ
variants for the others); the LLM consumes audio tokens and text
tokens jointly; output is audio tokens that decode back to waveform.
Single forward pass for the conversational turn. The speech-and-text
foundation-model framing is laid out in
[Moshi's tech report](https://arxiv.org/html/2410.00037v2): Mimi as
the codec, the LLM trained on parallel "user audio" and "Moshi
audio" streams plus inner-monologue text. Gemini Live, ChatGPT
Advanced Voice Mode, OpenAI's Realtime API, and Kyutai Moshi all
implement variations of this architecture
([OpenAI Realtime API intro](https://openai.com/index/introducing-the-realtime-api/),
[gpt-realtime production launch](https://openai.com/index/introducing-gpt-realtime/)).

**Hybrid (where production deployments are landing in 2026).** S2S
for short conversational turns — greetings, follow-ups, casual
exchanges — and a cascade fallback for tool calls, RAG lookups, and
long reasoning. The
[AssemblyAI 2026 voice-stack writeup](https://www.assemblyai.com/blog/the-voice-ai-stack-for-building-agents)
and the
[Inworld voice-platforms 2026 survey](https://inworld.ai/resources/best-voice-agent-platforms)
both report this is the dominant production pattern: S2S for the
prosody-sensitive moments, cascade for the work.

---

## Latency — what each path actually delivers

The cascade's first-audio-out latency is the sum of (STT decode for
the captured turn) + (text-LLM time-to-first-token) + (TTS
synthesis-to-first-audio of sentence one). Sabrina's pass-1
validation puts this around 1.6 s warm.

V2V latency floors are dramatically lower:

- **Moshi.** Theoretical 160 ms (80 ms Mimi frame + 80 ms acoustic
  delay), practical 200 ms on an L4
  ([Kyutai Moshi repo](https://github.com/kyutai-labs/moshi)).
- **OpenAI Realtime / gpt-realtime.** 300–500 ms typical
  end-to-end response latency
  ([gpt-realtime announcement](https://openai.com/index/introducing-gpt-realtime/),
  [OpenAI realtime guide 2026](https://crazyrouter.com/en/blog/openai-realtime-api-complete-guide-2026)).
  Production deployments report median 2.24 s on real calls — the
  best-case is the API's, the median is the network's.
- **Sub-500 ms is the documented threshold for "feels real-time"**
  ([Inworld 2026 production-quality threshold](https://inworld.ai/resources/best-speech-to-speech-apis));
  cascades that hit ~1.5 s feel responsive enough for an assistant
  but unmistakably "robot pacing" compared to V2V.

The latency win is real and not subtle. It's the single most
material thing V2V buys you for the cost of basically everything
else.

---

## Quality trade-offs — reasoning vs. prosody

V2V models in 2026 reason worse than text-LLMs of the same compute
class. Moshi's
[paper](https://kyutai.org/Moshi.pdf) is explicit that the model is
~7B-class on a backbone tuned for audio rather than text reasoning;
benchmark tables show it lagging text-only LLMs of similar size on
MMLU-style evaluation by significant margins. Open-source CSM-1B is
explicitly framed by Sesame as a *speech generation* model, not a
reasoning engine
([Sesame uncanny-valley writeup](https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice),
[CSM repo](https://github.com/SesameAILabs/csm)). The OpenAI
Realtime API is closer in raw reasoning to GPT-4o because it shares
the backbone, but function-calling reliability still trails text-API
GPT-4o
([gpt-realtime ComplexFuncBench score](https://openai.com/index/introducing-gpt-realtime/)
of 66.5 vs. text-LLM ceiling).

In the other direction, V2V models have unmistakably better prosody.
Sesame's CSM is the canonical demonstration: the model emits
emotionally-aware speech with pitch variation, conversational rhythm,
disfluencies, breathing patterns, and tone shifts that match the
context history
([CSM technical analysis](https://www.flowhunt.io/blog/breaking-the-uncanny-valley-sesames-conversational-ai-voice-models/)).
The "she sighs" or "her voice catches" moments that the
[portrayal study](2026-04-26-portrayal-study.md) names as
load-bearing for Sabrina's Cortana-like earned-warmth come naturally
to V2V; they are physically not in Piper's output space, which
synthesizes from text + a fixed length-scale knob and emits
roughly-uniform prosody.

The trade is sharp: V2V wins on the layer where Sabrina's
*personality* lives; cascade wins on the layer where Sabrina's
*reasoning* lives.

---

## Personality projection

V2V models tend to ship with stronger built-in defaults that are
harder to prompt-shape. The Maya / Miles voices in Sesame's demo are
characterful in a way that survives system-prompt overrides; the
[Sesame personality analysis](https://www.techjays.com/blog/the-dawn-of-believable-ai-voices-a-deep-dive-into-sesames-conversational-speech-model)
makes this explicit — personality is partly trained-in, not
purely prompted. OpenAI Realtime exposes a small set of named
voices and limited emotional/style control via system prompt; the
voice itself has its own residual identity. Moshi has only one
trained-in speaker; cloning is in the roadmap, not in the open
release.

Sabrina's design (decision 010 + the portrayal study) is a deliberate
character — register, anti-patterns, audience modes, and a sober
adversariness that is *not* the default register most V2V models
ship with. Piper-on-text gives you a cleanly factored stack: the
brain emits Sabrina's words; Piper says them in a chosen voice. V2V
collapses those decisions into one trained artifact, and the
artifact's defaults are louder than the prompt can usually shout
over.

That's the load-bearing risk. V2V buys prosody at the cost of
ceding *some* of "Sabrina is herself" to "Sabrina is what
OpenAI/Sesame/Kyutai's defaults said this voice does today."

---

## Hybrid architectures — what real deployments are doing

The
[Inworld 2026 platforms survey](https://inworld.ai/resources/best-voice-agent-platforms)
and the
[AssemblyAI voice-stack 2026 reference](https://www.assemblyai.com/blog/the-voice-ai-stack-for-building-agents)
agree on the dominant production pattern in 2026:

- **S2S for short, prosody-sensitive turns.** Greeting, casual
  back-and-forth, emotional moments, "earned warmth spike."
- **Cascade for tool-using, RAG, long-reasoning turns.** Calendar
  read, memory retrieval, anything where the response budget is
  >2 sentences or schema-typed output is needed.
- **Routing rule.** Length / complexity heuristic on the text-LLM's
  prediction of its own next response; explicit user signal ("walk
  me through this carefully" → cascade); tool-use intent → cascade.
- **Inworld / Vapi-style routers.** A reasoning layer in front of
  the actual LLM call that picks the path
  ([Inworld Router writeup](https://inworld.ai/resources/best-speech-to-speech-apis)).

That maps cleanly onto Sabrina's existing structure: the text-LLM
decision (Claude vs. Ollama vs. router) is already a
single-conditional in the brain protocol; adding a third path
("V2V for this turn") is a `Brain` implementation, not an
architecture change. The brain protocol's `chat()` already returns
`StreamEvent`; the V2V path would emit a different stream type
(audio-token deltas instead of text deltas), which the speaker
worker can drain straight to sounddevice without going through
Piper.

---

## Local V2V — what runs on the 4080?

The interesting near-term option is
[Kyutai Moshi](https://github.com/kyutai-labs/moshi). Three
inference stacks: PyTorch (research), MLX (Apple), Rust
(production). The 7B-class Moshi runs on a 4080's 16 GB VRAM with
fp16 weights, has demonstrated 200 ms first-audio on an L4 GPU,
and is end-to-end open
([Kyutai Pocket TTS](https://kyutai.org/tts) shows the trajectory
toward smaller variants — 100 M params, runs on CPU).

The realistic Sabrina path is "Moshi Rust binary as a sidecar
process; Sabrina speaks to it over an audio-token WebSocket."
That's roughly the pattern Kyutai already documents.

CSM-1B is open-sourced too
([Sesame CSM open-source announcement](https://learnprompting.org/blog/sesame-conversational-speech-model-open-sourced))
but framed as a TTS replacement, not a full V2V stack. It would
slot into the cascade in place of Piper, not replace the whole
loop.

OpenAI Realtime / gpt-realtime needs no local resources but **the
mic audio leaves the box**. For the privacy posture the
[threat model](2026-04-26-threat-model.md) just landed, that's the
single hardest pill: cloud V2V means continuous audio over the
wire, not just transcripts. ZDR helps but doesn't fully address
the "audio is more revealing than transcript" issue.

---

## Cost — daily-driver economics

OpenAI Realtime / gpt-realtime in April 2026: $0.06 / minute of
audio input, $0.24 / minute of audio output
([OpenAI pricing 2026](https://developers.openai.com/api/docs/pricing),
[TokenMix breakdown](https://tokenmix.ai/blog/gpt-4o-realtime-audio-api-guide-2026)).
Cached input drops to $0.02. Eric's expected usage as a daily
driver — call it 30 minutes of conversation a day, ~10 minutes
output — runs $0.06 × 30 + $0.24 × 10 = $4.20/day. Roughly
$125/month. Compare to current cascade: Claude Sonnet on an
average turn is in the $0.01–$0.05 range, Whisper is local,
Piper is local; daily cost is well under a dollar. V2V via
OpenAI is **40–100×** the cascade cost.

Local V2V via Moshi is "free" at the marginal level (electricity)
once it's installed.

---

## Sabrina-specific implications

The
[avatar / cue-track plan](2026-04-26-avatar-cue-track-implementation.md)
and the
[portrayal study](2026-04-26-portrayal-study.md) both assume
Piper-driven amplitudes for lip-sync and a brain-emitted
`<emotion>...</emotion>` tag stream as the cue track. Both
assumptions go fuzzy under V2V:

- Piper amplitudes don't exist; the lip-sync source is the
  audio-token stream itself, decoded back to waveform. Live2D
  drivers can read the audio amplitude envelope post-decode the
  same way, but the *cue track* is no longer a clean text-side
  signal — emotion lives implicitly in the audio.
- Tag-based emotion cues would need to be emitted *into the audio*
  by the V2V model, which is not how current V2V models
  factor.
- The Cortana-style "earned warmth spike" moments where prosody
  matters most are exactly where V2V earns its keep — but they're
  also exactly the moments the personality plan wanted explicit
  control over.

That doesn't kill V2V as a future option; it argues that V2V should
be *additive*, behind a feature flag, used only for the moments
where prosody pays for the lost personality control. Tearing out
the cascade to put V2V at the center would cost more than it buys
for an assistant whose primary value is reasoning, memory, and
(eventually) tool use.

---

## Recommendation

**Keep the current text-cascade pipeline as the baseline. Treat V2V
as a future feature flag for specific moments, not as an
architectural rewrite.**

Concretely:

1. **Don't put V2V on the critical path for any of Sabrina's planned
   components.** Tool-use, vision, semantic memory, and the avatar
   all proceed on cascade assumptions.
2. **When the V2V landscape stabilizes** — open-weight prosody-
   competitive models with promptable persona control, or OpenAI
   Realtime with a per-call ZDR option — **prototype a `MoshiBrain`
   or `RealtimeBrain` Brain implementation** that the voice loop
   can switch to per-turn, with the speaker worker draining audio
   tokens straight to sounddevice instead of through Piper.
3. **Reserve V2V for prosody-mattering moments.** Greeting on
   start-up, "earned warmth spike" replies the personality plan
   surfaces, casual chit-chat. Everything else (tool calls, long
   reasoning, vision turns) stays on the cascade.
4. **Don't lock a V2V-first architecture until at least Q4 2026.**
   The space is moving fast; Moshi's 200 ms latency floor and
   OpenAI Realtime's $0.24/min output cost are both likely to
   improve substantially in the 6–12 months following this writeup.
   Locking now is rebuilding a moving target.

---

## What surprised me

**The cost gap is wider than I expected.** OpenAI Realtime at
$0.24/min output is genuinely "30 minutes of conversation a day
costs $125 a month," which is enough money that for a personal
daily-driver project it changes the answer. Even with cached
input ($0.02) it's an order of magnitude over the cascade.

**Moshi's local-runnability is more real than I expected.** A 7B
audio-and-text foundation model that does full-duplex with 200 ms
end-to-end on an L4 is *the* open-source story to watch. If the
Pocket-TTS direction extends to a full Pocket-Moshi at 1–2 B
params, the local V2V economics flip from "interesting research"
to "practical." 4080 has the headroom.

**Function calling on V2V trails text-LLMs by a meaningful
margin.** gpt-realtime's 66.5% on ComplexFuncBench
([gpt-realtime announcement](https://openai.com/index/introducing-gpt-realtime/))
is up from 49.7% on the previous V2V model, and OpenAI explicitly
called out "asynchronous function calling so long-running tools
don't disrupt session flow" as a 2026 improvement. That's the
exact axis tool-use Sabrina needs to ship on cascade first;
V2V isn't ready to *be* the tool-using brain.

---

## Decisions Eric needs to lock

1. **Confirm the cascade is the architecture for the next ~6 months
   of components.** Recommended: yes — tool-use, vision, semantic
   memory, avatar, all assume it.
2. **Add a `MoshiBrain` / `RealtimeBrain` to the watch-list, not
   the do-list.** Recommended: yes; budget a Sunday in Q3-Q4 2026
   to A/B Moshi locally for the greeting-only path.
3. **Hold the avatar / cue-track design on the explicit
   `<emotion>` tag stream from the cascade.** V2V would force a
   redesign there; don't pre-pay that cost.
4. **Reject cloud V2V (OpenAI Realtime) as a default path.** The
   privacy delta of "continuous audio leaves the box" plus the
   cost order-of-magnitude both point this direction. Worth
   reconsidering only with a per-call audit + ZDR contract.
5. **Watch the open-weight V2V latency-vs-prosody curve in 2026
   H2.** If Sesame open-sources a prompt-shapeable persona-control
   layer, or Moshi adds tool-use to its joint stream, revisit the
   "V2V for greeting only" prototype.
