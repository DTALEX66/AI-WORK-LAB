# Mini-game Event-Chain and Package-Gate Reference

Use this reference for a full-stack Canvas mini-game pass where content, scheduler, runtime, renderer, generated bundles and platform packaging can drift independently.

## Boundary matrix

| Boundary | Required evidence | Typical false positive |
|---|---|---|
| Content → scheduler | every chain step resolves to a normal/anomaly record; round type and visual state survive installation | JSON is valid but an ID is unresolved |
| Scheduler → runtime | installing a shift also creates a pending inspection with ID/kind/title/duration | `currentShift` exists but previous inspection is already resolved |
| Renderer → runtime | visible buttons carry `decision` metadata and click dispatch reaches the semantic decision branch | quick buttons are sent to legacy `performAction()` as unknown IDs |
| Teaching → event chain | post-teaching transition installs step zero without advancing it | handoff calls advance before first chain step and skips the opening event |
| Decision → chain | correct/wrong outcome advances exactly one step; wrong flags and consequences persist | engine tests pass but Canvas path never calls the advance function |
| Consequence → next shift | modifier is consumed at the next install, produces an observable state change, and is cleared | modifier is copied through state but never changes gameplay |
| Chain → debrief | ending selector reads `eventChainFlags`; modifiers are separate debrief data | ending selector reads `nextShiftModifiers` and misses chain endings |
| State → timeline | decision, chain and contamination entries have a shared monotonic sequence | each subsystem starts its own sequence at 1 |
| Source → bundle | both target bundles are rebuilt after source changes and include the current runtime path | source WIP is green while tracked bundle still contains HEAD code |

## Minimal runtime probe

For a real chain, exercise this sequence rather than only calling pure engine tests:

1. Create a fresh state and schedule the teaching baseline.
2. Complete the third teaching decision.
3. Assert `tutorialStep === 4` and the first event-chain shift is now `inspection.status === 'pending'`.
4. Click the visible quick/identity/classification/high-risk control through the runtime callback.
5. Assert the decision was recorded, the chain advanced once, and the next shift is pending.
6. Repeat for wrong and correct outcomes; assert flags, contamination and modifiers.
7. Finish the chain and create debrief; assert every stage appears in the timeline and the expected ending is selected.
8. Run the same check against the rebuilt WeChat/Douyin IIFE with a host Canvas/API mock when possible.

## Package measurement

Measure each generated target with a file walk:

```text
TOTAL = every file under target/
MAIN = TOTAL - files under declared subpackage roots/
SUBPACKAGE = files under declared subpackage roots/
LEGACY = known stale output directories that should be absent
```

Keep the visual manifest path identical to the copied directory when using a native `game.json` subpackage root. Report both compressed file bytes and, when memory is relevant, decoded RGBA cost (`width × height × 4` per image). A total under a platform cap does not prove the main-package cap; a main package under cap does not prove release readiness.

## Configuration authority

Use a safe development fallback (`touristappid` or equivalent) only for fresh clones and local checks. The release gate must reject fallback/placeholder AppIDs and ad-unit IDs. When a private release overlay is present:

- inject the target AppID into the generated public project config if the Developer Tool reads that file;
- generate private project config only as a local ignored convenience;
- test both fallback and configured paths;
- never commit credentials or private ad-unit values;
- re-read the generated config after build before claiming release readiness.

## Failure taxonomy

- **Targeted green, full red:** update stale exact-count/state-shape tests, then rerun the full command.
- **Strict checker green, release check red:** runtime package is structurally valid but credentials/configuration are not publish-ready.
- **Total package green, main package red:** move the large asset family into a real subpackage; do not merely report the total.
- **Source green, bundle stale:** rebuild target outputs and compare bundle markers or runtime smoke against source.
- **Static screenshot green, asset proof missing:** verify image load success and state-to-state visual difference; a procedural fallback can make every screenshot look valid.
- **Automated acceptance green, tool/device unverified:** label official Developer Tool or real-device evidence as pending; never convert H5 screenshots into platform evidence.
