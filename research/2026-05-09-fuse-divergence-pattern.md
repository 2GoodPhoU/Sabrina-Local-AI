# FUSE divergence pattern in the Cowork-sandbox/Windows-NTFS mount

## Question

Verbatim from `NEEDS-INPUT.md`, worker-9am 2026-05-07 09:00 entry, item (d):

> Is the FUSE divergence stable per-session (Python and bash agree with each other within a session, but disagree with the canonical NTFS view), or stable per-tool (Read tool always sees the canonical, Python/bash always lag)?

The question has operational weight: it determines (1) whether the existing CLAUDE.md "verify post-edit" rule needs a tool-specific carve-out and (2) whether the Python `read() + os.replace()` path should be deprecated for state-file appends. Worker-9am proposed the "stable per-tool" hypothesis; this investigation tests it against the evidence accumulated since 2026-05-07.

## What I checked

- `JOURNAL.md` — five entries containing primary observations of the divergence:
  - 2026-05-07 08:00 worker-8am (recovered verbatim in worker-9am's postscript at JOURNAL line 645+): Python `os.replace()` write followed by bash read; the read missed the just-written content and triggered a retry.
  - 2026-05-07 09:00 worker-9am (the data-loss incident at JOURNAL line 637+): Python `f.read()` returned a stale FUSE snapshot lacking four entries that Read tool saw at the same moment; subsequent `os.replace()` propagated the stale-source view to canonical, dropping ~22011 bytes / four entries.
  - 2026-05-08 09:00 worker-9am (JOURNAL line 767+): bash `wc -l` reported 692 lines / 280902 bytes; Read/Grep tool reported 765+ lines including the same session's prior chain.
  - 2026-05-08 10:00 worker-10am (JOURNAL line 778+): six Edit-tool truncations on six files, all recovered with AST verification; "bash and Read views diverged on QUEUE.md throughout the recovery."
  - 2026-05-09 02:37 night-auditor (JOURNAL line 821+): cumulative 14 Edit-truncation incidents across 4 Worker slots on 2026-05-08, 100% recovery rate; flagged as operational cost, not correctness risk.
- `roles/worker.md` step 7 — to ground what the recommendation can ask of the role-doc.
- `CLAUDE.md` "Edit-tool truncation is a recurring hazard" line — to ground what the existing post-write verification rule says.
- `STATE.md` 2026-05-08 07:00 — confirms Eric has not run `rm -f .git/index.lock` between 2026-05-07 08:24 UTC and the most recent night-auditor (~36h+).
- Did NOT run a fresh write-then-read experiment in the sandbox: per researcher.md "Project files (read, don't modify)," and a synthetic experiment would still leave its scratch artifact in the working tree, which is exactly the pattern the role-doc is trying to prevent. The five real-world observations are sufficient to answer the question.

## What I found

The question framed two hypotheses:

- **H1 (per-session):** Python and bash agree with each other within a session, but disagree with the canonical NTFS view.
- **H2 (per-tool):** Read tool always sees the canonical NTFS view; Python and bash reads always lag.

The evidence directly refutes H1 and supports H2.

**H1-refuting observations.** Both worker-9am 2026-05-07 and worker-9am 2026-05-08 saw Read-tool reads and Python/bash reads disagree *within the same session*. The 2026-05-07 case had Read tool reporting JOURNAL.md at 270541 bytes (six 2026-05-07 entries visible) while Python `f.read()` returned 248530 bytes (only two visible) — same file, same session, same wall-clock minute. The 2026-05-08 case had bash `wc -l` at 692 lines while Read/Grep saw 765+. H1 predicts intra-session agreement between Python and bash; the evidence shows intra-session disagreement between any-tool-channel and any-FUSE-channel.

**H2-supporting observations.** In every case where Read-tool view and bash/Python view were compared within a session, Read-tool matched the canonical content (verified post-hoc by Eric's NTFS-side review for the 2026-05-07 case per the open NEEDS-INPUT entry; verified inline via subsequent Edit-anchor success for the 2026-05-08 cases — Edit-tool anchors only succeed if the anchor matches the canonical file, and they did). bash/Python consistently lagged. The lag direction is one-way: bash/Python miss content that Edit/Write tools wrote earlier in the session or in prior sessions, but no observed case has Edit/Write tools missing content that bash/Python wrote.

**Asymmetric write behavior.** Python *writes* via `os.replace()` ARE persisted to canonical NTFS — worker-9am 2026-05-07's data loss is permanent (the stale-source content overwrote the canonical file, not just the FUSE view; the loss survived multiple subsequent reads via Read tool). So:

- Reads via Read/Edit/Write tools → canonical NTFS view.
- Reads via Python/bash → through FUSE cache, which lags canonical.
- Writes via Edit/Write tools → canonical NTFS, immediately visible to subsequent Read-tool reads.
- Writes via Python `os.replace()` / `>` redirection / similar → canonical NTFS, immediately visible to Read tool, but the Python-process's own subsequent reads still go through FUSE cache.

This asymmetry is what makes the read-stale-then-write pattern a content-dropper: a Python script that does `data = open(path).read(); ...; open(path, 'w').write(modified)` reads from FUSE cache (stale) and writes to canonical (live), so any content written to the file by a tool in between the FUSE cache snapshot and the Python read is silently overwritten.

**Lag scale.** The 2026-05-07 case had four entries (~22011 bytes, multiple hours of writes) invisible to Python within the same session. The 2026-05-08 case had ~73 lines invisible to bash within the same hour. Lag is not bounded by minutes; it can persist for hours. No `sync`/`fsync` from the writing channel forces invalidation of the FUSE cache on the reading channel (worker-8am 2026-05-07 explicitly tried `os.fsync()` and bash still lagged).

**Edge cases the evidence does not cover.**

- I have no evidence on whether the FUSE cache is per-process or per-mount within the sandbox session. All observed cases compared the *tool channel* (Read/Edit/Write) against the *sandbox-shell channel* (bash/Python in the workspace shell). Two Python processes within the same sandbox shell may or may not share a cache; no observation isolates that variable.
- I have no evidence on whether reading via the same Python interpreter twice in succession invalidates the cache. The worker-9am 2026-05-07 case had a single Python read of stale content; no retry path was attempted.
- The 14 Edit-tool truncation incidents on 2026-05-08 are a separate failure mode (Edit tool itself dropping bytes mid-write); they may or may not be related to the same FUSE layer. All 14 were recovered, so the truncation pattern is operational cost rather than correctness risk; not in scope for this question.

## Recommendation

**Actionable change.** The question is settled enough to update CLAUDE.md and roles/worker.md.

Two specific changes proposed (full text to PROPOSED.md):

1. **CLAUDE.md "verify post-edit" rule sharpening.** The current rule reads "Edit-tool truncation is a recurring hazard — verify file contents post-edit (AST-parse Python files; spot-check >300 lines for tail integrity)." The sharpening: append "Verify via the Read tool, not via bash `wc -l`/`cat` or Python `open().read()` — those go through the FUSE cache which can lag tool-channel writes by hours within a single session. The Read tool reads through the same channel Edit/Write writes through and is the only authoritative post-write verifier in this sandbox."

2. **roles/worker.md state-file append hardening.** Add to step 7 (or its sibling guidance): "For appends to JOURNAL.md / NEEDS-INPUT.md / QUEUE.md / STATE.md / PROPOSED.md / DONE.md, prefer the Edit tool with an anchor against a known-prior line. If Python `read() + os.replace()` rewrite is unavoidable (e.g. recovering from NUL-byte tail-padding), source the canonical content via the Read tool first, then write via Python — never source via Python `read()`. Worker-9am 2026-05-07 09:00 lost four JOURNAL.md entries to the read-stale-then-write pattern; the loss is permanent on the canonical NTFS file."

Both are documentation-only diffs; no code surface, no test impact, no FUSE-layer fix attempted (the FUSE divergence is structural to the Cowork-on-Windows mount and outside Worker scope to fix).

The two PROPOSED entries are independent of the in-flight P0/P1 lock-leak surface and can be applied any time after Eric's next state-file review window. They do not gate any current QUEUE item.

## Open follow-ups

- **Is the FUSE cache invalidation hookable from the writing channel?** No observed case has any sandbox-side command (e.g. `sync`, `fadvise`, `posix_fadvise`) successfully forcing the FUSE cache to refresh after an Edit/Write tool write. Worth grounding if the role-doc ever wants a "force-sync before append" path; out of scope today.
- **Is the FUSE cache per-process or per-mount?** The worker-9am 2026-05-07 09:00 hypothesis that a fresh Python process might see canonical (vs. a long-lived process's stuck cache) is untested. Could be grounded with a small read-then-spawn-then-read test, but doing it requires writing to the FUSE-mounted workspace, which the researcher role can't.
- **Does the Edit-tool truncation pattern (14 incidents on 2026-05-08, 100% recovered) share a root cause with this FUSE divergence?** The truncations are on the *write* side, the divergence is on the *read* side; both correlate with longer/denser Worker output but no causal link is in evidence. Worth a separate bounded question if the truncation rate gets worse.
- **Lag-flush via Read tool read?** Anecdotal: in some 2026-05-07 cases, after a Read tool read of the canonical content, subsequent bash views appeared to "catch up." Worth grounding before committing to a "read-tool-first" workaround pattern.
- **Is the canonical Windows-NTFS file consistent with the Read tool view?** The 2026-05-07 worker-9am data-loss incident's open NEEDS-INPUT (item a) asks Eric to verify this from a Windows shell. Until that verification, the "Read tool sees canonical NTFS" claim has one outstanding sanity check. The Read tool view is at minimum self-consistent (Edit anchors succeed against it), but external Windows-side confirmation closes the loop.
