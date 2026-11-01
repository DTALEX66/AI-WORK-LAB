---
name: python-testing
description: "Python testing patterns, gotchas, and conventions for unittest/pytest."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, python, unittest, pytest, gotchas]
    related_skills: [test-driven-development]
---

# Python Testing Patterns & Gotchas

## When to Use

When writing Python tests with `unittest` or `pytest`.

## Global disciplines

- **Run tests with the CI-parity env and groups.** `env -u PYTHONPATH uv run --frozen --group ci --group ci-adapters pytest` — mirror the workflow's install matrix (see §23), and prefer `python -m pytest` over the bare `pytest` trampoline (see §24).
- **`patch` `old_string` must be UNIQUE.** Test files repeat near-identical blocks; a short `old_string` lands on the FIRST match and silently corrupts a sibling test. Read the region, include the test-method name, re-read after patching (see §21). When an API-shape change touches many similar call sites (e.g. a helper signature refactor across a test file), REWRITE the whole file (write_file) instead of batched regex substitutions — regex rewrites leave partial `**`/stale-argument patterns on the call shapes you did not enumerate, each costing a red round.
- **unittest results are on stderr, not stdout.** When automating a standalone unittest run via `subprocess.run(capture_output=True)` (no pytest involved), the `Ran N tests / OK / FAILED` lines and all failure detail go to `result.stderr` while `stdout` is empty — a green run looks like "no output" if you check the wrong stream. Gate on `returncode == 0 and "OK" in stderr` and read failure text from stderr.
- **Assert behavior, not just "no exception" or hit count.** All-`None` fields and `len(hits)==1` pass silently; assert field values and observed state (see §29, §32).

## Pitfall index

Symptom → one-line cause → full write-up in `references/python-testing-pitfalls.md` (§N).

| Symptom | Cause | Ref |
|---|---|---|
| Lock lists a name with no package stanza / new deps never locked | Phantom PyPI name or never re-ran `uv lock` | §1 |
| Flagging an "unused" dep that's actually used — or "used" that's planned | Framework-internal use or frozen-baseline approval | §2 |
| `assertIn` on a list "not found" | List membership, not substring | §3 |
| Float equality flaky | Use `assertAlmostEqual` | §4 |
| `assertRaises` not catching | Needs context-manager form | §5 |
| Fixture isolation | `setUp`/`setUpClass`/`setUpModule` scoping | §6 |
| Regex "look-behind requires fixed-width" | Variable-width lookbehind | §7 |
| `\s` matching newlines inside `[...]` | Use a literal space | §8 |
| S-V-O extractor swallows "was" into subject | Passive-voice be-verbs | §9 |
| `WindowsPath.is_relative()` missing | Use `relative_to` + `except ValueError` | §10 |
| Monorepo subdir imports / dedup | Hyphen dirs, SQL-free services | §11 |
| `python -m unittest a.b-c.test_x` → `No module named ...` | Hyphenated test dirs are not valid dotted module paths; run the test file directly | §11 |
| Vector-search test ranks wrong doc | Weak anchors in query terms | §12 |
| Green suite hides deprecation defects | Probe `-W error::DeprecationWarning` | §13 |
| Compliance test missed a blocked engine | Hardcoded list vs registry-driven | §14 |
| Lifecycle feature never actually schedules | Hard-coded schedule constants in INSERT | §15 |
| CLI import fails at load | Helper name guessed, not grep'd | §16 |
| Lint findings CI never sees | ruff scope excludes `tests/` | §17 |
| Pipeline hits network on default run | Optional stage not opt-in gated | §18 |
| SQLite test fails on stale rows | Persistent DB + positional assert | §19 |
| `WinError 32` on `TemporaryDirectory` cleanup | Leaked SQLite connection | §20 |
| Patch landed in the wrong test block | Non-unique `old_string` | §21 |
| `NameError: name '_return' not defined` in CI | Blind global `sed -i` helper wrap | §22 |
| "Pre-existing failures" that are actually env drift | Missing dependency group | §23 |
| `uv pip install` says installed but import fails | Installed into the wrong venv | §23.1 |
| `uv trampoline failed to canonicalize script path` | Use `python -m pytest` | §24 |
| Merged on a pre-amend green run | Force-push invalidates old CI | §25 |
| Test job fails at `setup-uv` step | Runner infra, rerun not code | §26 |
| Stage silently skipped forever | `pytest.skip` masking a real bug | §27 |
| `--run-network` silently skips / "unrecognized arguments" | Option not registered in `pytest_addoption` | §28 |
| Aggregator parses providers to all-`None` | One fake per provider's real shape | §29 |
| Zero-coverage modules hiding defects | Grep sweep before feature work | §29.1 |
| Orchestrator with only indirect coverage | Function-level gap check | §29.2 |
| Test package never collected | `testpaths` excludes it | §30 |
| `monkeypatch` AttributeError | Function-local import → patch source | §31 |
| Patch no-op, module still uses real dep | Module-top import → patch consumer | §32 |
| Real DB init during test | Module-level singleton instances | §32.1 |
| Path-scanning test finds 0 files | conftest TMPDIR hidden-root trap | §33 |
| ONNX output flattened to `unknown` | Double-softmax on already-probabilistic output | §34 |
| WIP fixture re-dirties with CRLF/LF | Test opens it in default text mode | §35 |
| Convention gate flags CRLF that's blob-clean | Working-tree vs blob divergence | §36 |
| `isinstance`/`assertIs` on a class or enum loaded via `spec_from_file_location` passes locally, breaks in CI (or vice-versa) | Two copies of the same module hold two distinct class objects | §37 |
| Green run littered with `WinError 10038` thread tracebacks | Teardown closed the socket while the background `serve_forever` thread was still in `select()`; close before join | §38 |
| Client awaiting an error response on an HTTP request that carries a body sometimes gets `ConnectionAbortedError` (WinError 10053) instead of the 4xx | Server sent the error before draining the unread request body → socket reset | §39 |
| A stress/"green" script whose only assertion is `errors == 0` proves nothing | Requests never actually reached the server (e.g. a NameError at connection setup), so the error set is empty — assert the expected status distribution instead | §40 |
| Concurrent fan-out summary order flaps between runs | Output built from `as_completed()` completion order, not input order — derive slots in input order and add a forced-ordering negative control | §41 |

