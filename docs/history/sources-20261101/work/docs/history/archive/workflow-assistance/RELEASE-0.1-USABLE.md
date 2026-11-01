# WORK-LAB 0.1-usable Release Notes

**Frozen at**: 2026-08-26
**Commit**: 511fa46 (WLR-130 freeze)
**TaskPack**: WLR-FINAL-20260825-R2-OSS-FAST-TRACK

## What's in this release

### Core Governance (WLR-000~020)
- Authority Index v1 covering 19 domains (rules/config/skills/plugins/models/taskpacks/ledger/capsules/telemetry/observer/federation)
- Root rules updated: DSH managed, CC Switch LEGACY_OBSERVE, task-level four-dimensional model policy
- Taskpack authority index with CURRENT/SUPERSEDED/DEFERRED classification

### Context Continuity Protocol (WLR-030)
- Capsule schema v1 (session/decision/task-state/config-snapshot/knowledge/handoff)
- CLI: export/import/verify/migrate/redact
- Content hash deduplication + conflict preservation

### Canonical Config Compiler (WLR-040)
- Intent schema v1 (set-field/add-skill/remove-skill/enable-plugin/disable-plugin/update-model)
- Pipeline: create → plan → approve → apply → readback
- Idempotency key support

### Observer Truth (WLR-050)
- Pricing schema: provider/model/version/currency/effective_at/source
- Usage fields: nullable integers + observation_state (observed/estimated/unknown)
- Models registry (deepseek/opencode-go with pricing)

### Events + OTel (WLR-070)
- CloudEvent envelope schema v1 (specversion 1.0)
- OTel trace/span correlation
- in-toto receipt structure

### Supply Chain (WLR-080)
- Plugin inventory: 3 active (chrome-profiles, security-guidance, web-ddgs)
- 2 quarantined (media-studio: 89 findings, telegram-business: 2 findings)

### Client Evidence (WLR-090)
- 6 clients documented: Hermes (E2), Codex (E1/quarantined), DSH (E2), GitHub (E1), Open Design (E0), OpenHuman (E0)

### Backup/Restore (WLR-100)
- 9/9 critical governance files verified: backup → restore → integrity check

### Upstream Baselines (WLR-110)
- Mission Control / Dagu / TokenTelemetry versions locked (pending installation)

### Cross-Project (WLR-120)
- WORK-LAB ↔ ArcheAxis interface via project-profiles.json
- WORK-LAB ↔ DESIGN-LAB interface via adapter open-design

## Known gaps
- WLR-060 (CI production gates): typecheck/lint/unit/playwright/axe not yet in CI workflow
- WLR-110 upstream tools: Mission Control/Dagu/TokenTelemetry not yet installed
- ArcheAxis/DESIGN-LAB integration: pending
