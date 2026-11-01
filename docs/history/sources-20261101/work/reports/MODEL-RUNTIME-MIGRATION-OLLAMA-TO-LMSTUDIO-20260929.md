# WORK-LAB 模型运行时迁移报告：Ollama → LM Studio（2026-09-29）

> **归属**：WORK-LAB 模型控制面。
> **授权**：用户直接决定 —— "卸载删除 OLLAMA，使用 LM Studio 接收/部署/迁移/配置"。
> **取代关系**：本报告**取代** `reports/MODEL-GOVERNANCE-20260928.md` 中第 27–33 行的运行时
> 分配表（该表把 FAST 记为 llama.cpp :8081、EMBEDDING/OCR 记为 Ollama）。09-28 报告作为
> 历史记录保留不改写；其模型身份、哈希、benchmark 数据仍然有效。
> **下载通道**：按用户指示全程走国内镜像（hf-mirror.com），**未占用个人 VPN**。

---

## 0. 一句话结论

Ollama 已**卸载完毕**（程序目录、进程、端口、注册表项、快捷方式全部清零，卸载器 exit code 0），
**零权重被误删**；6 条能力线现已全部落在 **LM Studio :1234 单一运行时**上，
卸载后 E2E 复验 **6/6 PASS**。

---

## 1. 卸载执行与核验

| 项 | 值 |
|---|---|
| 卸载命令 | `unins000.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART` |
| 退出码 | **0** |
| 程序目录 | 已删除（释放 **2830.5 MiB**） |
| ollama 进程 | **0**（卸载前 2 个：`ollama.exe serve` / `ollama app.exe`，已显式停止） |
| 端口 11434 | **无监听** |
| 注册表卸载项 | **0** |
| 开始菜单快捷方式 | **0** |
| 附带清理 | `C:\Users\ALEX\.ollama`（空 blobs/models、cache、ssh key、onboarding 标记）；用户级环境变量 `OLLAMA_MODELS` |
| **误删权重数** | **0** |

### 卸载前保护基线（先取证，后动手）

`.project-local/runs/model-governance-20260928/ollama-protection-baseline.json`：
18 个 blob 的逐文件 sha256、5 个 manifest 原文与 digest、进程命令行、
`OLLAMA_MODELS` 两处作用域取值、服务器日志中的生效路径、卸载器路径与回滚步骤。

登记表备份：`.project-local/runs/model-governance-20260928/governance-backup/`（含 `.postremoval` 版本）。

### 为什么这次卸载是低风险的

**Ollama 0.34.4 其实一个模型都没在服务。** 实测：

- 运行中的服务把 `OLLAMA_MODELS` 解析为 C: 默认值 `C:\Users\ALEX\.ollama\models`，
  **而非** User 作用域指向的共享库；`server.log` 记录 `OLLAMA_MODELS:C:\Users\ALEX\.ollama\models`
  与 `"total blobs: 0"`。
- `GET /api/tags` → `{"models":[]}`；`ollama list` 为空表；该 C: 目录 blobs **0 个文件**。
- 时间点：Inno Setup 日志显示 0.34.4 就地升级发生在 **2026-09-28 20:50:09**
  （`/CLOSEAPPLICATIONS /FORCECLOS…`），新服务于 **20:51:06** 启动即报告 `total blobs: 0`。

所以共享库里那 28.76 GiB 自升级那一刻起就对 Ollama 不可见 —— 指向 `:11434` 的
`fast.legacy` / `code` / `embedding` / `reranker` / `ocr` 五个绑定**全是死的**。
旧登记表记录的"0.34.3 + 5 个在线模型"是过期信息，已更正。

---

## 2. 迁移方法与"权重只有一份"

**关键发现（推翻了本会话早期的判断）**：LM Studio 的模型根目录**就是**共享库根目录
`D:\All projects\Model library`（`settings.json` 的 `downloadsFolder`），按
`<publisher>/<repo>/<file>.gguf` 扫描。用探针目录实测确认：把一个副本放在
`_idx_test_/acme/demo-repo/`，LM Studio 立即以 `publisher=acme id=demo-repo` 收录。

因此**源与目标同卷**，迁移是**同卷移动（`os.replace`）**：

- 早期担心的"跨盘必须复制/硬链接不可能"问题**根本不存在**（本会话早期曾据此提出三个方案，现作废）。
- 实测：Windows 目录 junction 可跨卷，符号链接不可（本机无开发者模式、非管理员）。
- 结果：**一份物理字节、一个路径**，无副本、无链接、无 import 调用。

