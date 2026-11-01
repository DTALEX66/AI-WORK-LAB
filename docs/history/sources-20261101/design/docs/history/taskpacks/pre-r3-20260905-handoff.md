# DESIGN-LAB MULTIMODAL 任务交接：DEEPSEEK 侧已完成 / CODEX 侧待执行（2026-09-05 最终版）

> 依据：`docs/taskpacks/DESIGN-LAB-MULTIMODAL-TASK-PLAN-2026-09-05.md`（已归档入仓，T01–T18）。
> 分工：DEEPSEEK 侧（可离线/可复核的仓库、盘点、契约/后端、单测、文档台账）**已全部完成**；CODEX 侧（真实宿主/模型/GPU/前端实机）**待用户调用 CODEX 执行**。
> 状态纪律：仅"目标环境实测并附结果"标"已验证"；CI 绿但未实机 → "待实机"；H3 权利门未清 → `BLOCKED_BY_LICENSE`。

## 0. 共用前置事实（2026-09-05）

- 仓库基线：cloud main `2aca27f`；工作分支 `feat/r0-freeze-baseline`（PR #115，当前 head `caa32a8`，OPEN/MERGEABLE，CI 全绿）。
- E 盘受保护（未触碰）；个人研究非商业；不伪造完成。
- **本机实测**（T02）：Windows 11；i5-14600KF 14 核 / 64GB RAM；**RTX 5060 8GB**；**Illustrator 2025 29.5.1 与 Photoshop 2025 26.7 已安装**；ffmpeg 在 PATH；codex-cli 0.153.1；**ComfyUI 未装**；**Blender 未装**；模型缓存：ASR faster-whisper base/tiny **READY(145MB)**，OCR PaddleOCR 系列 **INCOMPLETE(仅 refs 无字节)**，图像生成 checkpoint 未发现。

## 1. DEEPSEEK 侧 —— 已完成（附交付物指针，全部已提交并推送）

| 任务 | 状态 | 交付物（仓库内） |
|---|---|---|
| **T01** 仓库/历史对照 | ✅ | `reports/current/T01-REPO-BASELINE-2026-09-05.md`（SHA/PR/映射 + PR115 F01–F10 逐项证据） |
| **T02** 只读盘点 | ✅ | `reports/current/T02-MACHINE-INVENTORY-2026-09-05.md`（含模型就绪 ASR READY / OCR INCOMPLETE） |
| **T05** 资产+任务服务 | ✅ | `src/design_lab/runtime/asset_store.py` + `job_store.py` + 两个 state DDL + 11 单测（幂等/重启恢复/终态不可回退/单写锁） |
| **T06** 平面拆解（结构） | ✅ | `src/design_lab/analysis/decomposition.py` + `model_cache.py`（fail-closed 缓存探测）+ `planar-decomposition.schema.json` + 15 单测 |
| **T09** 生成入口（结构） | ✅ | `src/design_lab/generators/comfy_task.py`（工作流指纹/cache-hit≠新生成/状态机+取消）+ 11 单测 |
| **T18** 归档/台账/规范 | ✅ | AGENTS 登记、唯一台账 `reports/current/MULTIMODAL_PROGRESS-2026-09-05.json`、旧任务包 SUPERSEDED、schema 无效输入负例测试、能力矩阵新增 3 能力(E1 structural-pass) |
| **R0-005** 测试隔离（附带） | ✅ | `design-lab/scripts/run_test_isolation.py` + `reports/current/R0-005-TEST-ISOLATION-2026-09-05.md`（三序各 580 全绿 + 敏感模块 20 次全绿） |

- 全套 Python：固定顺序 559→580 tests 全绿；PR #115 CI Python gate pass（两次运行）。

## 2. CODEX 侧 —— 待执行（实机依赖）

| 任务 | 内容 | 实机前置 | DEEPSEEK 已备的可复用结构 |
|---|---|---|---|
| **T03** | AI/PS 控制组件对比（Illustrator 官方 MCP / adb-mcp / Photoshop MCP 同案例 Windows 实测选型） | AI 2025 + PS 2025 已装（本机即可） | — |
| **T04** | 前端 + Codex 官方集成可运行切片 | Codex SDK + 前端构建 | `analysis/`、`generators/`、`runtime/` 结构层 |
| **T07** | AI/PS 真实混合海报工程（建/读回/改字改色换图/重开） | AI + PS 实机 | T06 `planar-decomposition` 对象映射契约、T05 `asset_store`（资产版本/依赖/单写锁） |
| **T08** | 对比叠加与局部修订（定位到对象、只重跑相关步骤） | 依赖 T07 | T05 依赖图 `asset_dependency` |
| **T10** | 音频首条闭环（Qwen3-TTS 中文逐句 WAV+文稿） | GPU + 模型 | T02 已确认 ASR 模型本地 READY；`generators/` 任务协议可扩展音频 |
| **T11** | ACE-Step 音乐生成与音轨管理 | GPU + 模型 | 同上 |
| **T12** | H3 本地 + 视频生成 | **H3 权利/地域门先清** + GPU | 当前 `BLOCKED_BY_LICENSE`；不冒充 |
| **T13** | Premiere PRPROJ 闭环（UXP 优先） | Premiere 实机（T02 未探，需装/确认） | — |
| **T14** | OpenDesign / MiniMax Design 协作（三档接入） | 两软件实机 + 接口探测 | — |
| **T15** | Blender 参考重建 | Blender 未装 → 先装 | `analysis/` 结构层可扩展三维对象映射 |
| **T16** | 跨媒体依赖更新联动 | 依赖 T07/T13/T15 | T05 `asset_dependency` |
| **T17** | 桌面启动/便携/媒体校验/交付质量 | 集成环境 + 实机宿主重开 | ffmpeg 已就绪 |

### CODEX 执行约定
1. 每项交付回写 DESIGN-LAB 仓库，附：机器/软件版本、命令、结果、证据 hash；未实机验证的能力一律 `待实机`。
2. 复用 DEEPSEEK 侧结构层：`src/design_lab/{runtime,analysis,generators,adapters}` 与 `design-lab/schemas/{contracts,state}`，不要另起默认实现（T18 纪律：同一功能无两个默认实现）。
3. 遵守：E 盘不碰；H3 `BLOCKED_BY_LICENSE` 至权利门清；生成/复刻/可编辑性边界按 plan §6（分层≠可编辑字体路径、波形≠无损逆推、分声部≠原 MIDI、生成视频物体≠三维/矢量可编辑）。
4. PR #115 合入 cloud main 由人工决定，不影响本交接执行。

## 3. 交付物索引（仓库内，CODEX 可直接引用）

- 方案：`docs/taskpacks/DESIGN-LAB-MULTIMODAL-TASK-PLAN-2026-09-05.md`
- 台账：`reports/current/MULTIMODAL_PROGRESS-2026-09-05.json`
- T01/T02 报告：`reports/current/T01-REPO-BASELINE-2026-09-05.md`、`reports/current/T02-MACHINE-INVENTORY-2026-09-05.md`
- R0-005 隔离证据：`reports/current/R0-005-TEST-ISOLATION-2026-09-05.md`
