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
    # Embedder backend default is ONNX (decision 011).
    assert sem.embedder.backend == "onnx"


def test_embedder_factory_routes_by_backend():
    """`build_embedder(..., backend=...)` returns the right concrete class."""
    from sabrina.memory.embed import (
        OnnxMiniLMEmbedder,
        SentenceTransformerEmbedder,
        build_embedder,
    )

    onnx = build_embedder(backend="onnx")
    assert isinstance(onnx, OnnxMiniLMEmbedder)
    legacy = build_embedder(backend="sentence-transformers")
    assert isinstance(legacy, SentenceTransformerEmbedder)
    with pytest.raises(ValueError):
        build_embedder(backend="garbage")


def test_embedder_dim_constant_is_384_for_default():
    """Default model is 384-dim — sqlite-vec table is created with this dim."""
    from sabrina.memory.embed import DEFAULT_DIM, DEFAULT_MODEL, OnnxMiniLMEmbedder

    assert DEFAULT_DIM == 384
    assert "MiniLM-L6" in DEFAULT_MODEL
    e = OnnxMiniLMEmbedder()  # cheap; no model load
    assert e.dim == 384


def test_onnx_embedder_round_trip(tmp_path, monkeypatch):
    """Cosine similarity sanity check against a known pair.

    We skip when onnxruntime / tokenizers / the model file are unavailable
    (CI may not have network access). The test guards Eric's "drop-in
    replacement" claim: similar sentences score higher than dissimilar ones,
    and embeddings are L2-normalized so cosine == dot product.
    """
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    from sabrina.memory.embed import OnnxMiniLMEmbedder, ensure_onnx_assets

    # Force the cache into the test dir so we don't pollute the dev tree.
    monkeypatch.setenv("SABRINA_EMBEDDER_CACHE_DIR", str(tmp_path / "embedder_cache"))
    try:
        ensure_onnx_assets()
    except Exception as exc:  # noqa: BLE001 - network-gated test
        pytest.skip(f"can't fetch ONNX assets: {exc}")

    e = OnnxMiniLMEmbedder()
    a = e.embed("the cat sat on the mat")
    b = e.embed("a feline rested on the rug")
    c = e.embed("python list comprehensions are concise")
    assert len(a) == len(b) == len(c) == 384
    # L2-normalized: ||v|| approx 1.
    import math

    for v in (a, b, c):
        assert abs(sum(x * x for x in v) ** 0.5 - 1.0) < 1e-3
    # Synonyms should be much closer than unrelated sentences.
    sim_ab = sum(x * y for x, y in zip(a, b))
    sim_ac = sum(x * y for x, y in zip(a, c))
    assert sim_ab > sim_ac + 0.10, (
        f"expected synonyms (ab={sim_ab:.3f}) to outscore unrelated "
        f"(ac={sim_ac:.3f}) by >= 0.10"
    )


def test_embed_module_no_torch_import():
    """The default embedder path must NOT import torch at module load.

    Regression guard for decision 011: if someone re-introduces a top-level
    `import torch` (or sentence_transformers, which pulls torch), `pytest -q`
    will fail before the legacy-embedder extra is installed.
    """
    import importlib
    import sys

    sys.modules.pop("sabrina.memory.embed", None)
    importlib.import_module("sabrina.memory.embed")
    assert "torch" not in sys.modules
    assert "sentence_transformers" not in sys.modules


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


# --- decision 009: barge-in ---


def test_cancel_token_basic():
    # Monotonic boolean flag. `.cancel()` sticks; `.cancelled` reports truthfully.
    from sabrina.brain.protocol import CancelToken

    t = CancelToken()
    assert t.cancelled is False
    t.cancel()
    assert t.cancelled is True
    # Idempotent — calling cancel twice is a no-op, not an error.
    t.cancel()
    assert t.cancelled is True


async def test_cancel_token_propagates_through_stub_brain():
    # Stub brain that yields deltas until the token trips, then emits a
    # final Done. Confirms the protocol contract: "check between yields;
    # bail promptly with stop_reason='cancelled'."
    from collections.abc import AsyncIterator

    from sabrina.brain.protocol import (
        CancelToken,
        Done,
        Message,
        StreamEvent,
        TextDelta,
    )

    class StubBrain:
        name = "stub"

        async def chat(
            self,
            messages: list[Message],
            *,
            system: str | None = None,
            max_tokens: int | None = None,
            cancel_token: CancelToken | None = None,
        ) -> AsyncIterator[StreamEvent]:
            for i in range(5):
                if cancel_token is not None and cancel_token.cancelled:
                    yield Done(stop_reason="cancelled")
                    return
                yield TextDelta(text=f"chunk{i} ")
            yield Done(stop_reason="end_turn")

    token = CancelToken()
    brain = StubBrain()
    events: list[StreamEvent] = []
    async for ev in brain.chat([], cancel_token=token):
        events.append(ev)
        if isinstance(ev, TextDelta) and ev.text == "chunk1 ":
            token.cancel()

    # We should see chunk0, chunk1, then Done(cancelled). No chunk2+.
    texts = [e.text for e in events if isinstance(e, TextDelta)]
    assert texts == ["chunk0 ", "chunk1 "]
    done = [e for e in events if isinstance(e, Done)]
    assert len(done) == 1
    assert done[0].stop_reason == "cancelled"


async def test_cancel_token_stops_stub_speaker():
    # Stub speaker that loops sleeping-and-checking. Cancelling the token
    # must break its loop within a bounded time; verify the polling
    # pattern the real speakers use actually works.
    import asyncio as _asyncio

    from sabrina.brain.protocol import CancelToken
    from sabrina.speaker.protocol import SpeakResult

    class StubSpeaker:
        name = "stub"

        async def speak(
            self,
            text: str,
            *,
            voice: str | None = None,
            cancel_token: CancelToken | None = None,
        ) -> SpeakResult:
            # Simulate chunked playback. Check the token between chunks.
            for _ in range(50):  # would take 5s if we waited
                if cancel_token is not None and cancel_token.cancelled:
                    break
                await _asyncio.sleep(0.01)
            return SpeakResult(engine=self.name, duration_s=0.0)

        async def stop(self) -> None:
            return None

    token = CancelToken()
    sp = StubSpeaker()
    # Cancel 30ms in; speak should return promptly after the next chunk check.
    task = _asyncio.create_task(sp.speak("hello", cancel_token=token))
    await _asyncio.sleep(0.03)
    token.cancel()
    result = await _asyncio.wait_for(task, timeout=0.5)
    assert result.engine == "stub"


def test_vad_state_machine_ignores_below_min_speech_ms(monkeypatch):
    # Feed a burst of "speech" shorter than min_speech_ms, then silence.
    # VAD should never fire. Mocks the model so the test doesn't require
    # loading Silero's ONNX weights — isolates the state-machine logic.
    import numpy as np

    from sabrina.listener.vad import SileroVAD, _FRAME_SAMPLES

    class _Prob:
        def __init__(self, v: float) -> None:
            self._v = v

        def item(self) -> float:
            return self._v

    vad = SileroVAD(threshold=0.5, min_speech_ms=300)
    # 300 ms at 16 kHz = 4800 samples = ~9.4 frames of 512. So we need
    # 10+ consecutive high-prob frames to fire.
    probs = iter([0.9, 0.9, 0.9, 0.1] * 10)  # bursts of 3 high then silence
    vad._model = lambda _frame, _sr: _Prob(next(probs))

    # Feed 12 frames — speech-silence-speech-silence pattern means each
    # burst is only 3 frames before resetting. Never reaches 10 in a row.
    samples = np.ones(_FRAME_SAMPLES * 12, dtype=np.float32)
    assert vad.feed(samples) is False


def test_vad_fires_on_sustained_speech(monkeypatch):
    # Same rig, but the model returns high prob for long enough to clear
    # min_speech_ms. Confirms the gate actually opens on sustained speech.
    import numpy as np

    from sabrina.listener.vad import SileroVAD, _FRAME_SAMPLES

    class _Prob:
        def __init__(self, v: float) -> None:
            self._v = v

        def item(self) -> float:
            return self._v

    vad = SileroVAD(threshold=0.5, min_speech_ms=300)
    vad._model = lambda _frame, _sr: _Prob(0.95)  # always "speech"

    # 15 frames of constant speech — well past the 10-frame / 300 ms gate.
    samples = np.ones(_FRAME_SAMPLES * 15, dtype=np.float32)
    assert vad.feed(samples) is True


