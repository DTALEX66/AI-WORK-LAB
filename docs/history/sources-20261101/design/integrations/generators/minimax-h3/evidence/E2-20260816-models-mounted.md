# MiniMax H3 — E2 模型挂载取证（真实，2026-08-16）

> 4 个 H3 权重已通过 ComfyUI extra_model_paths.yaml 挂载至共用模型库
> `D:/All projects/Model library/ComfyUI`（本体外置，不进 Git）。生成能力未验证。

## 挂载验证（GET /object_info 回读，2026-08-16）

- diffusion_models：`minimax_h3_fl2va_pruned_int8_convrot.safetensors`（19.53 GB）→ UNETLoader 可见
- text_encoders：`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（14.61 GB）→ CLIPLoader 可见（type=minimax）
- vae：`minimax_h3_video_vae_fp16.safetensors`（4.85 GB）、`minimax_h3_audio_vae_fp32.safetensors`（0.56 GB）→ VAELoader 可见

## 诚实边界

- status=models-mounted；capabilities（video-generation / motion-bridge）**supported=false**——无端到端生成证据。
- 未调用 MiniMax API；权重文件未修改/移动（外置原件只读引用）。
- E3 晋级需：真实 T2V workflow 执行 + 输出 artifact + provenance 读回 + 回滚验证。
