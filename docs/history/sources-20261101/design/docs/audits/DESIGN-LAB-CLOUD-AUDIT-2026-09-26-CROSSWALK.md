# CROSSWALK — 云端全量审计 ingest 2026-09-26（基线 main@0e9f687，第四份独立 GPT 审计）

> **定位**：本 CROSSWALK 对 `DESIGN-LAB-CLOUD-AUDIT-2026-09-26-RAW.md`（verbatim
> 粘贴件，`sha256:2cfee7fd1780457545fe2a152f5b0d785bc524eba944379ba4a8d5643f2aee2c`，
> 22,895 bytes）做**事实层活核对**（live main `f1fbbb3`，2026-09-26）。RAW 是
> NON_AUTHORITATIVE 历史证据；当前权威 = `/AUTHORITY.md`
> （`DL-AUTHORITY-2026-09-18-R2`）+ `.project/governance/authority-index.json`。
> 本文件**不是**任务派工账本；可执行项一律映射到现有 lane（见 §3），
> 不建第二 mutable ledger。

## §0 审计基线识别

- 该 RAW 描述的快照 `main@0e9f687ca306226f984f9ac49d222c0d8ff8a1e5` 恰为
  authority-index `dynamicBaseline.observedMainSha`（09-18 R2 记录值）：
  即该 GPT 读取的是 **09-18 基线快照**，其中 "28 个远端分支" 直接抄自
  authority-index 的 `remoteBranchCountObserved: 28` 快照字段（该字段标注
  "snapshot only; refetch on every audit"，GPT 未 refetch 即写成现状）。
- 与仓内 09-23 / 09-24 / 09-25 三份 RAW 经 probe 比对**互不相同**，
  为独立第四份粘贴审计，故按 09-24/09-25 同款模式 ingest（RAW + CROSSWALK）。

## §1 事实层活核对（RAW 声明 → 实况判定）

| # | RAW 声明 | live 实况（main `f1fbbb3`） | 判定 |
|---|---|---|---|
| 1 | "当前已有 28 个分支快照" | 远端仅 `main` + 5 个 `archive-evidence/2026-09-25/*` tag（本地仅 main） | **STALE**（抄 authority-index 快照字段未 refetch；#149/#157 已收敛 main-only） |
| 2 | "无 DeepSeek Authority gate（缺口）" | 9 项 required 之一：`DeepSeek authority gate chain (DLDS-H010 / DL-AUDIT-20260914-07)` + `Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)` | **STALE（已闭环）** |
| 3 | "前端仅 index.html/main.ts/style.css，无组件分层" | `apps/workbench` 10 个 tracked 文件（含 `contracts.ts`、strict-TS product gate、browser E2E gate、build/main.js Build Output Truth 门） | **STALE**（UI 产品化 C/D/E 仍是 owner 门，见 §4） |
| 4 | "需建立路径健壮性校验 + 禁用外部自动下载政策" | #160 已落：`resolve_tool_locator.py`（fail-closed 定位器，五态）+ `verify_execution_path_gate.py`（命中必须 pin 五元组 receipt，`execution-path-allowlist.json`）+ `install-authorization.schema.json` | **已闭环（#160）** |
| 5 | "上下文丢失 → 强制上下文校验与会话缓存（防失忆）" | #161 已落：`context_capsule.py` + `verify_context_integrity.py`（STALE 上报不续行；current-looking 历史文档检测器） | **已闭环（#161）** |
| 6 | "Jury 人工审查与模型结果对比" | 既有 `src/design_lab/assurance/`（qa_plane / human_jury / quality_record：automated score 永不入 gate）+ #162 五层 readiness 组合器（BLOCKER/WARNING/INFO 双馈 UI/backend） | **已闭环（既有 + #162）** |
| 7 | "GEP 等重叠数据模型需合并" | 全仓 `GEP` 零引用；object-model 声明 `evidence-record` 与 `candidate-knowledge` 为两个不同对象（Evidence 属仓内，KnowledgeCandidate 属 ArcheAxis 出口合同） | **GEP=幻觉；Evidence/知识分离为 by-design**，无需合并 |
| 8 | "PROJECT_STATUS 不应人工自由书写" | 机器生成投影（`scripts/generate_current_reports.py`，`--check` 只读漂移门）；ingest 时发现投影漂在 pre-#159 的 `43003618`（`fresh:false`） | **成立，本 PR 修复**（§2） |
| 9 | "0 open PR / main 受保护多必检" | 0 open PR（本 PR 之前）；main 9 项 required + strict=true | 当前为真（open PR 计数对本 PR 本身不适用） |
| 10 | "README 版本应对齐 0.1.0-alpha.0" | README 无版本串；`product-manifest.json` 无 version 字段（版本真值在 capability/evidence 门内） | **DECLARED**（不新增版本串，避免幻影 KPI） |
| 11 | "证据 JSON + 截图进 CI artifacts" | H001 artifact proof 门（#159 修 415 根因后 advisory lane PASS，sha 校验闭环） | **已闭环（#159）** |
| 12 | "Host E3 未验证 / 需 PS 插件原型端到端" | Host Matrix 8 项 E1、live=0（GD-1 门锁假声明） | **owner-gated（H lane，ledger §5）** |
| 13 | "CI 增加 Quality Score/Control Matrix 一目了然分数" | Quality 侧已被 #162 readiness 组合器 + QualityRecord 门覆盖；ControlMatrix 未建 | **Quality 已闭环；ControlMatrix DECLARED（不新建，避免平行 quality truth）** |

