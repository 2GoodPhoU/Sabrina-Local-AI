# Supervisor + autostart plan (working doc — ready-to-ship)

**Date:** 2026-04-23
**Status:** Draft. One open-question block remains (see end). Implementable
in one session once that's resolved or left at defaults.
**Closes:** daily-driver gaps #2 (autostart) and #3 (crash recovery) from
decision 006.

## The one-liner

`sabrina run` becomes the supervised entrypoint: spawns `sabrina voice`
as a subprocess, watches it, restarts on unhandled exit with a budget.
`sabrina autostart enable` registers a Windows Task Scheduler entry so
`sabrina run` starts at user logon. A `supervisor.mode` config knob
switches between Task Scheduler (default) and a Windows Service via
nssm; the Service path is there for the "start before login" user and
nobody else.

## Scope

In:
- Supervisor process (`sabrina/supervisor.py`, ~120 lines).
- `sabrina run` CLI verb.
- `sabrina autostart {enable, disable, status}` CLI verbs, mode-aware.
- Task Scheduler XML template + at-logon registration via `schtasks.exe`.
- nssm-based Service mode: detects `tools/nssm/nssm.exe`, shells out to
  `nssm install/remove/start/stop`. Fails clearly if nssm is absent.
- `[supervisor]` config block: `mode`, `max_restarts_per_minute`,
  `restart_backoff_s`, `log_path`.
- Tests: supervisor unit tests (stub subprocess), autostart XML
  generation tests, nssm command-line builder tests.

Out:
- Writing our own `win32serviceutil.ServiceFramework` subclass. Running
  a Python process from LocalSystem is a can of worms (audio-device
  access, user-session API keys, GUI-subsystem mismatch). nssm papers
  over all of it by running the user's Python in the user's session.
- Watchdog-style health checks (pinging the voice process every N
  seconds). Supervisor reacts to process exit only. If we observe real
  hangs, we add a watchdog then.
- Telemetry (Sentry / crash reports). Structured logs are enough until
  they aren't.
- Cross-platform autostart (Linux systemd, macOS launchd). Windows-only
  this session.

## Files to touch

```
sabrina-2/src/sabrina/
├── supervisor.py                 # NEW, ~120 lines
├── autostart/
│   ├── __init__.py               # NEW
│   ├── task_scheduler.py         # NEW, ~80 lines
│   └── service_nssm.py           # NEW, ~80 lines
├── cli.py                        # +run, +autostart verbs
└── config.py                     # +SupervisorConfig
sabrina-2/
├── sabrina.toml                  # +[supervisor]
├── tools/
│   └── nssm/                     # (runtime-populated; .gitignore'd)
├── install-nssm.ps1              # NEW, mirrors install-piper.ps1
└── tests/test_smoke.py           # +supervisor tests
```

One new package (`autostart/`) because the two backends justify the
split — single-responsibility modules, each under 100 lines. Guardrail #3
comfortable; neither supervisor.py nor either autostart module should
exceed the split threshold.

## Protocol / API changes

None. Supervisor is a process-level concern; it never touches Brain,
Listener, Speaker, Memory, or the event bus. The voice-loop process
it supervises is identical to today's `sabrina voice` — no code change
in `voice_loop.py`.

## Config additions

```toml
[supervisor]
# How to register autostart:
#   "task_scheduler"  = Windows Task Scheduler "at user logon" task (default).
#                       No admin needed. Starts after the user logs in.
#                       Has access to user audio devices + .env secrets.
#   "service"         = Windows Service via nssm. Admin needed once to
#                       install. Can start before user logon if configured.
#                       Requires `.\install-nssm.ps1` to have run.
#   "none"            = Do not register. User runs `sabrina run` manually.
mode = "task_scheduler"

# How many restarts we allow before giving up (prevents tight crash loops).
max_restarts_per_minute = 5

# Seconds to wait between restart attempts (exponential-ish; multiplied per
# consecutive crash, capped at 60 s).
restart_backoff_s = 2

# Supervisor's own log file (the voice process keeps logging to its stream).
log_path = "logs/supervisor.log"
```

## Supervisor behavior

```
┌──────────────┐    spawn     ┌─────────────────┐
│ sabrina run  │ ───────────> │ sabrina voice    │
│ (supervisor) │              │ (subprocess)     │
└──────┬───────┘              └────────┬─────────┘
       │                               │ exits (exception / crash / sigterm)
       │ <─────────────────────────────┘
       │
       ├── exit code 0 or SIGINT? => supervisor exits too.
       ├── crash within budget?   => log + backoff + respawn.
       └── crash budget exceeded? => log loudly + exit with code 2.
```

- Restart budget is a rolling 60-second window. More than `max_restarts_per_minute`
  crashes in that window ⇒ bail.
