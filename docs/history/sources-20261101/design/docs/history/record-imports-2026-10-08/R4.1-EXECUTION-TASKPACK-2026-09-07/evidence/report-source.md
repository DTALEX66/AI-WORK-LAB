# R4.1 增强包研究来源与证据账本

**标题：** DESIGN-LAB R4.1 增强任务包调研审计  
**受众：** 项目负责人和后续执行 Agent  
**日期：** 2026-09-07  
**范围：** 审核附件中 ComfyUI/MCP、可复现资产、人工 Jury、DCC 自动化和交付预检五类要求，决定是否纳入冻结的 R4 执行包。  
**不在范围：** 安装任何 MCP、连接云端、下载模型、改动远端仓库、或宣称宿主实机已通过。

## 直接结论

附件的产品边界和安全方向可采纳。其对 ComfyUI-MCP 的描述不再是“待寻找的社区候选”：ComfyUI 官方文档已列出第一方开源本地 `comfy-mcp`，并说明它驱动本机安装的 ComfyUI；同一页也将整个 Comfy MCP 标为 public beta。因此将其作为受控、可替换的本地 RuntimeAdapter 是有依据的；将其视为稳定的唯一执行内核则没有依据。

本地 REST/WebSocket 适配与 MCP 应并存：前者承载任务、产物、取消与审计的服务端事实；后者为 Agent 的标准工具入口。云端、付费、批量与外传触发额外的范围授权，不能由本地默认路径隐式触发。

Photoshop 原生 API 和 Windows UI Automation 的官方资料支持“原生脚本/API 优先、UIA 后备”的架构选择；副本限制、禁止发布/购买/上传是 DESIGN-LAB 的安全策略，而不是声称平台自动保证。

## 证据账本

| 结论 | 一手来源 | 证据与适用范围 | 置信度 |
|---|---|---|---|
| 官方 Comfy MCP 可生成图像、视频、音频、3D，且有 cloud/local 两种连接 | [Comfy MCP](https://docs.comfy.org/agent-tools/mcp)（ComfyUI，访问 2026-09-07） | 文档概览与本地连接章节；本地连接用于本机 ComfyUI。 | 高 |
| 官方本地 `comfy-mcp` 是第一方开源 server，MCP 仍为 public beta | [Comfy MCP](https://docs.comfy.org/agent-tools/mcp)（ComfyUI，访问 2026-09-07） | 文档明确标注 beta，并列出 `pip install comfy-mcp` 及本机连接。 | 高 |
| 云端、本地与 In-App Agent 具有不同运行位置、GPU 和先决条件 | [Agent Tools](https://docs.comfy.org/agent-tools)（ComfyUI，访问 2026-09-07） | 对照表将本地模型/本地 GPU 和云端服务分开。 | 高 |
| Partner MCP 不应纳入默认路径 | [Comfy Partner MCP](https://docs.comfy.org/agent-tools/partner-mcp)（ComfyUI，访问 2026-09-07） | 文档标注 private preview，需要 API key，且工具包括上传与余额查询。 | 高 |
| Photoshop 可用官方 UXP DOM 打开/修改文档 | [Photoshop API](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/)（Adobe，访问 2026-09-07） | API 概览说明可打开文档、修改文档与运行菜单。 | 高 |
| Windows UIA 提供桌面 UI 元素的程序访问，适合作为树式后备 | [UI Automation Overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview)（Microsoft，访问 2026-09-07） | 官方说明其供辅助技术和自动化测试与 UI 交互。 | 高 |

## 本地仓库核对

冻结 R4 已含 Comfy 真实适配、资产事务、质量/可编辑验收和交付维护任务，但未把“指定实例 MCP、三条 golden workflow、Human Jury 实际选择、UIA hard allowlist、媒体 profile 预检”写成完整可验收门。R4.1 将这些落到 DL-R4-005、008、014、023—027；当前状态仍为 `PLAN_DELIVERED_NOT_IMPLEMENTED`。

## 限制与不确定性

- 官方 beta 状态意味着工具、版本和行为可能变化；每次真实接入必须重新记录版本与工具清单。
- 本研究没有目标 Windows 主机、Comfy 实例、显卡、模型、许可或用户工程可用于实测，因此不能证明兼容性、性能或 H3 合规性。
- “连续 10 次”和 Human Jury 是项目验收策略，来源是用户附件，不是外部产品保证。

## 查询与停止理由

已检索并阅读 ComfyUI 官方 MCP/Agent Tools/Partner MCP、Adobe Photoshop API、Microsoft UI Automation 官方文档。关键主张均获得一手资料或已被明确限制；再扩展社区项目检索不会改变“采用官方本地 MCP、保留服务端审计、云端/Partner 需单独授权”的结论，故停止。
