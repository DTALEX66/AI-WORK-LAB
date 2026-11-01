# 独立增强任务包审计与纳入决定

**审计日期：** 2026-09-07  
**输入：** `DESIGN-LAB-ENHANCEMENT-TASKPACK-2026-09-07(1).md`  
**对照基线：** `DTALEX66/DESIGN-LAB@c4dccd58331bc4561eb89265283d924b7630d113`  
**结论：** 方向整体采纳，已写入 R4.1；三处按真实依赖收敛，不增加“文档已写即完成”的假状态。

## 直接结论

DESIGN-LAB 应拥有 ComfyUI/Comfy MCP、设计宿主控制、音视频/3D/交互资产交付的**专业适配与质量链路**，但不复制 ComfyUI、不重建 DCC/游戏引擎，也不成为通用聊天 Agent。它仍是独立、本地优先、个人非商业研究工作台。

ComfyUI 官方现在提供了第一方本地 `comfy-mcp`，用于驱动用户本机的 ComfyUI；其文档同时明确标注 Comfy MCP 为 public beta。故 R4.1 将 MCP 作为受控 RuntimeAdapter，而实际 REST/WebSocket、产物、取消回执和可复现清单仍是系统真相源。详见 [Comfy MCP 官方文档](https://docs.comfy.org/agent-tools/mcp)。

## 逐条决定

| 输入项 | 决定 | R4.1 归属 | 收敛说明 |
|---|---|---|---|
| ComfyUI 归属本项目、不复制其本体 | 采纳 | DL-R4-008 | 仅做本地实例适配、编排、证据和产品 UI。 |
| 工作流发现、提交、进度、取消、恢复、输出收集 | 采纳并强化 | DL-R4-008 | REST/WebSocket 仍为运行真相；MCP 不能绕过审计。 |
| ComfyUI-MCP 只连指定实例 | 采纳 | DL-R4-008 | 采用官方本地 MCP 的资格门；记录 server/client 版本和实例，beta 不视为稳定承诺。 |
| 下载、付费云端、批量和外传分开授权 | 采纳 | DL-R4-008、03 | 默认本地最小权限；只接受记录过的作用域授权，禁止普通生成任务隐式升级为外传/付费。 |
| Brief、rights、workflow、版本、seed、hash、操作者、评审结论 | 采纳 | DL-R4-005、008、014 | 形成不可变清单；排除凭据、私有会话及未获授权的原始内容。 |
| 平面/图像编辑 golden workflow | 采纳，M1 必需 | DL-R4-008 | 连续 10 次有完整记录，包含成功、取消、失败恢复。 |
| 短视频/动效 golden workflow | 采纳，M1 后 | DL-R4-025 | 模型/显存/许可不明不能阻塞首个 AI/PSD 闭环。 |
| 提取与透明通道 golden workflow | 采纳，M1 后 | DL-R4-026 | 与视频分开验收，避免将“能出图”误报为透明资产可交付。 |
| Human Jury，模型评分只辅助 | 采纳，M1 必需 | DL-R4-014 | 五项人工选择/驳回结论进入版本记录。 |
| API/脚本 → UIA tree → 视觉操作 | 采纳为硬顺序 | DL-R4-024、011、012、021 | 视觉鼠标键盘仅在人工确认的后备模式使用。 |
| 首个 UIA 只操作副本、禁止覆盖/发布/购买/上传 | 采纳为硬 allowlist | DL-R4-024 | 读取、打开副本、导入、导出新文件之外一律拒绝。 |
| 统一音频、视频、3D、交互资产交付 | 采纳 | DL-R4-023、027 | 使用统一资产/版本/交付契约；不重建成熟 DCC 或游戏引擎。 |
| 尺寸、字体、出血、alpha 等交付前检查 | 采纳并改为媒体 profile | DL-R4-023 | 平面、视频、音频、3D 只运行各自适用项，避免错误的“一刀切清单”。 |

## 首个闭环与后续能力的边界

M1 不再只是“能生成一张图”。它要求：真实 Brief → 有完整清单的可复现候选 → Human Jury 选定版本 → Illustrator/Photoshop 可编辑工程与交付包。平面 Comfy workflow 是 M1 的生成记录门；短视频和 alpha 提取是后续独立门，不可因设备或模型条件拖慢第一个可用版本。

MCP 的云端连接、Partner MCP 和任何付费 provider 不属于默认执行路径。官方资料显示云端和本地连接是不同连接，且 Partner MCP 仍处 private preview；本项目只在明确的任务授权和费用/传输范围内评估它们。[Comfy Agent Tools](https://docs.comfy.org/agent-tools) [Comfy Partner MCP](https://docs.comfy.org/agent-tools/partner-mcp)

“官方 API/脚本优先”不仅是偏好：Photoshop 的官方 UXP API 已能打开和修改文档，Windows UI Automation 是可访问性树和自动化接口。因此 UIA 可作为可审计后备，但不应先用脆弱坐标点击。[Photoshop API](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/) [Windows UI Automation Overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview)

## 验收更新

新增或加强的可验证门：

1. Comfy 平面 golden workflow 连续 10 次均留下完整清单，且实证取消、断线重连与失败恢复。
2. 每个 M1 接受版本均有人类 Jury 的五项结论；模型分数不能单独使版本通过。
3. 任一 GUI 后备流程只接触副本；审计日志可证明未覆盖源文件、未发布、未购买、未上传。
4. 交付清单按媒体 profile 输出可编辑源、rights 与实际适用的生产预检项。

## 仍未宣称完成的内容

- 当前冻结仓库尚未以实机证据证明 Comfy、Illustrator 或 Photoshop 的完整运行链路；R4.1 是实施清单，不是完成报告。
- 官方 Comfy MCP 为 public beta，版本、工具和行为可能变化；上线前必须记录实际安装版本、工具清单、实例连接与回读。
- 短视频、H3、云端或 Partner provider 需在目标机器、许可和费用边界下另行资格验证。

完整研究来源、查询范围、证据账本和停止条件见 `evidence/report-source.md`。
