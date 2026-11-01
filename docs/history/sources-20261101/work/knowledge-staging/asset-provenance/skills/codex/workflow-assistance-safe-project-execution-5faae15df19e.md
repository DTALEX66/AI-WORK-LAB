---
name: workflow-assistance-safe-project-execution
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-safe-project-execution/SKILL.md
---

---
name: workflow-assistance-safe-project-execution
description: "Use for any coding or project task that needs bounded scope, preserved user work, real execution, and honest completion evidence."
---

# Safe project execution

1. Resolve the Git root, branch, HEAD, applicable `AGENTS.md`, dirty paths, and owning module before edits.
2. Classify dirty paths as task-owned or unknown. Preserve unknown work and stop before overlapping writes.
3. Inspect relevant files, definitions, usages, manifests, and neighboring conventions before designing the change.
4. Keep one writer per checkout. Use an isolated worktree for a parallel writer.
5. Make the smallest coherent change. Do not refactor unrelated code or fabricate APIs and dependencies.
6. Run targeted checks, then the repository's canonical gate when available.
7. Inspect the final diff and status. Separate local verification from CI, publication, and live readback.
8. Do not commit, push, publish, or change global configuration without explicit authorization for that side effect.

If a prerequisite or required check cannot run, report `BLOCKED` or `NOT EXECUTED`; never substitute plausible output.

## Risk-tiered operating model

Classify every action before running it:

1. **Read-only inspection** — Git status/history, source search, version checks,
   logs, port diagnostics: low-friction where the command has no write side
   effects (still requires an explicit Git-project workdir).
2. **Write-capable task execution** — tests, builds, downloads, installs, code
   generation, caches, logs, browser artifacts, reviews, temporary scripts:
   scope temporary/cache/output into `<project>/.hermes/task-runtime/` via the
   project-local launcher.
3. **High-risk global operations** — deploying to Hermes/Codex Home, modifying
   global configuration/rules, global installation, cross-project writes,
   external absolute paths: require explicit user authorization plus the
   relevant quality gate.
4. **Forbidden by default** — user-home task artifacts, system temp for project
   data, another project, protected drives (`E:\`), unreviewed UNC/absolute
   destinations.

## Guard design requirements

- Require a canonical Git root and verify the project runtime root is
  Git-ignored before creating task state.
- Reject real shell chaining and output redirection for guarded write-capable
  calls.
- Detect Windows drive paths, UNC paths, and path traversal before
  platform-specific tokenization reinterprets them.
- Validate child-command output paths against the resolved Git root.
- Avoid lexical overblocking: a literal `&`, `..`, URL query string, regex, or
  inline-language expression is not by itself proof of an external write.
  Parse quote state before classifying shell control characters.
- In Git-Bash/MSYS, shell expansion happens before command hooks see argv.
  Reject `$VAR`, `${VAR}`, command substitution, and backticks in guarded
  command source unless a wrapper requires a narrowly exact allowlisted token.
- Preserve existing user skills, credentials, model/provider selection, custom
  MCPs, sessions, and unrelated runtime state during any deployment.
- Bootstrap and optional global installers must be create-only: atomic
  exclusive creation, retain `FileExistsError` as a no-op, reject
  symlink/reparse-point targets plus all existing ancestors before write.

## Contract-first task-pack execution

When a user authorizes a task pack, blueprint, attached archive, or
cross-repository execution package:

1. Read the authoritative task-pack body before implementing. Do not infer
   required filenames, directories, schema counts, acceptance markers, or task
   order from a summary, README, or current tree.
2. Extract/archive text safely into project-local ignored runtime evidence.
   Enumerate exact required paths and negative controls; never execute scripts
   from the attachment merely to read it.
3. Convert the exact requirements into a short acceptance matrix: required
   artifacts, positive instance, negative instance, focused command, canonical
   gate, live/runtime boundary. Keep it in `.hermes/task-artifacts/`.
4. Use one canonical contract location. If an exploratory implementation lands
   in the wrong directory or uses the wrong names/count, migrate it to the
   authoritative layout and remove the duplicate.
5. Follow RED → GREEN → REFACTOR for each behavior slice. A field-presence
   scan is not a JSON Schema test: run a real validator with at least one
   valid and one invalid instance where the contract requires it.
6. After each slice, run the narrow test and then the repository canonical
   gate. Distinguish static/isolated checks from live runtime, and report
   blocked/unverified evidence honestly.
7. Preserve task-pack defaults: local changes only unless commit/push/PR/
   release is explicitly authorized; do not apply user-level configuration,
   read credentials, or call real providers just because the package mentions
   them.