def test_make_barge_in_vad_degrades_on_load_failure(monkeypatch):
    """A broken silero-vad install must not crash voice loop startup.

    We swap SileroVAD._ensure_loaded for one that raises, force barge-in
    on in the config, and assert _make_barge_in_vad returns None — the
    voice loop then runs happily without barge-in.
    """
    from sabrina.config import load_settings
    from sabrina.listener.vad import SileroVAD
    from sabrina.voice_loop import _make_barge_in_vad

    def _raise(self):
        raise ImportError("silero-vad stub failure")

    monkeypatch.setattr(SileroVAD, "_ensure_loaded", _raise)
    settings = load_settings(reload=True)
    # Barge-in ships disabled by default; force it on for this test.
    settings.barge_in.enabled = True

    assert _make_barge_in_vad(settings) is None


def test_audio_monitor_trims_capture_to_speech_onset():
    """stop() drops pre-fire silence, keeps speech window + margin + post-fire.

    Populates AudioMonitor's state directly (bypassing sounddevice) to
    exercise just the stop()-side trim math: _fire_at_samples is set at
    the end of the speech window, and stop() should walk back by
    speech_window_samples + _PRE_FIRE_MARGIN_MS and keep everything
    from there forward.
    """
    import numpy as np

    from sabrina.brain.protocol import CancelToken
    from sabrina.listener.vad import (
        _PRE_FIRE_MARGIN_MS,
        _SAMPLE_RATE,
        AudioMonitor,
        SileroVAD,
    )

    vad = SileroVAD(threshold=0.5, min_speech_ms=300)  # 4800-sample window
    token = CancelToken()
    mon = AudioMonitor(vad, token)

    # 1.0 s of pre-fire capture (silence / TTS bleed) + the 300 ms speech
    # window (fires at its end) + 0.5 s of post-fire capture (the user
    # still talking after the cancel).
    pre = np.zeros(_SAMPLE_RATE, dtype=np.float32)            # 16000
    speech = np.ones(4800, dtype=np.float32)                  # 4800
    post = np.ones(_SAMPLE_RATE // 2, dtype=np.float32)       # 8000

    mon._captured = [pre, speech, post]
    mon._detected = True
    mon._fire_at_samples = pre.size + speech.size             # 20800

    out = mon.stop()

    assert out is not None
    margin_samples = int(_PRE_FIRE_MARGIN_MS * _SAMPLE_RATE / 1000)  # 2400
    # keep_from = 20800 - 4800 - 2400 = 13600
    # full size = 28800 ; expected out = 28800 - 13600 = 15200
    full = pre.size + speech.size + post.size
    expected = full - (mon._fire_at_samples - 4800 - margin_samples)
    assert out.size == expected
    # Sanity: output starts in the pre-fire silence region and extends
    # through the post-fire chunk (which is 1.0 in this setup).
    assert out[0] == 0.0
    assert out[-1] == 1.0


# --- step 1 (overnight): logging-vocabulary completion ---


def test_turn_id_binds_during_simulated_turn(tmp_path):
    """A log event emitted while turn_id is bound must carry it; outside, must not.

    Mirrors the voice-loop pattern: bind at top of iteration, unbind in finally.
    Uses a tmp file sink + the real structlog config so the contextvars
    processor is exercised end-to-end.
    """
    import json
    import logging as _logging

    import structlog

    from sabrina.logging import setup_logging

    log_path = tmp_path / "sabrina.log"
    try:
        setup_logging("INFO", log_file=log_path)
        log = structlog.get_logger("test.turnid")

        log.info("turn.outside_before")  # no turn_id bound
        structlog.contextvars.bind_contextvars(turn_id="abc12345")
        try:
            log.info("turn.started")
        finally:
            structlog.contextvars.unbind_contextvars("turn_id")
        log.info("turn.outside_after")  # turn_id should be cleared

        for h in _logging.getLogger().handlers:
            h.flush()

        # File sink writes JSON-per-line via _make_file_tee. Each event becomes
        # one line; assert presence/absence of turn_id per line.
        body = log_path.read_text(encoding="utf-8")
        lines = [ln for ln in body.splitlines() if ln.strip()]
        events = [json.loads(ln) for ln in lines if ln.lstrip().startswith("{")]

        before = next(e for e in events if e["event"] == "turn.outside_before")
        started = next(e for e in events if e["event"] == "turn.started")
        after = next(e for e in events if e["event"] == "turn.outside_after")

        assert "turn_id" not in before
        assert started.get("turn_id") == "abc12345"
        assert "turn_id" not in after
    finally:
        for h in list(_logging.getLogger().handlers):
            _logging.getLogger().removeHandler(h)
            try:
                h.close()
            except Exception:
                pass


def test_voice_loop_imports_structlog_and_uuid_for_turn_correlation():
    """Sanity-check that the voice loop module wires the correlation pieces.

    The plan calls for `structlog.contextvars.bind_contextvars(turn_id=...)`
    on turn-start and `unbind_contextvars` on turn-end. We grep the module
    source rather than spinning up an asyncio loop here -- the integration
    test above exercises the end-to-end contextvar flow.
    """
    from pathlib import Path as _Path

    src = _Path(__file__).resolve().parents[1] / "src" / "sabrina" / "voice_loop.py"
    body = src.read_text(encoding="utf-8")
    assert "import structlog" in body
    assert "import uuid" in body
    assert "bind_contextvars(turn_id=" in body
    assert 'unbind_contextvars("turn_id")' in body
    # And the canonical turn.* event names are emitted.
    assert '"turn.started"' in body
    assert '"turn.done"' in body
    assert '"turn.first_audio_ms"' in body


def test_logging_vocabulary_renames_landed():
    """Renames per the logging-vocabulary plan: fw.* -> asr.*, rec.* -> asr.rec.*."""
    from pathlib import Path as _Path

    pkg = _Path(__file__).resolve().parents[1] / "src" / "sabrina"
    fw = (pkg / "listener" / "faster_whisper.py").read_text(encoding="utf-8")
    rec = (pkg / "listener" / "record.py").read_text(encoding="utf-8")
    vl = (pkg / "voice_loop.py").read_text(encoding="utf-8")

    # Old names must be gone from these files.
    assert '"fw.loading"' not in fw
    assert '"fw.loaded"' not in fw
    assert '"fw.cuda_detect_failed"' not in fw
    assert '"rec.start"' not in rec
    assert '"rec.done"' not in rec
    assert '"embedder.ready"' not in vl
    assert '"embedder.warmup_failed"' not in vl

    # Canonical names present.
    assert '"asr.loading"' in fw
    assert '"asr.loaded"' in fw
    assert '"asr.cuda_detect_failed"' in fw
    assert '"asr.rec.started"' in rec
    assert '"asr.rec.done"' in rec
    assert '"embed.ready"' in vl
    assert '"embed.warmup_failed"' in vl
    assert '"brain.error"' in vl


# --- step 2 (overnight): wake-word scaffolding ---


class _StubOpenWakeWordModel:
    """In-memory stand-in for openwakeword.model.Model."""

    def __init__(self, scores: dict[str, float] | None = None) -> None:
        self._scores = scores or {"hey_jarvis": 0.0}
        self.predict_calls: list = []
        self.reset_calls = 0

    def predict(self, frame_i16):  # noqa: ANN001
        self.predict_calls.append(int(getattr(frame_i16, "size", 0)))
        return dict(self._scores)

    def reset(self) -> None:
        self.reset_calls += 1


def _wake_with_stub(monkeypatch, scores):
    """Build a WakeWordDetector wired to the stub model."""
    from sabrina.listener import wake_word

    stub = _StubOpenWakeWordModel(scores=scores)
    # wake_word imports openwakeword inside `_ensure_loaded`; replace
    # the lookup so neither the real package nor onnxruntime is needed.
    fake_module = type(
        "fake_owww_model_module", (), {"Model": lambda **_kwargs: stub}
    )
    fake_pkg = type("fake_owww_pkg", (), {"model": fake_module})
    monkeypatch.setitem(__import__("sys").modules, "openwakeword", fake_pkg)
    monkeypatch.setitem(__import__("sys").modules, "openwakeword.model", fake_module)
    return wake_word.WakeWordDetector(model="hey_jarvis", threshold=0.5), stub


def test_wake_word_detector_below_threshold_returns_none(monkeypatch):
    """Score < threshold -> feed() returns None, no fire."""
    import numpy as np

    detector, _stub = _wake_with_stub(monkeypatch, scores={"hey_jarvis": 0.2})
    chunk = np.zeros(1280, dtype=np.float32)
    assert detector.feed(chunk) is None


def test_wake_word_detector_fires_at_threshold(monkeypatch):
    """Score >= threshold past first frame -> feed() returns the score."""
    import numpy as np

    detector, _stub = _wake_with_stub(monkeypatch, scores={"hey_jarvis": 0.9})
    chunk = np.zeros(1280, dtype=np.float32)
    score = detector.feed(chunk)
    assert score == 0.9


def test_wake_word_detector_cooldown_suppresses_rapid_retriggers(monkeypatch):
    """Two hot frames inside cooldown -> only the first fires."""
    import numpy as np

    detector, _stub = _wake_with_stub(monkeypatch, scores={"hey_jarvis": 0.9})
    # Wake_word default cooldown is 2000ms. Feed two back-to-back chunks.
    chunk = np.zeros(1280, dtype=np.float32)
    first = detector.feed(chunk)
    second = detector.feed(chunk)
    assert first == 0.9
    assert second is None


def test_wake_word_detector_does_not_fire_on_noise_below_threshold(monkeypatch):
    """Repeated noise frames below threshold never fire."""
    import numpy as np

    detector, _stub = _wake_with_stub(monkeypatch, scores={"hey_jarvis": 0.4})
    rng = np.random.default_rng(42)
    for _ in range(10):
        # Random low-amplitude noise. Score is hardcoded by the stub
        # regardless, but we confirm there's no accidental fire from
        # any path-quirk.
        chunk = rng.standard_normal(1280).astype(np.float32) * 0.01
        assert detector.feed(chunk) is None


def test_wake_word_config_round_trip():
    """[wake_word] block in sabrina.toml round-trips through pydantic."""
    from sabrina.config import load_settings

    s = load_settings(reload=True)
    assert s.wake_word.enabled is False
    assert s.wake_word.model == "hey_jarvis"
    assert 0.0 <= s.wake_word.threshold <= 1.0
    assert s.wake_word.cooldown_ms > 0


# --- step 3 (overnight): supervisor + autostart ---


def _supervisor_cfg(**overrides):
    """Build a SupervisorConfig with sensible test defaults overridden."""
    from sabrina.config import SupervisorConfig

    base = dict(
        mode="task_scheduler",
        task_name="SabrinaTest",
        restart_max=3,
        restart_window_s=60,
        nssm_binary="",
    )
    base.update(overrides)
    return SupervisorConfig(**base)


def test_supervisor_exits_on_clean_child_exit():
    """rc 0 from the child -> supervisor returns 0 immediately, no restart."""
    from sabrina.supervisor import run_supervised

    spawn_calls = []

    def stub_spawn(_argv):
        spawn_calls.append(1)
        return 0

    rc = run_supervised(
        ["python", "stub"], _supervisor_cfg(), spawner=stub_spawn, sleeper=lambda _s: None
    )
    assert rc == 0
    assert len(spawn_calls) == 1


def test_supervisor_restarts_within_budget_then_gives_up():
    """Crashes inside window count toward `restart_max`; over -> rc 2."""
    from sabrina.supervisor import run_supervised

    sleeps: list[float] = []
    spawn_calls: list[int] = []

    def stub_spawn(_argv):
        spawn_calls.append(1)
        return 1  # crash

    rc = run_supervised(
        ["python", "stub"],
        _supervisor_cfg(restart_max=2),
        spawner=stub_spawn,
        sleeper=lambda s: sleeps.append(s),
    )
    assert rc == 2
    # restart_max=2 means: first crash counts (1 entry, not exceeded),
    # second crash counts (2 entries, not exceeded > max=2 is False),
    # third crash (3 entries) -> exceeded -> bail. So 3 spawns.
    assert len(spawn_calls) == 3
    # Backoff doubles per consecutive crash, capped at 60.
    assert sleeps[0] == 2.0
    assert sleeps[1] == 4.0


def test_supervisor_user_interrupt_returns_immediately():
    """Exit codes that mean Ctrl+C must not respawn."""
    from sabrina.supervisor import run_supervised

    def stub_spawn(_argv):
        return 130  # POSIX SIGINT exit code

    rc = run_supervised(
        ["python", "stub"], _supervisor_cfg(), spawner=stub_spawn, sleeper=lambda _s: None
    )
    assert rc == 130


def test_supervisor_backoff_caps_at_60_seconds():
    """Consecutive backoff grows but never exceeds the documented 60 s cap."""
    from sabrina.supervisor import run_supervised

    sleeps: list[float] = []

    def stub_spawn(_argv):
        return 1

    run_supervised(
        ["python", "stub"],
        _supervisor_cfg(restart_max=12),
        spawner=stub_spawn,
        sleeper=lambda s: sleeps.append(s),
    )
    assert max(sleeps) <= 60.0


def test_task_scheduler_xml_renders_with_paths_and_user():
    """XML contains the python exe, project root, and user verbatim."""
    from sabrina.supervisor import render_task_scheduler_xml

    xml = render_task_scheduler_xml(
        python_executable=r"C:\Python312\python.exe",
        project_root=r"C:\projects\sabrina-2",
        user_id="DESKTOP-ABC\\eric",
    )
    assert "<LogonTrigger>" in xml
    assert "<Command>C:\Python312\python.exe</Command>" in xml
    assert "<Arguments>-m sabrina run</Arguments>" in xml
    assert "<WorkingDirectory>C:\projects\sabrina-2</WorkingDirectory>" in xml
    assert "DESKTOP-ABC\\eric" in xml


def test_task_scheduler_xml_carries_restart_on_failure_block():
    """RestartOnFailure block (P2.6 spec Q1 (a)): defense-in-depth recovery.

    Per `rebuild/drafts/research/2026-05-07-p26-supervisor-validation-spec.md`
    Q1 (a), answered A 2026-05-15 via dashboard at NEEDS-INPUT.md:75. Without
    this block, a supervisor-itself-crash (rc 2 budget-exceeded, or an
    unhandled exception in `run_supervised`) leaves Sabrina silent until Eric
    manually re-runs `sabrina run`. With it, Task Scheduler re-launches the
    supervisor up to three times at 5-minute intervals.
    """
    from sabrina.supervisor import render_task_scheduler_xml

    xml = render_task_scheduler_xml(
        python_executable="x",
        project_root="y",
        user_id="z",
    )
    assert "<RestartOnFailure>" in xml
    assert "<Interval>PT5M</Interval>" in xml
    assert "<Count>3</Count>" in xml
    assert "</RestartOnFailure>" in xml


def test_task_scheduler_xml_writes_with_utf16_le_bom(tmp_path):
    """schtasks /xml requires UTF-16 LE with a BOM. We assert both bytes."""
    from sabrina.supervisor import render_task_scheduler_xml, write_task_scheduler_xml

    xml = render_task_scheduler_xml(
        python_executable="x",
        project_root="y",
        user_id="z",
    )
    out = tmp_path / "task.xml"
    write_task_scheduler_xml(out, xml)
    raw = out.read_bytes()
    # BOM is 0xFF 0xFE for little-endian UTF-16.
    assert raw[:2] == b"\xff\xfe"
    # Body must round-trip through utf-16-le decoding.
    decoded = raw[2:].decode("utf-16-le")
    assert decoded == xml


def test_task_scheduler_install_invokes_schtasks(tmp_path):
    """Install path shells out to schtasks /create /tn ... /xml ... /f."""
    from sabrina.supervisor import install_task_scheduler_task

    captured: list[list[str]] = []

    def fake_run(cmd):
        captured.append(cmd)
        return 0

    rc = install_task_scheduler_task(
        task_name="SabrinaTest",
        xml_path=tmp_path / "task.xml",
        runner=fake_run,
    )
    assert rc == 0
    assert captured == [
        ["schtasks", "/create", "/tn", "SabrinaTest", "/xml",
         str(tmp_path / "task.xml"), "/f"],
    ]


def test_nssm_install_command_sequence_shape():
    """Install sequence for service mode: install + 5 set + restart-default."""
    from sabrina.supervisor import build_nssm_install_commands

    cmds = build_nssm_install_commands(
        task_name="SabrinaTest",
        python_executable="C:/Python312/python.exe",
        project_root="C:/sabrina",
        nssm_binary="C:/tools/nssm.exe",
        log_path="C:/sabrina/logs/service.log",
    )
    assert len(cmds) == 6
    assert cmds[0][:3] == ["C:/tools/nssm.exe", "install", "SabrinaTest"]
    # The post-install configures all live in `nssm set`.
    for c in cmds[1:]:
        assert c[:3] == ["C:/tools/nssm.exe", "set", "SabrinaTest"]
    # AppExit Default Restart pair tells nssm to restart on crash too.
    assert ["AppExit", "Default", "Restart"] == cmds[-1][3:]


def test_supervisor_config_round_trip():
    """[supervisor] block round-trips through pydantic."""
    from sabrina.config import load_settings

    s = load_settings(reload=True)
    assert s.supervisor.mode in ("task_scheduler", "service")
    assert s.supervisor.task_name == "SabrinaAI"
    assert s.supervisor.restart_max >= 1
    assert s.supervisor.restart_window_s >= 1


# --- step 4 (overnight): semantic-memory GUI + compaction ---


def test_memory_store_migrates_to_v1_idempotently(tmp_path):
    """First open adds kind+summarized_at; second open is a no-op."""
    import sqlite3

    from sabrina.memory.store import MemoryStore

    db = tmp_path / "memory.db"
    store = MemoryStore(db_path=db)
    cols = {row[1] for row in store._conn.execute("PRAGMA table_info(messages)")}
    assert "kind" in cols
    assert "summarized_at" in cols
    v = store._conn.execute("PRAGMA user_version").fetchone()[0]
    assert v == 1
    store.close()
    # Re-open should not error.
    store2 = MemoryStore(db_path=db)
    v2 = store2._conn.execute("PRAGMA user_version").fetchone()[0]
    assert v2 == 1
    store2.close()


def test_memory_store_load_summaries_returns_only_summary_rows(tmp_path):
    from sabrina.memory.store import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.db")
    store.append("s1", "user", "what time is it?")
    store.append("s1", "assistant", "around 9 am")
    sid = store.append_summary("s1", "User asked about the time.")
    summaries = store.load_summaries()
    assert len(summaries) == 1
    assert summaries[0].id == sid
    assert summaries[0].content == "User asked about the time."
    # load_recent must NOT return the summary.
    recent = store.load_recent(limit=10)
    roles = [m.role for m in recent]
    assert "user" in roles
    assert all(m.id != sid for m in recent)
    store.close()


def test_memory_store_count_uncompacted_drops_after_mark(tmp_path):
    from sabrina.memory.store import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.db")
    ids = [store.append("s1", "user", f"turn {i}") for i in range(5)]
    assert store.count_uncompacted() == 5
    store.mark_summarized(ids[:3])
    assert store.count_uncompacted() == 2
    store.close()


def test_memory_store_total_turn_chars_excludes_marked(tmp_path):
    from sabrina.memory.store import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.db")
    ids = []
    for body in ["aaaa", "bbbbbb", "cccccccc"]:
        ids.append(store.append("s1", "user", body))
    assert store.total_turn_chars() == 4 + 6 + 8
    store.mark_summarized(ids[:1])  # the 4-char one
    assert store.total_turn_chars() == 6 + 8
    # only_uncompacted=False counts all turn rows.
    assert store.total_turn_chars(only_uncompacted=False) == 4 + 6 + 8
    store.close()


def test_compaction_should_compact_below_threshold_returns_false(tmp_path):
    from sabrina.config import CompactionConfig
    from sabrina.memory.compaction import should_compact
    from sabrina.memory.store import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.db")
    store.append("s1", "user", "x" * 100)
    cfg = CompactionConfig(mode="auto", threshold_tokens=10_000, batch_size=200, chars_per_token=4.0)
    assert should_compact(store, cfg) is False
    store.close()


def test_compaction_should_compact_above_threshold_returns_true(tmp_path):
    from sabrina.config import CompactionConfig
    from sabrina.memory.compaction import should_compact
    from sabrina.memory.store import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.db")
    # 40,000 chars / 4 chars-per-token = 10,000 tokens.
    store.append("s1", "user", "x" * 40_000)
    cfg = CompactionConfig(
        mode="auto", threshold_tokens=5_000, batch_size=200, chars_per_token=4.0
    )
    assert should_compact(store, cfg) is True
    store.close()


def test_compaction_manual_mode_never_auto_triggers(tmp_path):
    from sabrina.config import CompactionConfig
    from sabrina.memory.compaction import should_compact
    from sabrina.memory.store import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.db")
    store.append("s1", "user", "x" * 1_000_000)  # huge corpus
    cfg = CompactionConfig(
        mode="manual", threshold_tokens=10, batch_size=200, chars_per_token=4.0
    )
    # Even with overflowing content, manual mode never auto-triggers.
    assert should_compact(store, cfg) is False
    store.close()


async def test_compaction_compacts_marks_originals_and_writes_summary(tmp_path):
    from sabrina.config import CompactionConfig
    from sabrina.memory.compaction import compact, make_callable_summarizer
    from sabrina.memory.store import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.db")
    for i in range(20):
        store.append("s1", "user" if i % 2 == 0 else "assistant", f"turn {i}")

    captured_transcripts: list[str] = []

    async def fake_summarize(transcript: str) -> str:
        captured_transcripts.append(transcript)
        return "User and assistant exchanged 20 turns about test data."

    summarizer = make_callable_summarizer(fake_summarize)
    cfg = CompactionConfig(
        mode="auto", threshold_tokens=10, batch_size=20, chars_per_token=4.0
    )
    result = await compact(store, summarizer, cfg, force=True)

    assert result.summaries_written == 1
    assert result.turns_compacted == 20
    assert len(captured_transcripts) == 1
    # Summary row written; turns marked.
    summaries = store.load_summaries()
    assert len(summaries) == 1
    assert "exchanged 20 turns" in summaries[0].content
    assert store.count_uncompacted() == 0
    store.close()


async def test_compaction_skips_when_below_threshold_and_not_forced(tmp_path):
    from sabrina.config import CompactionConfig
    from sabrina.memory.compaction import compact, make_callable_summarizer
    from sabrina.memory.store import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.db")
    store.append("s1", "user", "small")

    summarize_called = []

    async def fake_summarize(_t):
        summarize_called.append(1)
        return "should not be called"

    cfg = CompactionConfig(
        mode="auto", threshold_tokens=10_000, batch_size=200, chars_per_token=4.0
    )
    result = await compact(
        store, make_callable_summarizer(fake_summarize), cfg
    )
    assert result.skipped_reason == "below_threshold"
    assert summarize_called == []
    store.close()


# --- Phase 2 deferred items: regression guards ---


def test_voice_loop_summary_block_helper_returns_none_for_no_summaries(tmp_path):
    """`_summary_block(memory)` -> None when there are no summary rows."""
    from sabrina.memory.store import MemoryStore
    from sabrina.voice_loop import _summary_block

    with MemoryStore(tmp_path / "mem.db") as m:
        assert _summary_block(m) is None


def test_voice_loop_summary_block_renders_header_and_rows(tmp_path):
    """`_summary_block(memory)` -> 'Long-term memory ...' + one line per summary."""
    from sabrina.memory.store import MemoryStore, new_session_id
    from sabrina.voice_loop import _summary_block

    with MemoryStore(tmp_path / "mem.db") as m:
        sid = new_session_id()
        m.append_summary(sid, "user is named eric, prefers terse replies")
        m.append_summary(sid, "user is rebuilding sabrina; second-gen project")
        block = _summary_block(m)
    assert block is not None
    assert block.startswith("Long-term memory")
    assert "user is named eric" in block
    assert "second-gen project" in block


def test_voice_loop_imports_wake_word_classes():
    """voice_loop should import WakeWordDetector + WakeWordMonitor for idle wiring."""
    from pathlib import Path

    src = (Path(__file__).parent.parent / "src/sabrina/voice_loop.py").read_text()
    assert "WakeWordDetector" in src
    assert "WakeWordMonitor" in src


def test_cli_memory_compact_command_registered():
    """`sabrina memory-compact` should be a registered Typer command."""
    from sabrina.cli import app

    names = {cmd.name for cmd in app.registered_commands}
    assert "memory-compact" in names


def test_cli_download_models_command_registered():
    """`sabrina download-models` should be a registered Typer command."""
    from sabrina.cli import app

    names = {cmd.name for cmd in app.registered_commands}
    assert "download-models" in names


def test_gui_settings_window_has_mainloop_method():
    """Regression for Phase 0 finding: SettingsWindow.mainloop dropped."""
    from sabrina.gui.settings import SettingsWindow

    assert hasattr(SettingsWindow, "mainloop")
    assert callable(SettingsWindow.mainloop)


def test_gui_collect_filters_underscore_keys_and_translates_preset():
    """GUI _collect: underscore-prefixed control vars don't leak; _piper_preset
    translates to tts.piper.voice_model."""
    from sabrina.gui.settings import SettingsWindow

    class _FakeVar:
        def __init__(self, v):
            self._v = v

        def get(self):
            return self._v

    win = SettingsWindow.__new__(SettingsWindow)
    win._vars = {
        "memory.enabled": _FakeVar(True),
        "_piper_preset": _FakeVar("amy-medium"),
    }
    out = SettingsWindow._collect(win)
    assert "_piper_preset" not in out
    assert out.get("tts.piper.voice_model") == "voices/en_US-amy-medium.onnx"
    assert out["memory.enabled"] is True


# --- step 1 (overnight 2026-04-26): ToolSpec MCP shape ---


def test_toolspec_to_anthropic_dict_uses_input_schema_key():
    """`to_anthropic_dict()` returns the snake_case `input_schema` key the
    Anthropic SDK expects."""
    from sabrina.tools import ToolSpec

    async def _h(**_kw):
        return {"ok": True}

    spec = ToolSpec(
        name="dummy",
        description="A dummy tool used in tests.",
        input_schema={
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
        handler=_h,
    )
    out = spec.to_anthropic_dict()
    assert out == {
        "name": "dummy",
        "description": "A dummy tool used in tests.",
        "input_schema": {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
    }
    # Handler is intentionally NOT in the wire payload.
    assert "handler" not in out


def test_toolspec_to_mcp_dict_uses_camelcase_input_schema_key():
    """`to_mcp_dict()` returns `inputSchema` (camelCase) per the MCP
    `tools/list` spec — same content, different field name."""
    from sabrina.tools import ToolSpec

    async def _h(**_kw):
        return {"ok": True}

    spec = ToolSpec(
        name="dummy",
        description="A dummy tool used in tests.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_h,
    )
    out = spec.to_mcp_dict()
    assert "inputSchema" in out
    assert "input_schema" not in out
    # Top-level field set matches the published MCP tool schema.
    assert set(out.keys()) == {"name", "description", "inputSchema"}
    assert out["inputSchema"] == {"type": "object", "properties": {}, "required": []}


def test_toolspec_round_trip_both_serializations_share_payload():
    """Both serializations must carry the same name/description/schema —
    only the schema key name differs."""
    from sabrina.tools import ToolSpec

    async def _h(**_kw):
        return {}

    schema = {
        "type": "object",
        "properties": {"x": {"type": "integer", "minimum": 0}},
        "required": ["x"],
    }
    spec = ToolSpec(
        name="dummy",
        description="Round-trip fixture.",
        input_schema=schema,
        handler=_h,
    )
    a = spec.to_anthropic_dict()
    m = spec.to_mcp_dict()
    assert a["name"] == m["name"] == "dummy"
    assert a["description"] == m["description"] == "Round-trip fixture."
    assert a["input_schema"] == m["inputSchema"] == schema


def test_toolspec_mcp_shape_has_required_fields_per_spec():
    """The MCP tool schema requires `name`, `description`, `inputSchema`
    at minimum. Guard against drift."""
    from sabrina.tools import BUILTIN_TOOLS

    assert BUILTIN_TOOLS, "BUILTIN_TOOLS must ship at least one tool"
    for spec in BUILTIN_TOOLS:
        d = spec.to_mcp_dict()
        for key in ("name", "description", "inputSchema"):
            assert key in d, f"missing {key!r} in {spec.name}"
        # inputSchema must itself be a JSON-Schema-shaped object.
        assert d["inputSchema"]["type"] == "object"
        assert "properties" in d["inputSchema"]


# --- step 2 (overnight 2026-04-26): write_clipboard tool ---


def test_write_clipboard_registered_in_builtin_tools():
    from sabrina.tools import BUILTIN_TOOLS, find

    spec = find("write_clipboard")
    assert spec is not None, "write_clipboard must be in BUILTIN_TOOLS"
    assert spec in BUILTIN_TOOLS
    # Schema accepts a `content` string and requires it.
    assert spec.input_schema["required"] == ["content"]
    assert spec.input_schema["properties"]["content"]["type"] == "string"


async def test_write_clipboard_writes_via_pyperclip(monkeypatch):
    """Happy-path: the handler routes to the pyperclip backend and
    returns success + byte length."""
    from sabrina.tools import clipboard as clip_mod

    captured: list[str] = []

    def fake_pp(text: str) -> None:
        captured.append(text)

    monkeypatch.setattr(clip_mod, "_set_clipboard_pyperclip", fake_pp)
    # Make sure the native fallback can never be reached (would shell
    # out for real on this test box).
    def _fail(_t):
        raise AssertionError("native fallback should not be invoked")
    monkeypatch.setattr(clip_mod, "_set_clipboard_native", _fail)

    result = await clip_mod.write_clipboard(content="hello from sabrina")
    assert result == {"success": True, "length": len("hello from sabrina")}
    assert captured == ["hello from sabrina"]


async def test_write_clipboard_falls_back_to_native_when_pyperclip_raises(monkeypatch):
    """If the pyperclip backend errors (broken install, no display),
    the handler must fall through to the native subprocess path."""
    from sabrina.tools import clipboard as clip_mod

    def fake_pp(_text: str) -> None:
        raise RuntimeError("pyperclip not available")

    native_calls: list[str] = []

    def fake_native(text: str) -> None:
        native_calls.append(text)

    monkeypatch.setattr(clip_mod, "_set_clipboard_pyperclip", fake_pp)
    monkeypatch.setattr(clip_mod, "_set_clipboard_native", fake_native)

    result = await clip_mod.write_clipboard(content="abc")
    assert result == {"success": True, "length": 3}
    assert native_calls == ["abc"]


async def test_write_clipboard_truncates_input_above_max_bytes(monkeypatch):
    """Long inputs are clamped at the byte cap. Reported length reflects
    the truncated payload."""
    from sabrina.tools import clipboard as clip_mod

    captured: list[str] = []

    def fake_pp(text: str) -> None:
        captured.append(text)

    monkeypatch.setattr(clip_mod, "_set_clipboard_pyperclip", fake_pp)

    # 200 KB of ASCII; cap is 100 KB. Truncation policy: take MAX_BYTES//4
    # characters (which is ~25 KB ASCII bytes — well under the cap).
    long_text = "x" * 200_000
    result = await clip_mod.write_clipboard(content=long_text)
    assert result["success"] is True
    assert result["length"] <= clip_mod._MAX_BYTES
    # Backend got the truncated string, not the original.
    assert captured and len(captured[0]) < len(long_text)


async def test_write_clipboard_returns_failure_on_backend_error(monkeypatch):
    """If both backends raise, the handler returns success=False rather
    than propagating — the brain shouldn't crash on a clipboard hiccup."""
    from sabrina.tools import clipboard as clip_mod

    def boom(_t):
        raise RuntimeError("clipboard contended")

    monkeypatch.setattr(clip_mod, "_set_clipboard_pyperclip", boom)
    monkeypatch.setattr(clip_mod, "_set_clipboard_native", boom)

    result = await clip_mod.write_clipboard(content="x")
    assert result["success"] is False
    assert result["length"] == 0
    assert "error" in result


async def test_write_clipboard_rejects_non_string_content():
    """Handler is defensive against bad model output (None, dict, ...)."""
    from sabrina.tools.clipboard import write_clipboard

    result = await write_clipboard(content=None)  # type: ignore[arg-type]
    assert result["success"] is False
    assert "error" in result


def test_tools_config_block_loads_with_defaults():
    from sabrina.config import load_settings

    s = load_settings(reload=True)
    # Master switch defaults off; per-tool defaults on.
    assert s.tools.enabled is False
    assert "write_clipboard" in s.tools.allowed
    assert s.tools.write_clipboard.enabled is True
    assert s.tools.write_clipboard.max_bytes == 100_000


# --- step 3 (overnight 2026-04-26): Park-style retrieval scoring ---


def test_memory_store_migrates_to_v2_adds_importance_column(tmp_path):
    """Schema v1 -> v2 adds importance REAL DEFAULT 0.5; idempotent."""
    from sabrina.memory.store import MemoryStore

    db = tmp_path / "memory.db"
    with MemoryStore(db_path=db) as store:
        cols = {row[1] for row in store._conn.execute("PRAGMA table_info(messages)")}
        assert "importance" in cols
        v = store._conn.execute("PRAGMA user_version").fetchone()[0]
        assert v == 2
    # Re-open: must not double-migrate.
    with MemoryStore(db_path=db) as store2:
        v2 = store2._conn.execute("PRAGMA user_version").fetchone()[0]
        assert v2 == 2


def test_memory_store_default_importance_is_half(tmp_path):
    """Newly-inserted rows default to importance=0.5 (neutral midpoint)."""
    from sabrina.memory.store import MemoryStore

    with MemoryStore(tmp_path / "mem.db") as store:
        msg_id = store.append("s1", "user", "hello")
        row = store._conn.execute(
            "SELECT importance FROM messages WHERE id = ?", (msg_id,)
        ).fetchone()
        assert abs(float(row[0]) - 0.5) < 1e-9


def test_memory_store_set_importance_clamps_and_persists(tmp_path):
    from sabrina.memory.store import MemoryStore

    with MemoryStore(tmp_path / "mem.db") as store:
        a = store.append("s1", "user", "very important")
        b = store.append("s1", "user", "trivial")
        store.set_importance(a, 0.95)
        store.set_importance(b, -0.4)  # clamped to 0
        row_a = store._conn.execute(
            "SELECT importance FROM messages WHERE id = ?", (a,)
        ).fetchone()
        row_b = store._conn.execute(
            "SELECT importance FROM messages WHERE id = ?", (b,)
        ).fetchone()
        assert abs(float(row_a[0]) - 0.95) < 1e-9
        assert float(row_b[0]) == 0.0


def test_recency_score_decays_with_half_life():
    """`_recency_score` is 1.0 at now, ~0.5 at one half-life, ~0.25 at two."""
    from datetime import datetime, timedelta, timezone

    from sabrina.memory.store import _recency_score

    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    half_life = 30.0  # days

    # Today: ~1.0
    assert abs(_recency_score(now, now=now, half_life_days=half_life) - 1.0) < 1e-6
    # 30 days ago: ~0.5
    s_30 = _recency_score(now - timedelta(days=30), now=now, half_life_days=half_life)
    assert abs(s_30 - 0.5) < 1e-3
    # 60 days ago: ~0.25
    s_60 = _recency_score(now - timedelta(days=60), now=now, half_life_days=half_life)
    assert abs(s_60 - 0.25) < 1e-3
    # 90 days ago: ~0.125
    s_90 = _recency_score(now - timedelta(days=90), now=now, half_life_days=half_life)
    assert abs(s_90 - 0.125) < 1e-3


def test_recency_score_half_life_zero_disables_decay():
    from datetime import datetime, timedelta, timezone

    from sabrina.memory.store import _recency_score

    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    # half_life=0 -> always 1.0 regardless of age
    s = _recency_score(now - timedelta(days=365), now=now, half_life_days=0.0)
    assert s == 1.0


def test_search_scored_basic_orders_by_combined_score(tmp_path):
    """When importance is uniform, search_scored matches search ordering
    on the `relevance` term alone (recency cancels out for same-time rows)."""
    _require_sqlite_vec()
    from sabrina.memory.store import MemoryStore, new_session_id

    e1 = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    e2 = [0.99, 0.141, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    e3 = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    with MemoryStore(tmp_path / "mem.db", embedding_dim=8) as m:
        sid = new_session_id()
        m.append(sid, "user", "anchor", embedding=e1)
        m.append(sid, "user", "close", embedding=e2)
        m.append(sid, "user", "ortho", embedding=e3)

        scored = m.search_scored(e1, k=3, alpha=1.0, beta=1.0, gamma=1.0)
        assert len(scored) == 3
        # anchor first (relevance=1.0), then close, then ortho.
        assert scored[0].message.content == "anchor"
        assert scored[1].message.content == "close"
        # Score is non-increasing.
        assert scored[0].score >= scored[1].score >= scored[2].score
        # All sub-scores populated.
        for h in scored:
            assert 0.0 <= h.recency <= 1.0
            assert 0.0 <= h.importance <= 1.0
            assert 0.0 <= h.relevance <= 1.0


def test_search_scored_promotes_high_importance_over_close_distance(tmp_path):
    """An older / less-relevant turn with importance=1.0 can outrank a
    fresh / highly-relevant turn with importance=0.0 when beta is large."""
    _require_sqlite_vec()
    from sabrina.memory.store import MemoryStore, new_session_id

    e1 = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]   # close to query
    e2 = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]   # orthogonal
    query = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    with MemoryStore(tmp_path / "mem.db", embedding_dim=8) as m:
        sid = new_session_id()
        rid_close = m.append(sid, "user", "close low importance", embedding=e1)
        rid_far = m.append(sid, "user", "far high importance", embedding=e2)
        m.set_importance(rid_close, 0.0)
        m.set_importance(rid_far, 1.0)

        # Heavily weight importance; near-zero on relevance and recency.
        scored = m.search_scored(
            query, k=2, alpha=0.01, beta=10.0, gamma=0.01,
            recency_half_life_days=30.0,
        )
        assert len(scored) == 2
        # The "far" but high-importance row should rank first.
        assert scored[0].message.id == rid_far
        assert scored[1].message.id == rid_close


def test_search_scored_recency_breaks_tie_when_importance_equal(tmp_path):
    """With equal importance + same query distance, the more-recent turn
    scores higher because its recency term is higher."""
    _require_sqlite_vec()
    import time

    from sabrina.memory.store import MemoryStore, new_session_id

    e = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    with MemoryStore(tmp_path / "mem.db", embedding_dim=8) as m:
        sid = new_session_id()
        old_id = m.append(sid, "user", "old", embedding=e)
        # Backdate the old row so the recency term diverges noticeably.
        m._conn.execute(
            "UPDATE messages SET ts = ? WHERE id = ?",
            ("2026-01-01T00:00:00+00:00", old_id),
        )
        time.sleep(0.01)
        new_id = m.append(sid, "user", "new", embedding=e)

        scored = m.search_scored(
            e, k=2, alpha=10.0, beta=0.01, gamma=0.01,
            recency_half_life_days=30.0,
        )
        assert scored[0].message.id == new_id
        assert scored[1].message.id == old_id
        assert scored[0].recency > scored[1].recency


def test_search_scored_respects_max_distance_cutoff(tmp_path):
    _require_sqlite_vec()
    from sabrina.memory.store import MemoryStore, new_session_id

    e_close = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    e_far = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    with MemoryStore(tmp_path / "mem.db", embedding_dim=8) as m:
        sid = new_session_id()
        m.append(sid, "user", "close", embedding=e_close)
        m.append(sid, "user", "far", embedding=e_far)

        # max_distance=0.5 should drop "far" (distance ~ 1.0).
        scored = m.search_scored(e_close, k=5, max_distance=0.5)
        assert len(scored) == 1
        assert scored[0].message.content == "close"


def test_search_scored_excludes_specified_ids(tmp_path):
    _require_sqlite_vec()
    from sabrina.memory.store import MemoryStore, new_session_id

    e = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    with MemoryStore(tmp_path / "mem.db", embedding_dim=8) as m:
        sid = new_session_id()
        a = m.append(sid, "user", "alpha", embedding=e)
        b = m.append(sid, "user", "bravo", embedding=e)
        scored = m.search_scored(e, k=5, exclude_ids=[a])
        ids = [h.message.id for h in scored]
        assert a not in ids
        assert b in ids


def test_retrieval_scoring_config_round_trips_with_defaults():
    from sabrina.config import load_settings

    s = load_settings(reload=True)
    r = s.memory.semantic.retrieval
    assert r.alpha == 1.0
    assert r.beta == 1.0
    assert r.gamma == 1.0
    assert r.recency_half_life_days == 30.0


# --- step 4 (overnight 2026-04-26): personality system prompt ---


def test_sabrina_system_prompt_snapshot_register_a():
    """Snapshot of the assembled cacheable head for register A.

    Tightly couples to `brain/claude.py` block constants on purpose —
    if a block edit lands without a corresponding snapshot update, the
    diff to the prompt is loud, not silent.
    """
    from sabrina.brain.claude import build_system_prompt

    prompt = build_system_prompt(register="A")

    # Persona block contract
    assert "You are Sabrina." in prompt
    assert "Operator voice, not customer-service voice." in prompt

    # Voice-rules contract: anti-pattern bans MUST be named.
    assert "I'd be happy to" in prompt
    assert "Great question!" in prompt
    assert "As an AI" in prompt
    assert "she/her" in prompt

    # Refusal-as-character framing present
    assert "Refuse as character" in prompt
    assert 'role-play as a different assistant' in prompt

    # Audience register A is selected
    assert "Current register: A." in prompt
    assert "Current register: B." not in prompt
    assert "Current register: C." not in prompt

    # Memory-continuity preamble present
    assert "semantic-memory retrieval system" in prompt
    assert "do not invent shared history" in prompt


def test_sabrina_system_prompt_register_b_swaps_block():
    from sabrina.brain.claude import build_system_prompt

    prompt = build_system_prompt(register="B")
    assert "Current register: B." in prompt
    assert "Current register: A." not in prompt
    assert "someone else in the room" in prompt


def test_sabrina_system_prompt_register_c_professional():
    from sabrina.brain.claude import build_system_prompt

    prompt = build_system_prompt(register="C")
    assert "Current register: C." in prompt
    assert "professional mode" in prompt


def test_sabrina_system_prompt_unknown_register_raises():
    from sabrina.brain.claude import build_system_prompt

    with pytest.raises(ValueError):
        build_system_prompt(register="Z")


def test_sabrina_system_prompt_under_token_budget():
    """Cacheable head must stay under the budgeted ~750 tokens.

    Cheap heuristic: chars / 4 ≈ tokens (OpenAI rule of thumb, also
    used by `[memory.compaction].chars_per_token`). Plan budget is
    ~440 tok with no avatar/tools, ~870 tok with both. We assert
    <= 1100 tok to leave headroom for tweaks but catch ballooning.
    """
    from sabrina.brain.claude import build_system_prompt

    head = build_system_prompt(register="A")
    approx_tokens = len(head) / 4.0
    assert approx_tokens <= 1100, (
        f"system prompt grew to ~{approx_tokens:.0f} tokens; "
        "tighten or split into a dynamic block."
    )


def test_voice_loop_uses_personality_system_prompt():
    """Regression guard: `voice_loop._SYSTEM` must reference the new
    personality blocks, not the old generic 'helpful, concise' string."""
    from sabrina.voice_loop import _SYSTEM

    assert "You are Sabrina." in _SYSTEM
    assert "Operator voice" in _SYSTEM
    # The legacy stub must be gone.
    assert "helpful, concise personal assistant" not in _SYSTEM


def test_chat_repl_uses_personality_system_prompt():
    """Same guard for the REPL entry point."""
    from sabrina.chat import _SYSTEM

    assert "You are Sabrina." in _SYSTEM
    assert "Operator voice" in _SYSTEM


def test_tool_use_block_inserted_when_provided():
    from sabrina.brain.claude import build_system_prompt

    tool_block = "Tool-use rules:\n- Confirm before destructive actions."
    prompt = build_system_prompt(register="A", tool_use_block=tool_block)
    assert "Confirm before destructive actions." in prompt
    # Default omits it cleanly.
    plain = build_system_prompt(register="A")
    assert "Confirm before destructive actions." not in plain


def test_sabrina_system_prompt_constant_matches_register_a_default():
    from sabrina.brain.claude import SABRINA_SYSTEM_PROMPT, build_system_prompt

    assert SABRINA_SYSTEM_PROMPT == build_system_prompt(register="A")


# --- step 5 (overnight 2026-04-26): personality eval substrate ---


def test_personality_eval_command_registered():
    """`sabrina personality-eval` should be a registered Typer command."""
    from sabrina.cli import app

    names = {cmd.name for cmd in app.registered_commands}
    assert "personality-eval" in names


def test_personality_golden_set_present_at_canonical_path():
    """The golden set must live at the path the CLI verb defaults to."""
    from pathlib import Path

    p = (
        Path(__file__).parent / "personality" / "golden_set.yaml"
    )
    assert p.is_file(), f"missing golden set at {p}"


def test_personality_judge_prompt_present():
    """The judge prompt template must ship alongside the golden set."""
    from pathlib import Path

    p = Path(__file__).parent / "personality" / "judge_prompt.md"
    assert p.is_file()
    body = p.read_text(encoding="utf-8")
    # Sanity guards: spec text must be present so the judge can't fall
    # back to its own RLHF priors.
    assert "Operator voice" in body
    assert "Refuses as character" in body or "refuses **as character**" in body


# --- step 4 (overnight 2026-05-04, worker-9am): tool-use wire-up ---
#
# These tests exercise ClaudeBrain.chat()'s tool-use path end-to-end against
# a scripted Anthropic-SDK stub. They cover the six gates the (a)-half of the
# QUEUE P1 owes per `research/2026-04-29-claudebrain-tool-wire-up-surface.md`
# section 7. The stub mimics the bits of the real SDK we touch:
# `messages.stream()` as an async context manager that exposes `.text_stream`
# (async iterable) and `.get_final_message()` (coroutine returning a Message
# with `.content`, `.stop_reason`, `.usage`).


class _FakeBlock:
    """Stand-in for an Anthropic ContentBlock (text or tool_use)."""

    __slots__ = ("type", "text", "id", "name", "input")

    def __init__(self, type_, *, text=None, id=None, name=None, input=None):
        self.type = type_
        self.text = text
        self.id = id
        self.name = name
        self.input = input

    def model_dump(self):
        d = {"type": self.type}
        if self.text is not None:
            d["text"] = self.text
        if self.id is not None:
            d["id"] = self.id
        if self.name is not None:
            d["name"] = self.name
        if self.input is not None:
            d["input"] = self.input
        return d


class _FakeUsage:
    def __init__(self, input_tokens=10, output_tokens=20):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeFinalMessage:
    def __init__(self, content, stop_reason, usage=None):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or _FakeUsage()


class _FakeStream:
    """Async-context-manager + async-iterator-bearing fake of an SDK stream."""

    def __init__(self, text_chunks, final):
        self._text_chunks = text_chunks
        self._final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def _gen():
            for t in self._text_chunks:
                yield t
        return _gen()

    async def get_final_message(self):
        return self._final


class _FakeMessages:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if not self._scripted:
            raise AssertionError(
                "ClaudeBrain made more stream() calls than the test scripted."
            )
        return self._scripted.pop(0)


class _FakeAnthropicClient:
    def __init__(self, scripted):
        self.messages = _FakeMessages(scripted)


def _make_claude_with(scripted):
    """Build a ClaudeBrain whose internal client is the scripted fake."""
    from sabrina.brain.claude import ClaudeBrain

    brain = ClaudeBrain(api_key="sk-ant-test-dummy", model="claude-test")
    brain._client = _FakeAnthropicClient(scripted)
    return brain


def _toolspec_echo(name="echo", *, raises=None):
    """Build a ToolSpec whose handler returns its input or raises if asked."""
    from sabrina.tools import ToolSpec

    async def handler(**kwargs):
        if raises is not None:
            raise raises
        return {"echoed": kwargs}

    return ToolSpec(
        name=name,
        description=f"Test tool {name}.",
        input_schema={
            "type": "object",
            "properties": {"q": {"type": "string"}},
        },
        handler=handler,
    )


async def test_claude_executes_one_tool_and_continues():
    """Happy path: model emits tool_use, we dispatch, recurse, model emits
    final text + end_turn. Event sequence and tool_result follow-up shape
    must match the spec from the research doc."""
    from sabrina.brain.protocol import (
        Done,
        Message,
        TextDelta,
        ToolUseDone,
        ToolUseStart,
    )

    spec = _toolspec_echo("echo")

    round_1 = _FakeStream(
        text_chunks=["thinking..."],
        final=_FakeFinalMessage(
            content=[
                _FakeBlock("text", text="thinking..."),
                _FakeBlock(
                    "tool_use",
                    id="toolu_01",
                    name="echo",
                    input={"q": "hello"},
                ),
            ],
            stop_reason="tool_use",
        ),
    )
    round_2 = _FakeStream(
        text_chunks=["done."],
        final=_FakeFinalMessage(
            content=[_FakeBlock("text", text="done.")],
            stop_reason="end_turn",
            usage=_FakeUsage(input_tokens=42, output_tokens=7),
        ),
    )
    brain = _make_claude_with([round_1, round_2])

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="say hi")],
        tools=[spec],
    ):
        events.append(ev)

    types = [type(ev).__name__ for ev in events]
    assert "ToolUseStart" in types
    assert "ToolUseDone" in types
    start = next(ev for ev in events if isinstance(ev, ToolUseStart))
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert start.tool_id == done_ev.tool_id == "toolu_01"
    assert start.name == "echo"
    assert start.input == {"q": "hello"}
    assert done_ev.error is None
    assert done_ev.result == {"echoed": {"q": "hello"}}
    final = events[-1]
    assert isinstance(final, Done)
    assert final.stop_reason == "end_turn"
    assert final.input_tokens == 42
    assert final.output_tokens == 7
    text_after_tool = [
        ev for ev in events
        if isinstance(ev, TextDelta) and ev.text == "done."
    ]
    assert text_after_tool, "expected post-tool TextDelta from round 2"
    calls = brain._client.messages.calls
    assert len(calls) == 2
    for call in calls:
        assert "tools" in call
        assert call["tools"][0]["name"] == "echo"
    second_messages = calls[1]["messages"]
    last_user = second_messages[-1]
    assert last_user["role"] == "user"
    assert isinstance(last_user["content"], list)
    tr = last_user["content"][0]
    assert tr["type"] == "tool_result"
    assert tr["tool_use_id"] == "toolu_01"
    assert tr["is_error"] is False
    import json as _json
    assert _json.loads(tr["content"]) == {"echoed": {"q": "hello"}}


