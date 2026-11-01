# Skill-library Overlap Audits

Companion reference for `agent-workflow-fortress`. Read when auditing or
consolidating a profile's skill library for overlap.

## Audit steps

1. Keep the scan profile-scoped. Resolve the active skill root first and never traverse sibling profile directories unless the user explicitly requests it.
2. Start read-only: inventory skill roots and enabled status, then compare trigger descriptions and exact rule families such as provider switching, PTY mode, writer ownership, review identity, and skill loading. Do not modify skills during an audit-only request.
3. Verify volatile commands against live `--help` or authoritative docs. Treat hard-coded model names, ports, credential schemas, and CLI aliases as runtime-discovered values rather than permanent contracts.
4. Assign one class-level umbrella per rule family. Other overlapping skills become thin intent/platform/project entries that link to the umbrella; session-specific evidence belongs in `references/`.
5. Flag credential-file copying/parsing, command-line secret injection, default sandbox bypass, multiple writers in one checkout, manual config edits during concurrent writes, verdicts without exact candidate identity, and commits that stage unrelated paths.
6. For review gates, bind approval to `git write-tree`; any edit, rebase, rebuild, or amend invalidates it. Verification/review does not itself authorize commit or push.
7. Distinguish on-demand skill loading, explicit preloading, and relationship metadata. A `related_skills` entry or prose such as "also load X" does not guarantee that dependency is installed or loaded; validate referenced skill names.
8. Produce an umbrella/thin-entry/delete-candidate matrix with exact file and line evidence. If the user requested read-only, stop at recommendations.
