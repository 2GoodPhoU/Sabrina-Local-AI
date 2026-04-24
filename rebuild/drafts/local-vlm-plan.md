# Local VLM plan — vision-language model via Ollama

**Date:** 2026-04-23
**Status:** Research + draft. Implementation blocked on two open
questions at the top. Research below is settled.
**Closes:** decision 005 thin-spot + decision 006 "Local VLM fallback"
+ ROADMAP component 5 "local VLM fallback" line item.

## OPEN QUESTIONS (block implementation — Eric's call)

1. **Model choice: `qwen2.5-vl:7b`, `moondream:v2`, or both behind a
   `[vision.local]` model knob?** Research below says Qwen2.5-VL-7B is
   the strongest 7B-class VLM today, especially on UIs and text-in-
   image (reading errors, reading emails on screen). Moondream 2 is
   much smaller (~1.8B), ~3× faster, but weaker on text. The pattern
   Eric picked earlier (e.g. Piper voice selection) was "commit to
   one and move on." Asking here: commit to Qwen2.5-VL as the single
   choice, or ship with a model knob from day one?

   **Recommendation: commit to `qwen2.5vl:7b` as the single default;
   the model knob already exists for override but we don't bless
   Moondream as a "supported alternative."** Matches the Piper
   commit-and-move-on precedent (decision 002) — one good default +
   override via config. Sabrina's daily-driver vision use case is
   reading errors and UI text, which is the exact axis Moondream is
   weaker on; there's no user persona today where Moondream wins.
   `vision.local.model` is already a string field so swapping to
   `moondream:v2` is zero code; keeping the plan to one officially-
   supported VLM cuts test matrix, README, and "which one should I
   pull?" support load. Override: if Eric wants to bless two, add a
   `moondream` row to the bake-off doc + a short "pros/cons" block in
   `sabrina.toml` comments — no code change.

2. **Default tier for vision — cloud-first or local-first?**
   Today every vision turn uses Claude Haiku. Decision 005 vision was
   designed around "Claude is better; local is a fallback." Post-
   rebuild, flipping to local-first (privacy, offline, $0) for
   vision turns — and escalating to Claude only on a trigger phrase
   ("have Claude look at this") — is tenable. Affects default config.

   **Recommendation: `tier = "cloud"` by default; ship `"local"` and
   `"auto"` as opt-ins.** Decision 005 committed to Claude-first
   explicitly and nothing in Eric's use pattern has changed that
   calculus: Haiku vision is ~600 ms and materially sharper on text-
   in-image than any 7B local VLM, vision turns are relatively rare
   (voice-phrase or hotkey-armed only), and the cost envelope from
   decision 006 is ~60¢/month at 20 vision turns/day — not worth a
   quality regression. Local-first makes sense for a specific subset
   (privacy mode, offline sessions, post-barge-in where interruption
   budget matters), which is why the knob exists — but the default
   should match the shipped posture. Override: if Eric wants local-
   first, change the default in `sabrina.toml` to `tier = "local"`
   and the test that asserts cloud-by-default flips. Zero code
   change. The router plan's "vision turns bypass routing" rule is
   unaffected either way — `[vision].tier` is the vision-specific
   dial.

Everything below reflects these recommendations.

---

## The one-liner

Teach `OllamaBrain` to pass images through to Ollama's chat API when
`Message.images` is non-empty and the configured Ollama model is
multimodal. Add a `[vision.local]` config block. Thread the
local-vs-cloud choice through the voice-loop's existing vision
branch — the rest of the vision pipeline (mss capture → PIL resize →
PNG encode → `Message.images`) stays unchanged.

## Research — realistic VLMs on a 16 GB 4080

Ranked by fit for Sabrina's use cases (reading errors, summarizing
emails on screen, UI help).

### 1. `qwen2.5-vl:7b` — the pick

- **Size:** ~5.5 GB at Q5 quantization.
- **VRAM at runtime:** ~7 GB with a short-context image inference;
  comfortably below the 4080's 16 GB even with Ollama also hosting
  `qwen2.5:14b` loaded (~9 GB). Ollama's default model-swap behavior
  unloads an idle model to free VRAM, so both can coexist with
  juggling.
