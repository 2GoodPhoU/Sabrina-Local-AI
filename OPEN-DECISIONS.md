# Open Decisions — Sabrina-Local-AI

> Snapshot 2026-05-11. **15 decisions in 6 groups.** Read top-to-bottom; quick-answer hints at the end of each.

## Workflow & Infra

**S1: Clear the leaked `.git/index.lock`**
Question: do you clear `.git/index.lock` from a Windows shell so 10 lock-blocked Worker diffs can commit?
Options: (a) clear it tonight; (b) leave it and let me promote diffs via a different route; (c) defer.
Recommendation: (a). The lock is 0 bytes, owned by sandbox user, leaked by Worker's own `git checkout -b`.
Impact: unblocks P0 cli/config repair, P5.4, P5.5, P5.1, P5.3, P2.7, P2.2, P4.B1, P4.C1, P4.C2 (a-halves).
Quick answer hint: answer with: a / b / c

**S2: GitHub MCP gate in night-auditor**
Question: install/connect GitHub MCP for scheduled sessions, or remove the remote-PR audit step from the role doc?
Options: (a) install; (b) remove the step; (c) leave as best-effort skip.
Recommendation: (b). Local commits are the DoD; remote pushes are informational.
Impact: closes oldest NEEDS-INPUT item (2026-04-30).
Quick answer hint: answer with: a / b / c

**S3: Worker.md FUSE-lock carve-out**
Question: amend `roles/worker.md` step 7 to let Workers `rm -f` their own leaked lock when forensic markers match (mtime <5min + 0-byte + owner = sandbox user)?
Options: (a) add the carve-out; (b) keep strict bail rule; (c) defer.
Recommendation: (a). Pattern is structural to FUSE+NTFS, will recur.
Impact: stops every 8am Worker bailing on its own leaked lock.
Quick answer hint: answer with: a / b / c

## Windows-session scheduling

**S4: Next Windows session ETA**
Question: when will you run the queued `[windows-required]` validations (Phase 3 b-half, P2.3 wake-word, P2.5 autostart, P2.6 supervisor, P2.8 budget e2e)?
Options: (a) this weekend; (b) within 2 weeks; (c) deferred indefinitely.
Recommendation: (a). Five items collapse into one Saturday; promotion to `[done]` unblocks Phase 4 entry.
Impact: closes Gate 1 components 3, 5, plus daily-driver readiness items 1-3, 5.
Quick answer hint: answer with: a / b / c

## Roadmap & Scope

**S5: Wake-word path for v1.0**
Question: ship custom "Hey Sabrina" (P2.2 → P2.3) or accept PTT-only as the readiness-item satisfier?
Options: (a) custom model; (b) PTT-only, defer wake-word to v1.1; (c) `hey_jarvis` placeholder.
Recommendation: (a). Stated daily-driver vision in ROADMAP §"Gate 2".
Impact: decides whether P2.2 (a)-half tooling actually executes on WSL2.
Quick answer hint: answer with: a / b / c

**S6: Start P4.A1 avatar architecture research?**
Question: kick off avatar architecture research now (Linux-runnable, pure paperwork) or hold until Phase 2/3 close?
Options: (a) start now; (b) hold until Phase 3 b-half lands; (c) deprioritize avatar to v1.1.
Recommendation: (a). Pure research, no diff surface, unblocks P4.A2/A3.
Impact: starts the 15%-weight Phase 4 ladder.
Quick answer hint: answer with: a / b / c

**S7: Bake-in week start**
Question: start the 7-day bake-in clock now, after Phase 5 port lands, or after Phase 4 ships?
Options: (a) after Phase 5; (b) after Phase 4 + 5; (c) start informally now.
Recommendation: (b). Honest to ROADMAP §"Phase 6" entry criteria.
Impact: sets realistic v1.0 ship calendar.
Quick answer hint: answer with: a / b / c

