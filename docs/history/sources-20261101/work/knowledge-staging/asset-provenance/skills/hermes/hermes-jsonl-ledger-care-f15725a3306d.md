---
name: hermes-jsonl-ledger-care
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/hermes-jsonl-ledger-care/SKILL.md
---

---
name: hermes-jsonl-ledger-care
description: "避免 write_file 覆盖 JSONL/活动账本；追加语法、恢复模式和 Python venv 发现"
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [jsonl, ledger, append, write-file, activity-log, autonomous-loop]
    related_skills: [sleep-mode, agent-workflow-fortress, project-data-boundary]
---

# Hermes JSONL / Ledger Care

当写入 JSONL 活动日志、结果账本、事件流或追加式日志时加载。

## Core rule

**Never use `write_file` to add a line to an existing JSONL or log file.** `write_file` overwrites the entire file — it does not append. This destroys every prior entry.

## Correct append patterns

### Via terminal (preferred for simple single-line entries)

```bash
cat >> .hermes/sleep-mode/activity.jsonl << 'EOF'
{"event":"cycle_done","mode":"active","head":"abc123","at":"ISO-8601"}
EOF
```

All entries are preserved; run N times → N lines.

### Computed entries: append from a project-local script

Do **not** implement computed append as `read_file` → rebuild → `write_file`, and do not use `execute_code` for project ledger I/O. Both patterns can resolve the wrong working directory or silently replace history when a deduplicated/partial read is mistaken for full content.

Instead, write a short ignored project-local Python script that opens the ledger directly in append mode (`open(path, "a", encoding="utf-8")`), run it through the project-data wrapper, and parse the final line afterward. The complete pattern is in **Append via temp script** below.

## Recovery after accidental overwrite

If `write_file` already destroyed prior JSONL entries:

1. Check `state.json` `last_evidence` for the previous cycle's summary to reconstruct the most recent entry.
2. Check terminal scrollback for prior command output if still available.
3. Reconstruct lost entries from in-memory state or session context captured earlier in the conversation — e.g. the `read_file` output from earlier tool calls still in agent context. Use those verbatim JSON strings.
4. **Safe reconstruction with verification (preferred):** Write ALL reconstructed + new entries to a `.tmp` file first, so a mistake does not destroy the (already corrupted) real file:
   ```bash
   cat > .hermes/sleep-mode/activity.jsonl.tmp << 'EOF'
   {first entry}
   {second entry}
   ...
   {new entry}
   EOF
   wc -l .hermes/sleep-mode/activity.jsonl.tmp   # verify expected count
   mv .hermes/sleep-mode/activity.jsonl.tmp .hermes/sleep-mode/activity.jsonl
   python -c "import json; lines=open('.hermes/sleep-mode/activity.jsonl').readlines(); print(f'{len(lines)} events, last task: {json.loads(lines[-1])[\"task\"]}')"
   ```
   The `.tmp` → `mv` pattern is safe because `mv` is atomic on the same filesystem — even if the agent is killed mid-command, only the `.tmp` file is lost, not the target.
5. If the agent cannot reconstruct prior entries from its own context (conversation compressed, entries too old), loss is permanent — accept the gap rather than fabricating data.

## Shell-safe append for computed entries

When the new JSON object contains non-ASCII text, Windows paths, quotes, or backslashes, a direct `python -c` string can be rewritten by Git Bash before Python receives it. Do not retry increasingly complex quoting. Serialize the entry with `json.dumps(..., ensure_ascii=False)`, UTF-8 encode it, base64-encode the bytes, and have a short Python command decode and append in binary mode. Verify afterward with a fresh read of the final line and `json.loads`.

This is an append technique, not permission to overwrite the ledger. Preserve every existing line, keep entries redacted, and record the command failure as a failure only when the append did not occur. See `references/windows-git-bash-jsonl-append.md` for the reproducible Windows/Git Bash recipe and readback checklist.

## Append via temp script (preferred under project-data-boundary)

When `hermes-project-data.py` wrapper is active (true for sleep-mode cron cycles), shell chaining and here-docs are blocked:

```bash
# ❌ These are BLOCKED by the wrapper:
cat >> ledger.jsonl << 'EOF' ... EOF     # here-doc blocked
cmd1 && cmd2                              # shell chaining blocked
cmd1 | cmd2                               # pipes blocked
```

The reliable workaround: write a temporary Python script inside `.hermes/sleep-mode/`, then run it through the wrapper.

**Step 1 — Write the script** (via `write_file` tool — safe because this is a script, not the ledger):