- **Quality:** strong OCR (text embedded in screenshots — errors,
  menu labels, UI copy). Strong grounding ("what's at the top-left?").
  Multilingual.
- **Ollama availability:** `ollama pull qwen2.5vl:7b` works on
  Windows. Supports `images` field in the chat API just like `llava`.
- **Latency on 4080:** ~800-1500 ms for one 1568px image plus a
  short question, depending on answer length. Slower than Claude
  Haiku (~600 ms) but in the same order of magnitude.

### 2. `moondream:v2` — the tiny alternative

- **Size:** ~2 GB at Q4/Q5.
- **VRAM:** ~3 GB.
- **Quality:** surprisingly good at description. Weaker on text-in-
  image. Great for "describe this image" but less good at "read
  this error and summarize."
- **Latency:** ~300-500 ms. Fastest local option.
- **Ollama availability:** `ollama pull moondream:v2`. Solid on
  Windows.

### 3. `llava:13b` — the older option

- **Size:** ~8 GB at Q4.
- **VRAM:** ~10 GB.
- **Quality:** the pre-2024 benchmark; most newer VLMs match or beat
  it. Still strong on general description.
- **Why it's not the plan's pick:** Qwen2.5-VL is newer and better on
  Sabrina's use cases (UIs + text). LLaVA's one-sentence pitch in
  2026 is "solid option for non-English workflows" — not Eric's
  need.

### 4. `pixtral:12b` — Mistral's VLM

- **Size:** ~7 GB at Q4.
- **VRAM:** ~9 GB.
- **Quality:** competitive with Qwen2.5-VL on many benchmarks; weaker
  on OCR.
- **Why it's not the plan's pick:** no clear quality advantage;
  research-note only.

## What Ollama actually wants

The Ollama chat API takes images on a per-message basis:

```json
{
  "model": "qwen2.5vl:7b",
  "messages": [
    {
      "role": "user",
      "content": "What's on my screen?",
      "images": ["<base64-encoded PNG>"]
    }
  ]
}
```

`images` is an array of base64-encoded raw bytes (no `data:` prefix,
no media-type wrapper). Ollama's Python client
(`ollama.AsyncClient`) accepts this shape directly. Our existing
`OllamaBrain.chat` loops `messages` and emits
`{"role", "content": str}`; it needs to optionally add `"images": [...]`.

## The plan's default

Text turns: unchanged (existing config). Vision turns: cloud-first per
Q2 recommendation, with a config knob for opt-in local / auto:

```toml
[vision]
# ...existing fields...
# "cloud" (Claude), "local" (Ollama VLM), "auto" (tries local if configured,
# falls back to cloud on error).
tier = "cloud"
```

Eric flips to `"local"` or `"auto"` in config if he wants that posture;
no code change needed.

## Scope

In:
- `brain/ollama.py`: forward `Message.images` to Ollama's `images`
  field when present. Check the configured model's
  `capabilities` (`ollama.show(model).capabilities`) at init; raise
  cleanly if the model is non-multimodal when images arrive.
- `vision/local_vlm.py` (~60 lines): a convenience
  `see_local(question, ...)` mirroring `vision/see.py`'s Claude-based
  `see(...)`. Routes through `OllamaBrain`.
- `voice_loop.py`: the vision branch picks Claude vs. local per
  `settings.vision.tier`.
- `cli.py / cli/vision.py`: `sabrina look` gains a `--local` flag.
- `[vision.local]` config block: model name, fallback behavior.
- Tests: image plumbing through OllamaBrain, tier selection in
  voice-loop, `--local` on `sabrina look`.

Out:
- Per-call model override in `Message`. Already possible at the
  OllamaBrain constructor level; not needed.
- Streaming images (only relevant for hypothetical future video).
- A unified `VisionBrain` protocol. `Brain` already carries images
  via `Message.images`; introducing another protocol violates
  guardrail #2 (no new abstraction until the second caller exists,
  and "local VLM" and "Claude vision" are both "brains with images,"
  not two different abstractions).

