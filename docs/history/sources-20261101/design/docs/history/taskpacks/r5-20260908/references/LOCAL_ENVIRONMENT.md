# DESIGN-LAB 本机环境与外置目录

用户确认日期：2026-09-07。这是项目持久记录，不是模型/宿主验收证书。
机器路径唯一配置入口为 [`.project/paths.json`](../.project/paths.json)，诊断使用 `scripts/design_lab_doctor.py --paths --json`。换机时重新核对路径，不把本机 D 盘路径当产品安装前提。

| 配置别名 | 本机精确根 | 用途/归属 |
|---|---|---|
| design-assets | `D:/All projects/Design assets` | DESIGN-LAB 专属外置资料库 |
| model-library | `D:/All projects/Model library` | 跨项目共用本地模型库 |
| os-toolchain | `D:/All projects/OS External Configuration` | 外置共用工具链 |
| design-toolchain | `D:/All projects/Design External Configuration` | DESIGN-LAB 专属设计类工具链 |

四个根已在 2026-09-07 的初次只读检查中观察为目录。配置中的 `shared_inputs` 是“仓外复用输入”的旧字段名，不表示专属资料/设计工具链也归其他项目所有。解析器只报告声明，不自动扫描或写入这些根；项目测试产物、临时文件、环境、证据仍写本仓 `.project-local/`。资料/模型存在不代表其许可允许任意复刻、再发布或商用。

## 已知软件和模型，后续测试先从这里接续

以下为已有观测与后续审计入口，不是此刻进程存活快照；正式状态及证据新鲜度以[生成投影](../reports/current/PROJECT_STATUS.md)为准。修改本文件不会重跑或刷新旧测试时间。

| 对象 | 位置或定位依据 | 已有证据与剩余边界 |
|---|---|---|
| ComfyUI portable | `design-toolchain` 下 `toolchains/comfyui/ComfyUI_windows_portable/` | [两轮真实服务及无模型夹具](decisions/R3-COMFY-ENTRY-LIVE-2026-09-07.md)已执行；专用进程已结束。真实模型生成、运行取消和生产协议接入未完成 |
| Adobe Photoshop（PS） | 公开安装元数据：2025 / 26.7.0.15；`C:/Program Files/Adobe/Adobe Photoshop 2025`；COM 实测 26.7.0 | [原生 PSD 两次修改/重开/恢复](decisions/R3-PHOTOSHOP-NATIVE-ROUNDTRIP-2026-09-08.md)受控合成案例通过；工作台/复杂参考/UXP 实机仍未完成。[旧控制器失败](decisions/R3-READBACK-AND-H3-PREFLIGHT-2026-09-07.md)保留，不能误判未安装 |
| Adobe Illustrator（AI） | 公开安装元数据：2025 / 29.5.1；`C:/Program Files/Adobe/Adobe Illustrator 2025` | [批操作实测](decisions/R3-ILLUSTRATOR-BATCH-AUDIT-2026-09-07.md)和[恢复补测](decisions/R3-ILLUSTRATOR-RECOVERY-AUDIT-2026-09-07.md)已有原生工程；生产桥仍未完成，合法路径误拒绝及 SVG 字节差异保留 |
| MiniMax Design 软件 | 公开安装元数据：3.0.10；`C:/Users/ALEX/AppData/Local/com.minimax.hub`；exe 尚未固定 | 仅安装登记，不读取该目录私有数据；界面/API控制单独验证，不等同 ComfyUI 或 H3 |
| MiniMax H3 本地模型 | `model-library` 下 `ComfyUI/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` | [四组件固定来源全量校验](decisions/R3-READBACK-AND-H3-PREFLIGHT-2026-09-07.md)已完成；仍未加载或推理，许可适用条件未确认，不开启 profile |
| H3 text encoder | `model-library` 下 `ComfyUI/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 纳入上述四组件全量校验；不代表编码器加载或算子资格 |
| H3 video/audio VAE | `model-library` 下 `ComfyUI/vae/minimax_h3_video_vae_fp16.safetensors`、`minimax_h3_audio_vae_fp32.safetensors` | 纳入上述四组件全量校验；H3 整体加载、资源峰值和输出仍待实测 |
| Whisper ASR | `model-library` 下 `whisper/faster-whisper-large-v3-turbo/` | [CPU INT8 转写与 VAD 对照](decisions/R3-ASR-CPU-VAD-AUDIT-2026-09-07.md)已执行；无 VAD 静音误识别原件保留。只证明受控识别，不是 TTS、GPU、自然录音基准或生产资格接入 |
| OCR det＋rec 候选 | 项目 `.project-local/task-artifacts/ocr-qualification/`；隔离环境 `.project-local/task-runtime/o6-01/v/` | [固定来源及安装核验](decisions/R3-OCR-PREPARATION-BOUNDARY-2026-09-07.md)已有记录；Paddle 导入仓外缓存被拒，未加载或识别。不要重装或关闭保护求绿 |

## 禁止重复的错误

上述三款软件的安装登记观测时间为 `2026-09-06T17:25:20Z`（本地 09-07），来源为 Windows Uninstall 的 DisplayName、DisplayVersion、InstallLocation 公共字段。原始结构化记录在 `.project-local/task-artifacts/normalization-20260907/installed-software-observation.json`；版本登记不证明此刻进程正在运行或工作流已通过。

- ComfyUI 在 `toolchains/comfyui`，不是 `runtimes/comfyui`。先读本记录，再做范围有限的存在性核对，不盲目全局重装。
- MiniMax Design 软件、MiniMax H3 模型、MiniMax 云端 API 是三个不同能力，不能互相充当成功证据。
- 不从时区推定实际许可适用地区；地域/用途、资源、依赖分别核实。
- 使用隔离测试文档/工作流，保护用户正在编辑的文件，不关闭共享进程来清锁。
- 用户要求人工审计。自动运行、测试或模型自评都不能代签 Human Gate；保留产物、读回、错误、差异与回滚证据供用户验收。

## 接续入口

- [当前 R3 任务包](taskpacks/DESIGN-LAB-CLOUD-REAUDIT-TASKPACK-2026-09-06.md)
- [GPT 高难度接续包](taskpacks/DESIGN-LAB-GPT-REMAINING-2026-09-06.md)
- [DP 修订综合交接](handoffs/GPT-R3-REVISION-HANDOFF-2026-09-06.md)（资料证据，不自动改项目任务状态）

知识迁移仍延后；仓外路径登记不等于迁移、写入共享库或发布授权。
