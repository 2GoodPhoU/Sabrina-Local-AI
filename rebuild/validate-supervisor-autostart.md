# Supervisor + autostart — Windows validation procedure

**Purpose:** confirm the supervisor and autostart plumbing (Task
Scheduler default, optional nssm Service path) work end-to-end on
Eric's Windows box before we call the supervisor decision validated.
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from
`sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`.
Supervisor implementation has landed per `rebuild/drafts/supervisor-autostart-plan.md`
(`supervisor.py`, `autostart/task_scheduler.py`, `autostart/service_nssm.py`,
`sabrina run`, `sabrina autostart {enable,disable,status}`, `[supervisor]`
block in `sabrina.toml`, `install-nssm.ps1`).

This doc tests **both** branches. If you only care about one path, skip
the other's section. The Task Scheduler path is the default and should
run start-to-finish without any admin prompts. The Service path needs
one elevated PowerShell for the initial install.

---

## Step 0 — Sanity-check schtasks is available

```powershell
schtasks /query /tn ""
```

**Success:** prints "ERROR: The filename, directory name, or volume
label syntax is incorrect." — that's `schtasks.exe` itself reporting,
which means the binary is on PATH and working. Any schtasks error
output means the binary runs.
**Failure signal:** `schtasks : The term 'schtasks' is not
recognized...`. Means `%SystemRoot%\System32` isn't on your PATH —
fix your PATH before continuing. This basically never happens on a
normal Windows 10/11.

---

## Step 1 — `uv sync` (no new Python deps expected)

```powershell
uv sync
```

**Success:** no-op or near-no-op; supervisor adds no Python deps.
`uv.lock` unchanged unless other components bumped it.

---

## Step 2 — `uv run pytest -q`

```powershell
uv run pytest -q
```

**Success:** existing tests pass, plus the supervisor/autostart block
(roughly 8-10 new tests):

- `test_supervisor_exits_on_child_clean_exit`
- `test_supervisor_restarts_on_crash_within_budget`
- `test_supervisor_gives_up_when_budget_exceeded`
- `test_supervisor_backoff_grows`
- `test_supervisor_resets_consecutive_on_long_run`
- `test_task_scheduler_xml_renders_executable_and_project_root`
- `test_task_scheduler_invocation_calls_schtasks_with_xml`
- `test_service_nssm_bails_clearly_when_binary_missing`
- `test_service_nssm_builds_install_commands`

**Failure signal:** anything red. Capture the traceback.

---

## Step 3 — Supervisor foreground smoke (the crash-recovery core)

With the default config (`mode = "task_scheduler"`, we haven't
registered anything yet), run the supervisor in the foreground against
a deliberately-crashing stub child. The test harness for this lives in
the plan's ship criterion — simplest practical smoke is the plan's
"supervises a crashing stub for 3 restart cycles then bails."

```powershell
$env:SABRINA_SUPERVISOR_SMOKE = "crash"
uv run sabrina run
```

**Success:** supervisor spawns the child, child exits non-zero, log line
like `supervisor.restart rc=1 backoff_s=2 consecutive=1` appears,
supervisor sleeps and respawns. After `max_restarts_per_minute + 1`
crashes in the rolling window, log line
`supervisor.giving_up crashes=6` and process exits with code 2.

Remove the env var for the rest of this doc:

```powershell
Remove-Item Env:SABRINA_SUPERVISOR_SMOKE
```

**Failure signals:**
- Supervisor never respawns → `_spawn_and_wait` is returning `rc=0`
  incorrectly on a crashing child, or `_user_interrupted(rc)` is
  matching too eagerly.
- Supervisor respawns forever, no "giving up" → rolling-window math
  in `_budget_exceeded` is wrong.
- Crash is silent (no logs) → structlog not hooked in supervisor.py's
  module-level logger.

---

## Step 4 — Ctrl+C propagation

```powershell
uv run sabrina run
```

Wait until the voice loop's "Ready" message appears (confirms child
booted), then press Ctrl+C once.