```python
# .hermes/sleep-mode/append_entry.py
import json
from pathlib import Path

ENTRY = {
    "event": "cycle_example",
    "mode": "active",
    "head": "abc123",
    "task": "example-task",
    "at": "ISO-8601"
}

LEDGER = Path(".hermes/sleep-mode/activity.jsonl")
with open(LEDGER, "a", encoding="utf-8") as f:
    f.write(json.dumps(ENTRY, ensure_ascii=False) + "\n")

# Verify
with open(LEDGER, "r", encoding="utf-8") as f:
    lines = [l for l in f.readlines() if l.strip()]
last = json.loads(lines[-1])
print(f"appended: {last['event']} | total: {len(lines)}")
```

**Step 2 — Run it** through the data-boundary wrapper (when wrapper is active):

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- .venv/Scripts/python .hermes/sleep-mode/append_entry.py
```

**Step 2b — Run it directly** (when no project-data-boundary wrapper is installed or active):

```bash
cd /path/to/project && python .hermes/sleep-mode/append_entry.py
```

The direct variant works on any platform and avoids the wrapper's shell-blocking entirely. Prefer this when you have a plain terminal with no pre-tool-call hooks blocking shell chaining.

**Step 3 — Clean up** (remove the temp script when done):

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- rm .hermes/sleep-mode/append_entry.py
```

This pattern is preferred on Windows + Git Bash + project-data-boundary because:
- No shell quoting issues — the JSON is a Python dict, not a shell string.
- No `&&`/`>>`/`|` shell chaining needed — a single `run --` command.
- The `.tmp` → `mv` atomic-replace pattern is unnecessary; `"a"` (append mode) is the correct file operation.

## Project venv discovery (companion pattern)

When running project-local commands (`pytest`, `ruff`, etc.) in a cron/loop cycle, the global Hermes Python may not have project dependencies:

1. Check `ls .venv/Scripts/` (Windows) or `ls .venv/bin/` (Linux/macOS).
2. Under a plain terminal (no wrapper): activate and chain: `source .venv/Scripts/activate && python -m pytest ...`
3. **Under project-data-boundary wrapper** (sleep-mode cron cycles): shell chaining (`&&`) is blocked. Use the venv's Python directly:
   ```bash
   python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- .venv/Scripts/python -m pytest tests/
   ```
4. If no `.venv` exists, check `pyproject.toml` or `setup.py` for tool config and fall back to system `python3` if available.

## Structured JSON ledgers with summary counts (error-ledger pattern)

For a single-document JSON ledger that carries a `summary` with counts (e.g.
WORK-LAB `50-taskpacks/error-ledger.json` with `summary.total` +
`summary.by_classification`), appending an entry is NOT just pushing to the
list — the summary must stay consistent or a verify gate fails:

1. Read the file once (via a Python script, not `write_file` — full rewrite
   destroys formatting and invites drift).
2. Append the new entry object; then update `summary.total = len(errors)` and
   increment the matching `by_classification` bucket for the entry's
   `classification` value.
3. Update the generated-at timestamp if the schema has one.
4. Write back atomically (`Path.replace()`, not `rename()` on Windows — see
   the rename pitfall below).
5. Run the ledger's verify script afterwards; a green check is the only proof
   the counts are consistent. Do not trust visual inspection.

