# DESIGN-LAB GPT 高难度接续 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans（若可用）逐项执行并保留审查节点；此处是接续与派工计划，不是批准发布或扩大权限。步骤使用 checkbox 跟踪。

**Goal:** 在保留既有成果和 R3 依赖的前提下，由 GPT 完成核心运行行为、真实推理与设计生产闭环。

**Architecture:** DEEPSEEK 提交限范围的资料/验收输入，GPT 单写整合核心代码、证据与正式 ledger。任务准备可以提前，但整项完成必须满足原始依赖、真实宿主和 Human Gate；H3 不阻塞 M1。

**Tech Stack:** Python/SQLite、Windows、现有 reconstruction；后续产品 Python 3.12、TypeScript 工作台、Adobe 宿主桥、ComfyUI 按 R3 执行，不另起算法重写。

**Spec:** [R3 权威任务包](DESIGN-LAB-CLOUD-REAUDIT-TASKPACK-2026-09-06.md)。本文件只拆分职责，不修改验收合同。

## Global Constraints

- 独立运行；WORK-LAB/ArcheAxis 默认关闭，Open Design 为可选 adapter。
- 所有运行/缓存/证据在项目 `.project-local/`；不写 `.hermes` 或共享库。
- 知识迁移延后；凭据、私有 Agent 数据与 E 盘不访问。
- 同一 checkout 单写；当前是未提交工作树，不从 HEAD 新建 worktree 后误以为拥有全部成果。
- 不自动 commit/push/PR/merge/release；最终发布要单独确认 exact side effect。
- DEEPSEEK 输出只作候选输入；它不能给模型 trust、人审或正式账本盖章。
- 原 13 项 GPT 范围：R3-01/02/03/04/05/06/07/08/09/10/13/16/24。其余 R3 高难度项列为后续接续归属，执行需保持原包授权与宿主/发布门，不因本次拆分自动安装/调用/发布。

## 1. 接管基线和已完成代码

仓库 `D:/All projects/DESIGN-LAB`；分支 `codex/r3-runtime-correctness`；HEAD `c4dccd58331bc4561eb89265283d924b7630d113`。2026-09-06 的修改尚未提交，当前树还含未跟踪源码/配置/测试。接管先读取 `git status --short` 和当前 AGENTS；不要覆盖未知变更。

正式状态及依赖实时读取[账本生成投影](../../reports/current/PROJECT_STATUS.md)，不在本接续包维护第二份状态表。DONE_LOCAL 不是已上传、实机验收或发布。2026-09-07 已有新增 ASR、ComfyUI、H3 完整性和 Illustrator 受控证据；下文旧断点仅作历史保留，不得覆盖这些新增观察。

已有实现及应复用路径：

| 模块 | 实际文件 | 已做/剩余边界 |
|---|---|---|
| 状态投影 | `src/design_lab/governance/reporting.py`、`scripts/generate_current_reports.py` | 冻结定义/源与证据 hash、四轴与过期降级；正式输入 `design-lab/config/task-ledger-r3.json` |
| 路径 | `src/design_lab/runtime/paths.py`、`migration_preview.py`、`.project/paths.json` | 中央运行根、foreign CWD、reparse 防护、只读迁移预演；真实多入口追踪未齐 |
| 任务恢复 | `attempt_contract.py`、`operation_coordinator.py`、`job_store.py`、`state_store.py`（均在 runtime 下） | Operation/Attempt、重试、取消/对账、恢复及持久化已修；勿退回旧成功语义 |
| 资产 | `src/design_lab/runtime/asset_store.py`、`design-lab/schemas/state/*-v2.sql` | 事务、独立产物身份、发布恢复、租约/fencing；整项仍受路径及真实工作流约束 |
| Profile | `src/design_lab/runtime/profile_resolver.py`、`design-lab/config/profiles.json` | 四类用途条件及新鲜证据硬过滤；7 个候选默认禁用，不以代码测试批准真实 profile |
| 模型 | `src/design_lab/analysis/model_manifest.py`、`model_cache.py` | 独立信任、完整 hash/size/分片/链接校验；结构探测最高 WEIGHTS_COMPLETE，不产生实际推理资格 |
| Doctor | `src/design_lab/runtime/doctor.py`、`scripts/design_lab_doctor.py` | 正确 ffmpeg 参数、退出码/版本/路径来源；版本查询不等于插件工作流 |