**Success:** the voice process catches SIGINT, shuts down cleanly
(you'll see its "goodbye" log lines), the supervisor reaps it, and
exits itself with code 0 — no automatic restart.

**Failure signals:**
- Ctrl+C kills the supervisor but orphans the voice process (check
  `Get-Process python` in another window while the supervisor is
  exiting) → `CREATE_NEW_PROCESS_GROUP` flag missing from Popen, or
  CTRL_BREAK_EVENT not being sent.
- Ctrl+C restarts the voice process instead of exiting → `_user_interrupted`
  not recognizing the signal as user-initiated.

---

## Step 5A — Task Scheduler registration (default path)

```powershell
uv run sabrina autostart status
```

**Expected pre-register:** `SabrinaAI: not registered`.

```powershell
uv run sabrina autostart enable
```

**Success:** prints `registered: SabrinaAI (trigger: at user logon)`.
No UAC prompt (Task Scheduler per-user tasks don't need admin).

```powershell
schtasks /query /tn SabrinaAI /fo LIST
```

**Success:** output includes `TaskName: \SabrinaAI`, `Status: Ready`,
`Next Run Time: At log on of <YourUser>`, `Task To Run` pointing at
`<sys.executable> -m sabrina run` with `Start In` at the project
root.

```powershell
uv run sabrina autostart status
```

**Success:** prints `SabrinaAI: registered (status: Ready, trigger: at
user logon)`.

**Failure signal:** schtasks exits non-zero on `enable` → the XML
rendered wrong. Capture it:

```powershell
uv run sabrina autostart enable --dry-run > task.xml
type task.xml
```

The XML should reference `<sys.executable>`, `-m sabrina run`, and the
project root verbatim. Backslash vs. forward-slash bugs are the usual
culprit.

---

## Step 5B — At-logon trigger smoke

This is the one step that requires a reboot. Decide whether you're
willing before running it.

```powershell
Restart-Computer
```

Wait to reach the desktop. Don't launch PowerShell yourself — let
Task Scheduler do its thing for ~30 s. Then:

```powershell
Get-Process python -ErrorAction SilentlyContinue | Format-Table Id, ProcessName, StartTime
```

**Success:** two python processes. One started within ~10 s of your
logon (the supervisor) and one started 1–5 s after (the voice
process). Confirm via the supervisor log:

```powershell
type logs\supervisor.log
```

**Success:** last lines show `supervisor.started` and `supervisor.spawn
pid=<X>` with `StartTime` matching the at-logon window.

**Failure signal:** zero python processes running → Task Scheduler
didn't fire, or the task fired and the process crashed immediately.
Check:

```powershell
schtasks /query /tn SabrinaAI /fo LIST /v
```

`Last Run Time` and `Last Result` tell you if it fired and what happened.
`Last Result: 0` + no process = supervisor exited cleanly (bad); any
non-zero = it failed — capture `logs/supervisor.log` and the Windows
event viewer's Task Scheduler log.

---

## Step 5C — Disable and verify cleanup

```powershell
uv run sabrina autostart disable
```

**Success:** prints `unregistered: SabrinaAI`.

```powershell
schtasks /query /tn SabrinaAI /fo LIST
```

**Success:** `ERROR: The system cannot find the file specified.` — task
is gone. On next reboot, nothing starts automatically.

```powershell
uv run sabrina autostart status
```

**Success:** `SabrinaAI: not registered`.

---

## Step 6A — Toggle `supervisor.mode` to Service

Edit `sabrina-2/sabrina.toml`:

```toml
[supervisor]
mode = "service"
```

```powershell
uv run sabrina autostart status
```

**Success:** the CLI now reports the Service-mode view. Before
`install-nssm.ps1` has run, expect:

```
SabrinaAI: not registered (service mode; nssm not installed)
```

**Failure signal:** the CLI still checks Task Scheduler state instead
of Service state → the mode dispatch in `cli.py`'s `autostart` subgroup
is broken. Run `sabrina config-show | findstr /i supervisor` to
confirm the mode setting actually loaded.

---

## Step 6B — Install nssm

```powershell
.\install-nssm.ps1
```

**Success:** downloads `nssm.exe` into `tools/nssm/`, prints success.
`tools/nssm/nssm.exe` exists and `tools\nssm\nssm.exe version` prints
`NSSM 2.24`.

**Failure signal:** corporate-proxy / cert errors on download — same
failure mode as the Piper installer. Capture the full output.

---

## Step 6C — Service install (requires elevated PowerShell, one time)

Open a new PowerShell as administrator. Navigate back to the project
root. Then:

```powershell
uv run sabrina autostart enable
```

nssm will prompt once for your user password (so the service runs as
your user, not LocalSystem — important for audio + `.env` access).

**Success:** prints `installed: SabrinaAI (service, log-on as
<your-user>)`. Back in the non-admin PowerShell:

```powershell
sc.exe query SabrinaAI
```

**Success:** `STATE: 4 RUNNING` (nssm starts the service immediately
on install by default). If `STATE: 1 STOPPED`, start it:

```powershell
uv run sabrina autostart start
```

Then re-check with `sc.exe query SabrinaAI`.

```powershell
Get-Content logs\service.log -Tail 20
```

**Success:** `supervisor.started` and `supervisor.spawn` lines, same
as the Task Scheduler path.

**Failure signals:**
- nssm install fails because the PowerShell wasn't elevated → the
  error message is explicit. Re-open elevated and retry.
- Service starts but the voice process never appears (`Get-Process
  python` shows only one) → nssm is running Python but as LocalSystem
  despite the ObjectName setting. Check `nssm get SabrinaAI ObjectName`
  — should be `<domain>\<user>`, not `LocalSystem`.
- Audio device errors in the voice process's structlog → the service
  is running but can't see your audio devices. This is *the* canonical
  Service-mode problem. Confirm ObjectName via `nssm get`; if it's the
  user, the session might still be pre-login (service-startup before
  user logon). This is why the plan's default is Task Scheduler.

---

## Step 6D — Uninstall cleanup

```powershell
# back to non-admin PowerShell
uv run sabrina autostart disable
```

**Success:** stops and removes the service. `sc.exe query SabrinaAI`
reports `The specified service does not exist as an installed service.`

```powershell
uv run sabrina autostart status
```

**Success:** `SabrinaAI: not registered (service mode; nssm installed
at tools/nssm/nssm.exe)`.

Flip the mode back to Task Scheduler (or leave it; the choice is
Eric's):

```toml
[supervisor]
mode = "task_scheduler"
```

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 3 | No respawn | `_user_interrupted` matching non-user signals | Full log output during the crash loop |
| 3 | Infinite respawn | Rolling-window math off | Backoff values per restart line |
| 4 | Orphaned python child | Missing `CREATE_NEW_PROCESS_GROUP` or CTRL_BREAK not sent | `Get-Process python` output during shutdown |
| 5A | schtasks exits non-zero | Malformed XML | `sabrina autostart enable --dry-run` XML output |
| 5B | No process after reboot | Task fired but child crashed | `schtasks /query /tn SabrinaAI /fo LIST /v` + `logs/supervisor.log` + Task Scheduler event viewer |
| 5B | Task never fired | At-logon trigger malformed | `<LogonTrigger>` element of dry-run XML |
| 5C | `disable` no-op | `schtasks /delete` needs `/f` on this box | try `schtasks /delete /tn SabrinaAI /f` manually |
| 6B | nssm download fails | Corporate proxy | Full `install-nssm.ps1` output |
| 6C | ObjectName = LocalSystem | nssm set command skipped | `nssm dump SabrinaAI` output |
| 6C | Audio errors in service mode | Service running as user but session type wrong | Compare `nssm get SabrinaAI Type`; should be `SERVICE_WIN32_OWN_PROCESS` |

---

## Known risks from the pre-validation code audit

1. **Windows Task Scheduler XML is unforgiving about encoding.** The
   XML must be UTF-16 LE with a BOM when fed to `schtasks /create /xml`.
   If `autostart/task_scheduler.py` writes UTF-8, schtasks silently
   rejects it. Verify the temp file encoding before blaming the content.
2. **`CTRL_BREAK_EVENT` signals the whole process group, including the
   supervisor itself.** The implementation must flip to its own
   process group (`CREATE_NEW_PROCESS_GROUP` on the *child*, not the
   supervisor) or the Ctrl+C smoke in step 4 will kill both cleanly and
   step 3's crash smoke will kill supervisor-parent too. Watch for this
   if Ctrl+C behaves differently than expected.
3. **nssm's "log-on as user" stores the password in the service
   configuration.** Rotating your Windows password invalidates the
   service; you'll need to re-run `autostart enable` (elevated) with
   the new password. Flag to Eric; expected behavior.
4. **Task Scheduler's `RunOnlyIfNetworkAvailable = false` matters on
   an offline boot.** Sabrina should start even with no network (Ollama
   works offline). The plan sets this correctly; verify by rendering
   the XML in step 5A and confirming the flag.
5. **Rebooting takes ~2 min on this hardware.** If you don't want to
   reboot-test step 5B today, skip it and mark the validation
   "partial — 5B deferred" in the ROADMAP bump.

---

## If all green — the ROADMAP bump

Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line.
2. Append one line at the end of the "Status:" paragraph:

```
Supervisor + autostart validated on Windows (i7-13700K/4080, Python
3.12) <YYYY-MM-DD>: crash recovery across <K> restart cycles,
Task Scheduler at-logon confirmed<, Service-mode path <S>>.
```

`<K>` from step 3. `<S>` is "also confirmed" if you ran step 6 branch,
"deferred" if you didn't.

Commit with message:
```
validate: supervisor + autostart on Windows
```

---

## If any step failed

1. Capture per the triage table.
2. File a follow-up decision doc under `rebuild/decisions/` with the
   next free number. Separate the failure by step (step 3 = supervisor
   core, step 5 = Task Scheduler, step 6 = Service/nssm) — those are
   nearly-independent subsystems and mixing them in one doc is
   anti-sprawl-unfriendly.
3. Task Scheduler XML encoding failures (risk #1) are common enough
   that a canned decision-doc stub is worth keeping if it happens.