## Files to touch

```
sabrina-2/src/sabrina/
├── brain/ollama.py                # image forwarding + capability check
├── vision/
│   ├── local_vlm.py               # NEW, ~60 lines
│   └── __init__.py                # export see_local
├── voice_loop.py                  # vision-tier branch
├── cli.py / cli/vision.py         # `sabrina look --local`
└── config.py                      # +VisionLocalConfig
sabrina-2/
├── sabrina.toml                   # +[vision.local] + [vision].tier
└── tests/test_smoke.py            # +local-vlm tests
```

## Protocol / API changes

**None at the `Brain` protocol level.** This is the whole point of
keeping `Message.images` as an additive field in decision 005 — a
backend that chooses to honor it is a drop-in.

`OllamaBrain` gains a private capability check:

```python
def _detect_multimodal(self) -> bool:
    try:
        info = self._client.show(self._model)
        return "vision" in info.get("capabilities", [])
    except Exception:
        return False  # if the check fails, assume text-only
```

At `chat` time:

```python
for m in messages:
    api_msg: dict[str, Any] = {"role": m.role, "content": m.content}
    if m.images:
        if not self._multimodal:
            raise ValueError(
                f"Model {self._model!r} is not multimodal. "
                "Set vision.local.model to a VLM (e.g. qwen2.5vl:7b)."
            )
        api_msg["images"] = [
            base64.b64encode(img.data).decode("ascii")
            for img in m.images
        ]
    api_messages.append(api_msg)
```

## Config additions

```toml
[vision]
# ... existing fields ...
# Tier selection for vision turns.
#   "cloud"  = Claude Haiku (current behavior; default)
#   "local"  = Ollama VLM using vision.local.model below
#   "auto"   = local when the model is loaded and responsive,
#              fall back to cloud on any failure
tier = "cloud"

[vision.local]
# Ollama model id. `ollama pull qwen2.5vl:7b` first.
model = "qwen2.5vl:7b"

# Max tokens on the local reply. Usually shorter than cloud replies;
# local VLMs ramble. 256 is a safe default.
max_tokens = 256

# Downscale more aggressively for local? Local VLMs tend to tolerate
# smaller inputs better than Claude (Claude's sweet spot is ~1568 px).
# 1024 is a reasonable starting point for Qwen2.5-VL.
max_edge_px = 1024
```

## `vision/local_vlm.py` sketch

```python
async def see_local(
    question: str,
    *,
    history: list[Message] | None = None,
    settings: Settings | None = None,
    screenshot: Screenshot | None = None,
) -> AsyncIterator[StreamEvent]:
    settings = settings or load_settings()
    shot = screenshot if screenshot is not None else capture_local(settings)

    vcfg = settings.vision.local
    brain = OllamaBrain(
        host=settings.brain.ollama.host,
        model=vcfg.model,
    )
    user_msg = Message(
        role="user",
        content=question or "What's on my screen?",
        images=(Image(data=shot.data, media_type=shot.media_type),),
    )
    messages = [*(history or []), user_msg]

    async for event in brain.chat(
        messages,
        system=DEFAULT_VISION_SYSTEM_PROMPT,
        max_tokens=vcfg.max_tokens,
    ):
        yield event

def capture_local(settings: Settings) -> Screenshot:
    """Same as vision/see.capture but uses vision.local.max_edge_px."""
    v = settings.vision
    return grab(monitor=v.monitor, max_edge_px=v.local.max_edge_px)
```

## Voice-loop integration

Today `voice_loop.py` always builds a `ClaudeBrain` for vision turns.
After this plan:

```python
if use_vision:
    tier = settings.vision.tier
    if tier == "local":
        turn_brain = OllamaBrain(
            host=settings.brain.ollama.host,
            model=settings.vision.local.model,
        )
        turn_max_edge = settings.vision.local.max_edge_px
    elif tier == "auto":
        turn_brain, turn_max_edge = _auto_select_vision(settings)
    else:  # "cloud"
        turn_brain = ClaudeBrain(...)   # unchanged
        turn_max_edge = settings.vision.max_edge_px

    shot = await asyncio.to_thread(capture_screen, settings, turn_max_edge)
    turn_user_msg = Message(role="user", content=user_text,
                             images=(Image(data=shot.data, ...),))
```

