# WORK-LAB FROZEN LEGACY RECORD INDEX

**Freeze ID:** `WORK-LAB-HISTORY-FREEZE-20260918-V2`  
**Normative:** NO  
**Frozen source commit:** `803268da9dc356fe63f26b3b5405f724bc06b5b9`  
**Frozen source tree:** `606db598abd3724baf6a45ffcfb319f9b0a4d550`  
**Tracked `taskpacks/current/` entries at freeze:** 71

This file exists only to retrieve history.

## Freeze rule

At the frozen source commit:
- all historical TaskPack/Handoff/Complete/Audit bodies under `taskpacks/current/` are non-normative;
- root legacy directories `50-taskpacks/` and `90-archive/` are historical;
- current compatibility files may remain temporarily only if `project-authority-index.json` explicitly allowlists them.

Retrieve an old file as:

```text
803268da9dc356fe63f26b3b5405f724bc06b5b9:<original-path>
```

Do not duplicate the old body on current `main` merely to preserve history.

## Notable historical families

- WLR/NX predecessor taskpacks;
- Stage 2 / Stage 3 handoffs/graph/baseline history;
- directory-convergence handoff;
- R4 handoff;
- Hermes/DSH/Codex handoffs;
- Integrated TaskPack 2026-09-16;
- Universal Workflow TaskPack 2026-09-16;
- Branch convergence / retirement 2026-09-17.

## Historical semantic anchors

- MiniGame = `FOREIGN_HISTORICAL`, never a WORK-LAB product capability.
- r4/migration branches = retired historical execution lines.
- old `.hermes` project-runtime rules = superseded by `.project-local`.
- old broad OpenHuman/Open Design MANAGE claims = superseded by current scoped ownership.
- old static Observer UI = legacy compatibility material, not final production target.

## Audit rule

Current authority first, named history second. Historical `PASS`, `COMPLETE`, path, branch or architectural statement cannot override current authority.