## 2. GPT 执行切片与验收

每个切片先读表列文件及其 usages；行为变更用真实负例 RED→GREEN→定向回归。不要在旧测试输出目录重跑覆盖证据。完整任务依赖仍读取原包/ledger，以下是优先实现顺序而非新 DAG。

### G-01：接管、资料复核与 CI/路径剩余缺口（R3-02/03/04）

- [ ] 接收 DEEPSEEK 的 `docs/handoffs/deepseek-r3-20260906/`，核对源 hash、记录数量、缺失范围和越界文件。
- [ ] R3-03 逐条验收原清单/occurrence，涉及私密原文或新归档授权先停；不要把摘要拼成原文。
- [ ] 接续[规范化审计](../decisions/R3-NORMALIZATION-2026-09-07.md)：workflow 顶层路径过滤已移除、renderer 已固定校验；复核当前源码与绑定后补干净 checkout／exact-SHA CI，勿重复写同一修改，勿把本地检查当托管 CI。
- [ ] R3-02 补项目实际入口写入追踪，不擅改全局 Agent 配置、IDE 或 Adobe scratch。实际 DB/缓存迁移另需精确范围及备份，不将 preview 当迁移成功。

验收：原 R3-02/03/04 每条条件都有证据或明确缺口；CI exact SHA 未跑就保持未执行；不删除现有 gate 求绿。

### G-02：真实 OCR/ASR 与模型就绪资格（R3-08，依赖 R3-02）

- [x] ASR 固定来源五文件校验、专用环境安装与真实 CPU INT8 转写已有[审计与原件](../decisions/R3-ASR-CPU-VAD-AUDIT-2026-09-07.md)。此勾选只覆盖该受控实验，不是 R3-08 整项完成。
- [ ] 复用 `.project-local/task-runtime/asr-qualification/20260906T195532284136Z/venv/` 和模型库，先核对绑定，不重装主 venv/Comfy。早期 `r3-asr` 目录不是当前有效环境。
- [ ] 将来源/加载/转写证据接入产品就绪与失效规则；source integrity 不代替 owner/rights 审批。
- [ ] 将静音误识别的 VAD 对照约束用于后续生产设计；保留无 VAD 失败。CPU 合成音频结果不证明自然录音、GPU、TTS 或 H3。
- [ ] 从[OCR 隔离阻塞](../decisions/R3-OCR-PREPARATION-BOUNDARY-2026-09-07.md)继续：官方 det/rec 已下载校验、短路径环境已安装，导入仓外缓存被拒；先解决可审查的隔离路线，再实际检测识别，不将安装通过升级为推理通过。
- [ ] Windows native symlink WinError 1314 仍未执行；不私自提权、开启开发者模式或改系统配置来隐去跳过。

验收：R3-08 完整原条件；缺任一实际模型/资源证据保持 PARTIAL。读取 `design-lab/tests/test_model_manifest.py`、`test_model_cache.py`、`test_doctor_evidence.py`，扩展有意义的失败/成功测试而非改断言认 READY。

### G-03：资产剩余实测与产品服务（R3-06/09）

- [ ] 复核 asset_store 对实际保存三版本、I/O失败、并发发布、崩溃重启的语义，保留旧字节及 DB。
- [ ] 读取 `pyproject.toml` 与现有 reconstruction 门面，按 R3 建 installable 包/CLI/本地 API；锁定产品 Python 3.12，当前 3.13 测试不得冒充 3.12 资格。
- [ ] 合同先固定，再做项目/导入/任务/事件/产物/修改/取消/导出；服务重启后任务与资产恢复，foreign CWD 干净安装验收。

