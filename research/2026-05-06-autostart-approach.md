# Windows autostart approach — Task Scheduler vs. registry Run vs. NSSM service vs. shell:startup

**Researcher run, 2026-05-06 03:30. P2.4 from QUEUE.md.**

## Question

Verbatim from `QUEUE.md` P2.4: "research approach + draft (Task Scheduler vs.
registry vs. NSSM vs. shell:startup)" — bounded comparison of the Windows
autostart-on-login mechanisms with respect to (1) reliability under power
events + RDP login + multi-user, (2) install/uninstall surface (does Eric
need to elevate?), (3) crash-recovery composition with the Phase-2
supervisor (P2.6), (4) Eric's recommendation. Output is a research file;
no code changes. P2.5 implements install/uninstall against the pick.

## What I checked

- `rebuild/drafts/supervisor-autostart-plan.md` (2026-04-23) — predecessor
  draft. Picks Task Scheduler as default with NSSM service mode as opt-in.
  P2.4 explicitly supersedes this.
- `sabrina-2/src/sabrina/supervisor.py` (in HEAD per `acd6725`,
  2026-05-05) — `run_supervised` crash-budget loop;
  `render_task_scheduler_xml` / `install_task_scheduler_task` /
  `uninstall_task_scheduler_task` (schtasks.exe shell-out, UTF-16-LE BOM
  XML); `find_nssm` / `build_nssm_install_commands` /
  `build_nssm_uninstall_commands` (NSSM helpers — build the argv list,
  caller executes). 317 lines.
- `sabrina-2/src/sabrina/cli.py` lines 1130–1241 — `sabrina run`
  (supervisor entry) and `sabrina autostart {enable,disable,status}`
  (Task Scheduler + NSSM-service routes already wired). Both verbs in
  HEAD.
- `sabrina-2/src/sabrina/config.py` lines 193–210 —
  `SupervisorConfig(mode: Literal["task_scheduler", "service"], task_name,
  restart_max, restart_window_s, nssm_binary)`. Default `task_scheduler`.
- `sabrina-2/sabrina.toml` lines 163–173 — `[supervisor] mode =
  "task_scheduler"` shipped as the runtime default.
- `sabrina-2/install-nssm.ps1` and `sabrina-2/install-piper.ps1` —
  exist; service-mode binary fetcher mirrors piper-voice fetcher.
- `CLAUDE.md` — Eric's box is i7-13700K/4080/Win11; daily-driver
  single-user; voice loop needs user-session audio (mic + speakers).
- Microsoft Task Scheduler v1.4 schema:
  `LogonTrigger`/`StartWhenAvailable`/`MultipleInstancesPolicy` semantics
  matched against the existing XML template at supervisor.py:160-193.
- NSSM 2.24 documented behavior at `nssm.cc/usage` (last release 2017,
  still the canonical Windows-service wrapper).

No web searches needed — the question is grounded in the existing draft +
implementation + Microsoft's documented Task Scheduler / Service Control
Manager semantics, all of which I had access to via project files and
stored knowledge.

## What I found

### Inventory: what's already shipped

The supervisor + autostart implementation is **already in `main` as of
HEAD `acd6725` (2026-05-05)**. Specifically:

- `sabrina run` — supervises `sabrina voice` with a rolling crash budget
  (`restart_max=5` per `restart_window_s=300`); exponential backoff capped
  at 60 s; exits 0 on clean child exit / Ctrl+C, exit 2 on budget
  exceeded.
- `sabrina autostart enable` — registers a Task Scheduler `LogonTrigger`
  task named `SabrinaAI`, action = `<sys.executable> -m sabrina run`,
  WorkingDirectory = project root. UTF-16-LE BOM XML written via
  `write_task_scheduler_xml`. Shells to `schtasks /create /tn /xml /f`.
- `sabrina autostart disable` / `status` — `schtasks /delete` and
  `schtasks /query /fo LIST` respectively.
- `[supervisor] mode = "service"` route exists but errors if `nssm.exe`
  isn't on PATH or in `tools/nssm/`; explicit opt-in requiring
  `install-nssm.ps1` to have been run.