async def test_claude_recursion_cap_yields_done_with_cap_reason():
    """If the model keeps invoking tools, the loop bails after
    _MAX_TOOL_RECURSION dispatch rounds and reports `tool_recursion_cap`."""
    from sabrina.brain.claude import _MAX_TOOL_RECURSION
    from sabrina.brain.protocol import Done, Message

    spec = _toolspec_echo("echo")

    def _looping_round(i):
        return _FakeStream(
            text_chunks=[],
            final=_FakeFinalMessage(
                content=[
                    _FakeBlock(
                        "tool_use",
                        id=f"toolu_{i:02d}",
                        name="echo",
                        input={"q": str(i)},
                    ),
                ],
                stop_reason="tool_use",
            ),
        )

    scripted = [_looping_round(i) for i in range(_MAX_TOOL_RECURSION + 2)]
    brain = _make_claude_with(scripted)

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="loop")],
        tools=[spec],
    ):
        events.append(ev)

    final = events[-1]
    assert isinstance(final, Done)
    assert final.stop_reason == "tool_recursion_cap"
    calls = brain._client.messages.calls
    assert len(calls) == _MAX_TOOL_RECURSION


async def test_claude_tool_handler_error_surfaces_in_tool_result():
    """Handler raises -> ToolUseDone.error set, tool_result has is_error=True
    so the model can see the failure and react instead of crashing the loop."""
    from sabrina.brain.protocol import Done, Message, ToolUseDone

    boom = _toolspec_echo("boom", raises=RuntimeError("clipboard contended"))

    round_1 = _FakeStream(
        text_chunks=[],
        final=_FakeFinalMessage(
            content=[
                _FakeBlock(
                    "tool_use",
                    id="toolu_err",
                    name="boom",
                    input={"q": "x"},
                ),
            ],
            stop_reason="tool_use",
        ),
    )
    round_2 = _FakeStream(
        text_chunks=["sorry."],
        final=_FakeFinalMessage(
            content=[_FakeBlock("text", text="sorry.")],
            stop_reason="end_turn",
        ),
    )
    brain = _make_claude_with([round_1, round_2])

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="break it")],
        tools=[boom],
    ):
        events.append(ev)

    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error == "clipboard contended"
    assert done_ev.result is None

    calls = brain._client.messages.calls
    last_user = calls[1]["messages"][-1]
    tr = last_user["content"][0]
    assert tr["type"] == "tool_result"
    assert tr["is_error"] is True
    assert "clipboard contended" in tr["content"]

    final = events[-1]
    assert isinstance(final, Done)
    assert final.stop_reason == "end_turn"


