# MiniMax H3 — E3 端到端生成取证（真实运行，2026-08-16）

> 用户授权部署并执行测试。本文件为真实生成证据：workflow 提交 → 采样 → 解码 → 输出 artifact → 回读验证。
> 运行环境：ComfyUI 0.33.1 / python_embeded 3.13.14 / PyTorch 2.13.0+cu130 / RTX 5060 (8GB, async offload)

## 执行记录

- 任务（prompt_id）：`79013288-adfd-4fad-be6d-77d15e93770d`（图生视频 t2va）
- Workflow：UNETLoader(minimax_h3_fl2va_pruned_int8_convrot) + CLIPLoader(qwen3vl_32b, type=minimax)
  + VAELoader(video_vae_fp16 / audio_vae_fp32) → MiniMaxH3ImageToVideo → MiniMaxH3SigmaShift(12.0/3.0)
  → KSampler(euler/simple, 20 steps, cfg 1.0) → VAEDecode + VAEDecodeAudio → SaveAnimatedWEBP
- 参数：prompt "a calm modern corridor with soft cinematic lighting, slow steady camera"，384×384，17 → 22 帧（17k+5 网格）
- 模型加载：H3 diffusion 19995MB staged / Qwen3-VL TE 14956MB staged，动态 VRAM offload

## 输出与回读验证

- Artifact：`dl_h3_test_webp_00001_.webp`（151,538 bytes，animated，384×384，22 帧 @24fps）
- 帧回读（PIL 分析 22 帧全量）：
  - RGB 均值 (134–139, 116–121, 99–104)：暖色调稳定画面，非黑屏
  - 边缘强度 8.27–9.17：存在真实画面结构
  - 相邻帧差异 1.6–5.01（均值 2.9）：运动平滑连续，非跳变/非噪声
- 失败→恢复记录：首次用 SamplerARVideo（Causal-WAN 专用）报 5-D 要求错误；改用标准 KSampler 后成功；
  SaveVideo DynamicCombo 在 API 层不传 codec，改 SaveAnimatedWEBP 输出成功（前端 UI 可正常用 SaveVideo 存 mp4）。

## 诚实边界

- 这是**最小端到端验证**（384px / 22 帧 / 20 步）。生产级参数（分辨率 768+、时长 124–362 帧、cfg/采样调优）未做。
- 音频 latent 已随采样产出（VAEDecodeAudio 成功），但输出仅保存了视频帧动图，音频流未单独导出验证。
- 该 E3 证据绑定 ComfyUI 0.33.1 运行时与上列 prompt_id；current-tree qualification：提交 7aa0c34aefd5fee4cf4e817754f5fe835ed711ff（分支 fix/design-lab-governance-closure-r4，本地）。本文件为当前树真实运行证据（runtime_id + task_id + artifact 回读），非历史候选。


## 当前树限定（P0 云端闭环，75d2596b6063）

- 当前 main HEAD：`75d2596b6063bc15ec47a57520b2dbc585899396`（squash merge 后）。本 E3 证据在 `fix/r4-h3-prod-e3` 分支产生（f8ce6c0 祖先），经 PR #94 squash 合入 main；运行时证据绑定 ComfyUI 0.33.1 + prompt_id，与 git 树 SHA 的绑定为历史限定（squash 后 tree 变化，E3 运行证据本身仍有效，由 evidence-attestation 独立持有）。
