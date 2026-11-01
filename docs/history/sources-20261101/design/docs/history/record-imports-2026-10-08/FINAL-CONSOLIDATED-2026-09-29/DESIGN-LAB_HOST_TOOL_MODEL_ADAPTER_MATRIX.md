# 宿主、工具、模型与适配矩阵

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。


| 对象 | 能力层 | 优先级 | 版本事实 | Windows/本地/GPU | 集成方式 | 许可 | 证据 | benchmark（未执行） | fallback/rollback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Photoshop | HOST_ADAPTER | 首批 | 26.7.0.15 / COM26.7历史环境声明；当前设备未测 | Windows本地；GPU依操作 | COM/脚本；UXP按安装版本验证 | Adobe商业EULA | E1/E2，历史实机范围另见账本 | PS重开PSD、图层文字可编辑、两轮patch/readback | 手工PSD+before副本 |
| Illustrator | HOST_ADAPTER | 首批 | 29.5.1历史环境声明 | Windows本地 | 脚本/COM能力子集，UXP支持不与PS混同 | Adobe商业EULA | E1/E2；当前E3未新建 | AI源文件重开、字体链接/文字回读 | 手工AI/PDF及before副本 |
| Figma | HOST_ADAPTER | 第二批 | 本轮未固定客户端版本 | 云/桌面；无需专用GPU | 官方Plugin/API/MCP可用范围；权限由用户配置 | 服务条款/插件许可分别核对 | 规划/结构E0–E1；不认证产品接入 | 组件/变量/布局/字体往返、可编辑handoff | 文件/规范导出 |
| Penpot | HOST_ADAPTER | 第二批 | 上游pin见OSS | 自托管可本地；Windows浏览器 | Plugin/API或文件交换 | MPL-2.0代码；素材另计 | E0–E1 | 组件/token/图层往返 | SVG+token+handoff |
| Blender | HOST_ADAPTER | 后续DL-R5-020 | 上游pin见OSS | 本地；GPU按渲染器 | Python adapter；MaterialX/USD/OCIO按需 | GPL；扩展与素材另计 | E1规划 | blend场景、材质、依赖重开 | 原场景副本/手工渲染 |
| InDesign | HOST_ADAPTER | DEFERRED | 未取得本机版本 | 本地Windows | 官方脚本/插件版本矩阵 | Adobe商业EULA | E0–E1方法 | 排版、缺字、链接、打包、印前 | 手工package/PDF |
| Premiere / After Effects | HOST_ADAPTER | DEFERRED | 未取得本机版本 | 本地；GPU按任务 | 官方脚本/插件，OTIO仅中间层 | Adobe商业EULA | E1规划 | 可编辑轨道/工程/媒体重定位，不仅mp4 | 手工工程包 |
| Eagle | TOOL_PROVIDER | EVALUATE | 未取得本机版本 | 本地；官方API端口41595 | 只读资产查询起步，授权后特定写入 | 商业EULA；不能视为开源 | E0–E1规划 | 来源标签、重复、丢失路径、失败回退 | 普通文件导入 |
| Open Design | HOST_ADAPTER | 可选 | nexu-io/open-design pin见OSS | 外部客户端；本地/云能力依配置 | client/host adapter | Apache-2.0代码；外部服务另计 | 协议/结构E1，CI子集E2 | DL对象→宿主→回读，禁全局配置接管 | standalone工作台 |
| OpenPencil | HOST_ADAPTER / UX_DONOR | 可选 | 上游pin见OSS | 桌面/网页依上游 | 文件/插件能力待实测 | MIT代码 | E0–E1 | 可编辑图层和样式往返 | Figma/Penpot或文件交付 |
| MiniMax Design | 外部CLIENT/HOST | EVALUATE | 3.0.10为历史本机声明 | 官方Windows客户端；服务依供应商 | 独立app launcher / 文件handoff | 商业产品条款；非模型license | E0/E1当前资格 | 完成一个Brief及可编辑输出检查 | 已有Adobe；不依赖该client启动DL |
| MiniMax H3 | MODEL_PROVIDER | DL-R5-018专项 | 官方MiniMax-AI/MiniMax-H3 pin见OSS | Base可本地；IR为hosted；GPU未基准 | Comfy插件/模型适配，拆分组件资格 | Community权重条款，代码/服务分别检查 | 本地文件校验≠推理E2；当前E0/E1 | Base加载/生成/内存；hosted IR独立追踪 | 其他模型/手工素材 |
| MiniMax Comfy plugin | TOOL_PROVIDER | EVALUATE/BLOCKED许可 | 官方仓名minimax-desgin-plugin | Comfy sidecar | 插件版本固定，网络能力显式 | 未取得明确LICENSE，不自动分发 | E0/E1 | API错误、计费/网络提示、取消、产物归属 | 标准Comfy/手工client |
| ComfyUI | SIDECAR / TOOL_PROVIDER | DL-R5-008 | 历史0.33.1；上游最新pin不等于本地升级 | portable；GPU按模型 | HTTP/WS/history/取消；专用实例生命周期 | GPL-3.0代码；节点/模型各有条款 | 历史model-free真实任务；当前stale/unsupported不得漂白 | 10次真实模型任务、断连/取消ACK、PNG与history回读 | 文件导入；不改用户既有实例 |
| Qwen-Image / Wan2.2 / Hunyuan3D | MODEL_PROVIDER | EVALUATE/DEFERRED | 各上游pin见OSS | 本地潜力；显存待测 | 受控provider，禁止硬编码默认 | 逐模型权重条款；Hunyuan有地域限制 | E0/E1 | 授权任务集+质量/时延/显存/失败率 | 云provider或宿主手工作业 |
| OCR / ASR / TTS / Music | TOOL/MODEL_PROVIDER | 按R5后置 | OCR5合成样例/ASR CPU INT8为历史受控范围 | 本地可选；硬件依模型 | 领域辅助工具，非全局语音平台 | 模型/工具分别审核 | OCR/ASR旧受控不证明TTS或音乐 | 真实文字识别/字幕同步；生成需另建证据 | 手动文字/授权音频 |
| MCP Inspector | SIDECAR | 局部诊断 | pin见OSS | 本地诊断，无专用GPU | 只连接用户选定设计适配器 | 许可迁移按pin审核 | 外部工具；DL集成未认证 | schema/超时/取消/权限/脱敏 | 内置只读状态+日志 |

## 供应商一手入口

- Photoshop: https://developer.adobe.com/photoshop/uxp/
- Illustrator: https://developer.adobe.com/illustrator/
- Figma: https://developers.figma.com/docs/plugins/
- MiniMax Design: https://design.minimax.io/en
- H3: https://github.com/MiniMax-AI/MiniMax-H3 与 https://huggingface.co/MiniMaxAI/MiniMax-H3
- Eagle API: https://api.eagle.cool/

H3 官方说明中 hosted Context/IR、本地 Base 与高分辨率 regenerate 的开放情况分开，不能宣传离线全链。一个名称相近的 `MiniMax-design-H3/minimax-design` GitHub 仓没有获得官方网站归属佐证，本包仅作未验证参考，不当官方分发源。

任何实际启动/写入宿主的下一轮都应使用隔离测试项目；本轮没有执行这些操作。