- Backoff grows per consecutive crash: `restart_backoff_s * 2^(n-1)`, capped
  at 60 s. Resets on a successful run that lasts > 60 s.
- SIGINT (Ctrl+C) to the supervisor is forwarded to the child, then the
  supervisor reaps and exits. No restart.
- On Windows, `CTRL_BREAK_EVENT` is the portable signal — use
  `subprocess.Popen(..., creationflags=CREATE_NEW_PROCESS_GROUP)` so we
  can send it without killing ourselves.

## Autostart: Task Scheduler (default)

Single XML template, rendered per-machine with `sys.executable` and
project root. Registered via:

```powershell
schtasks /create /tn "SabrinaAI" /xml <path> /f
```

Key template settings:
- Trigger: `LogonTrigger` for the current user.
- Action: `Execute = "<sys.executable>"`, `Arguments = "-m sabrina run"`,
  `WorkingDirectory = <project root>`.
- `StartWhenAvailable = true` (if the machine was asleep at login,
  start when it wakes).
- `StopOnBatteryStop = false` (desktop; no battery).
- `RunOnlyIfNetworkAvailable = false` — local-first; Ollama doesn't
  need network, Claude does but we want Sabrina up even offline.
- Priority: normal. Don't use `RealTimePriority`.

`sabrina autostart disable` calls `schtasks /delete /tn "SabrinaAI" /f`.
`sabrina autostart status` parses `schtasks /query /tn SabrinaAI /fo LIST`
for "Status: Ready" vs. missing.

## Autostart: Windows Service via nssm (opt-in)

nssm is a single ~200 KB binary (MIT-licensed) that wraps any executable
into a Windows Service. Why nssm over a pywin32 ServiceFramework subclass:

- **Less of our code.** The Python service wrapper would be ~100 lines
  of `ServiceFramework` boilerplate that lives in our repo and has to
  keep working across Python + pywin32 versions.
- **Runs in the user's session, not LocalSystem.** Service accounts
  running from LocalSystem can't reach the user's audio devices or
  `%USERPROFILE%\.env` without extra plumbing. nssm's "log-on as user"
  option fixes that with one flag.
- **Stable for a decade.** nssm 2.24 has been the last release since
  2017 and is still the go-to answer on Windows service Q&A.

Install path: `sabrina-2/tools/nssm/nssm.exe`, populated by
`install-nssm.ps1`. The Service mode explicitly checks for that path
and bails with a clear message if it's missing.

Service registration (inside `service_nssm.py`):

```
nssm install SabrinaAI <sys.executable> -m sabrina run
nssm set SabrinaAI AppDirectory <project root>
nssm set SabrinaAI ObjectName "<domain>\<user>" <password prompt>
nssm set SabrinaAI Start SERVICE_AUTO_START
nssm set SabrinaAI AppStdout <project root>\logs\service.log
nssm set SabrinaAI AppStderr <project root>\logs\service.log
nssm set SabrinaAI AppExit Default Restart     # nssm also restarts; belt+braces
```

Service mode requires admin once (to `nssm install`). After that,
`sabrina autostart enable` / `disable` / `status` work without admin
against the already-installed service (start/stop don't need admin for
a service configured to run as the user).

## `sabrina run` implementation sketch

```python
# supervisor.py (condensed)
def run_supervised(child_argv: list[str], cfg: SupervisorConfig) -> int:
    crashes: deque[float] = deque(maxlen=cfg.max_restarts_per_minute + 1)
    consecutive = 0
    log = get_logger("supervisor")
    while True:
        t0 = time.monotonic()
        rc = _spawn_and_wait(child_argv)  # forwards signals, returns exit code
        elapsed = time.monotonic() - t0
        if rc == 0 or _user_interrupted(rc):
            return rc
        # crash path
        consecutive = consecutive + 1 if elapsed < 60 else 1
        crashes.append(time.monotonic())
        if _budget_exceeded(crashes, cfg):
            log.error("supervisor.giving_up", crashes=len(crashes))
            return 2
        backoff = min(cfg.restart_backoff_s * (2 ** (consecutive - 1)), 60)
        log.warning("supervisor.restart", rc=rc, backoff_s=backoff, consecutive=consecutive)
        time.sleep(backoff)
```

The `_spawn_and_wait` helper handles the Windows-specific signal dance.

## Test strategy

Fast unit tests (< 100 ms each, no real spawn):

- `test_supervisor_exits_on_child_clean_exit` — stub `_spawn_and_wait`
  returning 0; supervisor returns 0 without looping.
- `test_supervisor_restarts_on_crash_within_budget` — stub returning
  non-zero N times; assert N spawns.
- `test_supervisor_gives_up_when_budget_exceeded` — stub crashing
  indefinitely; assert supervisor bails after `max_restarts_per_minute + 1`.
