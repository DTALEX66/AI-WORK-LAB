# WORK-LAB 本机模型统一治理 · 交付报告（2026-09-28）

> 归属：WORK-LAB 模型控制面（model discovery / registry / runtime / capability / provider /
> health / benchmark / sharing）。ArcheAxis 只持有逻辑 Capability/Provider 引用；
> DESIGN-LAB 只按需调用公共能力。**权重只有一份**，位于共享物理库。

## 1. 交付物（仓库内，可在任何机器复核）

| 文件 | 作用 |
|---|---|
| `.project/governance/model-registry.json` | 11 个受管模型：逻辑 id / family / revision / quant / 文件引用 / sha256 / license / runtime / capabilities / context_window / gpu_offload / estimated_vram·ram / supported_projects / owner / health / benchmark / last_verified |
| `.project/governance/runtime-registry.json` | Ollama 0.34.3 + llama.cpp b11221：二进制 sha256、endpoint、启动命令、env、并发/上下文默认、升级状态、为何需要两套 |
| `.project/governance/provider-registry.json` | 9 个逻辑 Provider（`local.fast.default` / `local.deep.default` / `local.embedding.default` / `local.reranker.default` / `local.ocr.default` / `local.asr.default` / 备用）；客户端禁止依赖文件名/quant/绝对路径 |
| `.project/governance/model-capability-matrix.json` | 18 条能力→Provider→模型→runtime + **去重守卫**（每能力组仅一个 active 默认） |
| `.project/governance/model-project-permission-matrix.json` | 三项目 × Provider 权限（`shared-common` / `archeaxis-first` / `worklab-only` / `standby`） |
| `.project/governance/archeaxis-local-ai-pipeline-matrix.json` | ArcheAxis 14 项需求逐条映射到真实 Provider 与真实测试（9 PASS / 5 PARTIAL / 0 BLOCKED） |
| `.project/governance/model-benchmark-record.json` | 本机实测：吞吐、冷启、offload 敏感性、并发、恢复、超长上下文、各模型金测 |

运行证据（体积较大，按数据边界留在 WORK-LAB 忽略区）：
`.project-local/runs/model-governance-20260928/`（`CLOSEOUT.md`、`protection-baseline.json`、
`inventory.utf8.json`、`bench-deep*.json`、`deep-serving.json`、`deep-usability.json`、
`e2e-results.json`、`e2e-console.log`、`DOWNLOAD-PLAN-20260928.md` 及全部脚本）。

## 2. 最终模型结构（brief §九/§十八，不膨胀）

```
FAST      Qwen3.5-4B            Q4_K_M      2.55 GB   llama.cpp :8081   共享
DEEP      Qwen3.8-27B UD-IQ4_XS  UD-IQ4_XS  13.27 GB  llama.cpp :8080   共享
EMBEDDING Qwen3-Embedding-0.6B  (复用)      0.60 GB   Ollama   :11434   ArcheAxis 优先
RERANK    Qwen3-Reranker-0.6B   (复用)      0.46 GB   llama.cpp :8082   ArcheAxis 优先
OCR       qwen2.5vl:7b          (复用)      5.56 GB   Ollama            ArcheAxis 优先
ASR       faster-whisper-large-v3-turbo     1.51 GB   进程内             ArcheAxis 优先
```

**通用 LLM = 2 + Retrieval 2 + Ingestion 2 = 6 条能力线**；4 个 standby 保留未删。

## 3. 实测关键数字

| 项 | 值 |
|---|---|
| DEEP 冷启 / 重启恢复 | 21.6s / 9.5s |
| DEEP 吞吐（ngl=8, t=14, 16k ctx） | prompt 14.12 tok/s · **gen 1.97 tok/s** |
| offload 增益 | ngl 0→8 仅 **+10%**（根因：桌面占用 6.8/8 GiB VRAM，实测仅 1.1 GiB 空闲） |
| FAST 吞吐（warm） | **8.04 tok/s**，首答 3.85s @312 prompt tokens |
| 对照 MoE 30B-A3B | **7.81 tok/s**（比 27B dense 快 3.9×） |
| Embedding | 1024 维；检索 top 0.6718 命中正确 chunk |
| Rerank | spread **0.9996**（1.0 / 0.7362 / 0.6036 / 0.0006 / 0.0004），1.77s/5 候选 |
| OCR | 中英混排页：英文全中 + 中文 **6/6** 探针命中，61.7s |
| ASR | 真实中文 4.49s → **逐字正确**，RTF 1.5（CPU int8） |
| E2E | **11/11 PASS**（真实模型 + 真实夹具，无 mock） |
| 超长上下文 | 40052 tokens @c=8192 → HTTP 400 `exceed_context_size_error`，fail-closed |
| 并发 2 | 均成功但**排队**（各 27.38s / 1.415 tok/s）——单 CPU 绑定模型的真实行为 |
| 磁盘 | 共享库 81.66 → **97.49 GB**（净增权重 +15.82 GB）；D: 剩余随宿主写入波动（实测 93.2–106.2 GB） |

## 4. 下载来源（国内优先，全部哈希校验）

| 模型 | 来源 | 实测速率 | sha256 |
|---|---|---|---|
| Qwen3.5-4B Q4_K_M | ModelScope `unsloth/Qwen3.5-4B-GGUF` | 28–29 MB/s | `00fe7986…ef11a4` |
| Qwen3.8-27B UD-IQ4_XS | ModelScope `unsloth/Qwen3.8-27B-GGUF` | 26.6 MB/s | `40fac405…0e6199` |
| llama.cpp b11221 win-cuda-12.4 | GitHub release via `gh-proxy.com` | 1.7–3.0 MB/s | `95e15aa4…a267d1` |

本机实测：**HF 与 hf-mirror 均不可达**；GitHub 直连 **77 KB/s**；Ollama CDN **136 KB/s**（因此放弃 Ollama 路由）。

## 5. 未做 / 明确边界

- 未删除任何模型或文件（3.62 GB 候选残留只登记，等用户确认）。
- 未升级 Ollama（0.34.4 安装包保持未安装）；`OLLAMA_MODELS` 仍指向共享库。
- 未改任何全局产品配置；未读取任何凭据；权重零入 Git。
- 未为「以后可能有用」下载任何模型；9B/35B/122B/第二套 embedding·rerank·OCR·ASR 全部跳过。

## 6. 结论

```
ARCHEAXIS_LOCAL_AI_BASE  = PARTIAL   # 14 项：9 PASS / 5 PARTIAL / 0 BLOCKED
SHARED_MODEL_RUNTIME     = PASS
WORKLAB_MODEL_GOVERNANCE = PASS
```

## 7. 后续维护要点

1. 启动/健康检查命令见 `CLOSEOUT.md` §19；FAST 调用必须带 `enable_thinking:false`。
2. 要真正让 27B/4B 驻留 GPU：先释放桌面占用的 6.8 GiB VRAM；否则接受 ~2 / ~8 tok/s。
3. 任何模型变更先跑 `inventory.py` 盘点哈希，再改 5 份 registry（model/runtime/provider/capability/permission）。
4. Ollama 可升级，但模型索引与路径必须保持在共享库内。
