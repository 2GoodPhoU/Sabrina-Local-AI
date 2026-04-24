"""Phase 0 smoke tests.

These cover the foundation only: config loads, bus delivers events, state
machine enforces transitions. Brain backends are mocked (no network / Ollama
required to run `pytest`).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from sabrina.brain.protocol import Brain, Done, Message, StreamEvent, TextDelta
from sabrina.bus import EventBus
from sabrina.config import load_settings
from sabrina.events import StateChanged, UserMessage
from sabrina.listener.protocol import Listener, Segment, Transcript
from sabrina.speaker.protocol import Speaker, SpeakResult
from sabrina.speaker.voices import PRESETS
from sabrina.state import IllegalTransition, StateMachine


# --- config ---


def test_settings_load_with_defaults():
    # sabrina.toml may or may not be present depending on cwd; defaults should hold.
    s = load_settings(reload=True)
    assert s.brain.default in {"claude", "ollama"}
    assert s.brain.claude.model
    assert s.brain.ollama.model


def test_anthropic_key_reads_unprefixed_env_var(monkeypatch):
    # Standard Anthropic env var name should work without the SABRINA_ prefix.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-dummy-value")
    s = load_settings(reload=True)
    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "sk-ant-test-dummy-value"


def test_anthropic_key_also_reads_prefixed_env_var(monkeypatch):
    # The SABRINA_-prefixed form should also work, for users who prefer it.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("SABRINA_ANTHROPIC_API_KEY", "sk-ant-test-prefixed")
    s = load_settings(reload=True)
    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "sk-ant-test-prefixed"


# --- bus ---


@pytest.mark.asyncio
async def test_bus_delivers_events():
    bus = EventBus()
    received: list[str] = []

    async def reader() -> None:
        async for ev in bus.subscribe("user_message"):
            received.append(ev.text)
            if len(received) == 2:
                return

    task = asyncio.create_task(reader())
    await asyncio.sleep(0)  # let subscriber register
    await bus.publish(UserMessage(text="hello"))
    await bus.publish(UserMessage(text="world"))
    await asyncio.wait_for(task, timeout=1.0)
    assert received == ["hello", "world"]


@pytest.mark.asyncio
async def test_bus_filters_by_kind():
    bus = EventBus()
    got_state: list[StateChanged] = []

    async def reader() -> None:
        async for ev in bus.subscribe("state_changed"):
            got_state.append(ev)
            return

    task = asyncio.create_task(reader())
    await asyncio.sleep(0)
    await bus.publish(UserMessage(text="ignored"))
    await bus.publish(StateChanged(from_state="idle", to_state="thinking"))
    await asyncio.wait_for(task, timeout=1.0)
    assert len(got_state) == 1


# --- state machine ---


@pytest.mark.asyncio
async def test_state_machine_legal_transition_publishes_event():
    bus = EventBus()
    sm = StateMachine(bus)
    events: list[StateChanged] = []

    async def reader() -> None:
        async for ev in bus.subscribe("state_changed"):
            events.append(ev)
            return

    task = asyncio.create_task(reader())
    await asyncio.sleep(0)
    await sm.transition("thinking", reason="test")
    await asyncio.wait_for(task, timeout=1.0)
    assert sm.state == "thinking"
    assert events[0].from_state == "idle"
    assert events[0].to_state == "thinking"


@pytest.mark.asyncio
async def test_state_machine_illegal_transition_raises():
    bus = EventBus()
    sm = StateMachine(bus, initial="idle")
    await sm.transition("listening")
    # listening -> speaking is not allowed.
    with pytest.raises(IllegalTransition):
        await sm.transition("speaking")


# --- brain protocol smoke (with a fake backend) ---


class FakeBrain:
    name = "fake:v1"

    async def chat(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        for chunk in ["hello", " ", "world"]:
            yield TextDelta(text=chunk)
        yield Done(input_tokens=1, output_tokens=3, stop_reason="end_turn")


@pytest.mark.asyncio
async def test_fake_brain_satisfies_protocol():
    b: Brain = FakeBrain()
    assert isinstance(b, Brain)
    pieces: list[str] = []
    done_seen = False
    async for ev in b.chat([Message(role="user", content="hi")]):
        if isinstance(ev, TextDelta):
            pieces.append(ev.text)
        elif isinstance(ev, Done):
            done_seen = True
    assert "".join(pieces) == "hello world"
    assert done_seen


# --- speaker protocol smoke (with a fake backend) ---


class FakeSpeaker:
    name = "fake-speaker:v1"

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.stopped = False

    async def speak(self, text: str, *, voice: str | None = None) -> SpeakResult:
        self.spoken.append(text)
        return SpeakResult(
            engine=self.name, duration_s=0.01, sample_rate=22050, samples=220
        )

    async def stop(self) -> None:
        self.stopped = True


@pytest.mark.asyncio
async def test_fake_speaker_satisfies_protocol():
    s: Speaker = FakeSpeaker()
    assert isinstance(s, Speaker)
    result = await s.speak("hello there")
    assert result.engine == "fake-speaker:v1"
    assert result.sample_rate == 22050
    assert s.spoken == ["hello there"]  # type: ignore[attr-defined]
    await s.stop()
    assert s.stopped is True  # type: ignore[attr-defined]


def test_voice_preset_hf_path_includes_language_group():
    # HF piper-voices repo layout is <lang_group>/<locale>/<voice>/<quality>/<id>.onnx.
    # Regression guard: we must include the leading language group (e.g. "en/").
    preset = PRESETS["amy-medium"]
    assert preset.hf_path == "en/en_US/amy/medium/en_US-amy-medium.onnx"


# --- listener protocol smoke (with a fake backend) ---


class FakeListener:
    name = "fake-listener:v1"

    async def transcribe(
        self,
        audio,  # noqa: ANN001 - accept Path or ndarray per protocol
        *,
        language: str | None = None,
    ) -> Transcript:
        return Transcript(
            text="hello world",
            language=language or "en",
            language_prob=0.99,
            audio_duration_s=1.0,
            transcribe_duration_s=0.05,
            segments=(Segment(start_s=0.0, end_s=1.0, text="hello world"),),
        )


@pytest.mark.asyncio
async def test_fake_listener_satisfies_protocol(tmp_path):
    L: Listener = FakeListener()
    assert isinstance(L, Listener)
    result = await L.transcribe(tmp_path / "doesnt_matter.wav")
    assert result.text == "hello world"
    assert result.language == "en"
    assert result.rtf == pytest.approx(0.05)
    assert len(result.segments) == 1
    assert result.segments[0].text == "hello world"


# --- voice loop: sentence splitter ---


def test_sentence_splitter_basic():
    from sabrina.voice_loop import _split_off_sentence

    sentence, rest = _split_off_sentence("Hello there. How are you")
    assert sentence == "Hello there."
    assert rest == "How are you"


def test_sentence_splitter_no_terminator_yet():
    from sabrina.voice_loop import _split_off_sentence

    sentence, rest = _split_off_sentence("Still typing")
    assert sentence is None
    assert rest == "Still typing"


def test_sentence_splitter_decimals_are_not_boundaries():
    # "Pi is 3.14 approximately." -- the "." in 3.14 must not split.
    from sabrina.voice_loop import _split_off_sentence

    sentence, rest = _split_off_sentence("Pi is 3.14 approximately. Next")
    assert sentence == "Pi is 3.14 approximately."
    assert rest == "Next"


def test_sentence_splitter_question_mark():
    from sabrina.voice_loop import _split_off_sentence

    sentence, rest = _split_off_sentence("Ready? Let's go")
    assert sentence == "Ready?"
    assert rest == "Let's go"


# --- speaker events schema guard ---


def test_speak_events_construct_with_required_fields():
    # Regression: SpeakStarted needs `text`, SpeakFinished needs `duration_s`.
    # This test fails fast if a publish-site is missing a field.
    from sabrina.events import SpeakAborted, SpeakFinished, SpeakRequest, SpeakStarted

    assert SpeakRequest(text="hi").text == "hi"
    assert SpeakStarted(engine="piper:amy", text="hello").text == "hello"
    assert SpeakFinished(engine="piper:amy", duration_s=0.42).duration_s == 0.42
    assert SpeakAborted(engine="piper:amy", reason="user").reason == "user"


# --- PTT audio trimming ---


def test_ptt_trim_ends_drops_configured_milliseconds():
    import numpy as np
    from sabrina.listener.ptt import _trim_ends

    # 2 s at 16 kHz = 32 000 samples. 150 ms at 16 kHz = 2 400 samples each end.
    audio = np.arange(32000, dtype=np.float32)
    trimmed = _trim_ends(audio, trim_ms=150)
    assert trimmed.size == 32000 - 2 * 2400
    assert trimmed[0] == 2400
    assert trimmed[-1] == 32000 - 2400 - 1


def test_ptt_trim_ends_returns_empty_for_too_short_clip():
    import numpy as np
    from sabrina.listener.ptt import _trim_ends

    # 250 ms clip: trimming 150 each side would leave < 100 ms.
    audio = np.ones(int(0.25 * 16000), dtype=np.float32)
    trimmed = _trim_ends(audio, trim_ms=150)
    assert trimmed.size == 0


def test_ptt_trim_ends_passthrough_when_trim_ms_zero():
    import numpy as np
    from sabrina.listener.ptt import _trim_ends

    audio = np.ones(8000, dtype=np.float32)
    assert _trim_ends(audio, trim_ms=0) is audio


# --- memory store ---


def test_memory_store_round_trip(tmp_path):
    from sabrina.memory.store import MemoryStore, new_session_id

    db = tmp_path / "mem.db"
    with MemoryStore(db) as m:
        sid = new_session_id()
        m.append(sid, "user", "what time is it?")
        m.append(sid, "assistant", "3 pm ish.")
        assert m.count() == 2
        loaded = m.load_recent(10)
        assert [x.role for x in loaded] == ["user", "assistant"]
        assert loaded[0].content == "what time is it?"
        assert loaded[1].content == "3 pm ish."


def test_memory_store_trims_leading_assistant_reply(tmp_path):
    # If load_recent cuts in the middle of a turn pair so the oldest
    # message is an assistant reply, drop it — the brain shouldn't see
    # a dangling assistant message as the first item of history.
    from sabrina.memory.store import MemoryStore, new_session_id

    db = tmp_path / "mem.db"
    with MemoryStore(db) as m:
        sid = new_session_id()
        m.append(sid, "user", "q1")
        m.append(sid, "assistant", "a1")
        m.append(sid, "user", "q2")
        m.append(sid, "assistant", "a2")
        loaded = m.load_recent(3)  # oldest would be "a1"; should get dropped
        assert [x.role for x in loaded] == ["user", "assistant"]
        assert [x.content for x in loaded] == ["q2", "a2"]


def test_memory_store_clear(tmp_path):
    from sabrina.memory.store import MemoryStore, new_session_id

    db = tmp_path / "mem.db"
    with MemoryStore(db) as m:
        sid = new_session_id()
        m.append(sid, "user", "hi")
        m.append(sid, "assistant", "hi back")
        assert m.count() == 2
        removed = m.clear()
        assert removed == 2
        assert m.count() == 0
        assert m.load_recent(10) == []


def test_memory_store_rejects_bad_role(tmp_path):
    from sabrina.memory.store import MemoryStore

    with MemoryStore(tmp_path / "mem.db") as m:
        with pytest.raises(ValueError):
            m.append("s", "moderator", "nope")


# --- semantic memory (sqlite-vec + stub embedder) ---


class _StubEmbedder:
    """Deterministic tiny-dim embedder for tests.

    Maps each input string to an 8-float vector by accumulating ord(c) % 7
    buckets, then normalizing. Same input -> same vector; substring overlap
    -> smaller cosine distance. Good enough for ordering assertions.
    """

    model_name = "stub-embedder"
    dim = 8

    def embed(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for i, c in enumerate(text):
            v[i % self.dim] += (ord(c) % 7) / 7.0
        norm = sum(x * x for x in v) ** 0.5 or 1.0
        return [x / norm for x in v]

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]

    def warmup(self):
        pass


def _require_sqlite_vec():
    """Skip the calling test if sqlite-vec isn't installed/loadable."""
    import sqlite3

    sqlite_vec = pytest.importorskip("sqlite_vec")
    try:
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
    except (AttributeError, sqlite3.OperationalError) as e:
        pytest.skip(f"sqlite-vec not loadable: {e}")


