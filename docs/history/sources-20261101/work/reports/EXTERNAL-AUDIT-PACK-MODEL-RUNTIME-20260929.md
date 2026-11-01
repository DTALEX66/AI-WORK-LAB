# WORK-LAB 模型运行时交付 · 外部审计包（2026-09-29）

**性质**：面向**外部审计者**（含网页版 GPT）的自包含审计入口。
**不是**任务权威、**不是**执行授权。权威仍是
`WORK-LAB-AUTHORITY.md` > `.project/governance/project-authority-index.json` > 当前 taskpack。

**被审计对象**：本机模型运行时从 Ollama 迁移到 LM Studio，并做成无人值守服务。
**被审计仓库**：`https://github.com/DTALEX66/WORK-LAB`（**公开**，匿名可读）
**审计锚点（exact commit）**：`3a98384a14c8af65e3360e2d6e85a3fe3bca3c35`

> ⚠️ 本审计包**不包含**以下声明，请审计者不要替我们补上：
> 未声称"生产级"、未声称"已完成 ArcheAxis 集成"、未声称"重排有分数"、未声称
> "OCR 全矩阵通过"、未声称"ASR 本轮复测"。

---

## 0. 给审计者的最短路径（三个 URL）

1. 本文件（审计要求与结论）
   `https://raw.githubusercontent.com/DTALEX66/WORK-LAB/3a98384a14c8af65e3360e2d6e85a3fe3bca3c35/reports/EXTERNAL-AUDIT-PACK-MODEL-RUNTIME-20260929.md`
2. 证据哈希清单（**先抓这个，用于校验下面每个证据文件**）
   `https://raw.githubusercontent.com/DTALEX66/WORK-LAB/3a98384a14c8af65e3360e2d6e85a3fe3bca3c35/reports/audit-evidence/model-runtime-20260929/MANIFEST.json`
3. 机器真相（运行时 / Provider / 模型 / 下载策略）
   `https://raw.githubusercontent.com/DTALEX66/WORK-LAB/3a98384a14c8af65e3360e2d6e85a3fe3bca3c35/.project/governance/runtime-registry.json`

证据文件根路径（把 `{file}` 换成清单里的文件名即可）：
`https://raw.githubusercontent.com/DTALEX66/WORK-LAB/3a98384a14c8af65e3360e2d6e85a3fe3bca3c35/reports/audit-evidence/model-runtime-20260929/{file}`

---

## 1. 摘要（被审计的结论）

| 项 | 结论 |
|---|---|
| Ollama | **已卸载**（退出码 0），程序/进程/端口/注册表/快捷方式全部清零 |
| 权重误删数 | **0**（6 份权重逐一复核仍在盘） |
| 运行时 | **单一 LM Studio :1234**（OpenAI 兼容，仅回环） |
| 能力线 | 6 条（FAST / DEEP / EMBEDDING / RERANK / OCR / ASR） |
| 无人值守 | 开机自启 + 登录预热 + 每 10 分钟自愈 |
| 最终验收 | **8/8 PASS**（`ACCEPTED_ALL_LINES`） |
| 服务端分支 | **仅 main**，与本地 `3a98384` 一致 |

---

## 2. 逐条可判定声明（审计者要验证的就是这些）

格式：**声明** → 证据文件 → 独立核验方法 → 预期结果。

### A. 服务与安全

| # | 声明 | 证据文件 | 核验方法 | 预期 |
|---|---|---|---|---|
| A1 | Ollama 卸载退出码为 0，且事后核验程序目录/进程/端口/注册表/快捷方式全为 0 | `ollama-protection-baseline.json`、`ollama-dependency-audit.json` | 读 JSON 中 `removal.verified_after`（在 `runtime-registry.json` 内）与基线文件 | 五项均为 0/False |
| A2 | 卸载前已做保护基线（18 blob 逐文件 sha256、进程、环境变量、日志生效路径） | `ollama-protection-baseline.json` | 检查是否存在 `blobs[]` 且每项含 `sha256`；`manifests[]` 含 digest | 18 个 blob 条目 |
| A3 | 卸载**没有**删除任何权重 | `runtime-registry.json` 的 `ollama.removal.weights_untouched`、`model-registry.json` | 读字段；再看 `model-registry.json` 每条是否有可解析路径 | `accidentally_deleted: 0`；10 条记录路径均可解析 |
| A4 | 服务只监听回环，无鉴权（符合"无鉴权"铁律） | `runtime-registry.json` 的 `lmstudio.server_endpoint` | 读 JSON | `http://127.0.0.1:1234` |
| A5 | 下载策略默认**禁止**境外通道（避免占用用户 VPN） | `model-download-policy.json` | 检查 `routes.forbiddenByDefault[]`；检查 `verifiedWeights[].usedForeignRoute` | 3 个禁止主机；全部 `false` |
| A6 | 公开仓库中**无凭据泄漏** | 全部证据文件 | 对每个文件跑正规表达式：`sk-[A-Za-z0-9]{20,}`、`gh[pousr]_[A-Za-z0-9]{20,}`、`AKIA[0-9A-Z]{16}`、`-----BEGIN .*PRIVATE KEY-----` | **0 命中**（注意：`disk-usage` 会误匹配裸 `sk-`，请用带长度的正规式） |

