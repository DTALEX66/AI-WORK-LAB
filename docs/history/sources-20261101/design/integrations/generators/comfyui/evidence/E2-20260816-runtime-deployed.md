# ComfyUI — E2 部署取证（真实运行，2026-08-16）

> 用户明确授权部署运行。本文件为**真实运行快照**，不冒充生成能力证据。
> 证据等级：E2（隔离运行 + 模型挂载回读）。E3 需要真实 workflow 执行 + artifact/provenance 读回。

## 运行快照（probe 时间 2026-08-16）

- 服务：http://127.0.0.1:8188（loopback-only，手动启动，非自动安装）
- 进程：python_embeded\python.exe（PID 25940，快照时）
- HTTP GET / → **200**（页面标题 ComfyUI）
- GET /system_stats → cuda:0 NVIDIA GeForce RTX 5060（VRAM 8150 MB，driver 595.97，cudaMallocAsync）
- ComfyUI 0.33.1 ｜ Python 3.13.14 ｜ PyTorch 2.13.0+cu130 ｜ frontend 1.48.7 ｜ aimdo 0.4.13
- 启动命令（含可写目录重定向）：
  `python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --port 8188 --disable-auto-launch --output-directory <runtime>/output --temp-directory <runtime>/temp --input-directory <runtime>/input --user-directory <runtime>/user`

## 模型挂载（extra_model_paths.yaml → Model library/ComfyUI）

- UNETLoader.unet_name → `minimax_h3_fl2va_pruned_int8_convrot.safetensors`（19.53 GB）
- CLIPLoader.clip_name → `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（14.61 GB，type=minimax）
- VAELoader.vae_name → `minimax_h3_audio_vae_fp32.safetensors`（0.56 GB）+ `minimax_h3_video_vae_fp16.safetensors`（4.85 GB）

## 限制与诚实边界

- **未执行 H3 推理 workflow**：图像/视频生成能力（supported）仍为 false；8GB VRAM 下 H3 fp8/int8 需要 CPU offload，端到端生成未验证。
- 数据库写 portable user/ 被本会话沙箱拒绝（WinError 5），服务器以 RAM 缓存模式运行（非致命）。
- 桌面快捷方式：`ComfyUI.url` + `启动ComfyUI.cmd`（C:\Users\ALEX\Desktop）。
- 本文件为部署级（E2）证据；E3 晋级需完成真实生成任务并回读 artifact。
