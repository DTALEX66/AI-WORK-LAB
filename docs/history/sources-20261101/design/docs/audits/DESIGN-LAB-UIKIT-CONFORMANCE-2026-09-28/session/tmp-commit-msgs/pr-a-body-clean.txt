## Scope

云端全量审计（2026-09-24）ingest：RAW 逐字节存档 + CROSSWALK 活核对拆解 + 投影 rebind。
**本 PR 不执行 CROSSWALK 任务清单**（G-A..G-E 各自独立 PR）。

## Authority & Observed SHA

- Authority: `DL-AUTHORITY-2026-09-18-R2`（`.project/governance/authority-index.json`, `TOP_LEVEL_CURRENT`）
- Observed main SHA: `cb9c3ca68a4eb0a12436b719668b16aa09def600`

## Fact-check highlights（RAW 声称 vs live 实测）

| 项 | RAW | live | 判定 |
|---|---|---|---|
| 分支集合 | 10× `codex/*` | 10 分支、0 个 `codex/*` | 分支表跨环境/幻觉，不继承 |
| #149 | `feat(ai) ai utilization registry` | G-3/B3 QualityRecord schema（head `feat/quality-record-schema-b3`） | 身份不符 |
| 机器索引 | 缺 | `.project/governance/authority-index.json` v2 + CI gate | 已闭 |
| 环境注册 | 缺 | `paths.json` + `LOCAL_ENVIRONMENT.md` + `MACHINE_INVENTORY.json` | 已闭 |
| 路径漂移校验 | 不存在 | 语言漂移检查器在（DL-GOV-130）但**未接 CI**；**路径引用校验器确缺** | 真缺口 → G-A |
| Workbench UI | 缺 preflight/token/host 面板 | grep `apps/workbench/src/` = 0 引用 | 真缺口 → G-E |

## Rollback

revert 单 commit；文档 + 再生成投影，无代码面。

## Gated remainders（不动）

`#149` user-managed；G-7 415 / G-9 / G-10 owner-parked；E3 真实 Host / E4 Human Jury owner-gated（CROSSWALK §2 只写 DECLARED）。
