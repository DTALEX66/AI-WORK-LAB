# 云端审计对照（CROSSWALK）— DESIGN-LAB-CLOUD-AUDIT-2026-09-23

> 分类：**NON_AUTHORITATIVE 对照层**。RAW 原文见同目录 `DESIGN-LAB-CLOUD-AUDIT-2026-09-23-RAW.md`。
> 顶层权威 = `AUTHORITY.md`（`DL-AUTHORITY-2026-09-18-R2`）。本对照不派工；新任务执行前必须经
> `DL-TP-20260918-FINAL-AUTHORITY-CONVERGENCE-R2` crosswalk 映射 `depends_on`。
> 对照基准：本地 = 云端 main @ `7b7335f`（2026-09-23，#145 合入后）。

## 1. 基线 SHA 事实核对（最重要）

doc 自述 baseline：`698eaa9c09a38b9b55493b406a1959dd11828e51`，声称是 HEAD commit
`fix(app): allow explicit refresh of deleted saved profiles`（2026-09-23 21:44:27 UTC）。

**逐项实测（`7b7335f` 上）：**

| doc 声称 | 实测 | 判定 |
|---|---|---|
| `698eaa9` 是 main 的 HEAD commit | `git cat-file -t` = **tree 对象**；该 tree 属于 commit `f3c7ed3`（#143 合入点）的 **tree-id**，不是任何 commit 的 SHA | **错置**：把 tree-id 写成了 commit SHA |
| commit 消息 `fix(app): allow explicit refresh of deleted saved profiles` | `git log --all` 全历史 **无此 commit** | **不存在于本仓历史** |
| 时间 2026-09-23 21:44:27 UTC | 晚于本仓当日全部提交（最晚 #145 @ 11:43Z） | **时间线在未来**，doc 生成环境与本仓不连续 |
| GitHub `license=null` | API 实测 `license=MIT`（根 `LICENSE` 存在） | **与实测相反** |
| `enforce_admins=false` | API 实测 `protection/enforce_admins.enabled=true` | **与实测相反** |
| required checks = 4（Governance/Test/Build/Package Final Gate） | 实测 **9** 项 required checks（P1-2 收紧后），名称与 doc 完全不同 | **陈旧/错误** |
| "最新9月权威文档：未指定" | 根目录有明确 `AUTHORITY.md`（`DL-AUTHORITY-2026-09-18-R2`）+ authority-index + 机器账本 | **doc 未读到仓内权威链** |
| `open_issues_count=0` | 实测 0 | 一致 |

**结论**：该 doc 的"直接读取 GitHub"声称（G1/G2/G3）与可复现实测大面积不符，且基线对象错置。
按 AGENTS.md 铁律"云端 GPT 审计必须声明确切观察 SHA"，本文档只能作为 **inert 观点材料**，
其所有"已验证"字样不继承；下文只采用它的 **框架性建议**（权威图、生命周期、证据 schema、
风险矩阵、外部项目决策），事实层全部以仓内实测为准。

## 2. 框架建议 vs 仓内实态（逐域对照）

| doc 建议域 | 仓内已有实态 | 差距 |
|---|---|---|
| Authority 单向图 / 版本冻结 | `AUTHORITY.md` + `authority-index.json` + `AUTHORITY_CHAIN` 生成器 + no-drift CI gate（`generate_current_reports.py --check`） | **已闭合**。doc 评 B-/待补证，因其未读到该链 |
| 任务生命周期（Contract→E2→Host E3→Readback→…→Evidence） | task-ledger `depends_on` + `verify_evidence_cards` / `verify_host_e3_evidence` / `verify_release_evidence`（fail-closed） | 结构已闭合；**真实 Host E3 仍 NO_RECORD**（owner-gated 操作层） |
| Evidence record schema（host/adapter/artifact hash/readback/reopen） | `verify_evidence_cards` 校验现有 evidence card；缺"append-only evidence ID + supersedes"强制 | **小 gap**：schema 字段可补 |
| Artifact hash/manifest 必填 | `sbom-v42.spdx.json`（vendor-adapt SDK）+ `verify_release_evidence` | **partial gap**：SBOM 未覆盖 lockfile 级（npm/pip） |
| Rights/License manifest | 库索引 4 件套（shared-inputs/external-assets/model-radar/task-resources）+ P1-3 一致性守卫 | **已闭合**（doc 未查到） |
| 外部项目 intake（Source→Provenance→License→Sandbox→E2→E3→decision） | `external_asset_intake.py` + source-registry v3 + quarantine 注册表 | **已闭合**（doc 未查到） |
| Secret 历史扫描 | CI "License & secret hygiene gate" 只扫 **当前 tracked 文件**（no obvious secret files） | **真实 gap**：无 git 历史扫描、无 workflow-artifact 扫描 |
| 三层 Quality（deterministic/automated/human 字段不互相覆盖） | 无真实 backend（#143 深化时已判定 QualityScore 无数据源，未上 UI） | **真实 gap**：需 schema + 接线 |
| Host 路径/版本 locator（无 hard-coded machine path） | `.project/paths.json` 约定 + `LOCAL_ENVIRONMENT.md`；runtime resolver fail-closed | **待审计 gap**：adapter 代码内绝对路径未系统扫描 |
| Rulesets 审计 | API 实测 **无 repo rulesets**，`enforce_admins=true` | **已核实、低风险** |
| 上下文防幻觉协议（BASE_SHA/AUTHORITY_REVISION 前置） | AGENTS.md TOP-LEVEL AUTHORITY 段已等价覆盖（先读 Authority→index→TaskPack→CI） | 已闭合；可把 doc 的 8 字段清单并入 agent 起手模板 |
| 外部项目决策表（ChatCut/Jev/GEP/Beacon/SoL-Pi/…） | 无对应仓内条目 | **新输入**：作为候选清单登记，执行=owner-gated |