验收：不复制旧算法另写；实际任务贯穿资产、状态、适配器与产物，旧 CLI兼容。测试目录延续 `design-lab/tests/`，新接口的准确签名在实施切片设计时固定，不在交接凭空编造。

### G-04：工作台与运行适配（R3-10）

- [ ] 在 R3-09 服务合同上实现 `apps/workbench`；选型一次记录，不反复调研。
- [ ] 完成真实导入、任务/失败/取消、局部修改、工程下载，刷新/重启恢复；loopback token/Origin与素材指令隔离由 GPT 实作和验证。
- [ ] Codex RuntimeAdapter 按当前官方接口验证；不更改用户全局 profile，不要求 WORK-LAB/ArcheAxis。

验收：服务证据驱动 UI 状态，不能用静态 mock 界面标 M1。截图只作辅助。

### G-05：参考图拆解接入（R3-13）

- [ ] 使用 DS-08 候选经 rights 核对后确定 5—10 图测试集，其中必含 R3 三类；不下载/复刻权属不明素材。
- [ ] `packages/capabilities/reconstruction/` 及现有 RIR 门面接真实 OCR、区域、几何、层级、稳定对象 ID、用户修正。
- [ ] 可矢量、透明栅格、隐藏区推断分开；文字可编辑与字体替代透明记录，不能整图贴回冒充重建。

验收：真实输入产生非预填对象计划，可映射 AI/PS；误差、结构、可编辑性分别测。像素级是目标，不能无条件承诺任意图无损恢复源矢量或隐藏结构。

### G-06：ComfyUI 真正集成（R3-16）

- [ ] 复用 `integrations/generators/comfyui/`，真实 REST/WS 关联 prompt_id/client_id/history/outputs。
- [ ] 工作流拓扑/节点版本/模型 revision+hash/参数形成完整指纹，路径限制任务根并校验媒体。
- [ ] 真实生成一图、重复缓存、取消对账、断线重连逐个验证；缓存必须标复用，禁止作为本次新推理。

验收：R3-05/06/07/08/09 前置及真实四场景通过，产物进入同项目资产库；默认一个实例，不私自停止用户已有 ComfyUI。

### G-07：高难度后续保留项（不是 DEEPSEEK 实现任务）

| 原任务 | GPT 接续内容 | 不得省略的门 |
|---|---|---|
| R3-11/12 | Illustrator / Photoshop 默认桥、文档身份、原生对象、保存重开、读回、失败回滚 | 使用当前宿主实际版本，固定任务文档；保护用户正在编辑的文档 |
| R3-14 | 两宿主 UI→制作→两次局部修改→保存重开，对照与修复 | 视觉/结构/编辑性/人审分开，不能单 SSIM 验收 |
| R3-15 | Windows 可用 M1 包、冷暖启动、升级恢复 | AI+PSD 双原生闭环、前端、CI与 Release gate |
| R3-17/18 | TTS、音乐真实生成及版本资产 | ASR≠TTS、混音≠分轨，各自真实音频验收 |
| R3-19 | H3 许可适用、硬件/算子与短推理 | 地区/用途/资源各自核实，本地真实结果，不用云端或缓存冒充 |
| R3-20 | 原生 Premiere 20—30秒可编辑工程 | FFmpeg MP4不能替代原生工程；此前15秒实验目标单独标注 |
| R3-21/22 | 可选软件真实回流、Blender 多对象/多视角重建 | MiniMax模型不是Design软件；3D不能单面贴整图 |
| R3-23/24 | 跨媒体依赖失效、选择性重建、打包、维护与发布 | 原 DAG、人审、exact SHA CI、发布授权与云端读回 |

## 3. 当前接续：复用证据，只补真实缺口

