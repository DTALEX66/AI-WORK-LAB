# AGENTS.md REQUIRED PATCH

Owner intent: 2026-09-18 已明确要求建立新的云端顶层 Authority，并冻结/清理不符合 Authority 的记录。

在 root `AGENTS.md` 顶部规则区加入：

```md
## TOP-LEVEL AUTHORITY — MUST READ FIRST

Top-level project authority: `/AUTHORITY.md` (`DL-AUTHORITY-2026-09-18-R2`).

Before any audit/planning/implementation:
1. fetch LIVE remote main/open PR
2. read `/AUTHORITY.md`
3. read `/.project/governance/authority-index.json`
4. then read `AGENTS.md`, current integrated TaskPack/Ledger and live CI
5. history only through authority-index/crosswalk
6. memory/chat/handoff/old taskpack/report never overrides Authority
7. every cloud GPT audit states exact observed SHA(s)
```

将“当前任务包”更新为：
- Top-level Authority = `/AUTHORITY.md`
- Current integrated remaining work = `docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md`
- R5 = product lineage
- DeepSeek 2026-09-14 = structural predecessor/subordinate execution lineage
- handoffs = NON_AUTHORITATIVE/HISTORICAL execution records
- old taskpacks = lineage/history unless index explicitly promotes

不得新建第二 mutable task ledger。