## 3. 风险矩阵采纳情况

doc R1–R14 中，与本仓实态相符且仍有价值的：
- **R11 model-memory hallucination**（本 doc 自身就是实例：tree-id 冒充 commit SHA、误报 license=null）→ 对照层已用实测纠错。
- **R13 evidence 被后续覆盖** → 采纳：补 append-only `supersedes` 字段约定。
- **R5/R6 依赖与自动下载** → 采纳：SBOM 扩到 lockfile 级 + download allowlist。
- **R12 secret 历史泄漏** → 采纳：历史扫描（当前最实的 gap）。
- 其余（R2/R3/R4/R7/R8/R9/R10/R14）：仓内守卫已覆盖或 owner-gated 操作层，不重复立项。

## 4. 后续任务清单（分级；执行前须 crosswalk 映射）

### A. 无需行动（doc 误判，实态已闭合；本对照即证据）
- A1 权威 SHA 冻结/漂移门 —— no-drift gate 已运行（`--check` 当前 STALE 为 squash 固有滞后，非缺口）
- A2 Rights/License manifest —— 库索引 4 件套 + P1-3 守卫
- A3 外部 intake pipeline —— `external_asset_intake.py` 在位
- A4 Rulesets/enforce_admins 审计 —— 实测无 rulesets、`enforce_admins=true`，本条关闭

### B. 结构性可执行（agent 可做 E1/E2，owner-gated 操作层不动）
- **B1 历史 secret 扫描**（对应 R12）：对全 git 历史 + workflow 输出做 secret 模式扫描（gitleaks 历史模式或等价 stdlib 扫描器），新增 CI gate；发现即 redact 报告。**当前最实 gap。**
- **B2 SBOM 扩至 lockfile 级**（对应 R5/R6）：npm(pnpm-lock) + python(requirements/uv lock) 导出进 `sbom-v42.spdx.json` 覆盖域，`verify_sbom.py` 校验 integrity。
- **B3 Quality 三层 record schema**（对应 R8）：定义 `quality.{deterministic, automated_judge, human_jury}` 三字段物理不覆盖 + 校验器；不引入模型评分假数据。
- **B4 Adapter 硬编码路径审计**（对应 R10）：扫 adapter/integration 源码的绝对路径/机位假设，输出 locator 改造清单（只出清单，改造走 TaskPack）。
- **B5 Evidence append-only 约定**（对应 R13）：evidence card 加 `supersedes` + immutable ID 校验（小改 `verify_evidence_cards`）。

### C. 操作层 / owner-gated（只留任务文档，按 standing instruction 不执行）
- C1 真实 Host E3 再认证（Photoshop/Illustrator/Premiere 链：executable→readback→editable→reopen）
- C2 ChatCut 独立 host qualification（doc 决策 PILOT；不得继承 Premiere 证据）
- C3 外部候选评估备忘：SoL-Pi（context 方法，ABSORB-方法）/ GEP（REFERENCE）/ Beacon（optional bridge）/ Jev（automated judge 候选）/ AMD Token Factory（DEFER）/ OpenMausBot、EigenFlux（DEFER）/ cc-haha（REJECT 隔离）/ Dalfox·Nuclei（security tooling REFERENCE）—— 仅登记为 `research/` 候选，不动 runtime。

### D. 治理登记（本轮已完成）
- D1 本文档入 `docs/audits/`（RAW inert + 本 crosswalk），基线错置与事实冲突全部留痕
- D2 执行 B 类前：经 `FINAL TaskPack` crosswalk 映射 `depends_on` 并登记 task-ledger；C 类 owner 批准后启动