`_auto_select_vision` does a fast capability check on the Ollama
model and falls back to Claude on any error. Logged either way.

## Scope gate — when "auto" mode falls back

The auto-mode fallback logic is simple but worth pinning down:

- Try local; any exception → log `vision.local_failed` + fall back to
  cloud.
- **Time limit: 3 seconds to first token.** If local hasn't produced
  a token in 3 s, abandon and switch to cloud. This prevents a hung
  Ollama process from stalling the voice loop.

## Test strategy

- `test_ollama_brain_forwards_images_as_base64` — stub the Ollama
  client; call `chat` with `Message.images=(one,)`; assert
  `images=[b64]` on the captured request.
- `test_ollama_brain_raises_cleanly_when_model_not_multimodal` —
  stub capability check to return empty; assert clear error.
- `test_ollama_brain_without_images_sends_no_images_field` —
  regression guard: text-only call doesn't gain an empty images field.
- `test_see_local_end_to_end_with_stub_ollama` — stub Ollama returning
  a canned reply; assert the reply streams back through the stream
  protocol.
- `test_voice_loop_vision_tier_local_uses_ollama` — stub settings with
  `tier=local`; spy on brain construction in the vision branch.
- `test_voice_loop_vision_tier_auto_falls_back_on_error` — stub
  Ollama that raises; assert fallback to Claude with a logged reason.

Manual smoke:
- `ollama pull qwen2.5vl:7b`.
- `sabrina look --local "what error is shown"` with a screenshot of a
  real error dialog; confirm the reply identifies the error.
- `sabrina voice` with `vision.tier=local`; say "look at my screen,
  what's this"; confirm local VLM answer.
- Confirm VRAM: `nvidia-smi` shows both `qwen2.5:14b` and
  `qwen2.5vl:7b` can be loaded concurrently (or swapped cleanly).

## Dependencies to add

None. `ollama>=0.3` already in deps; it supports the images field.

## Windows-specific concerns

- Ollama server runs as a Windows service (auto-started by the
  installer). If Eric's Ollama isn't running, the capability check
  fails clearly — we surface it with "Is ollama serve running?".
- Model pulls are ~5 GB each; flag in the README that first run
  after enabling vision.tier=local is going to be slow.
- Concurrent model hosting (`qwen2.5:14b` + `qwen2.5vl:7b`): Ollama's
  default `num_parallel=1` keeps one loaded at a time and will
  context-swap. On 16 GB VRAM, both can fit with
  `OLLAMA_MAX_LOADED_MODELS=2`. Document in comments; no code change.

## Ship criterion

- All new unit tests pass.
- `sabrina look --local "what's on my screen"` returns a plausible
  description on a real screenshot, with latency ≤ 2 s on the 4080.
- `sabrina voice` with `tier=local` performs a vision turn
  end-to-end; text-only turns are unaffected.
- `tier=cloud` remains the default until Eric flips it; everyone's
  existing behavior stays identical.
- `tier=auto` falls back to cloud when Ollama is unreachable (manual
  test: stop the Ollama service, run a vision turn, confirm it works
  via Claude and logs the fallback).

## Not in this plan (later)

- Local VLM tool-use (qwen2.5-vl supports it; defer until the tool-use
  plan lands first).
- Image-in-memory (persist screenshots in a short-retention store).
  Thin spot from decision 005; own plan when it gets scheduled.
- Window-region capture + active-window focus. See
  `vision-polish-plan.md`.
- A standalone vision benchmark script like the ASR one. Vision
  quality is harder to quantify; ad-hoc testing is sufficient for
  now.
- OCR pre-pass (run local OCR, attach extracted text as a sidecar
  to the image to cut tokens). Decision 005 deferred it;
  `vision-polish-plan.md` revisits.
