# Evidence-driven overnight game loop

Use this pattern when a user asks an agent to keep deepening an H5/Canvas mini-game unattended while the official WeChat/Douyin Developer Tool is already open.

## Task admission gate

A loop task is real only when its origin is one of:

1. A design-vs-code gap backed by a file and acceptance criterion.
2. A failing test/build/package/runtime gate.
3. A defect visible in an official Developer Tool/device capture.
4. An explicit pending item in the current progress report whose dependencies are already complete.

Do not admit heartbeats, repeated test-only runs, dry-runs, task-pack/context-pack generation, speculative refactors, placeholder assets, or documentation-only churn as game-development outcomes.

## Loop contract

Each tick completes one bounded vertical slice:

1. Read branch, clean/dirty status, recent commits, authoritative design and progress docs.
2. Re-evaluate the queue from current evidence; skip tasks already completed by newer commits.
3. State why the selected task is the highest-value reachable gap.
4. Add a failing behavioral or artifact test first.
5. Implement the smallest production path, including custom-bundler ordering/scope and platform asset copy when relevant.
6. Run targeted tests, canonical full tests, target build, strict package check, and package-byte measurement.
7. For visual/runtime work, use the already-open official tool; do not reopen, close, or switch the project. Capture a baseline before edits and the same state after edits.
8. Update the progress report with actual command output and remaining reachability gaps.
9. Commit and push only a green, reviewed slice; verify local HEAD equals remote HEAD and the tree is clean.
10. Report task origin, files, tests, screenshot evidence, SHA, push status and next highest-priority gap.

Use a finite repeat count or explicit stop condition. Fresh cron sessions need a self-contained prompt, fixed workdir, forbidden scope, canonical commands and a no-recursive-scheduling rule.

## Official-tool evidence

A unit suite proves logic, not visual completion. For each visual slice capture:

- before state;
- interaction/start gate used to reach the state;
- after state at the same device preset;
- representative intermediate state when motion is involved;
- console/runtime blockers if visible.

If the normal desktop driver returns no accessible windows, use a second deterministic Windows capture path (window enumeration plus PrintWindow/BitBlt or the project capture helper) rather than claiming the tool is unavailable. Verify click effects by recapturing; a sent click is not evidence that the UI changed.

## Visible loop status

After launch and on request, show a compact table:

| Field | Evidence |
|---|---|
| job/run id | scheduler handle |
| cycle | completed / total |
| current/last task | explicit gap and source |
| commit | actual SHA or `not committed` |
| tests | canonical pass/fail counts |
| simulator | captured state or not yet verified |
| next task | highest-priority remaining gap |

A scheduler status of `ok` is not sufficient. Confirm that the repository gained the expected verified commit/artifact and that it was pushed.

## Game-specific guardrails

- One game only unless the user explicitly expands scope.
- No permanent button accumulation; actions remain round/context specific.
- Preserve the dominant play surface.
- Full-screen UI handoff images remain references, not runtime backgrounds.
- A fixed CCTV viewport remains fixed when the user asks the image to fit it.
- Do not count bundle inclusion as runtime reachability or player-visible completion.
- Keep a safety margin below platform package limits; every new asset batch includes byte accounting.