- `[supervisor]` config block in `sabrina.toml` is shipped with `mode =
  "task_scheduler"` as the runtime default.

So this research item is post-hoc relative to code: P2.4 ratifies (or
contests) the existing pick before P2.5 (the Windows-side e2e + install
scripts) builds against it. Findings below treat all four mechanisms as
candidates anyway, then check the existing pick against them.

### Mechanism-by-mechanism, against the four DoD axes

#### Task Scheduler (LogonTrigger, schtasks /create /xml)

**Reliability.**
- Power events: `<StartWhenAvailable>true</StartWhenAvailable>` (already
  in template) makes missed triggers fire on resume. LogonTrigger
  re-evaluates on session reconnect, so sleep/wake → wake fires the
  task even if the user was logged in before sleep.
- RDP login: `LogonTrigger` fires on every `LOGON_USER` session start,
  including Remote Desktop. `<MultipleInstancesPolicy>IgnoreNew</...>`
  in the template prevents a duplicate supervisor when both Console
  and RDP sessions belong to the same user.
- Multi-user: `<UserId>DOMAIN\User</UserId>` scopes the trigger to
  Eric's SID. Other users on the box (none today) wouldn't fire it.
- Cold boot: fires on first user logon. Sabrina comes up after Eric
  logs in.
- Failure mode: silently disabled if a user toggles the task in
  `taskschd.msc` UI or via `schtasks /change /tn SabrinaAI /disable`.
  `sabrina autostart status` (already wired) catches this.

**Install/uninstall surface.**
- No admin needed for HKCU-scoped tasks. `schtasks /create` without
  `/ru SYSTEM` registers under the invoking user's context.
- Uninstall: `schtasks /delete /tn SabrinaAI /f`. Symmetric.
- Existing implementation handles UTF-16-LE BOM gotcha
  (supervisor.py:225 — `bom = b"\xff\xfe"` + utf-16-le body); some
  Windows builds reject UTF-8 XML with a misleading `0x80041318` error.

**Crash-recovery composition with supervisor (P2.6).**
- Two-tier separation. Task Scheduler launches `python -m sabrina run`
  once on logon. The supervisor handles in-session crashes via its
  rolling 60-s budget. If the supervisor itself exits with code 2
  (budget exceeded), Task Scheduler's `<RestartOnFailure>` block
  *could* re-launch it — but the existing template doesn't include
  that block, so a budget-exceeded exit currently means "Sabrina is
  silent until Eric runs `sabrina run` manually." Acceptable for
  daily-driver bake-in (failure becomes user-visible quickly), but
  worth flagging as a follow-up.

**Verdict:** strong. Already implemented. Lowest-ceremony native
Windows mechanism with all four reliability properties handled.

#### Registry Run key (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)

**Reliability.**
- Power events: NO wake-retry. Run-key entries fire exactly once when
  `explorer.exe` initializes the user session. Sleep/wake → no
  re-launch. If the supervisor died before sleep, it stays dead.
- RDP login: fires per session start. Same MultipleInstancesPolicy
  concern as Task Scheduler but no built-in dedup — would need a
  PID-file or named-mutex check inside `sabrina run` itself.
- Multi-user: HKCU is per-user. Only Eric's profile fires it.
- Cold boot: fires once on logon.
- Failure mode: silently disabled by Task Manager → Startup tab. No
  status command — would need to read the registry key.

**Install/uninstall surface.**
- No admin. Single `reg add` / `reg delete`.
- BUT: the value is a single command string. Setting the working
  directory requires either a `cmd.exe /c "cd <root> && <py> -m
  sabrina run"` wrapper (visible console flash) or a `.vbs`/`.ps1`
  shim (extra files to maintain). Task Scheduler's `<WorkingDirectory>`
  is cleaner.

**Crash-recovery composition.**
- Identical to Task Scheduler: launches supervisor once; supervisor
  handles restarts. No advantage.

**Verdict:** strictly worse than Task Scheduler. Same crash-recovery
composition, weaker reliability (no wake-retry), uglier `cwd`
handling, no clean status-check.

#### NSSM-wrapped Windows Service

