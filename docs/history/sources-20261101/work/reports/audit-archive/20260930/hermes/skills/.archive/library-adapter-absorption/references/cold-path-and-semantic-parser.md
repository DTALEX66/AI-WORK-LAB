# Cold-path and semantic-parser patterns

## Lazy import regression probe

A service may expose heavy dependencies as module-level `None` values and populate them through a lazy initializer. The first intake request can hide missing initialization in later command handlers. Test each public path from a fresh process/module state, especially:

- approval/promotion;
- learning/card projection;
- practice/mastery recording;
- audit/retry/replay.

The durable fix is to call the initializer at the beginning of every handler that dereferences a lazy seam. Do not initialize only in a neighboring intake handler, and do not “fix” the test by ordering intake first.

## Markdown checklist parsing

For simple checklist syntax, prefer line-oriented parsing:

1. `strip()` each line;
2. require `-` or `*` as the marker;
3. inspect the task token (`[ ]`, `[x]`, `[X]`);
4. extract the remaining text;
5. report unsupported or malformed forms as loss when the contract requires it.

This avoids double-escaped `\\s` / bracket patterns in Windows editing layers while keeping the semantic contract obvious. Verify with both unchecked and checked examples, plus no-write and path-containment tests.

## Evidence rule

A local green test is not delivery evidence by itself. For repository work, bind evidence to the candidate head SHA, then separately verify PR exact-head CI, merge SHA, and main CI. Canceled stale runs and Node runtime deprecation annotations are not implementation conclusions; inspect final run status, conclusion, jobs, and logs.