| 模型 | 迁移方式 | 目标 |
|---|---|---|
| Qwen3-Embedding-0.6B | 同卷移动（校验 sha256 后） | `Qwen\Qwen3-Embedding-0.6B-GGUF\...Q8_0.gguf` |
| Qwen3-Reranker-0.6B | 同卷移动（校验 sha256 后） | `Qwen\Qwen3-Reranker-0.6B-GGUF\...Q8_0.gguf` |

`lms import` **未被使用**：文件放入标准布局后 LM Studio 自动收录，故不存在工具层复制/移动/链接。

---

## 3. 六条能力线的最终状态

| 能力线 | 模型 | LM Studio ID | 状态 | 实测证据 |
|---|---|---|---|---|
| FAST | Qwen3.5-4B | `qwen3.5-4b` | **ONLINE** | 43 tok / 13.53 tok/s（本次 E2E）；早前 90.41 tok/s（warm） |
| DEEP | Qwen3.8-27B UD-IQ4_XS | `qwen3.8-27b` | **ONLINE** | 三参数通道均出内容；1.97 tok/s |
| EMBEDDING | Qwen3-Embedding-0.6B | `text-embedding-qwen3-embedding-0.6b` | **ONLINE** | **dim 1024**；同义 0.8340 / 异义 0.3396，分离 **+0.4944** |
| RERANK | Qwen3-Reranker-0.6B | `qwen3-reranker-0.6b` | **ONLINE（二值）** | 相关=yes / 不相关=no；**无分数** |
| OCR | Qwen2.5-VL-7B-Instruct + mmproj | `qwen2.5-vl-7b-instruct` | **ONLINE** | **8/8 行逐字精确，两轮一致，5.3 s** |
| ASR | faster-whisper-large-v3-turbo | 进程内 | **未受影响** | 非 Ollama 模型；本次未重跑，沿用既有实测（逐字正确，RTF 1.5） |

卸载后 E2E：`.project-local/runs/model-governance-20260928/e2e-post-removal.json`
→ **6/6 PASS，VERDICT = `ALL_LINES_ON_LMSTUDIO`**。

---

## 4. 必须诚实记录的三个限制

### 4.1 重排只有二值判定，没有分数（真实保真度下降）

LM Studio 0.4.25 实测：

- **无重排端点**：`/v1/rerank`、`/api/v0/rerank`、`GET /v1/rerank` 全部返回
  `{"error":"Unexpected endpoint or method"}`。
- **永不返回 logprobs**：`/v1/completions` 带 `logprobs=20` 返回 `"logprobs": null`
  —— 连已经加载的普通 LLM（`qwen3.5-4b`）也是这样，`/api/v0/completions` 同样。

驱动方式是用**模型自带的** `tokenizer.chat_template.rerank` 模板（从 GGUF 读出，逐字复现）
经 `/v1/completions` 取判定。它在全部用例上**判断正确**（中/英，以及一个高难中文三候选：
真事实=Yes、同主题干扰项=yes、仅上下文相关=no），但**两个都被接受的候选无法排序**。

> 旧登记表记录的 `score_spread 0.9996` 是 **llama.cpp `/v1/rerank --rerank --pooling rank`**
> 的实测值，**在 LM Studio 上不可复现**，已标记 `NOT REPRODUCIBLE ON LM STUDIO`，
> 仅作 llama.cpp 参考记录保留，不得当作 LM Studio 能力引用。

### 4.2 OCR 无法靠迁移解决，必须另取权威权重

Ollama 的 `qwen2.5vl:7b` blob 经 GGUF 头直接解析：`hasVision=false`（**无 `clip.*` 键**），
manifest 只有**一个** `image.model` 层，且整个共享库**没有任何 mmproj 文件**。
即该 blob 是纯文本 7B，**在任何运行时下都无法做视觉**。

改绑 llama.cpp 项目官方仓库 `ggml-org/Qwen2.5-VL-7B-Instruct-GGUF`（模型 + 配套 mmproj）。
LM Studio 自动完成配对并报告 `type=vlm`（5.54 GB = 4.36 权重 + 0.795 投影层）。

### 4.3 4B 的参数怪癖不适用于 27B