async def test_claude_unknown_tool_name_returns_error_result():
    """If the model invents a name we didn't advertise, the loop yields a
    ToolUseDone(error=...) and recurses with an error tool_result rather
    than crashing."""
    from sabrina.brain.protocol import Done, Message, ToolUseDone

    spec = _toolspec_echo("echo")

    round_1 = _FakeStream(
        text_chunks=[],
        final=_FakeFinalMessage(
            content=[
                _FakeBlock(
                    "tool_use",
                    id="toolu_unknown",
                    name="not_a_real_tool",
                    input={},
                ),
            ],
            stop_reason="tool_use",
        ),
    )
    round_2 = _FakeStream(
        text_chunks=[],
        final=_FakeFinalMessage(
            content=[_FakeBlock("text", text="oops")],
            stop_reason="end_turn",
        ),
    )
    brain = _make_claude_with([round_1, round_2])

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="trick it")],
        tools=[spec],
    ):
        events.append(ev)

    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error == "unknown tool: not_a_real_tool"
    calls = brain._client.messages.calls
    tr = calls[1]["messages"][-1]["content"][0]
    assert tr["is_error"] is True
    assert "unknown tool" in tr["content"]
    assert isinstance(events[-1], Done)


async def test_ollama_raises_cleanly_when_tools_provided():
    """OllamaBrain.chat() must NotImplementedError on tools= until parity
    lands. Message text is part of the contract — config error messages
    point users at the right knob."""
    from sabrina.brain.ollama import OllamaBrain
    from sabrina.brain.protocol import Message

    brain = OllamaBrain()
    spec = _toolspec_echo("echo")

    with pytest.raises(NotImplementedError) as exc_info:
        async for _ev in brain.chat(
            [Message(role="user", content="hi")],
            tools=[spec],
        ):
            pass
    msg = str(exc_info.value)
    assert "does not support tool use" in msg
    assert "set [tools] enabled = false" in msg


async def test_brain_chat_tools_none_is_backward_compatible():
    """Default-path regression: omitting tools= must keep the existing
    text-only behavior. No tools= on the wire, classic event sequence."""
    from sabrina.brain.protocol import Done, Message, TextDelta

    only = _FakeStream(
        text_chunks=["hi", " there"],
        final=_FakeFinalMessage(
            content=[_FakeBlock("text", text="hi there")],
            stop_reason="end_turn",
            usage=_FakeUsage(input_tokens=3, output_tokens=2),
        ),
    )
    brain = _make_claude_with([only])

    events = []
    async for ev in brain.chat([Message(role="user", content="hi")]):
        events.append(ev)

    deltas = [ev for ev in events if isinstance(ev, TextDelta)]
    assert [d.text for d in deltas] == ["hi", " there"]
    final = events[-1]
    assert isinstance(final, Done)
    assert final.stop_reason == "end_turn"
    assert final.input_tokens == 3
    assert final.output_tokens == 2
    call = brain._client.messages.calls[0]
    assert "tools" not in call
