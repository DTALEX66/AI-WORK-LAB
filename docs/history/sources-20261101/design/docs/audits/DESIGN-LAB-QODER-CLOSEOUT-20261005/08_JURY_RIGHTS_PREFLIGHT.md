# 08 — C6 Quality / Human Jury / Rights / Preflight / Editable Handoff

对应 `DL-R5-005 / DL-R5-014`。状态：**`PARTIAL` + 一个明确的人工门未过**。

## C6.1 Automated Quality（E1/E2）

- 存在且本轮通过其确定性门：
  `packages/capabilities/quality/jury/check_anti_slop.py`
  → `JURY_DETERMINISTIC=OK (human review still required)`（UI 分支与 closeout 分支各跑一次）。
- 该门的输出**自带**「仍需人工评审」的限定，符合 Authority「Automated Quality ≠ Human Jury」。
- 未新增质量维度，也未把自动分当验收。

## C6.2 Human Jury —— `BLOCKED_HUMAN`（未替用户打分）

任务书要求黄金流至少一次 `REJECT → correction → RE-SUBMIT → PASS`。
本轮**没有**任何人工评审发生，因此：

- 未创建任何 jury verdict 记录；
- 未在账本里写 E4；
- UI 侧「人工验收」KPI 保持 `—`（`shell.ts` 中该卡为
  `kpiCard('—', '人工验收', '字体 / 链接 / rights / 质量')`），
  本轮截图证据也确认它没有被偷偷填成数字。

需要用户回答的问题（准备好，等宿主 E3 产物到位后一并提交）：

1. 目标宿主产物（.ai / .psd）在你眼里是否达到可交付专业度？（PASS/REJECT + 理由）
2. 文字/字体是否可接受（含替换字体）？
3. 版式层级与留白是否符合品牌意图？
4. 有无明显 AI 痕迹 / 廉价感？指出具体位置。
5. 是否允许该产物进入 rights/preflight 终检？

## C6.3 Rights

- 本轮唯一新增的外部可见资产 = 40 张 UI 截图。
  每张配 `design-lab/asset-sidecar/v1` sidecar：`license: MIT`、
  `sourceId: null` + owner 例外（`approvedBy: DTALEX66 (project owner)`、
  `expiresAt: 2027-10-05`）、`modelInputAllowed: false`、`commercialUse: true`，
  notes 里写清画面构成（本仓 UI + 一方 MIT 参考栅格 + 本机系统字体）与授权依据。
- 通过 `verify_asset_governance.py`（`ASSET_GOVERNANCE=OK`）与
  `verify_license_coverage.py`。
- **未闭合的 rights 事实**：截图里由本机字体渲染的字形，其再分发权利
  只按「本地 OS 许可」主张，**未做法务级确认**。这属于 `UNKNOWN` 残留，
  不得因 sidecar 写了 `commercialUse: true` 就当已清。
  另外 `pack_mib=216.0 / hard_budget_mib=256`：仓库体积预算只剩约 40 MiB，
  后续再往 docs 里塞证据前必须先决定 artifact 策略。
- 未新增 `KnowledgeCandidate` 出口，未向 ArcheAxis 外溢任何内容。

## C6.4 Preflight

- 路由 `/api/task-preflight` 已存在且 Workbench `#/preflight` 真实读回
  （截图 `*-preflight@*.png` 为其真实渲染证据）。
- 本轮未扩展 preflight 维度；任务书要求的
  dimensions/resolution/color/bleed/fonts/missing links/rights/editability/
  native source/BOM/limitations/asset hashes **未逐项核对为已实现**，
  因此 C6.4 记 `PARTIAL`，不记 `DONE`。

## C6.5 Editable Handoff / C6.6 Close-Reopen

- `/bundle` → `NativeDelivery.create` 与 `/bundles` 读回 + hash fail-closed 已存在（E2）。
- 但「editable source + preview + BOM + rights + quality + human verdict +
  preflight + provenance + evidence + hash manifest + rollback data」的完整交付包
  **本轮没有产出实例**，且 `human verdict` 一项必然为空（见 C6.2）。
- C6.6（关文档→重开→改一个对象→保存）需要宿主，未执行。

结论：C6 整体 `PARTIAL`；`Human Jury` 是硬人工门，`BLOCKED_HUMAN`。
