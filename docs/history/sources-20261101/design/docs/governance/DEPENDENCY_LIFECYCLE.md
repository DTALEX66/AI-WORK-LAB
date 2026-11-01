# Dependency Lifecycle（DL-TP-R1-007）
- Lifecycle: DISCOVERED -> FETCHED -> VERIFIED -> STAGED -> CANARY_PASSED -> PROMOTED -> ACTIVE
- Failure states: QUARANTINED | DISABLED | ROLLED_BACK; keep current + last-known-good.
- Automation opens PRs only (never approves/merges/prod-lock changes).
- UpdateReceipt binds old/new source-lock, compatibility, permissions diff, migration, canary, rollback.
- Permission escalation / host minVersion / signature changes require re-approval + requalification.
- Actions pinned to full SHAs; downloads verified by hash.