早前记录"LM Studio 忽略 `chat_template_kwargs{enable_thinking:false}` 与 `/no_think`"
**只对 `qwen3.5-4b` 成立**。本次实测 `qwen3.8-27b` 在**三个通道**（`reasoning_effort=none`、
`chat_template_kwargs`、完全不控制）**都产出了真实内容**。已更正登记表措辞，避免误推广。

另外：LM Studio 默认 offload 达 **1.966 tok/s**，是 llama.cpp `-ngl 32`（**2.52 tok/s**）的约 78%，
明显优于 `-ngl 0`（1.32 tok/s）；llama.cpp 因此**保留**为可选逃生通道（不自动启动），
不再是任何 provider 的绑定目标。

---

## 5. 下载与国内通道

| 项 | 值 |
|---|---|
| 来源仓库 | `ggml-org/Qwen2.5-VL-7B-Instruct-GGUF`（llama.cpp 项目官方） |
| 通道 | **hf-mirror.com**（国内镜像，`?download=true`）；**未使用 huggingface.co 直连** |
| 模型文件 | `Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf` 4,683,072,032 B<br>sha256 `9258bf05b12686d097ff3b6b18d968ab393649780aa2b3cd67fec43d50554392` |
| 视觉投影 | `mmproj-Qwen2.5-VL-7B-Instruct-Q8_0.gguf` 853,119,712 B<br>sha256 `2ddb555391bae966e412deab9e07b58afa18bcc06930ba0f1c78a3695ab9e506` |
| 校验 | 两个 sha256 均与**镜像自身元数据**比对通过（未硬编码手抄哈希） |
| 并行提速 | 单连接 0.766 MiB/s → **8 连接聚合最高 13.4 MiB/s** |
| 共享库现在 | **102.65 GB**（ComfyUI 49.37 / ollama 27.71 / plain-gguf 15.83 / ggml-org 5.16 / sherpa-onnx 1.55 / whisper 1.51 / Qwen 1.06 / runtimes-tmp 0.46） |

### 我自己工具链的两个缺陷（已修复，如实记录）

1. **组装截断**：组装时用 `final_part`（= `<name>.part`）以 `"wb"` 打开，而它同时是
   续传前缀的**同一路径**，于是源被清零、前缀读回 0 字节，产物恰好少 960 MiB。
2. **前缀被静默丢弃**：修复后又出现 `keep_part = (final_part != resume_part and ...)`，
   而这两个路径**按设计永远相同**，判据恒为 False，前缀整段未写入。

两处均已修正；最终产物由**完好的分块重建**并重新校验 sha256 通过，未重新下载整份。

---

## 6. 未做 / 待决

| 项 | 状态 |
|---|---|
| Ollama 制品库（27.71 GB，16 blobs / 5 manifests） | **保留未删**，待用户单独决定 |
| `qwen3-8b`（5.22 GB）、`qwen3-coder-30b-a3b`（18.56 GB） | 标记 `RETIRED_PENDING_DECISION`，**未删**。二者超出 WL-MODEL-02 "恰好 2 个通用 LLM" 目标 |
| ASR | 本轮**未重跑**（沿用既有实测），不是新证据 |
| Rerank 分数 | 在 LM Studio 上**不可得**；若后续需要真实分数，唯一已验证路径是 llama.cpp `/v1/rerank` |
| OCR 测试矩阵 | 仅中英混排单页 8/8；zh/en/mixed/PDF/scanned/table/page-order 全矩阵**未跑** |

---

## 7. 复核入口

```
卸载前基线   .project-local/runs/model-governance-20260928/ollama-protection-baseline.json
依赖审计     .project-local/runs/model-governance-20260928/ollama-dependency-audit.json
迁移日志     .project-local/runs/model-governance-20260928/ollama-migration-journal.jsonl
候选权重解析 .project-local/runs/model-governance-20260928/candidate-inspect.json
嵌入/重排验证 lmstudio-embed-rerank-verify.json · lmstudio-rerank-scored.json
DEEP 验证    lmstudio-deep-verify.json
OCR 验证     lmstudio-vlm-ocr-scored.json（8/8 逐字）
下载证据     vl-download-mirror.json · mirror-probe.json
卸载后 E2E   e2e-post-removal.json（6/6 PASS）
登记表备份   governance-backup/（含 .postremoval）
脚本         ollama_snapshot.py · ollama_migrate.py · ollama_dependency_audit.py
             update_governance.py · record_removal.py · validate_governance.py
             vl_download_mirror.py · vl_fetch_prefix.py · lmstudio_*_verify.py
```
