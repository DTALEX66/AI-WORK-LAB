# 声明模型库实况清点 · 2026-10-07

**观测 exact SHA**：`main` = `a0aaa5b0`；本机声明根 = `D:/All projects/Model library`（由
`.project/paths.json → shared_inputs.model-library` 解析，**不是猜路径**）
**观察窗口**：2026-10-06T23:43Z–23:48Z
**动作**：`scripts/inventory_model_library.py`（默认 DRY，`--apply` 才写）把
`design-lab/config/external-assets-index.json` 从 **5 条** 清点到 **24 条**；
`VERIFY_EXTERNAL_ASSETS_INDEX=PASS assets=24`；新增一致性闸门
`test_external_assets_index_consistency.py`（7 项，全绿）。

## 一、清点出来的事实

声明根里实测 24 个模型权重文件，索引此前只登记 5 个（4 个 H3 + 1 个隔离资产）。
**19 个此前无人登记**，其中成规模的缺口有三处：

| 缺口 | 实测内容 | 为什么重要 |
|---|---|---|
| 完整 SDXL 图像生成栈 | `ComfyUI/diffusion_models/sd_xl_base_1.0.safetensors` + `text_encoders/clip_l.safetensors` + `clip_g.safetensors` + `vae/sdxl_vae.safetensors` | 项目有一条 image-generation 能力面，本机其实**已有可用权重栈**，但雷达/索引/能力计数都不知道它存在 |
| 视觉-语言与向量类 | `ggml-org/Qwen2.5-VL-7B-Instruct-GGUF/{Q4_K_M, mmproj-Q8_0}`、`Qwen/Qwen3-Embedding-0.6B`、`Qwen3-Reranker-0.6B` | `model_assets.py` 的 family 白名单里**本来就有** `embedding` 与 `vision-language`，即合同允许、资产也存在、登记为零 |
| 两套额外 ASR 引擎 | `sherpa-onnx/sense-voice…/model{,.int8}.onnx`（5 文件）+ `sherpa-onnx-streaming-zipformer-zh-14M…/{encoder,decoder,joiner}{,.int8}.onnx` | 雷达里 asr 只有 whisper 一条；`model_cache.MODELSCOPE_CANDIDATES` 写的 `iic/SenseVoiceSmall` 其实就是 SenseVoice 的 sherpa 导出，此前两边互相看不见 |

另有 `whisper/faster-whisper-large-v3-turbo/model.bin`：雷达**已经**以
`model-library:whisper/faster-whisper-large-v3-turbo` 引用它，但索引里没有——
同一资产两套记录不一致。清点时按雷达别名交叉引用，在 `note` 里写明
`already referenced by model-radar entry whisper-large-v3-turbo`。

## 二、权利姿态：清点不等于声称拥有

- 所有新登记项一律 `owned_by: "unattributed"` + `status: "review-required"`，
  `note` 明写 `licence not adjudicated`。
- **不从目录名推归属**：我第一版把 `ComfyUI/` 下的文件一律写成 `DESIGN-LAB`，
  那是错的——同一棵树下既有本项目的 H3 权重，也有社区常规下载
  （`sd_xl_base_1.0`、`clip_l/g`、`sdxl_vae`）。"挨着我们的文件"不是所有权证据，
  该规则已删，并由测试 `test_ownership_is_never_inferred_from_a_directory` 钉住。
- 这些许可多半**不是**本项目的 MIT（SDXL 系属 openRAIL-M 家族、Qwen 与 sherpa 各有条款），
  按 `AGENTS.md`「许可冲突 / 零 checksum 必须 fail closed」与
  `THIRD_PARTY_ISOLATION`「第三方许可随库保存、不混入项目许可面」，
  裁决属 Human Rights gate，**不由 agent 填写**。

## 三、顺手量到的一处残留

`runtimes-tmp/reranker-dl.gguf` = **494,879,360 B（约 472 MiB）** 下载中间产物，
留在声明根里。清点**刻意不把它登记成资产**（`RESIDUE_DIRS` 排除，并有测试断言
`runtimes-tmp/` 下不得出现登记项），因为登记一个 scratch 文件等于给脏数据发户口。
删除它属于跨项目共享根上的破坏性动作，需 owner 确认；本机不擅动。

## 四、"缺模型就下载"这一半：本轮明确不做，理由如下

目标句是「补齐缺失模型与工具到声明的库根」。工具半边已完成并合入
（#250：`node`/`ffmpeg` 由声明根绑定，`path_source=declared:…`，`drift=[]`）。
模型半边雷达记 8 条 `ABSENT`（omniparser、sam2、birefnet、grounding-dino、
swin2sr、ltx-video-2b、kokoro-82m、hunyuan3d-2），本轮**不下载**，四条理由：

1. **没有消费者**：这 8 条没有任何运行时路径会去加载它们；下载只把 `ABSENT` 变成
   `WEIGHTS_COMPLETE`，而能力面一点没动——雷达的 `LOAD_VERIFIED/INFERENCE_VERIFIED`
   仍需真机推理，那属宿主/真人项。
2. **权利门在前**：一次下载 8 个来源、8 套许可的权重，再等 owner 逐个裁决，
   等于把裁决成本换成 40+ GiB 的既成事实。`AGENTS.md` 要求许可未明时 fail closed。
3. **体积方向相反**：pack 已 236.4 MiB（警告线 220、硬预算 256，见 #253），
   声明根体积与仓体积虽不同盘，但登记后的资产会进入后续清单/快照链路。
4. **OCR 才是真缺**：`PP-OCRv6 det/rec` 在两个根里都不存在（实测 `find` 为空），
   且推理需要 paddle/onnxruntime，而它**不在** `pyproject.toml` 锁定依赖里；
   加依赖会牵动 CI 的 clean-wheel/`uv sync --locked` 闸门，属独立决策。

因此本轮把"补齐"落在**已存在但不可见**的那部分：让声明根的真实内容进入索引、
让两套记录不再互相矛盾、并把权利未决显式化。