### B. 能力线（实测，非"接口 200"）

| # | 声明 | 证据文件 | 核验方法 | 预期 |
|---|---|---|---|---|
| B1 | FAST 真实生成，且 reasoning token 为 0 | `final-acceptance.json` | 读 `lines.fast` | `reasoningTokens == 0`，`chars > 10` |
| B2 | DEEP 在**冷启动**下自动加载并作答 | `final-acceptance.json`、`jit-autoload-measurement.json` | 读 `lines.deep.wasCold` 与 `tests` | `wasCold: true`；4/4 模型冷启成功 |
| B3 | EMBEDDING 为 **1024 维**，且具有判别力 | `lmstudio-embed-rerank-verify.json` | 读 `dimensions`、比较两个相似度 | `[1024]`；同义 > 异义 |
| B4 | RERANK 判断正确，但**只有二值**、无分数 | `lmstudio-rerank-scored.json`、`final-acceptance.json` | 读 verdict 与 `fidelity` | 相关=`yes`、不相关=`no`；`BINARY_VERDICT_ONLY` |
| B5 | OCR 逐字**精确**（fixture 已知真值） | `lmstudio-vlm-ocr-scored.json` | 读 `exact` / `total` / `verdict` | `8/8`，`REAL_OCR_WORKING` |
| B6 | ASR **本轮未复测**（不得当作新证据） | `final-acceptance.json` | 读 `lines.asr` | 仅 `venvExists` / `weightsPresent` 为真，无新转录结果 |

### C. 性能与调优（含被数据推翻的假设）

| # | 声明 | 证据文件 | 核验方法 | 预期 |
|---|---|---|---|---|
| C1 | DEEP 用**自动**显存分配最快，手动比例都更慢 | `deep-offload-tuning.json` | 比较 `trials[].tokPerSec` 与 `best` | `best.gpu == "auto"` 且值最大 |
| C2 | FAST `parallel=1` 比默认 4 **省 153 MiB 且略快** | `parallel-tuning.json` | 读 `deltaVramMiB`、`deltaTokPerSec`、`verdict` | `153`、正值、`USE_PARALLEL_1` |
| C3 | 8 GiB 显存下三模型同时驻留会占满 | `runtime-registry.json` 的 `residentPolicy` | 读 `rationale` 中的实测数字 | 7673 / 8151 MiB |

### D. 无人值守机制

| # | 声明 | 证据文件 | 核验方法 | 预期 |
|---|---|---|---|---|
| D1 | LM Studio 服务随启动自启（原为 false） | `runtime-registry.json` 的 `serverAutostart`、`model-download-policy.json` | 读 `was`/`now` | `was: false` → `now: true` |
| D2 | 两个计划任务，且各自"已验证运行" | `lmstudio-autostart.ps1`、`lmstudio-heal.ps1`、`register-autostart-task.ps1` | 读脚本：是否解析 `lms ps --json`、是否用 `schtasks` 注册 | 存在精确标识符计数逻辑 |
| D3 | 自愈是**真杀进程验证过**的，不是声称 | `runtime-registry.json` 的 `scheduledTasks[].verified` | 读文字描述 | 含"killed"/"unreachable"/"HTTP 200" |
| D4 | 重复实例缺陷已发现并修复 | `runtime-registry.json` 的 `defectFoundAndFixed`、`lmstudio-autostart.ps1` | 读缺陷描述与脚本修复逻辑 | 含 `duplicate` 检测与卸载分支 |

### E. 仓库一致性

