# Evidence-driven autonomous game iteration

Use this workflow for unattended or “continue the next step” development of an H5/Canvas mini-game.

## Iteration contract

1. Inspect live repository state, current progress report, generated bundles, tests, and—when available—the official simulator/runtime frame.
2. Select exactly one concrete player-facing gap. Valid evidence includes a reachable-but-broken interaction, unwired content, failing test, simulator-visible defect, missing audio/haptic state, or package/runtime gate risk.
3. State the gap and acceptance criteria before editing. Never invent work to fill a round count.
4. Use TDD for logic and runtime routing: produce a meaningful RED failure, implement the smallest complete vertical slice, then run targeted tests.
5. Run full tests plus platform build/strict checks. For visual changes, capture official simulator/device evidence when available; if unavailable, say so and use executable renderer screenshots only as secondary evidence.
6. Commit one coherent slice, push it, and verify local/remote SHA equality. A loop iteration is not complete until this evidence exists.
7. Stop rather than generate heartbeat, placeholder docs, repeat-only tests, or speculative features when no real gap remains.

## Canvas/gameplay rules

- Trace content all the way through data → scheduler/state → runtime handler → renderer/hitbox → feedback → debrief. “Present in JSON” or “included in bundle” does not mean reachable gameplay.
- Dynamic round actions must settle through domain APIs; never let contextual actions silently fall into generic movement/action handlers.
- Investigation tools reveal evidence, not direct answers. Identity verification should reveal identity evidence and stay in identity mode until the player decides.
- Keep drawing rectangles and click hitboxes derived from the same layout function.
- Reuse semantic local audio cues and haptic strength before adding large media; verify package budget after each change.

## Generated project configuration pitfall

Do not manually fix only a generated platform project file. Find the build source that rewrites it. If a developer tool reads the main project config, ensure local ignored release configuration populates both the main generated config and any private config; retain a safe tourist/placeholder fallback for CI and clean clones. Add a regression test proving the release AppID reaches the exact file the developer tool consumes.

## Verification checklist

- Targeted RED→GREEN tests
- Full test suite
- Platform build and strict checker
- Package size/headroom
- Generated bundle/runtime smoke test
- Official simulator/device screenshot for visual changes when available
- Clean worktree
- Local and remote commit SHA match
