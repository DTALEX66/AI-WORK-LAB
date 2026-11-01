# Settlement, rewarded-ad, and generated-artifact review probes

Use these checks when reviewing staged H5/Canvas mini-game changes.

## 1. Review the staged snapshot, not the live worktree

Concurrent edits can appear after review starts. Treat `git diff --cached` and `git show :path/to/file` as authoritative. For executable verification, materialize the index into a temporary directory with `git checkout-index --all --prefix=<temp>/` and run tests/builds there. Do not run mutating build scripts in the source repository during a read-only review.

On Windows Git-Bash, native Git may interpret `/tmp/...` as `<drive>:/tmp/...`, while shell redirection may resolve it to `%LOCALAPPDATA%/Temp/...`. Prefer an explicit MSYS path such as `/d/tmp/review-index-...` or convert paths with `cygpath` before comparing files.

## 2. Terminal-result precedence probe

A healthy countdown test is insufficient. Exercise simultaneous terminal conditions:

- countdown reaches zero in the same tick as power/stability/passenger failure;
- success must not be followed by an unconditional failure classifier that overwrites `result`;
- `gameOver`, `result`, terminal log type, audio, analytics reason, and settlement CTA must agree.

Prefer one explicit precedence rule: return immediately after success, or make the failure checker preserve an existing terminal result.

## 3. Rewarded-ad callback matrix

For every platform wrapper (not only the Canvas runtime), test each attempt as a one-shot state machine:

- completed close twice → one reward;
- error twice → one error settlement;
- error then completed close → no contradictory second settlement;
- rejected show, rejected load, and retry close;
- incomplete close → no reward;
- two sequential legitimate attempts → at most one reward per attempt;
- two overlapping `show()` calls → callbacks cannot settle the wrong attempt;
- stale completion after restart/new run → must not mutate the new run.

Fail-closed means release mode grants only from a completed-close event. It does not by itself guarantee callback idempotency.

### Durable attempt isolation pattern

Do not let SDK event handlers settle a mutable global `attempt`. A delayed callback from attempt A can arrive after attempt B starts and accidentally settle B. Use all three layers:

1. **Immutable attempt closure:** create/register handlers per legitimate attempt; each handler closes over its own `{ id, context, settled, ad }` object and calls `settle(thatAttempt, ...)`.
2. **Lifecycle cleanup:** after terminal settlement, unregister `onClose`/`onError` handlers when the SDK supports `offClose`/`offError`, then destroy the ad instance when supported. Keep the attempt object's `settled` flag as the final defense because queued callbacks can still run.
3. **Runtime generation guard:** pass `{ runToken }` into `show(context)`, increment the token on restart, return it in reward metadata, and reject rewards whose token differs from the current run. Also validate action applicability at callback time: revive requires an active failure, decode requires a playing run with locked content, and truth requires the matching fake-ending state.

A wrapper that merely stores `attempt = { ... }` in shared mutable state is insufficient: an old handler may read the newer object. Tests must retain the first attempt's handler, start a second attempt, then invoke the retained old handler and prove it cannot reward or error-settle the second attempt.

## 4. Success settlement and decode gates

Check both rendering and hit testing:

- success draws no revive CTA;
- success hitboxes cannot invoke revive even if an invisible/stale button exists;
- asynchronous ad rewards validate that the originating run/action is still current;
- Canvas hidden-log decode calls the action only from the rewarded callback, never before `show()` completes.

## 5. Cross-run fake-ending state

Verify a full sequence, not only a copy helper:

1. Fail enough runs to reach the threshold through the real restart path.
2. Preserve consecutive-failure/cooldown counters across failed restarts.
3. Clear per-run trigger/unlock/display state on restart.
4. Complete a successful run.
5. Restart and prove counters are reset.

## 6. Portrait clipping review

Regex tests that merely find `100dvh` and `overflow:hidden` are not layout evidence. Test real computed geometry/screenshots for short portrait sizes, safe-area insets, and enlarged fonts. A `minmax(0, 1fr)` monitor row inside a fixed-height, overflow-hidden shell can collapse to zero when auto-sized controls consume the viewport. Provide a short-height breakpoint, minimum playable monitor size, or internal-scroll fallback.

## 7. Generated-source synchronization

Regenerate from the staged snapshot in a temporary directory and byte-compare normalized outputs with staged artifacts. Compare line endings consistently. Cover every tracked generated target (for example WeChat bundle, Android WebView bundle, and copied CSS), not just source-level tests.

## 8. Handoff-document claims

Separate verified facts from estimates. Completion percentages, “all devices fit,” “true-device ready,” and “tests were written failing first” require evidence; otherwise label them as estimates or unverified. Test-count success does not prove visual layout, callback ordering, or commercial ad integration.