- ASR：[CPU/VAD 审计](../decisions/R3-ASR-CPU-VAD-AUDIT-2026-09-07.md)。转写已运行；下一步是产品资格接入和真实语音范围验证，不是再次从 HTTPS EOF 起步。
- OCR：[准备与边界审计](../decisions/R3-OCR-PREPARATION-BOUNDARY-2026-09-07.md)。不可重复已失败的下载 URL、重装相同依赖或关闭路径保护。
- ComfyUI：[真实入口审计](../decisions/R3-COMFY-ENTRY-LIVE-2026-09-07.md)。已测 REST/WS、无模型夹具、缓存、重连；进程已结束。生产任务协议、模型生成、运行取消与持久恢复待做。
- Illustrator：[批操作](../decisions/R3-ILLUSTRATOR-BATCH-AUDIT-2026-09-07.md)和[恢复补测](../decisions/R3-ILLUSTRATOR-RECOVERY-AUDIT-2026-09-07.md)。诊断能工作不代表生产桥完成；Windows 合法路径误拒绝的修复设计待确认。
- H3/PS：[完整性与启动审计](../decisions/R3-READBACK-AND-H3-PREFLIGHT-2026-09-07.md)。H3 四权重校验及 Torch 设备查询已执行，但未推理；PS 控制入口失败不证明未安装，不重复相同失败启动。
- 服务、工作台、双 Adobe 产品桥、参考拆解与局部修改仍是 M1 主线；H3、可选软件与完整历史恢复不拖住 M1。知识迁移继续延后。

### 3.1 2026-09-06 早期 ASR 断点（历史原文，已由上文取代）

以下保留失败过程与当时环境，不作为当前执行命令或重新安装指令；其中“尚未”“未发现”“当前”等均指该早期检查点。

脚本：`.project-local/task-artifacts/r3-execution/prepare_asr_sources.py`。
失败：Python urllib 首次读取公开 HF API 出现 `[SSL: UNEXPECTED_EOF_WHILE_READING]`；同 API 的 PowerShell `Invoke-RestMethod` 当时成功。未关闭 TLS；未安装新依赖；未下载模型权重；尚未取本地权重完整 hash。

脚本失败前已建：`.project-local/task-artifacts/r3-execution/asr-live/`（本次交接检查为空）及 `.project-local/task-runtime/r3-asr/` 下 tmp/cache/hf/torch/triton/cuda。脚本当前 `mkdir(exist_ok=False)`，原样重跑会先遇目录存在错误。先确认当前内容及所有权，改为安全可恢复或使用新 run 目录，保留旧错误；不删除目录解决。

Whisper 本地：`D:/All projects/Model library/whisper/faster-whisper-large-v3-turbo/`。
已见五文件：model.bin 1617884929 bytes；config.json 2263；preprocessor_config.json 340；tokenizer.json 2710337；vocabulary.json 1068114。主 venv 和 Comfy 内嵌 Python 都未发现 faster_whisper/ctranslate2；主 venv 也无 torch/av，Comfy 内嵌有 torch/av。这里只是模块定位检查，不是 import/加载成功。

公开来源旧 mobiuslabsgmbh URL 重定向到 [dropbox-dash 模型卡](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo)。此前 API 返回 revision `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`，model.bin 上游 LFS SHA256 `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da`，许可元数据 MIT；使用前固定 revision 并重取可持久化来源。
小文件须核对官方 Git blob ID，再推导 SHA256，不能直接相信本地文件。