## §37 — Class/enum identity breaks across `spec_from_file_location` module copies

Services loaded with `importlib.util.spec_from_file_location` (no package `__init__`) get re-executed on every load, so the SAME `.py` can hold two distinct class objects — the provider copy and the caller/test copy. Consequences that cost test bugs:

- **`isinstance(obj, MemoryRecord)` fails even when the shape is right** — the record was built from a different module copy than the one `isinstance` was checked against. Fix: duck-type — check the required attribute/shape, not the class.
- **Enum / `assertIs` comparisons fail on the object identity, not the value.** `assertIs(kind, MemoryKind.KNOWLEDGE)` is a different `Enum` member across copies. Compare `.value` (`assertEqual(kind.value, "knowledge")`), never `is`/`isinstance`.
- **Prefer local constants over cross-module class introspection** (e.g. `ExtensionType._MEMBERS`): reach for the same data via a module-local mirror or duck-typed read so a re-loaded copy can't break the gate.

Rule: in any spec-loaded service boundary, write cross-object checks as shape/value tests, not identity tests; if a gate does `isinstance` on a loaded module's class, prove the check still holds when the module is loaded twice.

## §38 — Serve-loop teardown order: `shutdown()` → `thread.join()` → `server_close()`

A background-threaded `HTTPServer` test that only `addCleanup(server.shutdown)` + `addCleanup(server.server_close)` closes the socket while the `serve_forever` thread is still inside `selector.select()` on it. The thread then prints `OSError: [WinError 10038] 在一个非套接字上尝试了一个操作` (or the Linux equivalent) into stderr for every teardown — tests still pass, but the noise masks a later real failure and can trip strict runners. Fix: keep the thread reference, and in ONE cleanup do `server.shutdown(); thread.join(); server.server_close()`. `shutdown()` alone does not join the thread, and `server_close` before join is the race.

## §39 — Drained request body on error responses (deterministic 4xx under load)

When a request handler rejects BEFORE reading the request body (auth guard, routing 404, field validation), the socket still holds the client's unread body bytes; closing it makes the kernel send RST, so the client awaiting the error response gets `ConnectionAbortedError` (WinError 10053) instead of the 4xx payload. This is load- and timing-dependent, so it only surfaces under the full suite or a stress run. Server fix: before writing any error response, drain the unread body up to the declared `Content-Length` (best-effort, bounded chunks). Client/test side: never assert a 4xx over a connection whose request carried a body unless the server is known to drain.

## §40 — Prove a fix against the load that produced it; assert the distribution, not just emptiness

"No errors remain" is a vacuous green when the harness crashed before performing any request (a missing `import`, a NameError at connection setup, a mis-scoped fixture): `errors == []` then proves nothing. Rules:
- Re-run the failing scenario exactly as it failed (same concurrency pattern if the original failure was load-induced), and assert the POSITIVE expected shape — e.g. "N requests of path P all returned code C" (a status-count distribution), not merely "zero exceptions".
- A stress proof of a transport fix must keep in-flight concurrency at or under the server's listen backlog (single-threaded `HTTPServer` default `request_queue_size` is small); a burst that overflows the backlog produces refused connections that are a different bug from the one under test — it creates false positives and false negatives.
- Confirm the requests actually reached the server (assert on response status distribution / server-side observation) before trusting an empty error list.

## §41 — Concurrent dispatch must preserve input order, not completion order

A fan-out that runs N subtasks with `concurrent.futures` and whose result order must match the input order leaks nondeterminism when the summary/list is built by iterating `as_completed()` in completion order: which task finishes first varies with timing, so an output order like `['s2','s1']` vs `['s1','s2']` flaps. Two rules:
- **Derive order from the input, not completion.** Collect each result into a slot keyed by its input index as it completes, then read the slots in input order. `as_completed` is only for *running concurrently*; it must not drive the output ordering.
- **Ship a forced-ordering negative control.** Add a test that deliberately slows one specific task (a bounded sleep on task 0) so completion order is guaranteed to differ from input order, then assert the summary is still input-ordered. Without this, the flake only surfaces under load and the suite is green locally by luck. Re-run the control a handful of times to confirm the ordering is stable, not coincidentally green.

## Verification Checklist

- [ ] Ran with `env -u PYTHONPATH uv run --frozen --group ci --group ci-adapters pytest` (or mirrored the workflow's full group set)
- [ ] Assertions check field values / observed behavior, not just presence or "no exception"
- [ ] Any `patch` to a test file used a unique `old_string` and was re-read after applying
- [ ] New custom CLI options registered via `pytest_addoption` before `skipif`/`getoption` reference them
