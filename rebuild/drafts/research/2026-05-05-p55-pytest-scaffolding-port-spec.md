# P5.5 — pytest scaffolding port (`conftest.py` + `test_utils/`) — spec

**Date:** 2026-05-05
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed (next-pull-ready)` → **P5.5 Port — pytest scaffolding (`conftest.py` + `test_utils/`)** (`[linux-runnable] [partial-dod-eligible] [P1] [M]`).
**Predecessor:** legacy `tests/conftest.py` + `tests/test_utils/{paths.py,helpers.py}`. Plan reference: `rebuild/drafts/old-repo-migration-audit.md` port item #5; closeout target: `rebuild/LEGACY_REPLACEMENT_GATE.md` box #1.
**Scope:** net-additive. Off-limits: legacy `tests/` (read-only per CLAUDE.md) and `rebuild/decisions/`.

---

## What this item is

Port the test-harness primitives the legacy suite relied on into the rebuild's `sabrina-2/tests/` tree, throwing out the legacy abstractions the rebuild deliberately rejected. The legacy `tests/conftest.py` plus `tests/test_utils/{paths.py,helpers.py}` carry two kinds of code: (1) infrastructure primitives that have no opinion about Sabrina's architecture — temp-dir fixtures, project-root path helpers, GPU-skip markers — and (2) component mocks that only make sense if the rebuild also has `core.SabrinaCore`, `VoiceService`, `HearingService`, `AutomationService`, `mock_event_bus`, and `mock_state_machine`, which it doesn't (rebuild swapped to a `Brain`/`Listener`/`Speaker`/`Vision` protocol surface plus a typed event bus + `state.py` state machine — see `sabrina-2/src/sabrina/{bus.py,state.py,brain/protocol.py,listener/protocol.py}`). A Worker that ports the second kind verbatim wastes a slot and ships fixtures no test will use. This spec names the boundary so the Worker ports only the first kind and writes new mocks against the rebuild's actual protocols.

## Proposed approach

- **`sabrina-2/tests/conftest.py` (new file)** — house the path/temp/time fixtures. Port the following from legacy `tests/conftest.py`: `project_root`, `test_dir`, `data_dir`, `temp_dir`, `current_time`. Drop: `config_dir` (rebuild has no `config/` directory; it has `sabrina.toml` consumed by pydantic-settings), `mock_event_bus`, `mock_state_machine`, `mock_voice_service`, `mock_vision_service`, `mock_automation_service`, `mock_hearing_service`, `create_test_config`, `sabrina_core`. Keep the `pytest_configure` block but rewrite the marker list against the rebuild's protocol surface — replace `requires_voice/vision/hearing/automation` with a single `requires_windows` marker (matches the partial-DoD posture in CLAUDE.md "Partial-DoD tiers") plus the existing `requires_gpu`. Keep `pytest_collection_modifyitems` only for the `requires_gpu` skip-on-no-CUDA branch and add the `requires_windows` skip-on-non-Windows branch (which is the single marker every Windows-required path will tag).
- **`sabrina-2/tests/test_utils/paths.py` (new file)** — port the path helpers that aren't load-bearing on legacy directory layout: `get_project_root` (rewrite the key-indicator list — drop `core/`, `utilities/`, `services/`, keep `README.md`, add `sabrina-2/`), `get_test_dir`, `get_test_data_dir`, `get_test_temp_dir`, `ensure_project_root_in_sys_path`, `create_test_file`. Drop: `get_component_path`, `get_config_path`, `get_test_config_path`, `get_test_resource_path` (legacy-shaped), `get_test_unit_dir`/`integration_dir`/`e2e_dir` (rebuild's test layout is currently flat — `sabrina-2/tests/test_smoke.py` + `sabrina-2/tests/personality/`; subdivision can ship later if scale demands).
- **`sabrina-2/tests/test_utils/mocks.py` (new file, NOT a port)** — author against the rebuild's protocols, not the legacy services. Mock factories the rebuild surface actually wants: `make_fake_brain()` returning a `Brain`-protocol stub (per `sabrina-2/src/sabrina/brain/protocol.py`); `make_fake_speaker()` returning a `Speaker`-protocol stub (per `sabrina-2/src/sabrina/speaker/__init__.py`); `make_fake_listener()` returning a `Listener`-protocol stub (per `sabrina-2/src/sabrina/listener/protocol.py`); `make_fake_bus()` returning an in-memory event-bus double (per `sabrina-2/src/sabrina/bus.py`); `make_cancel_token()` for tests that exercise barge-in cancellation. None of these are ports — they're new code shaped to the rebuild. The unit shows up in the test_utils dir because the path is the natural cousin of the path helpers above.
- **`sabrina-2/tests/test_utils/__init__.py` (new file)** — empty marker so the directory imports cleanly. Mirrors the existing `sabrina-2/tests/personality/__init__.py`.
- **No changes to existing test files.** `sabrina-2/tests/test_smoke.py` keeps passing as-is. The new conftest/fixtures are opt-in; existing tests don't have to subscribe.

## Dependencies

- **P5.4 — test fixtures port** (`sabrina-2/tests/data/` with `conversation_history.json` + `default_memory.json`). The new `data_dir` fixture above resolves to that directory; without P5.4 the fixture exists but resolves to an empty path. Spec is shippable independently — order is "P5.4 first" only as a polish.
- **`sabrina-2/src/sabrina/brain/protocol.py`** — protocol shape for `make_fake_brain()`. Currently in flight via Phase 3 (a)-half (working tree, commit blocked on stale `.git/index.lock` per QUEUE entry); this spec uses the protocol as it exists post-(a)-half wire-up. If a Worker picks this item up before the (a)-half is committed, target the in-tree protocol (the Phase-3 wire-up only adds fields, doesn't reshape the surface).
- **`sabrina-2/src/sabrina/{bus.py,state.py,listener/protocol.py,speaker/__init__.py}`** — protocol shapes for the other fakes. All shipped per Phase 1; stable surface.
- **CLAUDE.md** — "Partial-DoD tiers" section defines the `requires_windows` marker semantics this spec relies on. The marker maps 1:1 to the partial-DoD framing: a test tagged `requires_windows` is a test the Cowork Linux/3.10 sandbox skips; promotion to `[done]` waits for Eric's Windows session.

## Concrete DoD (replaces the queue entry's "primitives, not abstractions" framing)

A Worker has shipped this item under Partial DoD when ALL of the following hold (verifiable inside the Cowork Linux/3.10 sandbox without any Windows-only step):

1. Four files exist with the contents described above: `sabrina-2/tests/conftest.py`, `sabrina-2/tests/test_utils/__init__.py`, `sabrina-2/tests/test_utils/paths.py`, `sabrina-2/tests/test_utils/mocks.py`.
2. `python -m compileall sabrina-2/src sabrina-2/tests` is clean.
3. `python -c "from tests.test_utils.paths import get_project_root; print(get_project_root())"` (run from `sabrina-2/`) prints the absolute path to `sabrina-2/` and exits 0.
4. `pytest sabrina-2/tests/test_smoke.py` continues to pass under Linux/3.10 — the new conftest must not break the existing suite.
5. At least one new test in `sabrina-2/tests/test_utils/test_mocks.py` exercises each of the five mock factories (`make_fake_brain`, `make_fake_speaker`, `make_fake_listener`, `make_fake_bus`, `make_cancel_token`) and at least one new test exercises each path helper (`get_project_root`, `get_test_dir`, `get_test_data_dir`, `get_test_temp_dir`, `create_test_file`, `ensure_project_root_in_sys_path`). One test per primitive is enough; this is scaffolding, not a deep suite.
6. `pytest_configure`'s marker list contains exactly two markers: `requires_gpu`, `requires_windows`. `pytest_collection_modifyitems` skips `requires_gpu` when `torch.cuda.is_available()` is False (or torch not installed) AND skips `requires_windows` when `sys.platform != "win32"`. A trivial test tagged `@pytest.mark.requires_windows` proves the skip fires under Linux.
7. Diff is committed to `automation/<role>-2026-05-MM-Nam` with `Windows-pending: e2e` in the body. Body also lists what the e2e gate is (one Windows pytest run that confirms no `requires_windows`-tagged test is unexpectedly skipping on Windows). Item moves to `[linux-shipped]` in QUEUE/DONE; promotion to `[done]` waits for the next Eric Windows session.

The "primitives, not abstractions" rule from the queue note is the bullet-list above's "Drop:" entries. If a future Worker is unsure whether to port a legacy fixture, the test is "does the rebuild have the abstraction this fixture mocks?" — if no, drop.

## Open questions for NEEDS-INPUT

None blocking. Two judgment calls a Worker can make in-line and surface in the commit body:

- **Test layout — flat vs. unit/integration/e2e split.** Legacy used the three-way subdivision; rebuild's `test_smoke.py` is flat. This spec doesn't subdivide. If a Worker thinks subdivision is the right move, ship flat first (per this spec) and propose the subdivision as a separate `PROPOSED.md` entry — don't bundle it.
- **`requires_windows` vs. finer-grained markers (`requires_audio`, `requires_clipboard`, `requires_pywin32`).** This spec picks the single marker because it matches the Partial-DoD tier in CLAUDE.md verbatim ("touches voice-loop runtime, audio I/O, clipboard, mss/pynput/pyperclip paths, or pywin32-only modules"). Finer-grained markers are over-engineering for current scale. Revisit when there are >50 Windows-required tests.

If a Worker hits a real ambiguity not on this list, mark `[in-progress]` and write to NEEDS-INPUT per the standard role-doc bailout — don't invent.
