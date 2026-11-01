# DESIGN_TOOL_POC_MATRIX（TP-20260819 DL-P1-002/003/004）

## Adapter 分级（STABLE / VALIDATION / QUARANTINED）

| 工具 | 分级 | 依据 | 状态 |
|---|---|---|---|
| Penpot MCP | STABLE | MPL-2.0 自托管，REST 导出；07 备份规则已有基础 | adapter-penpot E0 登记 |
| ComfyUI API | STABLE | 实测 E3（H3 生成取证） | adapter-comfyui E3 |
| Style Dictionary | STABLE | Apache-2.0 token 流水线，DTCG 已对齐 | adapter-style-dictionary E0 |
| Blender MCP (bpy) | VALIDATION | GPL-2.0 subprocess 契约；headless 渲染 | adapter-blender-bpy E0（missing） |
| Krita AI Diffusion | VALIDATION | GPL-3.0 位图；非管线核心 | 未登记（仅参考） |
| OpenPencil | VALIDATION（试点候选） | 见下 | 评估中 |
| Flue | QUARANTINED | 见下 | 隔离 |

## OpenPencil 试点评估（P1-003）

- 定位：可选 AI 原生 UI/UX 画布试点（.fig/.pen 读写、设计树、Lint、Token、HTML-CSS、导出、MCP-CLI、Windows-Tauri、回滚哈希）
- 现状态：非本项目已接入；需先核验许可证/API 稳定性（web 核实后定）
- 试点路径：E0 契约登记 -> adapter 开发 -> E3 取证（逐级）
- 结论：**候选试点**，等许可证核验 + 用户批准后才进入 adapter 开发

## Flue 隔离试验（P1-004）

- 受限 Adapter 后（禁止任意脚本/白名单/参数 Schema/路径沙箱/人工批准/备份/JSON 回读/无损 smoke）
- 现状态：未接入；按任务包要求保持 QUARANTINED（不并入）
- 结论：**隔离**，不执行

## P2 研究项（DL-P2，研究而非并入）

| 项目 | 判断 |
|---|---|
| Open AI Design Agent | 提炼 Brief 分解思想，不并入依赖 |
| UIClip | UI 质量信号参考，不替代人工 Jury |
| OpenCut | 等 API 稳定 |
| Remotion | 许可证后再评估 |
| Backstage/Temporal/Kestra | 不属于本项目 |
