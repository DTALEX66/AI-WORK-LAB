# Instruction precedence

1. Explicit user scope and safety boundaries.
2. Root `AGENTS.md` (scope/safety/bootstrap) and `.project/governance/`
   machine authorities (`project-authority-index.json`,
   `project-data-boundary.json`, `config-ownership.json`).
3. The owning module's `AGENTS.md`.
4. Task-card allowed paths and acceptance criteria.
5. Local tool defaults.

A module rule may narrow a root rule but may not weaken it. One writer owns a
mutation task. Read-only reviewers must use a frozen HEAD/tree and must stop if
the tree changes. A task touching more than one module must be an explicit
cross-module task; incidental cross-module edits are rejected.
