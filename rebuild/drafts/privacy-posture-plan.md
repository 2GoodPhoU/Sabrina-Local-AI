# Privacy posture plan — what leaves the box, what stays

**Date:** 2026-04-23
**Status:** Draft. Posture statement below; per-category audit + gap list.

## Posture (one sentence)

Sabrina is local-first. Transcribed user turns and retrieved memory
hits cross to the Claude API; vision frames cross when vision routes
cloud; everything else stays on disk. No training on API data.
Redaction of sensitive values in app logs is incomplete — gap flagged.

## Data Sabrina handles, per-category

| Category | Local? | Cloud? |
|---|---|---|
| Microphone audio | yes | **never** |
| ASR transcripts (user turns) | SQLite `data/sabrina.db` | sent to Claude on every turn (when default=claude) |
| Brain replies | SQLite | generated *by* Claude (when default=claude) |
| Retrieved memory hits ("Earlier..." block) | from SQLite | **sent to Claude** inside the system prompt |
| Semantic embeddings | vec0 table | never |
| TTS audio | streamed PCM; no file written | never |
| Screen frames | **in-memory only**, garbage-collected per turn | sent to Claude when `vision.trigger` fires |
| Tool-call arguments (drafted) | `logs/automation.log` | travel to Claude as tool-use blocks |
| Allow-list | `sabrina.toml` | never |
| Anthropic API key | `.env` → `SecretStr` in memory | bearer token only; never written anywhere else |

## Retention

- **SQLite memory (`data/sabrina.db`).** Forever. No eviction, no
  retention window. `sabrina memory-clear` wipes it. Growth is
  ~5 KB/turn per decision 006; years of use stay under 100 MB.
- **Semantic embeddings.** Same lifetime as the message row —
  `clear()` drops both tables.
- **Vision frames.** Ephemeral. Captured as `Screenshot.data` bytes,
  attached to one `Message.images`, then garbage-collected after the
  turn. We do **not** persist PNGs (confirmed in `vision/see.py`).
  The `[vision.archive]` block in `vision-polish-plan.md` would
  change that; it ships off by default.
- **TTS audio.** Not persisted. `speaker/piper.py` reads raw PCM from
  piper's stdout and pipes it straight to sounddevice — no WAV file.
  (Decision 006 says "writes a WAV"; that's wrong, the code streams.)
- **App logs (`logs/sabrina.log`, planned).** No rotation today. All
  structlog output goes to stderr; there's no file sink yet. **Gap.**
- **Audit log (`logs/automation.log`, planned).** Rotates at 5 MB per
  `automation-plan.md`. Not shipped.

## Anthropic data handling

Eric uses the Anthropic API directly, not Claude.ai. Per Anthropic's
commercial terms (see `https://www.anthropic.com/legal/commercial-terms`
and `https://privacy.anthropic.com/en/articles/7996868`), API inputs
and outputs are **not** used to train models by default. Retention is
currently 30 days for normal usage, longer for flagged content.

Two implications worth flagging:

1. **Prompt caching re-sends history.** Budget-and-caching plan wires
   `cache_control={"type": "ephemeral"}` on the system head. That
   still requires the identical text to arrive on each turn, which
   means old conversation content is transmitted every turn (just
   billed at 10%). Caching is a cost mechanism, not a privacy one.
2. **Semantic memory raises the stakes.** Once
   `[memory.semantic].enabled = true`, every turn pulls retrieved
   snippets from long-ago sessions into the system prompt. An
   off-topic retrieval can push old content into a new session.
   Acceptable for Eric's single-user use, but worth knowing.

## Ollama and model fetches

Ollama is fully local at runtime. One outbound flow at install time:
`ollama pull qwen2.5:14b` hits `registry.ollama.ai`.
sentence-transformers and faster-whisper download weights from
`huggingface.co` on first use. These are model fetches, not user
data — worth knowing, not worth gating.

## Tool-use / automation posture

Not shipped. `tool-use-plan.md` and `automation-plan.md` define the
posture: allow-list in `sabrina.toml` is the source of truth;
novel invocations prompt spoken confirmation; every call writes a
pre+post line to `logs/automation.log`. Default `confirm_mode =
"hybrid"` (never silently learn, never ask twice). `list_files` is
root-gated; `launch_app` is allow-list-gated; `list_open_windows` is
read-only. Principle: least privilege + consent + audit.

## Log hygiene — current state

`sabrina-2/src/sabrina/logging.py` configures structlog with
`ConsoleRenderer(colors=True)` and nothing else — no redaction
processor, no secret-scrubbing. API keys are held in `SecretStr`
which prints as `'**********'` if logged directly, but a caller who
does `api_key.get_secret_value()` and then logs the result bypasses
that. Tool-call arguments (once shipped) will flow through
`ToolInvocationStart(args={...})` with no redaction layer.

**Gaps to close before automation ships:**

- Add a `redact_secrets` structlog processor that drops known-sensitive
  keys (`api_key`, `authorization`, `anthropic_api_key`, any field
  ending in `_token`).
- Cap log values at ~512 chars per field; transcripts and tool-call
  arguments can be multi-KB and shouldn't land verbatim in logs.
- Teach `ToolInvocationStart` to hash or truncate `args` for tools
  flagged sensitive (`read_clipboard` is the obvious one).
- File sink for `logs/sabrina.log` with size-based rotation, separate
  from `logs/automation.log`. See `logging-vocabulary-plan.md`.

## User-facing controls — current + proposed

Today: `[memory.enabled]`, `[memory.semantic.enabled]`,
`[vision.trigger = "off"]`. That's it. Proposed additions (additive,
one session): `sabrina pause` verb + GUI button that holds a
`data/pause.flag` the voice loop checks — turns still speak but
don't persist to memory (incognito); `sabrina memory-forget --since
<ISO>` to drop a window without nuking the DB; per-tool toggles
(already in `tool-use-plan.md`).

## Honest gaps, one-line each

- **G1.** No secret-redaction processor in `logging.py`.
- **G2.** No file sink or rotation for app logs.
- **G3.** `Message.images` bytes can be logged by a careless caller;
  the render path is careful but no structural guarantee exists.
- **G4.** No "pause memory capture for this conversation" toggle
  (proposed above).
- **G5.** Semantic retrieval can surface old turns into the system
  prompt across unrelated sessions; documented, not controllable.
- **G6.** `ANTHROPIC_API_KEY` lives in `.env`; no secrets GUI. (By
  decision 004; secrets shouldn't touch TOML. Keep.)