def test_semantic_memory_append_and_search(tmp_path):
    _require_sqlite_vec()
    from sabrina.memory.store import MemoryStore, new_session_id

    # Use explicit unit vectors so we control distances exactly. Tests
    # the store's contract (k-NN, ordering, sorted-by-distance) — real
    # semantic quality is sentence-transformers' job, not ours.
    e1 = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # "anchor"
    e2 = [0.99, 0.141, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # very close to e1
    e3 = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # orthogonal
    e4 = [-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # opposite of e1

    with MemoryStore(tmp_path / "mem.db", embedding_dim=8) as m:
        assert m.vec_enabled, "vec should be enabled once dim is passed in"
        sid = new_session_id()
        m.append(sid, "user", "anchor", embedding=e1)
        m.append(sid, "user", "close", embedding=e2)
        m.append(sid, "user", "ortho", embedding=e3)
        m.append(sid, "user", "opposite", embedding=e4)
        assert m.count() == 4
        assert m.count_with_embeddings() == 4

        hits = m.search(e1, k=3)
        # Distance-sorted, anchor first (d=0), then close, then ortho.
        assert len(hits) == 3
        assert [h.message.content for h in hits[:2]] == ["anchor", "close"]
        # Distances are monotonically nondecreasing.
        assert hits[0].distance <= hits[1].distance <= hits[2].distance


def test_semantic_memory_search_excludes_ids(tmp_path):
    _require_sqlite_vec()
    from sabrina.memory.store import MemoryStore, new_session_id

    emb = _StubEmbedder()
    with MemoryStore(tmp_path / "mem.db", embedding_dim=emb.dim) as m:
        sid = new_session_id()
        ids = [
            m.append(sid, "user", t, embedding=emb.embed(t))
            for t in ["apple", "banana", "cherry", "apple pie recipe"]
        ]
        # Exclude the two most-recent rows: "cherry" and "apple pie recipe".
        recent = m.recent_ids(2)
        assert set(recent) == {ids[2], ids[3]}
        hits = m.search(emb.embed("apple"), k=3, exclude_ids=recent)
        # No retrieved hit should be in the excluded set.
        assert all(h.message.id not in set(recent) for h in hits)


def test_semantic_memory_backfill(tmp_path):
    _require_sqlite_vec()
    from sabrina.memory.store import MemoryStore, new_session_id

    emb = _StubEmbedder()
    with MemoryStore(tmp_path / "mem.db", embedding_dim=emb.dim) as m:
        sid = new_session_id()
        # Write without embeddings.
        for t in ["hello world", "goodnight moon", "good morning sunshine"]:
            m.append(sid, "user", t)  # no embedding arg
        assert m.count() == 3
        assert m.count_with_embeddings() == 0

        written = m.backfill_embeddings(emb, batch_size=2)
        assert written == 3
        assert m.count_with_embeddings() == 3
        # Re-running is a no-op.
        assert m.backfill_embeddings(emb) == 0


def test_semantic_memory_dim_mismatch_raises(tmp_path):
    _require_sqlite_vec()
    from sabrina.memory.store import MemoryStore, new_session_id

    with MemoryStore(tmp_path / "mem.db", embedding_dim=8) as m:
        sid = new_session_id()
        with pytest.raises(ValueError):
            m.append(sid, "user", "x", embedding=[0.1] * 16)  # wrong dim


def test_semantic_memory_search_disabled_raises(tmp_path):
    # No embedding_dim passed -> vec stays disabled even if sqlite-vec is installed.
    from sabrina.memory.store import MemoryStore

    with MemoryStore(tmp_path / "mem.db") as m:
        assert not m.vec_enabled
        with pytest.raises(RuntimeError):
            m.search([0.0] * 8, k=1)


def test_memory_store_append_without_semantic_still_works(tmp_path):
    # Regression guard: the old text-only API path must still insert cleanly
    # when `embedding_dim=None` is passed, even if sqlite-vec is installed.
    from sabrina.memory.store import MemoryStore, new_session_id

    with MemoryStore(tmp_path / "mem.db") as m:
        sid = new_session_id()
        m.append(sid, "user", "hello")
        m.append(sid, "assistant", "hi")
        assert m.count() == 2
        assert m.count_with_embeddings() == 0


# --- semantic memory: config + voice_loop wiring ---


def test_semantic_config_round_trip():
    from sabrina.config import load_settings

    s = load_settings(reload=True)
    # Attribute exists and has the documented defaults.
    sem = s.memory.semantic
    assert hasattr(sem, "enabled")
    assert sem.embedding_model.endswith("all-MiniLM-L6-v2")
    assert sem.top_k >= 1
    assert 0.0 < sem.max_distance <= 2.0


def test_voice_loop_format_retrieved_compact():
    from datetime import datetime, timezone
    from sabrina.memory.store import SearchHit, StoredMessage
    from sabrina.voice_loop import _format_retrieved

    hit = SearchHit(
        message=StoredMessage(
            id=1,
            session_id="s",
            ts=datetime(2026, 1, 15, tzinfo=timezone.utc),
            role="user",
            content="long text " * 40,
        ),
        distance=0.12,
    )
    block = _format_retrieved([hit], max_chars_per_hit=30)
    # Header + 1 line per hit.
    assert block.startswith("Earlier")
    assert "2026-01-15" in block
    # Truncated properly.
    lines = block.splitlines()
    assert len(lines) == 2
    assert len(lines[1]) <= 60  # "- [date role] " prefix + truncated body


# --- settings_io (tomlkit round-trip) ---


def test_settings_io_preserves_comments_on_roundtrip(tmp_path):
    from sabrina.settings_io import load_document, save_document

    path = tmp_path / "sabrina.toml"
    original = (
        "# top-level comment\n"
        "\n"
        "[brain]\n"
        "# which backend to use\n"
        'default = "claude"\n'
        "\n"
        "[brain.claude]\n"
        'model = "claude-sonnet-4-6"\n'
    )
    path.write_text(original, encoding="utf-8")
    doc = load_document(path)
    save_document(doc, path)
    # Round-trip with no edits should be byte-identical (or at least contain
    # the original comments).
    result = path.read_text(encoding="utf-8")
    assert "# top-level comment" in result
    assert "# which backend to use" in result
    assert 'default = "claude"' in result


def test_settings_io_applies_nested_updates(tmp_path):
    from sabrina.settings_io import apply_updates, load_document, save_document

    path = tmp_path / "sabrina.toml"
    path.write_text(
        "[brain]\n"
        "# documented choice\n"
        'default = "claude"\n'
        "\n"
        "[brain.claude]\n"
        'model = "claude-sonnet-4-6"\n'
        "max_tokens = 1024\n",
        encoding="utf-8",
    )
    doc = load_document(path)
    apply_updates(
        doc,
        {
            "brain": {
                "default": "ollama",
                "claude": {"max_tokens": 2048},
            },
        },
    )
    save_document(doc, path)
    out = path.read_text(encoding="utf-8")
    # Comment survived.
    assert "# documented choice" in out
    # Leaf values got updated.
    assert 'default = "ollama"' in out
    assert "max_tokens = 2048" in out
    # Untouched value stuck around.
    assert "claude-sonnet-4-6" in out


def test_settings_io_creates_missing_tables(tmp_path):
    from sabrina.settings_io import save_with_updates

    path = tmp_path / "sabrina.toml"
    path.write_text("# empty\n", encoding="utf-8")
    save_with_updates({"vision": {"trigger": "hotkey"}}, path)
    out = path.read_text(encoding="utf-8")
    assert "[vision]" in out
    assert 'trigger = "hotkey"' in out
    assert "# empty" in out  # original comment preserved


def test_settings_io_writes_atomically_no_tempfile_leftovers(tmp_path):
    from sabrina.settings_io import save_with_updates

    path = tmp_path / "sabrina.toml"
    save_with_updates({"brain": {"default": "claude"}}, path)
    assert path.is_file()
    leftover = list(tmp_path.glob(".sabrina.toml.*.tmp"))
    assert leftover == []


# --- vision config defaults ---


def test_vision_config_defaults_load():
    s = load_settings(reload=True)
    assert s.vision.trigger in {"both", "voice_phrase", "hotkey", "off"}
    assert s.vision.hotkey  # non-empty default
    assert s.vision.monitor >= 0


# --- GUI module import (smoke only; no window creation) ---


def test_gui_settings_module_imports():
    # Cheap smoke: module must be importable even without a display, as
    # customtkinter is imported lazily inside open_settings().
    import sabrina.gui.settings as mod

    assert hasattr(mod, "SettingsWindow")
    assert hasattr(mod, "open_settings")


def test_gui_settings_preset_key_resolution():
    from sabrina.gui.settings import _preset_key_from_model_path

    assert _preset_key_from_model_path("voices/en_US-amy-medium.onnx") == "amy-medium"
    assert (
        _preset_key_from_model_path("voices/en_US-libritts_r-medium.onnx")
        == "libritts_r-medium"
    )
    # Unknown path still yields *something* legal so the dropdown isn't empty.
    fallback = _preset_key_from_model_path("voices/not-a-real-voice.onnx")
    assert fallback  # any known key is fine


def test_gui_settings_nest_and_coerce():
    from sabrina.gui.settings import _coerce, _nest

    assert _coerce("memory.enabled", True) is True
    assert _coerce("tts.piper.speaker_id", "3") == 3
    assert _coerce("tts.piper.length_scale", "0.9") == pytest.approx(0.9)
    assert _coerce("brain.claude.model", "claude-sonnet-4-6") == "claude-sonnet-4-6"

    nested = _nest(
        {
            "brain.default": "claude",
            "brain.claude.model": "x",
            "vision.trigger": "off",
        }
    )
    assert nested == {
        "brain": {"default": "claude", "claude": {"model": "x"}},
        "vision": {"trigger": "off"},
    }


# --- vision: protocol + triggers + capture math ---


def test_message_carries_images_by_default_empty():
    from sabrina.brain.protocol import Image, Message

    # Default: no images, existing call sites unchanged.
    m = Message(role="user", content="hi")
    assert m.images == ()

    # Can carry image bytes.
    img = Image(data=b"\x89PNG\r\n...", media_type="image/png")
    m2 = Message(role="user", content="what's this?", images=(img,))
    assert len(m2.images) == 1
    assert m2.images[0].media_type == "image/png"


def test_claude_render_message_text_only_stays_compact():
    # Text-only turns should NOT balloon into content-block lists — we
    # deliberately keep the common path as {"role", "content": str}.
    from sabrina.brain.claude import _render_message
    from sabrina.brain.protocol import Message

    out = _render_message(Message(role="user", content="hello"))
    assert out == {"role": "user", "content": "hello"}


def test_claude_render_message_image_turn_builds_blocks():
    # With images, we emit the content-block form and base64-encode inline.
    import base64
    from sabrina.brain.claude import _render_message
    from sabrina.brain.protocol import Image, Message

    raw = b"fake-png-bytes"
    msg = Message(
        role="user",
        content="what do you see?",
        images=(Image(data=raw, media_type="image/png"),),
    )
    out = _render_message(msg)
    assert out["role"] == "user"
    blocks = out["content"]
    assert isinstance(blocks, list)
    assert blocks[0]["type"] == "image"
    assert blocks[0]["source"]["media_type"] == "image/png"
    assert blocks[0]["source"]["data"] == base64.standard_b64encode(raw).decode("ascii")
    # Text block follows the image so the question can reference it.
    assert blocks[-1]["type"] == "text"
    assert blocks[-1]["text"] == "what do you see?"


def test_vision_should_trigger_positive_phrases():
    from sabrina.vision.triggers import should_trigger_vision

    assert should_trigger_vision("Hey Sabrina, look at my screen please")
    assert should_trigger_vision("what's on my screen?")
    assert should_trigger_vision("What Does This Say")  # case insensitive
    assert should_trigger_vision("help me with this, I'm lost")


def test_vision_should_trigger_negative_phrases():
    # Bias is toward false negatives — these must NOT trip the detector.
    from sabrina.vision.triggers import should_trigger_vision

    assert not should_trigger_vision("what time is it")
    assert not should_trigger_vision("tell me a joke")
    assert not should_trigger_vision("")
    assert not should_trigger_vision("how was your day")


def test_vision_downscale_math_within_budget_is_passthrough():
    from sabrina.vision.capture import downscale_size

    # 1280x720 with 1568 budget -> unchanged.
    assert downscale_size(1280, 720, 1568) == (1280, 720)
    # max_edge_px=0 disables scaling.
    assert downscale_size(3840, 2160, 0) == (3840, 2160)


def test_vision_downscale_math_preserves_aspect_and_caps():
    from sabrina.vision.capture import downscale_size

    # 4K landscape -> cap at 1568 on the long edge.
    w, h = downscale_size(3840, 2160, 1568)
    assert w == 1568
    # Aspect 16:9 should hold within rounding.
    assert abs(w / h - 3840 / 2160) < 0.01
    # Tall portrait: cap the height instead.
    w2, h2 = downscale_size(1080, 1920, 1568)
    assert h2 == 1568
    assert w2 < h2


def test_vision_hotkey_arm_and_consume():
    # Pure-logic test: start() spawns pynput so we don't call it here,
    # but arm() and consume() are fair game.
    from sabrina.vision.hotkey import VisionHotkey

    hk = VisionHotkey("<ctrl>+<shift>+v")
    assert hk.armed is False
    hk.arm()
    assert hk.armed is True
    assert hk.consume() is True
    assert hk.armed is False
    # Second consume returns False — flag cleared.
    assert hk.consume() is False


def test_vision_see_module_rejects_missing_api_key(monkeypatch):
    # If no API key is configured, see() should fail fast with a clear
    # message rather than crashing deep in the anthropic SDK.
    #
    # Subtlety: delenv alone isn't enough, because pydantic-settings also
    # reads .env, which on a real dev machine typically has the key set.
    # We load settings normally and then stamp the key to None on the
    # instance so the test is independent of the user's shell/.env state.
    import asyncio as _asyncio
    from sabrina.config import load_settings
    from sabrina.vision.capture import Screenshot
    from sabrina.vision.see import see

    s = load_settings(reload=True)
    monkeypatch.setattr(s, "anthropic_api_key", None)
    assert s.anthropic_api_key is None

    fake = Screenshot(
        data=b"\x89PNG\r\n",
        media_type="image/png",
        width=10,
        height=10,
        source_width=10,
        source_height=10,
        capture_duration_s=0.0,
    )

    async def _run():
        gen = see("hi", settings=s, screenshot=fake)
        await gen.__anext__()

    with pytest.raises(ValueError):
        _asyncio.run(_run())


# --- decision 008: foundational refactor bundle ---


def test_schema_version_present_and_current():
    # The [schema].version field is declared on Settings and defaults to the
    # module-level CURRENT_SCHEMA_VERSION. Guards against a future rename that
    # drops the hook or a version bump without a corresponding migration.
    from sabrina.config import CURRENT_SCHEMA_VERSION, load_settings

    s = load_settings(reload=True)
    # Python attribute is `schema_` (trailing underscore) because pydantic's
    # BaseSettings parent class exposes a `schema` attribute. TOML key and
    # the rest of the codebase still use the unadorned `schema`; see
    # `config.py` for the alias pattern.
    assert s.schema_.version == CURRENT_SCHEMA_VERSION


def test_logging_redacts_known_secrets():
    # The redact_secrets structlog processor replaces sensitive values in
    # place. Covers exact-match keys, case-insensitive match, nested dicts,
    # and the *_token suffix rule.
    from sabrina.logging import redact_secrets

    event = {
        "event": "brain.request",
        "api_key": "sk-ant-should-never-see-this",
        "Authorization": "Bearer tok_abc",
        "headers": {"anthropic_api_key": "nested-secret", "user_agent": "ok"},
        "refresh_token": "tok_ref",
        "model": "claude-sonnet-4-6",
    }
    result = redact_secrets(None, "info", event)
    assert result["api_key"] == "***REDACTED***"
    assert result["Authorization"] == "***REDACTED***"
    assert result["headers"]["anthropic_api_key"] == "***REDACTED***"
    assert result["headers"]["user_agent"] == "ok"  # non-sensitive survives
    assert result["refresh_token"] == "***REDACTED***"  # *_token rule
    assert result["model"] == "claude-sonnet-4-6"  # non-sensitive survives


def test_logging_truncates_long_values():
    # Values longer than MAX_VALUE_CHARS get truncated with the marker.
    # Short values pass through untouched.
    from sabrina.logging import MAX_VALUE_CHARS, TRUNCATION_MARKER, truncate_long_values

    short = "x" * 100
    long = "y" * (MAX_VALUE_CHARS + 500)
    event = {"short": short, "long": long, "number": 42}
    result = truncate_long_values(None, "info", event)
    assert result["short"] == short
    assert len(result["long"]) == MAX_VALUE_CHARS
    assert result["long"].endswith(TRUNCATION_MARKER)
    assert result["number"] == 42  # non-string untouched


def test_logging_file_sink_writes(tmp_path):
    # setup_logging() creates the log file and writes events through it.
    # Keeps it fast by not exercising rotation — just proves the sink wires up.
    # Redaction is tested again here end-to-end to confirm the processor chain
    # is wired up in the right order (redact before file-tee).
    import logging as _logging

    import structlog

    from sabrina.logging import setup_logging

    log_path = tmp_path / "sabrina.log"
    try:
        setup_logging("INFO", log_file=log_path)

        log = structlog.get_logger("test.bundle")
        log.info("bundle.probe", api_key="should-be-redacted", value="ok")

        # Flush all handlers so the rotating file handler writes to disk.
        for h in _logging.getLogger().handlers:
            h.flush()

        assert log_path.is_file()
        body = log_path.read_text(encoding="utf-8")
        assert "bundle.probe" in body
        assert "should-be-redacted" not in body
        assert "REDACTED" in body
    finally:
        # Clean up so subsequent tests don't inherit our tmp file sink.
        for h in list(_logging.getLogger().handlers):
            _logging.getLogger().removeHandler(h)
            try:
                h.close()
            except Exception:
                pass