Field-level contracts a verify script may enforce (WORK-LAB
`scripts/ci/verify_error_ledger.py` — generalize to any ledger with a checker):
- `error_id` pattern (`ERR-[0-9]{3}`), unique across entries.
- enum fields must be valid: `phase`, `evidence_level`, `status_before/after`.
- `exit_code` must be a non-zero int for an original failure entry.
- `command` must contain an executable marker (`python|node|git|assessment|test|verify`) — a bare shell one-liner fails the gate.
- `repeat_prevention` must contain an enforceable token (`must|require|never|每|必须`).
- No credential-like values anywhere (`api[_-]?key`, `Bearer`, `sk-`, `ghp_`, …).
- `summary.total == len(entries)` and `summary.by_classification == Counter(classification)` exactly — a mismatch is a gate failure (WORK-LAB PR #47 failed exactly this way before the ledger was fixed).

## Event-ledger resumability design (recovery-source completeness)

When a JSONL ledger doubles as the RECOVERY source for a resumable worker
(batch import controllers, outbox dispatchers, sleep loops), the ledger
schema must carry enough data to rebuild state — not just audit counts.
Validated 2026-08-14 on a batch-import controller:

- **`tasks_added` events must record the FULL task list, not only
  `count`/`total`.** A ledger that stores only counts lets `from_checkpoint`
  restore `total` but NEVER the pending task ids — the un-finished tasks
  silently vanish from the rehydrated controller, and `total` collapses to
  completed-only (observed 200 → 36). The "interrupted batch is resumable"
  promise is broken without the task ids.
- **Recovery must restore four things from the ledger:** (1) recomputed
  completed/failed counts (count the `task_completed`/`task_failed` events —
  never trust stored summary counters), (2) the terminal state from the
  final `batch_end` event (`finished`/`shutdown` — an interrupted ledger
  with NO `batch_end` stays `idle` = resumable), (3) the pending queue
  (`all_tasks − completed − failed`, re-queued so a resumed run continues
  where it stopped), and (4) `total` from the full task set.
- **Old-ledger compatibility:** entries written before the schema gained the
  task list carry only `total`; fall back to the recorded `total` when the
  task list is absent (recovery of pending ids is then impossible — degrade
  honestly, don't fabricate).
- **Test the recovery path with a mid-run shutdown, not just completion:**
  start N tasks, shut down after a few complete, then assert status readback
  shows the terminal state, `total == N`, `0 < completed < N`, and the
  completed entries' results are intact. A completion-only test never
  exercises the pending-queue restoration.

## Markdown truth logs (LOG-### markers): duplicates accumulate across sessions

Append-only MARKDOWN truth logs (Cognitive-Loop-OS `docs/truth/EXECUTION_STATUS_LOG.md`
uses `### LOG-20260812-1XX — PR #NNN MERGED (...) — PASS` markers) have a
different failure mode than JSONL: appends never lose data, but **the same
event can be logged twice across sessions**, silently corrupting the
uniqueness guarantee of the audit trail. 2026-08-12: the log carried duplicate
entries for the SAME PR — LOG-101 logged #110 twice, and LOG-129 was written
for #129 by two different passes (one labeled "占位清理", one "占位卫生").
A sequence check (`grep -c "### LOG-"` showed 132 entries while the range was
only LOG-004..130) exposed it; dedup removed 17 lines.

- **Before appending a new LOG entry, check the tail and the marker sequence:**
  `grep "### LOG-" <file> | tail -3` — if the PR/event you are about to log
  already has a marker, UPDATE the existing entry or skip; never add a second
  marker with a new number.
- **Verify the number sequence is gap-free AND unique** after appending:
  `grep -oE 'LOG-[0-9]+' <file> | sort | uniq -d` (dupes) and compare count vs
  range. Count > range span = duplicates present.
- When two entries for the same PR disagree (different labels), keep the one
  whose content is accurate and delete the other's block (marker + body,
  bounded by the next blank-line + marker); never leave both.
- The same hazard applies to any numbered append-only ledger (receipt logs,
  delivery logs): uniqueness of the event id is part of the contract — audit
  before append, dedupe when found.

## Pitfalls

- `write_file` is NOT a line-append operation — it replaces the entire file. This is the most common data-loss source in autonomous loop workflows.
- Do not fabricate prior activity entries after overwrite. A gap in the ledger is acceptable; fabricated evidence is not.
- `state.json` uses `write_file` correctly (single object, full rewrite). Only `activity.jsonl` and similar append-only logs are affected.
- **`read_file` dedup returns empty content — silent ledger truncation.** When reading the ledger in `execute_code` via `read_file(path).get("content", "")`, Hermes' read_file dedup optimization returns a status message (`"unchanged"`) instead of file content if the same path was already read earlier in the conversation. The `.get("content", "")` call then returns `""` — the agent treats the file as empty, writes back only the new entry, and silently destroys every prior entry. This is a CRITICAL data-loss vector for autonomous loops that read-then-write in `execute_code`. **Workaround:** (a) Read the file fresh in a terminal command instead, or (b) read the ledger once and cache it in a Python variable, never re-read for the content, or (c) use the temp-script append pattern (`open(LEDGER, "a")`) which bypasses read entirely, or (d) pass `content, _ = json.loads(terminal("cat " + path)["output"])` via terminal. See `references/jsonl-dedup-data-loss.md` for the full failure pattern and all workarounds.
- **Wrapper blocks `cat >>`, heredocs, shell chaining.** Under `project-data-boundary` wrapper (`hermes-project-data.py`), `>>`, `|`, `&&`, `;`, and heredocs (`<< 'EOF'`) are all blocked. The "Via terminal (preferred)" cat >> pattern will fail with `PROJECT DATA BOUNDARY BLOCKED: shell chaining/redirection is forbidden`. Use the temp-script pattern instead (see "Append via temp script" above).
- **Base64 append can be fragile through wrapper on Windows.** The base64 approach works in a plain terminal but can fail with exit code -1 when passed through the wrapper + Git Bash + complex quoting. Prefer the temp-script approach for reliability.
- **`Path.rename()` fails on Windows when target file exists.** When atomically rewriting `state.json` (or any single-object file) via a `.tmp` → rename pattern, Python's `Path.rename()` raises `FileExistsError` on Windows — it only works when the target does not already exist. Use `Path.replace()` instead, which calls `os.replace()` and overwrites the target on all platforms. The safe Windows pattern:
  ```python
  tmp_path.write_text(content, encoding="utf-8")
  json.loads(tmp_path.read_text(encoding="utf-8"))  # verify parseable before replacing
  tmp_path.replace(target_path)  # atomic on same filesystem
  ```
  Git Bash `mv` already handles overwriting correctly; this pitfall only affects Python `pathlib.Path.rename()` calls.