**Reliability.**
- Pre-login: a service can run from system boot before Eric logs in —
  but a voice-loop process needs the **user's audio session**, which
  doesn't exist until Eric logs in. So pre-login start is moot.
  Either the service starts as `LocalSystem` (no audio access) or as
  Eric's user (only effective once Eric is logged in anyway).
- Power events: SCM handles wake-recovery. Good.
- RDP login: services live in session 0; they don't fire on login
  events. So the "service starts at boot" model and the "voice needs
  user session" requirement collide. Effectively, `nssm set ObjectName
  <user>` makes the service block on a user session existing.
- Multi-user: ObjectName is single-user. Switching users = manual
  reconfigure.
- Failure mode: SCM auto-restart (`nssm set AppExit Default Restart`)
  loops on its own schedule, *plus* the supervisor's loop, plus the
  supervisor's budget — three nested recovery layers with no shared
  state.

**Install/uninstall surface.**
- **Admin elevation required once** (`nssm install` writes to
  `HKLM\SYSTEM\CurrentControlSet\Services`). UAC prompt on first
  enable.
- ObjectName = Eric's user requires Eric's password (NSSM prompts).
  Stored encrypted in the service config but a thing the user has to
  see/enter.
- Requires `nssm.exe` binary fetched via `install-nssm.ps1`. One-time
  setup tax.
- Uninstall: `nssm remove SabrinaAI confirm` (admin again).

**Crash-recovery composition.**
- The dual-restart-loop is a real concern. Supervisor exits code 2
  (budget exceeded) → SCM treats that as failure → SCM restarts the
  service → supervisor immediately spawns voice again → defeats the
  budget. Coordinating SCM `RestartCount` with supervisor
  `restart_max` adds non-trivial logic.

**Verdict:** **the audio-session requirement is the dealbreaker for
default mode.** Services don't gain anything for a voice app whose
working state is gated on the user being logged in. The admin
elevation cost and the dual-restart-loop coordination are pure
additive complexity. Keep as opt-in (current `mode = "service"`
config knob) for a hypothetical future "I want SCM-managed lifecycle"
case; never default.

#### shell:startup .lnk (drop a shortcut into
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup)

**Reliability.**
- Power events: NO wake-retry. Same as Run key — fires once at
  Explorer init.
- RDP login: fires per session start.
- Multi-user: per-user folder. Good.
- Cold boot: fires once on logon.
- Failure mode: user can delete the .lnk by accident; can be disabled
  via Task Manager Startup tab.

**Install/uninstall surface.**
- No admin. Drop a .lnk file.
- BUT: programmatically creating .lnk files requires either
  `WScript.Shell` COM (`New-Object -ComObject WScript.Shell` from
  PowerShell) or `pywin32`'s `win32com.shell`. Either way: more
  moving parts than `schtasks.exe`, which is built into Windows.
- Setting "Run minimized" (window-state in the .lnk binary) requires
  the same COM dance.
- Uninstall: delete the .lnk file. Trivial.

**Crash-recovery composition.**
- Identical to Run key. Launches supervisor once.

**Verdict:** strictly worse than Task Scheduler. Same crash-recovery
composition, .lnk creation requires COM (more deps than schtasks),
no wake-retry. The "lowest ceremony" framing is misleading because
the implementation is *more* complex than schtasks.exe once you need
to set the working directory and window state.

### Side-by-side

| Mechanism | Admin? | User-audio? | Wake-retry? | RDP triggers? | Crash-recovery composition with supervisor | Implementation status |
|---|---|---|---|---|---|---|
| **Task Scheduler** | No (HKCU-scoped) | Yes (LogonTrigger fires user-session) | Yes (`StartWhenAvailable`) | Yes (per session-start) | Two-tier (TS → supervisor → voice). Clean separation. | **In `main`** at `acd6725` — `render_task_scheduler_xml` + `sabrina autostart enable/disable/status` |
| Registry Run | No | Yes | **No** | Yes | Same as Task Scheduler (no advantage) | Not implemented; ~5 LOC if needed |
| NSSM Service | **Yes once** | Conditional (audio only after Eric logs in anyway) | Yes (SCM) | No (session 0) | **Three layers (SCM + supervisor + voice). Risk of conflict** | Already wired as opt-in `mode = "service"`; `install-nssm.ps1` exists |
| shell:startup | No | Yes | **No** | Yes | Same as Task Scheduler (no advantage) | Not implemented; needs WScript.Shell COM dance |

## Recommendation

**Actionable change: ratify Task Scheduler as the default and proceed
to P2.5 against the existing implementation.**

The existing draft + code already pick Task Scheduler. This research
defends the pick rigorously:

1. Task Scheduler is the **only** mechanism in the four-way comparison
   that handles wake-retry, RDP, and per-user scoping without admin.
2. Run key and shell:startup are strictly worse — same crash-recovery
   composition, weaker reliability, more implementation ceremony for
   the working-directory + window-state concerns Task Scheduler
   handles in the XML template natively.
3. NSSM Service is wrong as default for a voice app. The audio-session
   requirement neutralizes the only thing Services give you (pre-login
   start), the admin-elevation cost is real, and the three-layer
   restart loop is a coordination problem that doesn't exist in the
   Task Scheduler path.
4. Implementation is **already in `main`** (`acd6725`,
   `sabrina-2/src/sabrina/supervisor.py` + `cli.py`). P2.5 reduces to
   Windows-side e2e validation + the small XML-polish follow-ups in
   the next section.

P2.5's actual remaining scope is much smaller than the QUEUE entry
suggests: it's not "implement install/uninstall scripts," it's
"validate `sabrina autostart enable` works on Eric's box and tighten
the XML template per the follow-ups below." A future planner /
spec-writer slot can sharpen the P2.5 description against this
finding.

NSSM-service mode stays as the opt-in `[supervisor] mode = "service"`
knob already shipped — there for a future "I want SCM lifecycle"
request that Eric can flip on without code changes.

## Open follow-ups

These don't block P2.5 picking up against Task Scheduler — they're
polish items the P2.5 e2e session can knock down or push to a
follow-up:

1. **`<RestartOnFailure>` block missing from `_TASK_XML_TEMPLATE`.** If
   the supervisor exits with code 2 (budget exceeded), Task Scheduler
   currently does nothing; Sabrina stays silent until Eric runs
   `sabrina run` manually. Adding `<RestartOnFailure><Interval>PT5M</Interval><Count>3</Count></RestartOnFailure>`
   gives the OS a "try the supervisor again three times at 5-minute
   intervals before giving up" recovery layer. Adds maybe 4 lines to
   the template + one pytest assertion. Low priority — daily-driver
   bake-in benefits from failures being user-visible early.
2. **`<Priority>7</Priority>` is "below normal."** Voice-loop response
   time may want normal (4) or higher. Validate during P2.5 with a
   stopwatch on a cold-boot-into-voice-turn flow.
3. **`<Hidden>false</Hidden>`.** Cosmetic — toggling to `true` keeps
   `taskschd.msc` history less cluttered but makes the task easier
   to lose track of. No load on either side.
4. **`<UserId>` substitution on a non-domain-joined box.**
   `cli.py:1173-1181` uses `USERDOMAIN_ROAMINGPROFILE` → `USERDOMAIN`
   → `USERNAME` fallback chain. Eric's box is non-domain-joined per
   CLAUDE.md, so `USERDOMAIN` is the local machine name. The chain
   should produce `MACHINENAME\Eric` which Task Scheduler accepts.
   Validate during P2.5 e2e — if the resulting user_id is wrong,
   schtasks errors loudly and we'd see it on first `enable`.
5. **`<RunOnlyIfIdle>` element absent from the template** — the
   schema's default is `false`, so Sabrina won't be blocked by
   non-idleness. Worth one `assert "<RunOnlyIfIdle>true</RunOnlyIfIdle>"
   not in xml` test for paranoia, but not a blocker.
6. **Task name uniqueness.** Default is `SabrinaAI`. If Eric ever runs
   two installs (sabrina-2 + a future sabrina-3 in parallel), the
   `task_name` config knob lets them coexist. No action needed; just
   noting the existing knob is load-bearing.

None of these escalate to PROPOSED items unless P2.5 e2e surfaces
something concrete; they're documentation for the P2.5 worker / Eric.
