# migration-20260805 archive notice

WL3-810 bloat cleanup (2026-08-16). Large JSON manifests (~1.06 MiB, ~21% of
tracked bytes) moved to git-ignored .hermes/task-artifacts/wl3-810-archive/.
git rm --cached keeps history; this pointer remains tracked.
migration-status.json legacyLocalArchiveManifest updated to archive location.
