# Global skill source ownership and portable live sync

Use this when a global workflow capability exists in a live Hermes profile but the portable repository is the intended source of truth.

## Ownership versus location

Separate capability scope from storage location. A `profile-live-only` skill can still be a core global capability; that label describes current provenance, not project scope. Do not hide drift by recording the current live hash as the repository baseline. Promote reviewed skill text into the repository, declare it `repository-controlled`, and let provenance detect later drift.

## RED → GREEN contract

Before changing ownership, add failing tests proving:

- every promoted skill has a repository `SKILL.md` and repository-controlled manifest entry;
- the sync backup covers the managed skill root, including newly promoted roots;
- an isolated empty Hermes Home receives the promoted skills;
- multiple fresh Git projects can run bootstrap plus the project-data wrapper without cross-project runtime paths.

Then make the smallest source/manifest/sync change, run targeted tests, and only afterward update live provenance.

## Safe promotion sequence

1. Read and scan live skill content; copy only skill text, never auth state, config, sessions, or logs.
2. Remove contradictory credential guidance in the repository version: prefer `gh auth` or OS-backed helpers and never plaintext credential storage.
3. Make repository source authoritative; remove old live-only special cases that would create duplicate/conflicting manifest entries.
4. Verify repository provenance without live state.
5. Run sync dry-run and verify provider/model preservation and declared path scope.
6. Apply through backup → staging → atomic replace; do not use a direct copy shortcut.
7. Run live provenance, hook doctor, isolated portable-install/runtime checks, and project-local wrapper checks.
8. Run the full quality gate and save evidence under `.hermes/task-artifacts/`.

Unmanaged extra live skills may remain when the sync contract preserves them. Do not delete or absorb them without an explicit ownership decision.

## Publication boundary

Local RED → GREEN, quality gates, and live sync prove the current checkout and live profile. They do not prove cloud publication. Only an explicitly authorized commit/push followed by exact-SHA CI can support a remote-release claim; otherwise report exact-SHA publication as pending.
