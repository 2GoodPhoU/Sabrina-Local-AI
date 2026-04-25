# 009a — Barge-in thin-spot patches (pre-validation bundle)

**Date:** 2026-04-24
**Status:** Draft. Gated on Eric's glance at the three open questions
below; rest of the plan reflects their recommendations.
**Closes:** the five thin spots in `rebuild/decisions/009-barge-in-shipped.md`
("Thin spots" section) + mirrors in `rebuild/when-you-return.md` lines 92–110.
**Anti-sprawl note:** rides on decision 009 as a footnote, no new
decision doc. The validate-barge-in doc's tail explicitly permits this
pattern for tight ride-along fixes.

## OPEN QUESTIONS (block implementation — Eric's call)

1. **Paper trail: footnote on 009, or new `010-barge-in-thin-spots.md`?**
   The fixes are ~70 lines total, touch three files, and nothing is
   architectural. A new decision doc for this is overkill; a footnote
   on 009 is the lightest thing that preserves the validation trail.

   **Recommendation: footnote on 009.** The validate-barge-in doc
   already green-lights this pattern ("fix in-place and annotate the
   decision 009 doc with a 'validation revealed X, fixed in commit Y'
   footnote"). This case is pre-validation, not validation-revealed,
   but the scope argument is identical — same subsystem, same session,
   no new judgment calls. Override: if Eric expects future sessions
   to treat the thin-spot list as a separate checkpoint, bump to a
   real 010.

2. **Thin spot #4 scope — just the poll-interval tighten, or dig into
   sub-sentence cancellation properly?** The thin-spot note claimed
   "~1 s worst case" for cancel granularity. Code reading contradicts
   that: the 30 ms poll task kills the Piper subprocess on cancel and
   the post-communicate check at `piper.py:173` skips playback. Real
   worst case today is ~30–60 ms. A proper sub-sentence fix would
   require streaming Piper output (stdin → stdout chunks played as they
   arrive) — a different component.

   **Recommendation: tighten 30 ms → 10 ms only, defer structural
   work.** One-line change tightens cancel detection 3× across synth
   and playback; fits the ride-along bundle. Streaming synth is its
   own ~200-line session and deserves the decision-doc treatment.
   Override: if Eric has actually felt the 1 s number in dogfooding,
   promote it to `streaming-piper-plan.md` and block this bundle on it.

3. **Thin spot #2 margin: how much pre-fire audio to keep?** The whole
   point of trim-to-VAD-start is to drop TTS bleed captured before the
   user began speaking. But too-aggressive trimming clips the start of
   the user's utterance — Whisper needs the onset of speech to
   transcribe correctly. The speech-window is `min_speech_ms` (default
   300 ms) by definition, so that much HAS to be kept. The question is
   how much extra margin to prepend.

   **Recommendation: 150 ms margin before the speech window (total
   450 ms of pre-fire audio at default settings).** Gives Whisper some
   prefix for the first phoneme; still drops ~80 %+ of the
   dead-zone-to-speech gap on a typical 1–2 s interrupt. Parameterize
   as `_PRE_FIRE_MARGIN_MS = 150` at module scope so tuning is trivial
   if step-6 of validation shows clipping. Override: 0 ms if Eric
   wants a strict "only speech" capture; 300 ms if Whisper's missing
   onsets show up in validation.

Everything below reflects the above recommendations.

---

## The one-liner

Five surgical follow-ups to decision 009 that collectively take
barge-in from "tests pass" to "ready to validate on real hardware":
graceful-degrade on Silero load, VAD probability DEBUG log, trim-to-
VAD-start capture, 3× tighter cancel detection, and pre-commit in the
venv. ~70 lines + 2 tests. One commit, footnoted on 009.

## Scope

In:
- **#1 Graceful-degrade on Silero load failure.** Mirror the
  `memory/store.py:_try_enable_vec` pattern in `voice_loop.py` where
  `SileroVAD` is instantiated. Eager warmup + try/except → log once,
  set `vad = None`, voice loop runs without barge-in.
- **#2 Trim-to-VAD-start in `AudioMonitor`.** Record capture-length at
  fire time; `stop()` returns the speech window + 150 ms margin +
  everything after, not the full buffer.
- **#3 Per-frame VAD probability DEBUG log** in `SileroVAD.feed`. One
  `log.debug("vad.prob", prob=prob)` line; unblocks step-7 threshold
  tuning in the validation procedure.
- **#4 Tighten cancel poll interval 30 ms → 10 ms** in
  `speaker/piper.py:_poll_and_stop`. One-line change; 3× tighter
  cancel detection across synth and playback.
- **#5 Install pre-commit hook in the venv.** `uv add --dev pre-commit
  && uv run pre-commit install`. Removes the `--no-verify` workaround
  on every future commit. Eric runs this on his box.
- **2 new unit tests** (degrade path + trim behavior). 57 → 59.

Out:
- Structural sub-sentence cancel (streaming Piper). Separate plan if #2
  recommendation above is overridden.
- Changing default barge-in values in `sabrina.toml`. Validation step 7
  may tune `threshold` and `dead_zone_ms`; that's a validation-stamp
  commit, not part of this bundle.
- Semantic-memory or other unrelated cleanups. One subsystem per
  commit — this one is strictly barge-in.

## Files to touch

```
sabrina-2/src/sabrina/
├── listener/vad.py              # +#1 (via voice_loop consumer), +#2, +#3
├── voice_loop.py                # +#1 warmup + degrade path
└── speaker/piper.py             # +#4 one-line poll-interval tweak
sabrina-2/
├── tests/test_smoke.py          # +2 tests (degrade, trim)
└── .pre-commit-config.yaml       # possibly touched by `pre-commit install`
rebuild/
├── decisions/009-barge-in-shipped.md   # +footnote at tail
└── when-you-return.md           # prune thin-spot list in step 2
```

One module net-changed (`listener/vad.py`). `voice_loop.py` gets ~15
lines of warmup+degrade. `speaker/piper.py` gets one character. Nothing
grows past its current size envelope.

## Protocol / API changes

None. `SileroVAD` constructor and `AudioMonitor` surface stay
identical; `_ensure_loaded` becomes reachable from outside for the
eager-warmup path but it's underscore-prefixed and the voice loop is
the only caller (second-caller rule satisfied by the test).

## Per-patch sketches

### #1 Graceful-degrade

In `voice_loop.py` around line 155–163 (current barge-in wiring):

```python
barge_enabled = settings is not None and settings.barge_in.enabled
vad: SileroVAD | None = None
if barge_enabled:
    candidate = SileroVAD(
        threshold=settings.barge_in.threshold,
        min_speech_ms=settings.barge_in.min_speech_ms,
    )
    try:
        candidate._ensure_loaded()  # eager warmup
    except Exception as exc:  # noqa: BLE001 - degrade to no-barge-in on ANY failure
        log.warning("vad.unavailable", error=str(exc))
        barge_enabled = False
    else:
        vad = candidate
```

All downstream `if vad is not None` guards already exist; no
consumer-side changes.

### #2 Trim-to-VAD-start

In `listener/vad.py:AudioMonitor`:

```python
# module scope, near _FRAME_SAMPLES etc.
_PRE_FIRE_MARGIN_MS = 150

# __init__: add tracker
self._fire_at_samples: int | None = None

# _callback, where self._detected flips True:
if fired:
    # Record position so stop() can trim pre-fire silence/TTS-bleed.
    total = sum(c.size for c in self._captured)
    self._fire_at_samples = total
    self._detected = True
    self._cancel.cancel()
    log.info("bargein.detected")

# stop():
if not self._detected or not self._captured:
    return None
full = np.concatenate(self._captured)
if self._fire_at_samples is None:
    return full
margin = int(_PRE_FIRE_MARGIN_MS * _SAMPLE_RATE / 1000)
speech = self._vad._min_speech_samples
keep_from = max(0, self._fire_at_samples - speech - margin)
return full[keep_from:]
```

Touches `SileroVAD._min_speech_samples` — it's underscore-prefixed but
AudioMonitor lives in the same module, so this is an acceptable
same-file private-attribute access. Alternative: expose a public
`speech_window_samples` property on `SileroVAD`. Recommend the property
for cleanliness; ~3 extra lines.

### #3 VAD probability DEBUG log

`listener/vad.py:SileroVAD.feed`, one line after the `prob = float(...)`:

```python
prob = float(self._model(frame_t, _SAMPLE_RATE).item())
log.debug("vad.prob", prob=prob)
if prob >= self._threshold:
    ...
```

Gated on `SABRINA_LOGGING__LEVEL=DEBUG`; zero overhead at INFO.

### #4 Tighter cancel poll

`speaker/piper.py:42`, one character:

```python
-        while not token.cancelled:
-            await asyncio.sleep(0.03)
+        while not token.cancelled:
+            await asyncio.sleep(0.01)
```

### #5 Pre-commit install

Eric's terminal:

```powershell
cd sabrina-2
uv add --dev pre-commit
uv run pre-commit install
```

If `.pre-commit-config.yaml` doesn't exist, Eric decides what hooks to
include (ruff, black, trailing-whitespace, etc.). Default suggestion is
ruff-check + ruff-format matching the `pyproject.toml` `[tool.ruff]`
settings already in place. Not required for this plan to land — even
the empty hook install removes the `--no-verify` friction.

## Test strategy

Two new unit tests in `tests/test_smoke.py`:

```python
def test_voice_loop_skips_barge_in_when_silero_load_fails(monkeypatch):
    """Broken silero-vad install must not crash voice loop startup."""
    import sabrina.listener.vad as vad_mod

    def _raise(self):
        raise ImportError("silero-vad stub failure")

    monkeypatch.setattr(vad_mod.SileroVAD, "_ensure_loaded", _raise)
    # instantiate the smallest viable voice_loop-setup path; assert
    # vad is None and barge_enabled is False post-setup. Exact assertion
    # depends on how much of run_voice_loop() can be exercised without
    # actual audio devices — may require extracting the wiring block
    # into a small helper. That extraction is fine (anti-sprawl budget
    # still green).


def test_audio_monitor_trims_capture_to_speech_onset():
    """Returned audio should drop pre-fire silence + bleed."""
    vad = _StubVAD(fires_after_n_chunks=2, min_speech_samples=4800)  # 300ms@16k
    tok = CancelToken()
    mon = AudioMonitor(vad, tok, dead_zone_ms=0)  # skip dead-zone for test
    # Fake 1 s of "silence", then 1 s of "speech", then 0.5 s of post-fire
    for _ in range(16):  # 16 × 64ms = ~1024ms
        _push_chunk(mon, _silent_chunk())
    _push_chunk(mon, _speech_chunk())  # fires here
    for _ in range(8):
        _push_chunk(mon, _silent_chunk())
    out = mon.stop()
    # Expected: ~450ms pre-fire (margin + speech window) + ~500ms post-fire
    assert 14400 <= out.size <= 16800  # 900-1050ms @ 16k
```

The stub setup for test 2 is the real work; might need a small helper
to shim `sd.InputStream` so we can drive `_callback` directly from the
test. Acceptable — existing tests already shim sounddevice.

## Ship criterion

- `uv run pytest -q` reports `59 passed` (was 57).
- Manual smoke: turn barge-in on in `sabrina.toml`, break the silero
  install (rename the wheel), `uv run sabrina voice` starts cleanly
  with `vad.unavailable` in the log. Undo the rename.
- `SABRINA_LOGGING__LEVEL=DEBUG uv run sabrina voice` emits `vad.prob`
  lines during speaking phases.
- `git commit` succeeds without `--no-verify`.
- Diff is ≤100 lines of source code excluding tests.

## Not in this plan (later)

- Streaming Piper output for true mid-sentence cancel — promote to
  `streaming-piper-plan.md` if #4's recommendation is overridden or
  validation shows user-facing lag.
- Replacing `_PRE_FIRE_MARGIN_MS` with a config knob — trivial to
  promote once step-6 of validation has evidence for what the number
  should be. Module constant is sufficient until then.
- Exposing a public `SileroVAD.speech_window_samples` property if the
  private-attribute access in #2 chafes (3-line addition; trivial).
- Any change to `[barge_in]` defaults in `sabrina.toml` — that's a
  validation-stamp concern, not a thin-spot patch.

## Thin spots of this plan

- **Test #1 may require extracting the barge-in wiring block from
  `run_voice_loop` into a helper.** That's a reasonable refactor but
  pushes file-size guardrail on `voice_loop.py` (currently 515 lines at
  HEAD, already past 300). If the extraction lands, note it in the
  commit message so future sessions see it was needed, not churn.
- **`vad._min_speech_samples` access from `AudioMonitor`** is a
  same-file private access — defensible, but a public
  `speech_window_samples` property is nicer. Flagged in #2; plan ships
  either path cleanly.
- **Pre-commit hook config not included.** This plan installs the
  framework; what hooks run is Eric's call. If we want ruff-check /
  ruff-format enforced on every commit, that's an additional
  `.pre-commit-config.yaml` write (~15 lines) — willing to add it if
  Eric wants, otherwise the bare install is fine.

## Alternatives worth researching

- **SileroVAD v6 / Silero v5 nano** — if load-time becomes a thin spot
  we'll want to know whether the alternative model weights are smaller
  or faster to load. Not relevant today; load is <50 ms on this
  hardware.
- **An onnxruntime-DirectML Silero run** (UHD 770 iGPU path) — frees
  the 4080's CUDA context for Whisper + Ollama. Probably overkill
  (CPU inference per 512-sample frame is ~1 ms) but the option is
  real.
- **Replacing the 30 ms / 10 ms poll with an `asyncio.Event` on
  `CancelToken`** — strictly event-driven cancel detection. Eliminates
  the poll entirely. Needs a `CancelToken` API change (add `wait()`
  coroutine). Out of scope for this bundle but cheap to revisit
  post-validation.