**S8: Reduce Worker schedule 5→2 slots**
Question: drop 9am/10am/12pm Worker tasks until queue produces multiple Linux-runnables per day?
Options: (a) drop to 8am+11am; (b) keep all 5; (c) drop to 8am only.
Recommendation: (a). 30 idle slot-runs/week today.
Impact: reduces JOURNAL noise; PROPOSED #27.
Quick answer hint: answer with: a / b / c

## Wake-word specific

**S9: Training-host pick**
Question: run wake-word training in Cowork sandbox or WSL2?
Options: (a) WSL2; (b) sandbox; (c) defer.
Recommendation: (a). Per 2026-05-05 research + spec-writer (a)-rec.
Impact: unblocks P2.2 (a)-half execution.
Quick answer hint: answer with: a / b / c

**S10: Model-file commit policy**
Question: how does the trained `.onnx` land in repo?
Options: (a) direct git commit; (b) git-lfs; (c) runtime download.
Recommendation: (a). ~1-5MB, infrequent updates.
Impact: closes second spec-writer 2026-05-06 ask.
Quick answer hint: answer with: a / b / c

## Process & Role-doc

**S11: Bulk-ratify all (a)-recommended spec answers**
Question: rubber-stamp the 16 spec-writer NEEDS-INPUT asks where Worker can already ship against (a) and reroute on override (P2.6, P2.7, P4.B1×3, P4.B2×3, P4.B3×3, P4.C1×2, P4.C2×3)?
Options: (a) yes, blanket-approve (a); (b) review each; (c) defer.
Recommendation: (a). Every spec recommends (a); reroute cost on override is small.
Impact: collapses 16 NEEDS-INPUT entries; lets Phase 4 (a)-halves flow without per-spec gating.
Quick answer hint: answer with: a / b / c

**S12: Sharpen post-edit verification rule (PROPOSED #36/#37)**
Question: add "verify via Read tool, not bash/Python" to CLAUDE.md and deprecate Python read+os.replace in worker.md?
Options: (a) ship both; (b) ship CLAUDE.md only; (c) defer.
Recommendation: (a). Worker-9am 2026-05-07 lost 4 JOURNAL entries to the pattern.
Impact: prevents recurrence; closes researcher 2026-05-09 asks.
Quick answer hint: answer with: a / b / c

## Graduations

**S13: Working-tree triage (PROPOSED #5/#11/#13/#14)**
Question: schedule the human-led `git status` triage + commit-plan session, or treat acd6725 as having absorbed enough?
Options: (a) schedule a session; (b) close PROPOSED #5-14 as obsolete post-acd6725; (c) audit first.
Recommendation: (b). acd6725 landed 78 files; remaining drift is small + tracked.
Impact: clears six aging PROPOSED items.
Quick answer hint: answer with: a / b / c

**S14: Idle-worker sidework + census auto-promote (PROPOSED #22/#23)**
Question: approve sidework ladder + auto-promote of doc-only census corrections?
Options: (a) approve both; (b) one only; (c) defer.
Recommendation: (a). Composes with S8 reduction.
Impact: turns idle slots into bounded sidework; clears 4 doc-correction items.
Quick answer hint: answer with: a / b / c

**S15: Ruff + JOURNAL hygiene pass (PROPOSED #12/#29/#30/#33/#34)**
Question: bundle ruff `--fix`+`format` + JOURNAL dedup + NUL-byte strip into one Worker shift?
Options: (a) bundle now; (b) split into separate passes; (c) defer.
Recommendation: (a). All Partial-DoD-eligible, ~1 slot.
Impact: closes five aging PROPOSED items.
Quick answer hint: answer with: a / b / c

---

**Top 3 urgent-gating:** S1 (lock clear), S4 (Windows ETA), S11 (bulk-ratify spec answers).
**Unlocks planner full M5+/Phase 4+ pull capacity:** yes — once S1+S11 land, every (a)-half is committable and the Phase 4 ladder runs on autopilot through Linux-shipped state. Phase 4 promotion to `[done]` still gates on S4.