## §2 本 PR 落地的真实修复

1. **投影 rebind**（§1-8 实证）：`generate_current_reports.py`（write 模式）
   重生成 10 份投影，`fresh:true`、subject 钉 `f1fbbb3`；
   `--check` 恢复 `CURRENT_REPORTS=PASS`。漂移根因：#159–#163 合入推进
   main 后未 rebind 机器投影（恰是 RAW 点名的"PROJECT_STATUS 不应
   人工自由书写"问题的正反面——它是机器投影，只须 rebind）。
2. **RAW + 本 CROSSWALK ingest**：第四份独立 GPT 审计按 09-24/09-25
   同款模式归档，事实层判定上表，不再重复 ingest 同族审计。

## §3 RAW 计划项 → lane 映射（不建第二账本）

| RAW 计划项 | lane / 归属 | 判定 |
|---|---|---|
| 1. Lite 工作台原型 + 线框（DL-R5-UI-01） | C/D/E owner 门 | **owner-gated**（UI 产品决策需 owner 定范围；本 CROSSWALK 不代决） |
| 2. 文档更新与权威同步（DL-R5-DOC-02） | authority chain 门 | **已闭环**（AGENTS 引 DeepSeek taskpack = by-design STRUCTURAL_PREDECESSOR 谱系记录，chain 门 42 条分类 PASS；无过期指针） |
| 3. 完善 CI 校验（DL-R5-CI-03） | H001 / H010 / authority gates | **已闭环**（#159 + 既有 9 required） |
| 4. 前端迭代开发（DL-R5-UI-04） | C/D/E owner 门 | **owner-gated** |
| 5. Host 适配器 E3（DL-R5-HOST-05） | H lane | **owner-gated**（ledger §5） |
| 6. 外部项目集成评估 + 吸收标准（ABSORB/PILOT/DEFER/REJECT） | J lane | **owner-gated**（真实下载/安装/许可）；候选表在 §4 记 DECLARED，判定权归 owner |
| 7. Prompt 模版库 | 09-25 RAW §prompt 已收录 | **已被 09-25 CROSSWALK 覆盖**（本份无新增 prompt 面） |
| 8. 接受准则与审查清单 | J lane owner 门 + 既有 `technical-research-absorption` 流程 | **owner-gated** |

## §4 OSS 候选（RAW §第三方开源项目对比）— DECLARED 记录，无判定

RAW 给出 7 个入口/控制台候选（Flow Launcher、PowerToys Run、Jan、Witsy、
Open WebUI、Backstage、Pinokio）。仓内已有 `research/design-software-oss-ecosystem.md`
（08-18，操作型设计软件生态）与本表互补（本表=用户入口/Agent 控制台候选）。
按 No-Phantom 规则：候选**只记 DECLARED**（候选身份 + RAW 出处 + 许可
自述），ABSORB/PILOT/DEFER/REJECT 判定与任何真实下载/安装/许可证核验
归 owner（J lane，#160 执行路径门保证未经 pin 的下载 token 无法进仓）。

## §5 残留 owner-gated（转引，不重述）

以 `docs/audits/DESIGN-LAB-FULL-SWEEP-CLOSE-OUT-LEDGER-2026-09-25.md` §5
为唯一清单（E3/E4、H003、G-9/G-10 PARKED、core 迁移、C/D/E、J）。
