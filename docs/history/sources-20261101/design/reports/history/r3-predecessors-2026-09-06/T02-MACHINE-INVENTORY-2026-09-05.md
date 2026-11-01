# T02 — Windows 软件与模型能力盘点（只读，2026-09-05）

> 任务来源：DESIGN-LAB-MULTIMODAL-TASK-PLAN-2026-09-05（T02）。
> 方式：只读探测（Win32_CIM / 路径存在性 / 版本文件），**未启动任何宿主软件、未安装、未下载**。E 盘受保护，未触碰。
> 状态口径：`发现`=路径存在；`可连接/可读取`需另行实机确认，本报告不冒充"已验证"。

## 机器事实

| 项 | 值 |
|---|---|
| OS | Windows 11 (10.0.26100) |
| CPU | Intel Core i5-14600KF（14 核） |
| RAM | 63.8 GB（68,487,733,248 B） |
| GPU | NVIDIA GeForce RTX 5060（报告 AdapterRAM ~4 GB 为 WMI 上限失真；显存实值需 nvidia-smi） |
| 驱动 | 32.0.15.9597 |
| 磁盘 | C: 476.6G/224.7G 空；D: 465.8G/218.1G 空；F: 1862.6G/940.2G 空（E: 3.7T 受保护，未访问） |
| 显示器 | 2560×1440 |

## 宿主软件（Adobe）

| 软件 | 发现 | 版本（可执行文件版本） |
|---|---|---|
| Adobe Illustrator 2023 | C:\Program Files\Adobe\Adobe Illustrator 2023 | （未细读） |
| Adobe Illustrator 2025 | C:\Program Files\Adobe\Adobe Illustrator 2025 | **29.5.1**（Illustrator.exe） |
| Adobe Photoshop 2023 | C:\Program Files\Adobe\Adobe Photoshop 2023 | （未细读） |
| Adobe Photoshop 2025 | C:\Program Files\Adobe\Adobe Photoshop 2025 | **26.7**（Photoshop.exe） |

备注：本报告与更早"已卸载/未安装"的记录冲突 —— 当前机器**已安装 AI 2025(29.5.1) 与 PS 2025(26.7)**。这对 T03/T07（Illustrator 官方 MCP / adb-mcp / Photoshop MCP 实机对比）是重要前提：CODEX 侧可做实机测试。是否可读取/可修改/可导出/重开验证，仍需后续实机案例。

## 生成 / 三维 / 其他

| 项 | 结果 |
|---|---|
| Blender Foundation | 未发现（C:\Program Files\Blender Foundation 不存在） |
| ComfyUI | 常见路径未发现（D:\ComfyUI / C:\ComfyUI / D:\All projects\ComfyUI 等均无） |
| Stable Diffusion WebUI (A1111/Forge) | 未发现 |
| FFmpeg | （待查 PATH/版本） |
| MiniMax Design 桌面客户端 | 未探测（默认非扫描范围；可在 T14 单独核对） |
| Open Design | DESIGN-LAB 仓内 Open Design host adapter / 安装器存在（integrations/hosts/open-design），桌面应用本体状态未知 |

## 模型缓存（只读发现，非运行证据）

- `C:\Users\ALEX\.cache\huggingface\hub`：PaddleOCR 系列（PP-LCNet、PP-OCRv6 det/rec、UVDoc）、faster-whisper（base/tiny）—— 与 T06 拆解/OCR、T10 音频相关候选。
- `C:\Users\ALEX\.cache\modelscope\models`：`iic--SenseVoiceSmall` —— 音频候选。
- 未见图像生成 checkpoint（SD/Comfy 模型目录未发现）。

### 模型就绪实测（2026-09-05，src/design_lab/analysis/model_cache.py 只读探测）

| 后端 | 判定 | 依据 |
|---|---|---|
| ASR（faster-whisper base/tiny） | **READY** | snapshots 含真实字节（base model.bin ~145 MB） |
| OCR（PaddleOCR PP-OCRv6 det/rec 等） | **NOT_READY（INCOMPLETE）** | 仅 refs 指针，无 snapshots 字节（未实际下载） |
| SenseVoiceSmall（modelscope） | 未在本报告判定（单独探测） | — |

结论：音频 ASR 模型本地已就绪；OCR 模型**未就绪**（不能宣称可用，fail-closed）。图像生成模型未发现。

## CLI / Agent（存在性）

- `codex.cmd`：C:\Users\ALEX\AppData\Local\hermes\bin\codex.cmd（存在；**codex-cli 0.153.1**）
- `dsh.cmd`：DSH Desktop host-commands（存在）
- git / gh / scoop python / nodejs-lts：均在 PATH 上
- uv：hermes 侧 uv.exe（C:/Users/ALEX/AppData/Local/hermes/bin/uv.exe）
- ffmpeg：`D:\All projects\OS External Configuration\10-toolchains\scoop\apps\ffmpeg\current\bin\ffmpeg.exe`（存在）

## GPU 实测补充（2026-09-05 nvidia-smi 只读）

- NVIDIA GeForce RTX 5060，**显存 8151 MiB（~8 GB）**，驱动 595.97。
- 意义：H3/图像大模型/Blender 同时跑会争显存；任务排队纪律（计划 §8）在此硬件上必须执行，单模型峰值需按 8 GB 预算。

## 缺口与下一步（待实机项，不冒充完成）

1. RTX 5060 真实显存与 CUDA 版本：需 `nvidia-smi`（只读命令，未执行——本轮未跑）→ 可补。
2. AI/PS 可读取/可导出/重开：需 T03/T07 实机案例。
3. ComfyUI：当前机器未发现安装；T09 生成入口需先部署/指向一套 ComfyUI（或明确阻塞）。
4. Blender：未安装；T15 需安装（实机，非本轮）。
5. H3 本地：权利门未清 → 保持 `BLOCKED_BY_LICENSE`，不做本地运行声明。

## 更新记录

- 2026-09-05：初版只读盘点（本文件）。