| # | 声明 | 核验方法（公开可做） | 预期 |
|---|---|---|---|
| E1 | 被审计 SHA 存在且可达 | `https://api.github.com/repos/DTALEX66/WORK-LAB/commits/3a98384a14c8af65e3360e2d6e85a3fe3bca3c35` | HTTP 200 |
| E2 | 服务端只有 main 分支 | `https://api.github.com/repos/DTALEX66/WORK-LAB/branches` | 仅 `main` |
| E3 | 该 SHA 是 main 的头 | `https://api.github.com/repos/DTALEX66/WORK-LAB/branches/main` | `commit.sha` 等于 E1 |
| E4 | 交付物确实在该 SHA 的树里 | 用 GitHub Trees API 或直接抓 raw URL | 返回 200 且非空 |

---

## 3. 审计者**无法**从公开信息验证的部分（请据此调整结论强度）

以下只能在受审机器上验证。**不要**因为公开证据齐全就推断这些为真：

| 无法公开验证 | 原因 | 本机的自证方式 |
|---|---|---|
| 服务此刻正在运行 | 回环地址，外部不可达 | 审计包只能证明脚本与配置；运行态是时点事实 |
| 计划任务真的已注册 | 任务计划程序是本机状态 | `register-autostart-task.ps1` 可读，但其"已执行"无法公开证明 |
| 完整原始归档（65 文件） | 位于刻意不跟踪的 `.project-local/` | 已发布其中 22 个关键文件及其 sha256 |
| 全部复现脚本 | 同上，脚本在不可跟踪区 | 本包含 3 个关键 PowerShell 脚本；其余按哈希记录 |
| 权重文件本身 | 数十 GB，且权重要求"只存一份" | 仅提供 sha256 与来源 URL，不提供下载 |

**因此本次可被支持的最强结论是**：
> 公开证据支持"迁移与部署**已实施且证据自洽**"；但"服务**此刻正在运行**"与"计划任务**已注册在本机**"属于机器时点事实，公开渠道不可核验。

---

## 4. 一致性自检（审计者可能发现的矛盾点，先说清）

| 可能的疑问 | 说明 |
|---|---|
| 为什么 `model-registry.json` 里有些路径含 `C:\Users\ALEX\`？ | 本机位置记录，用于回滚定位。仓库隐私门禁（`tests/workflow-assistance/test_wlgm_privacy.py`）只拦凭据，不拦本机路径；已确认无凭据。 |
| 为什么报告里说"重排分离度 0.9996"又叫"不可复现"？ | 0.9996 是 **llama.cpp `/v1/rerank`** 的实测值；LM Studio 0.4.25 **无该端点**，故标注 `NOT REPRODUCIBLE ON LM STUDIO`，仅作参考保留。见 `provider-registry.json`。 |
| 为什么 OCR 模型 ID 与早期的 `qwen2.5vl:7b` 不同？ | 早期那个 Ollama blob 经 GGUF 头解析 `hasVision=false`（无投影层），**任何运行时都无法做视觉**；已改用 `ggml-org` 官方 模型+mmproj 组合。见 `candidate-inspect.json` 与 `model-registry.json`。 |
| 为什么 `final-acceptance.json` 里 FAST 是 77.9 tok/s 而别处写 90.41？ | 90.41 是 warm 峰值；77.9 是最终验收该次的实测。两者都不含思考 token。 |
| 为什么有一个"未跟踪的 `docs/future/`"？ | 其 JWT/OAuth2/Vault 章节与"无鉴权"铁律冲突，**故意不提交**。 |

---

## 5. 内部交叉引用（公开可读）

| 内容 | 路径 |
|---|---|
| 迁移报告 | `reports/MODEL-RUNTIME-MIGRATION-OLLAMA-TO-LMSTUDIO-20260929.md` |
| 交接记录 | `taskpacks/current/MODEL-RUNTIME-HANDOFF-20260929.md` |
| 运行时登记表 | `.project/governance/runtime-registry.json` |
| 能力/Provider | `.project/governance/provider-registry.json` |
| 模型登记表 | `.project/governance/model-registry.json` |
| 下载策略 | `.project/governance/model-download-policy.json` |
| 外部库索引 | `.project/governance/external-libraries-index.json` |

---

## 6. 审计结论模板（供审计者填写）

```
仓库锚点            : 3a98384a14c8af65e3360e2d6e85a3fe3bca3c35
证据哈希校验        : __/22 通过
A 服务与安全        : __/6
B 能力线            : __/6
C 性能与调优        : __/3
D 无人值守          : __/4
E 仓库一致性        : __/4
发现的不实声明      : （如有）
未能验证项          : 运行态、计划任务本机注册状态、完整归档、复现脚本全集
总体判定            : 证据自洽 / 存在未支持声明 / 证据不足
```
