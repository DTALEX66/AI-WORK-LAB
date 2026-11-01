# K-CASE-SELECTION-RECORD — 条件依赖任务的案例选择与理由（2026-09-26）

> **定位**：`SESSION_CONVERGENCE_RECORD / EXECUTION`。本文件满足 AGENTS.md
> 「条件依赖须记录案例选择和理由，未决条件阻止验收完成」规则（顶层权威
> `/AUTHORITY.md` `DL-AUTHORITY-2026-09-18-R2` 之下，本文件不是任务派工
> 账本，也不是 Authority；它是 FINAL TaskPack K-lane（Golden Workflows）的
> 案例选择落仓记录）。

## 范围

活动账本 `design-lab/config/task-ledger-r3.json` 有 3 个任务携带条件依赖字段
（`conditional_gate` / `conditional_dependencies`）：`DL-R5-008`、
`DL-R5-019`、`DL-R5-024`。AGENTS 规则要求对每个条件依赖记录**选了哪个案例、
为什么**。本文件逐条钉死，使"未决条件"可被机器/人复核，而非停留在账本字段里。

顶层选择（AGENTS.md 第 138 行，权威措辞）：**Comfy、H3、UIA 不作为 Adobe
M1 的硬前置** —— 三条 Golden Workflow 的 M1 目标案例走**原生 Adobe
（Illustrator / Photoshop）脚本路径**，上述三者仅作能力级条件门，只阻塞
"使用本能力的任务"，不阻塞原生 M1。

## 逐条案例选择

### DL-R5-008 ComfyUI 生产适配与可选本地 MCP

- **条件字段原文**（账本 `definition.conditional_gate`）：
  「只阻塞使用本能力的任务，不阻塞原生Adobe M1」。
- **案例选择**：M1 目标案例 = **原生 Adobe M1**（Illustrator/Photoshop
  可编辑对象闭环），**不**选 ComfyUI 生成路径。
- **理由**：ComfyUI 是可选本地 MCP / 生产适配（P1，`depends_on` = R5-004/005/006/007），
  其"图参数/节点模型指纹/REST-WS/断线恢复"是能力级增强，不是 Adobe M1 的前置；
  把它设为硬前置会违反「不恢复旧架构 / 单宿主 M1」的 R5 冻结口径。
- **门控判定**：本任务 `axes.unit` = `PARTIAL`（evidence `r5-comfy-structural-rejection-20260909`），
  `host_live` = `PARTIAL`（evidence `r5-comfy-http-model-free-live-20260909`）——即结构层已建、
  **真实生成 E3 未做**（owner-gated，实操不执行）。条件依赖已记录，验收不被"假全成功"冒充。

### DL-R5-019 Premiere 可编辑视频

- **条件字段原文**（账本 `definition.conditional_dependencies`）：
  `{"TTS_required": "DL-R5-016", "generated_music_required": "DL-R5-017"}`。
- **案例选择**：视频任务 = **可用合法素材先剪辑**（20—30 秒、可改剪辑/音轨/字幕、
  保存重开媒体重连、MP4 不替代工程）；语音/音乐**按案例条件依赖**，**不强制从模型产出**。
- **理由**：implementation 原文「语音音乐生成按案例条件依赖，不强制从模型产出；
  纳入字幕媒体重连」——即本任务的验收案例**允许**用已授权合法素材完成剪辑闭环，
  只有"本案例真正需要 TTS(016)/生成音乐(017)"时才把该依赖拉进前置；否则以素材剪辑
  交付，不把未产出的模型输出当验收条件。
- **门控判定**：四轴 `PARTIAL`、evidence 空 = 结构占位未起，**实操剪辑/音轨 E3 未做**
  （owner-gated，实操不执行）。条件依赖记录于此即闭环"未决条件"。

### DL-R5-024 UIA 与视觉控制后备

- **条件字段原文**（账本 `definition.conditional_gate`）：
  「只阻塞使用本能力的任务，不阻塞原生Adobe M1」。
- **案例选择**：M1 目标案例 = **原生脚本路径**（Illustrator JSX / Photoshop COM-JSX）；
  UIA 仅当「原生接口不足时」才作为后备，首试点只做只读/开副本/导入/导出新文件。
- **理由**：implementation 原文「原生接口不足时才资格验证；首试点只读/开副本/导入/导出
  新文件；视觉步骤按已授权范围人工确认」+ acceptance「不得覆盖源/发布/购买/上传、
  进程窗口定位与超时可查、禁用后备不影响原生脚本路径」——UIA 是 fail-safe 后备，
  设硬前置会让 Adobe M1 依赖一块未资格的自动化层，违反 standalone-first（ADR-001）。
- **门控判定**：四轴 `PARTIAL`、evidence 空 = 结构占位未起，**真机 UIA 资格 E3 未做**
  （owner-gated，实操不执行）。

## 收口判定

- 3 个条件依赖任务的「案例选择 + 理由」已全部落仓（本文件），满足 AGENTS 规则 130
  「条件依赖须记录案例选择和理由」——**未决条件不再阻止验收记账**。
- 三者的**真实操作 E3 轴**（真跑 ComfyUI 生成 / Premiere 剪辑 / UIA 真机）仍归
  owner-gated（实操/自动化不执行，保留任务文档），本文件**只记录选择，不宣称 E3 闭环**。
- 与 09-25 收口账本 `docs/audits/DESIGN-LAB-FULL-SWEEP-CLOSE-OUT-LEDGER-2026-09-25.md`
  互补：该账本记 G/E3/E4/H001/core 处置；本文件补记 09-26 全量扫描后的 K-lane
  条件依赖选择，是「跑完所有非自动化任务」的 K-lane 终端记录。

**END — K-CASE-SELECTION-RECORD-2026-09-26**
