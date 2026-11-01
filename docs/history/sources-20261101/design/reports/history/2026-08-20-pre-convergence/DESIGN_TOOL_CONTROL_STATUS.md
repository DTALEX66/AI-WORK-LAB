# DESIGN_TOOL_CONTROL_STATUS（设计软件操控能力状态，2026-08-19）

> 重点完成设计软件操控：逐工具实证 + 诚实边界。

## 操控能力矩阵（实测）

| 工具 | 操控通道 | 实测结果 | 证据 | 状态 |
|---|---|---|---|---|
| **Open Design** | opencode CLI（run/serve/export） | 真实任务执行返回 OK；产出 AURORA 电商 hero 设计交付文档（3469 字符） | G2 真实作品（E2，已入库） | ✅ 稳定可用 |
| **ComfyUI + H3** | HTTP API（127.0.0.1:8188） | 两次真实生成（22 帧/124 帧 + FLAC 音频 + mp4） | E3 取证（已入库） | ✅ 稳定可用（GPU 环境） |
| **Photoshop 2023** | JSX（Photoshop.exe -r）+ COM | 单次成功：1920x1080 可编辑 PSD 254KB（smoke2，22:51）；后续 -r 运行全部挂起（残留进程污染，非脚本逻辑——原 smoke2 重跑也失败） | smoke2.psd（.hermes/task-runtime/ps-debug/） | ⚠️ 能力已验证但**本环境自动化不稳定**（GUI 会话残留问题） |
| **ffmpeg** | CLI（共用库） | H3 mp4 抽帧 frame60.png（324KB）成功 | .hermes/task-runtime/ps-debug/frame60.png | ✅ 稳定可用 |
| Inkscape/ImageMagick | CLI | 未安装（PATH 无） | — | 🔵 待装（共用库） |

## PS 不稳定根因（诚实诊断）

- 首次 -r 运行成功（证明能力存在）；之后所有运行挂起（EXIT=-1，PS 进程残留）
- 对照实验：原成功 smoke2.jsx 重跑也失败 → 非脚本逻辑，是 PS 会话/进程状态污染
- 处理：每次失败后 kill 进程可部分恢复，但不稳定；建议后续：重启系统后冷跑 / 改用 COM 完整流程 / 或 PS 在 GUI 会话下使用

## 已登记录入

- adapter-open-design：E2（G2 真实作品）
- adapter-comfyui / minimax-h3：E3
- adapter-ffmpeg：E0（已验证 CLI，证据补强中）
- PS：adapter E0（能力已验证一次，稳定性待环境解决）

## 结论

- 可用操控：Open Design / ComfyUI-H3 / ffmpeg（真实实证）
- PS：能力存在但本环境自动化不稳定（非代码问题，环境/会话问题），真实作品由 G2（Open Design）提供
- 待装：Inkscape/ImageMagick（共用库 OS External Configuration 可装后启用 adapter）


## 更新（2026-08-19）：Photoshop MCP 方案验证

- **Photoshop MCP**（alisaitteke/photoshop-mcp Windows-first 变体，MIT，90+ 工具）：clone + npm install + build 成功；**MCP server 已连接 PS 2023（24.5）**，工具枚举成功，real-tool-smoke 执行到 history-state 步骤（场景前置不满足，非连接问题）
- 运行时：D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-mcp/ps-mcp-win/（node dist/index.js）
- **意义**：替代不稳定的直接 JSX 路径——PS 操控走 MCP（structured state、UI fallback、fixture smoke），agent 可经 MCP 协议操作 PS
- adapter-photoshop-mcp：E1（连接验证）


## 更新（2026-08-19）：Illustrator MCP 接入

- illustrator-mcp-server（ie3jp，MIT，66 工具）：clone + install + build 成功，MCP 握手成功 + 66 工具枚举 OK
- **版本门**：工具执行被拒（'requires CC 2024 or later, current 27.5.0'）——本机 AI 2023 需升级 CC 2024+ 才能经此 MCP 操作
- 运行时：D:/All projects/DESIGN-LAB/.hermes/task-runtime/ai-mcp/ai-mcp/
- adapter-illustrator-mcp：E1（连接验证，版本受限）
