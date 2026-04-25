"""Process supervisor + autostart wiring (Windows-first).

Two surfaces:

1. ``run_supervised(child_argv, cfg)`` — spawns the voice-loop process,
   reaps it, restarts on unhandled exit subject to a budget, exits 0
   on a clean child exit / Ctrl+C. Crash-recovery only; no health
   pings, no telemetry. Mirrors `rebuild/drafts/supervisor-autostart-plan.md`.

2. ``render_task_scheduler_xml`` + ``install_task_scheduler_task`` /
   ``uninstall_task_scheduler_task`` — generate a Windows Task Scheduler
   XML for "run at user logon" and shell out to `schtasks.exe`. The XML
   is UTF-16 LE with a BOM, which `schtasks /create /xml` requires.

Service-mode helpers (``build_nssm_install_commands``,
``uninstall_nssm_service``) build the nssm command sequence without
actually executing it, so the same code path is exercised by tests
and on Windows. Running the commands is callers' job.

Why one file: the plan splits into supervisor.py + autostart/{task,
service}.py, but the three blocks below total ~250 lines and the
guardrail #2 ("anti-sprawl") wants a second caller before splitting.
A future commit can split if either function grows past ~150 lines or
gains a third backend.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sabrina.config import SupervisorConfig
from sabrina.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Supervisor: spawn-and-watch with a crash budget.
# ---------------------------------------------------------------------------


# Exit codes that mean "user asked us to stop" -- supervisor exits too
# without restart. Windows Ctrl+C is 0xC000013A which surfaces as 3221225786
# in cpython >= 3.8; SIGINT-style is also negative on POSIX. Be liberal.
_USER_INTERRUPT_RCS = frozenset({0, 130, 3221225786, -2})


@dataclass
class _RestartBudget:
    """Tracks crashes inside a sliding window for the crash-budget check."""

    max_crashes: int
    window_s: float
    times: deque  # type: ignore[type-arg]

    @classmethod
    def make(cls, cfg: SupervisorConfig) -> "_RestartBudget":
        return cls(
            max_crashes=cfg.restart_max,
            window_s=float(cfg.restart_window_s),
            times=deque(),
        )

    def record_crash(self, now: float | None = None) -> None:
        ts = time.monotonic() if now is None else now
        self.times.append(ts)
        # Drop entries outside the rolling window.
        cutoff = ts - self.window_s
        while self.times and self.times[0] < cutoff:
            self.times.popleft()

    def exceeded(self) -> bool:
        return len(self.times) > self.max_crashes


def run_supervised(
    child_argv: list[str],
    cfg: SupervisorConfig,
    *,
    spawner: Callable[[list[str]], int] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> int:
    """Spawn `child_argv`, watch for crashes, restart up to budget, then bail.

    `spawner(argv) -> exit_code` and `sleeper(seconds) -> None` are
    injected for tests; defaults call subprocess + time.sleep.
    """
    spawn = spawner or _default_spawn
    sleep = sleeper or time.sleep
    budget = _RestartBudget.make(cfg)
    consecutive = 0
    log.info(
        "supervisor.spawned",
        argv=child_argv,
        mode=cfg.mode,
        restart_max=cfg.restart_max,
    )
    while True:
        t0 = time.monotonic()
        rc = spawn(child_argv)
        elapsed = time.monotonic() - t0
        log.info("supervisor.child_exit", rc=rc, elapsed_s=round(elapsed, 2))
        if rc in _USER_INTERRUPT_RCS:
            return rc
        consecutive = consecutive + 1 if elapsed < cfg.restart_window_s else 1
        budget.record_crash()
        if budget.exceeded():
            log.error("supervisor.budget_exceeded", crashes=len(budget.times))
            return 2
        backoff = min(2.0 * (2 ** (consecutive - 1)), 60.0)
        log.warning(
            "supervisor.backoff",
            seconds=backoff,
            consecutive=consecutive,
            rc=rc,
        )
        sleep(backoff)


def _default_spawn(argv: list[str]) -> int:
    """Default child spawner. Forwards Ctrl+C to the child process group.

    On Windows we open a new process group (CREATE_NEW_PROCESS_GROUP) so
    that Ctrl+C delivered to the supervisor doesn't propagate
    automatically; we relay it ourselves and reap.
    """
    creationflags = 0
    if os.name == "nt":
        # Importing locally so non-Windows test runs don't blow up on
        # missing constants.
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(argv, creationflags=creationflags)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            return proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            return proc.wait()


# ---------------------------------------------------------------------------
# Autostart: Task Scheduler XML + install/uninstall via schtasks.
# ---------------------------------------------------------------------------


# Task Scheduler XML schema. Keep the placeholders distinct -- the
# project root and python executable are user-specific and must be
# substituted at install time.
_TASK_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{description}</Description>
    <Author>SabrinaAI</Author>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{user_id}</UserId>
    </LogonTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>{command}</Command>
      <Arguments>{arguments}</Arguments>
      <WorkingDirectory>{working_directory}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def render_task_scheduler_xml(
    *,
    python_executable: str | Path,
    project_root: str | Path,
    user_id: str,
    description: str = "Sabrina AI voice loop (auto-start at user logon)",
    arguments: str = "-m sabrina run",
) -> str:
    """Render the Task Scheduler XML body. UTF-16-LE BOM is added at write."""
    return _TASK_XML_TEMPLATE.format(
        description=description,
        user_id=user_id,
        command=str(python_executable),
        arguments=arguments,
        working_directory=str(project_root),
    )


def write_task_scheduler_xml(path: Path, body: str) -> None:
    """Write the XML body as UTF-16 LE with a BOM (schtasks /xml requires it).

    Plain UTF-8 is silently rejected by schtasks on some Windows builds
    with a misleading "0x80041318" error. The encoding is the one piece
    of this that the validate-supervisor-autostart.md doc flags.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Always BOM + UTF-16-LE; schtasks rejects plain UTF-8 silently.
    # BOM (\xff\xfe) + UTF-16-LE body. Atomic single write.

    bom = b"\xff\xfe"
    body_bytes = body.encode("utf-16-le")
    path.write_bytes(bom + body_bytes)