ASR 候选依赖 faster-whisper 1.2.1；[官方文档](https://github.com/SYSTRAN/faster-whisper)支持 CPU INT8，transcribe 的 segments 必须迭代才真正推理。GPU 的 CUDA/cuDNN要求另核；不能假定 Comfy cu130 环境直接适配。

真实 Comfy 路径：`D:/All projects/Design External Configuration/toolchains/comfyui/ComfyUI_windows_portable/`。不是 `runtimes/comfyui`；不要再搜错目录或全局重装。调用前将 output/temp/input/user 及模型工具缓存显式限制在本项目，不更改共享安装。

## 4. 早期 H3 调研接收记录（历史保留，不等于本地资格）

本节“本地未全 hash 比对”是早期观察，已由[四文件全量校验](../decisions/R3-READBACK-AND-H3-PREFLIGHT-2026-09-07.md)取代。保留原报告值与差异过程；不要再次将历史 main 指针当最新来源。完整性通过仍不代表模型加载、推理、许可审批或 profile 启用。

只读研究返回 Comfy revision `4cc1d817b6184899b41293954329f576cb5ae86b`，MiniMaxAI revision `42ed227ee7df40d41602854ae760620d6eb651fe`。下表是官方 LFS 指针报告值，本地未全 hash 比对；diffusion固定 revision读取成功，两VAE值来自当时 main，必须补固定 revision读回后才能声称整包绑定。

| ComfyUI 模型相对路径 | bytes | 上游 SHA256 |
|---|---:|---|
| diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors | 20970379616 | e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a |
| text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors | 15687142551 | 35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6 |
| vae/minimax_h3_video_vae_fp16.safetensors | 5207808496 | 7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522 |
| vae/minimax_h3_audio_vae_fp32.safetensors | 605254808 | 8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48 |

来源：[Comfy 模型](https://huggingface.co/Comfy-Org/MiniMax-H3)、[原始模型](https://huggingface.co/MiniMaxAI/MiniMax-H3)、[许可证](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE)、[官方 FAQ](https://design.minimax.io/h3)。研究报告提示许可有地区排除，个人研究不能豁免地区条件；不得从 Asia/Shanghai 时区推定实际地区。商业 FAQ 与 Comfy 支持页表述有差异，需核对具体用途，不写永久全局禁用。此处不作法律审批结论。

此前采样 RTX5060 8151MiB，总量/空闲只为当时观测；实际峰值未测。历史2026-08-16短视频成功日志不是当前验证，不能标本轮 H3 完成。

## 5. 错误、测试与返回条件

| 已遇问题 | 正确接续 |
|---|---|
| urllib HTTPS EOF | ASR 后续来源核验已完成；保留早期 TLS 失败，不重回该断点 |
| 模型仅少量文件曾报 READY | 已修；不回退，以独立来源/完整权重/加载/推理分级 |
| ffmpeg --version/错误版本解析 | 已修；实际 `-version` 回归保留，开发者字符串不等于 prerelease |
| WinError 1314 | 原生链接测试跳过，不计 PASS；不自动提权 |
| PS 精确进程名查询无结果 | 搜索范围无匹配，不证明 PS 关闭/显存占用 |
| ASR 环境缺包、Comfy 路径查错 | 环境与路径问题，不是产品算法回归，不重复全局安装 |
| 原始归档 CRLF/LF hash差异 | 保留原字节；仅已记录的末尾LF规范化可单独验证，不重写原件 |
| 旧全仓扫描进入临时DB | 已收紧扫描边界；被忽略证据另核，不能删除证据逃门 |
| SQLite锁/仓外空残留清理拒绝 | 保留现场，不改ACL、不杀共享进程或重试删除 |

早期测试快照（非当前最新）：`.project-local/task-artifacts/r3-execution/model-readiness-final/results.json` 时间 2026-09-06 19:10:05 +08:00；focused 9.024秒，unified 74.802秒；280 passed +1 skipped，49统一门通过。后续各轮测试见[生成进度及证据绑定](../../reports/current/TASK_PROGRESS.json)；文档更新时间不代表再次全量测试。

每次接续先检查 evidence subject_files 当前 hash；源码变了旧 PASS 必须重新验证，不能改旧日志或给旧 receipt 重盖时间。正式 ledger 更新后运行生成器，再 `--check`；最终区分 IMPLEMENTED_LOCAL、TESTED_LOCAL、host_live、exact-SHA CI、publication。只汇报真的已完成部分，不因为 DEEPSEEK 资料齐全就提升 M1。
