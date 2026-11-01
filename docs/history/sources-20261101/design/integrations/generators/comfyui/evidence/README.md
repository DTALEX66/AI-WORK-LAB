# comfyui — 取证目录

- **任务**：DL-CFY-001/002
- **当前状态**：**E3 已取证（用户授权，2026-08-16）**——ComfyUI 0.33.1 真实运行 + H3 t2va 生成（prompt 79013288…/85896e88…），产物与回读见 E3-20260816-end-to-end-generation.md。
- 历史 E0 占位记录保留于下方，不删除；当前以 E3 证据为准，生成物商用/分发权利未验证（见 sidecar）。
- 本轮未启动 ComfyUI、未启动 MiniMax H3、未下载模型、未执行工作流，也未把外部运行时状态当作当前证据。
- 目录中的旧运行记录已经标记为历史候选记录，不绑定当前 exact SHA，不得用于 E3/E4 晋级或发布 gate。

## 当前可证明范围

- 仅证明仓库侧 adapter manifest、loopback/manual-launch policy 和证据目录结构存在。
- 禁止自动安装、自动下载、外部端口和隐式启动。
- 重新晋级必须在明确授权后完成真实 runtime requalification，并同时提供当前 exact tree、runtime ID/version、task ID、artifact/provenance 和 read-back。

## 权利与边界

- ComfyUI 和模型不进入仓库 vendoring 路径。
- 当前没有任何 H3/ComfyUI 运行状态、GPU 状态、模型下载状态或生成物被认定为本轮结果。

- Current-tree qualification (P0 sync): `75d2596b6063bc15ec47a57520b2dbc585899396` — E3 runtime evidence for ComfyUI 0.33.1 + H3 t2va (prompt 79013288…/85896e88…), artifacts with readback; see E3-20260816-end-to-end-generation.md. Historical E0 placeholder retained above; E3 supersedes it for current facts. Generated-artifact commercial/distribution rights remain UNVERIFIED (see sidecars).