- `test_supervisor_backoff_grows` — capture backoff sleep values on
  consecutive crashes; assert monotonic growth capped at 60 s.
- `test_supervisor_resets_consecutive_on_long_run` — after a run > 60 s,
  a new crash gets the base backoff, not exponential.

Autostart unit tests:

- `test_task_scheduler_xml_renders_executable_and_project_root` —
  render with fake paths, assert XML contains them verbatim.
- `test_task_scheduler_invocation_calls_schtasks_with_xml` — monkeypatch
  `subprocess.run`, capture argv, assert `/create /tn SabrinaAI /xml ...`.
- `test_service_nssm_bails_clearly_when_binary_missing` — patch
  `nssm_path()` to return a nonexistent path, assert exception message
  names `install-nssm.ps1`.
- `test_service_nssm_builds_install_commands` — capture shell-out calls,
  assert the sequence matches the spec.

Manual smoke (documented in a new `validate-supervisor-windows.md`):
- `uv run sabrina run`, SIGTERM the voice process from another PowerShell,
  confirm it respawns within backoff.
- `uv run sabrina autostart enable`, reboot, confirm `sabrina voice`
  comes up after login (check `logs/supervisor.log`).
- `uv run sabrina autostart status`, `disable`, verify `schtasks /query`
  output matches.

## Step-ordered implementation outline

1. `SupervisorConfig` in `config.py` + `[supervisor]` block in
   `sabrina.toml`. One commit.
2. `supervisor.py` with `run_supervised` + unit tests. One commit.
3. `cli.py`: `sabrina run`. One commit. Manual smoke: `sabrina run` +
   Ctrl+C cleanly exits.
4. `autostart/task_scheduler.py` + XML template + unit tests. One commit.
5. `cli.py`: `sabrina autostart enable/disable/status` for Task Scheduler
   mode. One commit. Manual smoke: register, reboot, unregister.
6. `install-nssm.ps1`. One commit.
7. `autostart/service_nssm.py` + unit tests. One commit.
8. `cli.py`: route `autostart` to nssm when `mode = service`. One commit.
9. `validate-supervisor-windows.md` documenting both paths. Last commit.

Commit cadence matches the project's atomic-per-step norm.

## Dependencies to add

None at the Python level. `nssm.exe` is runtime-downloaded by
`install-nssm.ps1`, mirror of `install-piper.ps1`. `schtasks.exe` is
built into Windows.

## Windows-specific concerns (i7-13700K / Python 3.12)

- `subprocess.Popen(..., creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)`
  is required for clean Ctrl+Break propagation on Windows.
- `schtasks /create /xml` is stable across Windows 10/11; `/tn` name
  must not contain backslashes.
- nssm on Windows 11 works as documented; no known bugs on build 26200.
- Running the voice process from Task Scheduler at logon: the environment
  inherited is the user's, including `%USERPROFILE%\.env` if that's where
  `.env` lives. Confirm project-root resolution still works when `cwd`
  is set by the task. The XML's `WorkingDirectory` should be the project
  root, not `%USERPROFILE%`.
- Audio device indices can shift across reboots. If `sabrina.toml` pins
  `input_device` / `output_device` by index, supervisor restarts are
  fine (indices are stable within a boot), but a reboot may invalidate
  them. Recommend using a substring match in `sabrina.toml` (already
  supported by `test-audio` infra).

## Open questions (genuine blockers)

1. **nssm license + redistribution.** nssm is public-domain-ish (no
   formal license; see `nssm.cc/license`). Shipping the binary inline
   vs. download-on-demand: download is the conservative default, matches
   `install-piper.ps1`. OK to mirror that pattern?

Everything else is defaulted per Eric's guidance (Task Scheduler is the
default mode; Service mode is there for a future request).

## Ship criterion

- All new unit tests pass. Existing 70+ tests unchanged.
- Manual: `sabrina run` supervises a crashing stub for 3 restart cycles
  then bails; logs are legible.
- Manual: `sabrina autostart enable` + reboot leaves Sabrina running in
  the background; `Get-Process python` shows one supervisor + one voice
  process; `logs/supervisor.log` shows the at-logon start.
- Manual: `sabrina autostart disable` removes the task; next reboot has
  no Sabrina.
- Service-mode manual smoke deferred unless Eric asks; Task Scheduler
  covers the declared daily-driver use case.

## Not in this plan (later)

- Watchdog-style health pings.
- Cross-platform autostart (macOS launchd, Linux systemd).
- Restart-on-config-change (a self-triggered restart when the supervisor
  sees `sabrina.toml` change). That's better handled by the
  `ConfigReloaded` event work in the voice-loop polish item (#10 of the
  master plan).
