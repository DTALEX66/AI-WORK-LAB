# Full-Stack Game Vertical-Slice Recovery

Use this reference when a user asks to continue or fully advance both frontend and backend of a Canvas/mini-game project.

## 1. Contract

“全量推进 / 全部执行 / 继续” means:

- inspect the current repository rather than trusting prior summaries;
- choose the next real gap from code, content, runtime reachability, or a failing gate;
- implement and verify a vertical slice;
- continue through all runnable gates before reporting completion.

Never substitute a plan, a partial targeted test, a tool-quota explanation, or a status summary for execution.

## 2. Boundary and baseline

1. Load the game-production, UI-audit, debugging, and Git workflow skills that apply.
2. Confirm project path, branch, `git status --short --branch`, `git log`, and remotes.
3. Preserve unrelated dirty files and private platform config.
4. Read project context/design/next-task docs and inspect the current source of truth.
5. Create a task list with one active work item and explicit gates.

## 3. Data-to-screen reachability audit

Follow a representative action through this chain:

```text
content pack
  → state factory / persistence snapshot
  → scheduler or event-chain engine
  → platform runtime handler
  → renderer state mapping
  → Canvas draw and touch hit region
  → audio/haptic feedback
  → generated platform bundle
```

For each link, record a concrete file/function and a test or runtime probe. A manifest entry or export is not integration proof.

High-value checks:

- Every quick/normal/anomaly decision that can advance a chain calls the chain advancement wrapper before selecting the next shift.
- Wrapper state spreads the engine's updated progress before adding derived view fields.
- Debrief readers consume the same canonical history path the writer updates.
- Resource fields that affect decisions (power, contamination, stability) are visible in the live feedback surface.
- Compact visual controls expose separate `visual` and `hit` rectangles; convert design coordinates to CSS pixels before approving mobile targets.
- Overlay dismissal is bounded to the rendered close button, not the entire screen.
- Camera, tool, protocol, identity, classification, and high-risk interactions use semantic cue profiles.

## 4. Visual acceptance after a mood complaint

When the user says the game is ugly, flat, or has no atmosphere:

1. Acknowledge the composition defect before discussing tests or package size.
2. Compare the actual screenshot to the intended art direction.
3. Distinguish:
   - asset registered;
   - asset loaded;
   - asset drawn;
   - asset composed as a living surface.
4. Inspect render order and clipping. For CCTV, verify the scene is followed by CRT frame, scanlines, vignette, sweep/noise/glitch, threat treatment, and runtime monitoring HUD.
5. Use the same pausable frame clock for animated effects.
6. Ensure state changes alter both scene/treatment and feedback cadence; a static state-image swap is not animation proof.
7. Keep runtime labels dynamic and never bake answers, floors, timecodes, or decisions into source artwork.
8. Re-capture the same viewport before and after; inspect the CCTV region and the complete composition manually.

## 5. RED → GREEN sequence

For each gap:

1. Add a focused regression that fails against the current implementation.
2. Run only that test and preserve the RED evidence.
3. Make the smallest implementation change.
4. Run the focused test until GREEN.
5. Run the related subsystem tests.
6. Continue to the next independent gap instead of stopping after one fix.

Avoid broad fuzzy test edits that accidentally remove an existing test wrapper. After modifying a test file, read the affected region and run the file immediately.

## 6. Final gates

Do not call the task complete until all applicable outputs are real:

```text
npm test
npm run douyin:build
npm run douyin:check
git diff --check
```

Then:

- regenerate the documented screenshot set;
- inspect screenshots at the target portrait sizes;
- stage only intended files;
- commit with a semantic message;
- push the current branch;
- read back local `git rev-parse HEAD` and remote `git ls-remote`;
- verify `git status --short` is clean.

If any gate remains unrun because of a hard blocker, report the exact blocker and do not claim full completion.

## 7. User-specific behavior

This user expects direct Chinese communication, real execution, and timely progress checkpoints. Repeated “继续” or “全量推进” is not permission to reset to analysis. When a prior visual pass was rejected, do not defend it with test counts; fix the root composition and then continue the remaining backend/platform work. Keep session-specific paths, screenshots, and exact task findings in this reference or project evidence docs rather than bloating durable memory.
