---
name: python-testing
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/python-testing/SKILL.md
---

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
- **`patch` `old_string` must be UNIQUE.** Test files repeat near-identical blocks; a short `old_string` lands on the FIRST match and silently corrupts a sibling test. Read the region, include the test-method name, re-read after patching (see §21).
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

## Verification Checklist

- [ ] Ran with `env -u PYTHONPATH uv run --frozen --group ci --group ci-adapters pytest` (or mirrored the workflow's full group set)
- [ ] Assertions check field values / observed behavior, not just presence or "no exception"
- [ ] Any `patch` to a test file used a unique `old_string` and was re-read after applying
- [ ] New custom CLI options registered via `pytest_addoption` before `skipif`/`getoption` reference them