def install_task_scheduler_task(
    *,
    task_name: str,
    xml_path: Path,
    runner: Callable[[list[str]], int] | None = None,
) -> int:
    """Register the task via `schtasks /create /xml`. Returns rc."""
    run = runner or _default_runner
    cmd = ["schtasks", "/create", "/tn", task_name, "/xml", str(xml_path), "/f"]
    log.info("supervisor.task_scheduler.install", task_name=task_name)
    return run(cmd)


def uninstall_task_scheduler_task(
    *,
    task_name: str,
    runner: Callable[[list[str]], int] | None = None,
) -> int:
    """Remove the task via `schtasks /delete`. Returns rc."""
    run = runner or _default_runner
    cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
    log.info("supervisor.task_scheduler.uninstall", task_name=task_name)
    return run(cmd)


def _default_runner(cmd: list[str]) -> int:
    return subprocess.call(cmd)


# ---------------------------------------------------------------------------
# Autostart: nssm-wrapped Windows Service.
# ---------------------------------------------------------------------------


def find_nssm(cfg: SupervisorConfig) -> Path | None:
    """Locate nssm.exe per config or on PATH. Returns None if missing."""
    if cfg.nssm_binary:
        candidate = Path(cfg.nssm_binary)
        if candidate.is_file():
            return candidate
    found = shutil.which("nssm")
    return Path(found) if found else None


def build_nssm_install_commands(
    *,
    task_name: str,
    python_executable: str | Path,
    project_root: str | Path,
    nssm_binary: str | Path,
    log_path: str | Path,
    arguments: str = "-m sabrina run",
) -> list[list[str]]:
    """Return the ordered nssm shell-outs to install + configure the service.

    No execution -- callers run the list. Tests assert the sequence shape.
    """
    nssm = str(nssm_binary)
    return [
        [nssm, "install", task_name, str(python_executable), arguments],
        [nssm, "set", task_name, "AppDirectory", str(project_root)],
        [nssm, "set", task_name, "Start", "SERVICE_AUTO_START"],
        [nssm, "set", task_name, "AppStdout", str(log_path)],
        [nssm, "set", task_name, "AppStderr", str(log_path)],
        [nssm, "set", task_name, "AppExit", "Default", "Restart"],
    ]


def build_nssm_uninstall_commands(
    *, task_name: str, nssm_binary: str | Path
) -> list[list[str]]:
    """Stop + remove the service. Same shape as the install sequence."""
    nssm = str(nssm_binary)
    return [
        [nssm, "stop", task_name],
        [nssm, "remove", task_name, "confirm"],
    ]


# ---------------------------------------------------------------------------
# CLI helper: build the child argv for `sabrina run`.
# ---------------------------------------------------------------------------


def default_child_argv() -> list[str]:
    """The voice-loop subprocess we supervise. Mirrors `sabrina voice`."""
    return [sys.executable, "-m", "sabrina", "voice"]
