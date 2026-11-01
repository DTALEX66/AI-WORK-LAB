# WORK-LAB 项目全阶段审计报告（供外部审计用 · 2026-09-28）

> **用途**：本文件是**自包含**审计材料，供外部（如网页 GPT）独立审计。所有数字均来自
> 仓库/GitHub/本机实测回读，并标注证据来源。**不含任何凭据、令牌或私密内容。**
> 生成时的精确锚点：`origin/main = 17c645e520b245570c0dc591859eec2c24b44432`，
> tree = `8009d869198378aae6b7d7c8f22e64edf38b15c3`。

---

## 0. 审计须知（权威顺序与证据分级）

**权威顺序（最高到最低）**：
1. 用户最新明确决定
2. `WORK-LAB-AUTHORITY.md`（人类最高权威）
3. `.project/governance/project-authority-index.json`（机器最高权威）
4. 当前 taskpack（`.project/governance/taskpack-authority-index.json`）+ `taskpacks/current/OPEN-TASK-REGISTER.md`
5. `AGENTS.md` + 域内机器契约
6. 当前精确 SHA 的代码 + CI/运行回读
7. 历史会话/taskpack/交接/审计（**冻结证据，永不覆盖现状**）

**证据分级**：`NO_EVIDENCE < SIMULATED < SYNTHETIC < INTEGRATED < REAL`。
REAL 需要可验证句柄 + 回读；**编译通过 ≠ 行为通过；单元通过 ≠ 集成通过；CI 通过 ≠ 桌面通过；
本地结构 PASS ≠ exact-SHA CI PASS**。UNKNOWN 保持 UNKNOWN，不伪造 0。

**当前 taskpack**：`WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918`（唯一 CURRENT）

---

## 1. 项目身份与架构（阶段一：定位）

WORK-LAB 是用户的**客户端中立 AI 工作流 / Agent 运维 / 治理 / 联邦控制平面**。

| 层 | 规范语言 | 目录 |
|---|---|---|
| 产品 UI | TypeScript + React | `apps/observer/frontend` |
| 原生桌面包壳 | Rust + Tauri 2 | `apps/observer/src-tauri` |
| 工作流/配置/策略/适配器/编排 | Python | `packages/client-neutral-core/`、`services/` |
| 跨语言真相 | JSON Schema | 契约目录（37 个契约） |
| 引导脚本 | PowerShell / Shell | `scripts/` |

**两个规范模块根**（`.project/governance/module-ownership.json`）：
`packages/client-neutral-core`（workflow-assistance）与 `apps/observer`（只读投影）。
支撑面：`services/`、`integrations/`、`config/`、`apps/token-monitor/`、`scripts/`、`tests/`。

**三项目边界**（`.project/governance/three-project-boundary.json`，机器真相）：
- **WORK-LAB**：控制面（谁/何时/何权限/经何软件/如何执行/如何验证/如何恢复）
- **ArcheAxis-Knowledge-OS**：知识（长期记忆、学习、蒸馏、知识真值、分类、晋升、存储、召回）
- **DESIGN-LAB**：设计域（设计 agent、设计软件执行、设计资产、生成策略、质量体系、Adobe 域逻辑）
- 三者**互相不吞并**，只经统一协议对接。Open Design **客户端** ≠ DESIGN-LAB **项目**（两个身份）。

**仓库规模事实**：554 个提交 · 148 个 PR（147 MERGED / 1 CLOSED）· 远端分支 **1** 个（只有 `main`）·
若干历史 tag（`wl-retire-20260917/*` 为已退役分支归档）。

---

## 2. 全阶段时间线（按 PR 分段）

### 阶段 A · 起步与 Hermes 部署（PR #1–#119 区间）
早期提交（`54d084e` 起）为 Hermes Agent 部署包、凭据模板 + `.gitignore`、路由方案文档。
本阶段末段 **#119 `observer command center 2.0 + context control plane + github delivery`** 是
Observer 从静态页转向 React/Tauri 产品线的起点。

### 阶段 B · 运行时收敛与多客户端适配（#120–#123）
- **#120** DSH 0.1.1 官方运行时 + Codex 收敛 + 交接
- **#121/#122** DSH 2.0.2 cover-install 交接 + `AGENTS.md`/`config-ownership` v2 对齐 + WL-DLC-060 适配器修复
- **#123** `WL-DIR-MIG-R1` 目录收敛 + 清理 —— **CLOSED（未合并）**，其目标后来由其他 PR 达成

### 阶段 C · 分支收敛与权威冻结（#124–#127）
- **#124** `[Cutover] main = r4-recovery-exec`：把 `r4-recovery-exec` 整体切到 `main`
- **#125** 在 `BRANCH-RETIREMENT-LEDGER-20260917.json` 记录 cutover 事件
- **#126** 统一 `OPEN-TASK-REGISTER-20260917` + 修正收敛决策状态漂移
- **#127** **WORK-LAB V2：统一产品收敛**（权威/GAPS/Observer/联邦/U19/边界）—— 这是 V2 权威
  `WORK-LAB-AUTHORITY-20260918-V2` 落地的关键 PR
- 52 个遗留分支 → `wl-retire-20260917/*` tag 后删除；`main` 成为唯一 ACTIVE/AUTHORITATIVE 分支

### 阶段 D · 逐项闭环与治理最小化（#128–#139）
- **#128–#130** 基线复核、生命周期登记 READBACK、`90-archive` 物理收敛（MOVE-005）、D2 空集关闭
- **#131–#133** README 对齐 V2；ERR-088 DSH 数据根会话冻结 + DSH 声明清扫；P0 权威/文档/机器 SSOT 终局收敛
- **#134** **P0-01 Observer CI 真值修复**：锁定依赖 + fail-fast 分组（此前多命令步骤会掩盖失败造成"假绿"）
- **#135** P0-02 陈旧文档收敛 + P0-03 从属 task-card 权威模型（当前 task-card 校验 6 条不变量）
- **#136** ERR-089 生命周期关闭 + 交接绑定到已合并 main
- **#137** **stage-B 前端正确性**：B1 把 vitest 接入必需门 + B2 compact 入口契约 + B3 主题统一 + B4 `?api=` 保真 + B5 无伪造 0
- **#138** C1–C5 恢复材料、外部索引根解析、证据校验（含 exact-SHA CI 内容校验）
- **#139** D1/D3/D5 Lite 可见交付：只读静态入口 + Work lane + Inspector

### 阶段 E · Hermes 维护轮（#140–#141）
- **#140** Hermes 更新到 `v0.21.5+3115.g10938a7`（origin/main @10938a7c），config v45→v46，
  **受管覆盖层 21/21 CONVERGED**、curator 0 漂移、hooks healthy、桌面入口真实启动读回；
  5 项覆盖层漂移同日全部修复（含**拒绝两个弱化 live 版本**：`SOUL.md` 缺 E/F 边界、
  `project-data-boundary` 删掉 `F:\` 保护——与机器真相 `forbiddenExternalRoots` 冲突）
- **#141** 该维护轮的接手简版交接

### 阶段 F · UI 完全复刻（#142–#144）
- **#142** L10：B10 最终 UI 收敛（12 页 IA、交互式工作流编辑器、B10 设计系统 + glow token、
  只读投影、无鉴权铁律）
- **#143** **L10b：B10 1:1 DOM 复刻**（shell + 全部 12 lane 改用 B10 逐字类名；11 文件 / 72 测试全绿；
  17 张 headless 截图关闭 L10 遗留的像素层 UNVERIFIED；命令面板关闭时不再复制导航文案）
- **#144** L10b 裁决记录 D-11..D-16（含"B10 未分层皮肤胜过 Tailwind"与"浅色主题只部分实现"的诚实登记）

### 阶段 G · Hermes 执行面审计（#145）
- **#145** 按强制引导顺序解析权威后，对 Hermes 的 5 个任务面 + 工具面逐份回读，并**独立重跑**
  其声称的验证（21/21 覆盖层、curator 0 漂移、hooks healthy、skill-provenance、
  `test_curator_foldback` 17 OK、备份字节一致……）；**新增 8 项发现**（F-01..F-08），
  含"09-17 轮 4 个提交不在 main 祖先链""对账单据引用的附件已不存在""09-17 备份已被
  `keep_policy=2` 轮换掉"等；并确认 `kanban.db` 任务 0、`cron/jobs.json` 为空 ⇒
  **当前无 Hermes 侧定时自动化在跑**。

### 阶段 H · 本机模型统一治理（#146–#148，本轮）
见 §3。

---

## 3. 本轮（阶段 H）交付详情

### 3.1 目标与结论

**用户指令**：由 WORK-LAB 统一完成本机模型资源的部署、运行时配置、能力注册、健康检查、
性能验证与共享治理；ArcheAxis 得到完整但精简的本地 AI 底座；WORK-LAB 与 DESIGN-LAB
只复用必要公共能力；**本机只维护一份模型资产**。执行器 Hermes / AGENS 3.0。
禁止重新开启模型选型；禁止为相同能力下载近似模型；禁止权重入 Git；禁止业务源码写死绝对路径。

```
ARCHEAXIS_LOCAL_AI_BASE  = PARTIAL   # 14 项需求：9 PASS / 5 PARTIAL / 0 BLOCKED
SHARED_MODEL_RUNTIME     = PASS
WORKLAB_MODEL_GOVERNANCE = PASS
```

### 3.2 最终模型结构（6 条 active + 4 standby，0 删除）

| 档位 | 模型 | 体积 | Runtime | 端点 | 授权 |
|---|---|---|---|---|---|
| FAST | Qwen3.5-4B Q4_K_M | 2.55 GB | llama.cpp | :8081 | 三项目共享 |
| DEEP | Qwen3.8-27B UD-IQ4_XS | 13.27 GB | llama.cpp | :8080 | 三项目共享 |
| EMBEDDING | Qwen3-Embedding-0.6B（复用） | 0.60 GB | Ollama | :11434 | ArcheAxis 优先 |
| RERANK | Qwen3-Reranker-0.6B（复用） | 0.46 GB | llama.cpp | :8082 | ArcheAxis 优先 |
| OCR | qwen2.5vl:7b（复用） | 5.56 GB | Ollama | :11434 | ArcheAxis 优先 |
| ASR | faster-whisper-large-v3-turbo（复用） | 1.51 GB | 进程内 | — | ArcheAxis 优先 |

**standby（保留未删）**：`qwen3:8b`、`qwen3-coder:30b-a3b-q4_K_M`、sherpa-onnx SenseVoice、
sherpa-onnx streaming-zipformer-zh-14M。

### 3.3 下载台账（Inventory→Hash→Identify→Reuse→Missing→Download，国内源优先）

| 模型 | 字节 | 来源 | 实测速率 | sha256 | license |
|---|---|---|---|---|---|
| Qwen3.5-4B Q4_K_M | 2,740,937,888 | ModelScope `unsloth/Qwen3.5-4B-GGUF` | 28–29 MB/s | `00fe7986…ef11a4` | apache-2.0 |
| Qwen3.8-27B UD-IQ4_XS | 14,252,845,984 | ModelScope `unsloth/Qwen3.8-27B-GGUF` | 26.6 MB/s | `40fac405…0e6199` | apache-2.0 |
| llama.cpp b11221 win-cuda-12.4 | 264,519,230 | GitHub release via gh-proxy.com | 1.7–3.0 MB/s | `95e15aa4…a267d1` | MIT |

**网络实测**：huggingface.co 与 hf-mirror.com **本机不可达**；GitHub 直连 **77 KB/s**；
Ollama CDN **136 KB/s**（因此 4B 放弃 Ollama 路由，改由 llama.cpp 直接读共享库单份文件）。

**跳过（不再下载）**：Qwen3.5-9B/27B/35B-A3B/122B · 第二套 Embedding · 第二套 Reranker ·
PaddleOCR-VL / PP-OCRv6 · Qwen3-ASR-0.6B · Ollama 0.34.4 升级。

### 3.4 实测性能（同一台机）

| 项 | 值 |
|---|---|
| DEEP（ngl=32, t=14） | prompt **20.10** / gen **2.52** tok/s |
| DEEP（ngl=0，GPU 被占时） | prompt 14.54 / gen 1.32 tok/s |
| FAST（ngl=99, t=14） | prompt **114.20** / gen **10.81** tok/s |
| 对照 MoE `qwen3-coder:30b-a3b` | gen 7.81 tok/s |
| DEEP 冷启 / 重启恢复 | 21.6s / 9.5s |
| DEEP 并发 2 | 各 27.38s / 1.415 tok/s（排队，非吞吐） |
| DEEP 超长上下文 | 40052 tok @c=8192 → HTTP 400 `exceed_context_size_error`（fail-closed） |
| Reranker | spread **0.9996**（1.0/0.7362/0.6036/0.0006/0.0004），1.77s/5 候选 |
| Embedding | 1024 维；检索 top 0.6718 命中正确 chunk |
| OCR | 中英混排页：英文全中 + 中文 **6/6**，61.7s |
| ASR | 4.49s 中文音频 → **逐字正确**，RTF 1.5（CPU int8） |
| E2E | **11/11 PASS**（真实模型 + 真实夹具，无 mock） |
| 硬件 | RTX 5060 **8151 MiB**（释放桌面占用后 free 5887 MiB）· i5-14600KF 14C/20T · 64 GB DDR4-3600 |
| 磁盘 | 共享库 81.66 → **97.49 GB**（净增权重 +15.82 GB，回收废弃 partial −3.16 GB）；D: 剩余随宿主其他写入波动，实测区间 93.2–106.2 GB |

### 3.5 治理产物（已合并入 `main`）

`.project/governance/` 下 7 份机器真相：
`model-registry.json`（11 模型 × brief 要求全部字段）· `runtime-registry.json`（Ollama 0.34.3 + llama.cpp b11221）·
`provider-registry.json`（9 个逻辑 Provider）· `model-capability-matrix.json`（18 能力 + 去重守卫）·
`model-project-permission-matrix.json`（三项目权限）· `archeaxis-local-ai-pipeline-matrix.json`（14 需求矩阵）·
`model-benchmark-record.json`（全部实测）。

人类可读：`reports/MODEL-GOVERNANCE-20260928.md`；
交接记录：`taskpacks/current/MODEL-GOVERNANCE-HANDOFF-20260928.md`。

---

## 4. 当前仓库与 CI 状态（审计可复核）

| 项 | 值 |
|---|---|
| `origin/main` | `17c645e520b245570c0dc591859eec2c24b44432` |
| tree | `8009d869198378aae6b7d7c8f22e64edf38b15c3` |
| 远端分支数 | **1**（仅 `main`；所有短分支已删除） |
| 本会话 PR | #143 / #144 / #145 / #146 / #147 / #148 —— **全部 MERGED** |
| CI 门 | `work-lab-gate`（gate-plan / workflow-assistance / integration / observer / token-monitor / supply-chain-security / aggregate，**7 jobs**）+ `wlr-060-production-gates`（capsule-cli / config-compiler / observer-readonly / schema-fixtures / wlr060-aggregate） |
| 每次合并 | 均先等 exact-SHA CI 全绿再 squash merge；合并后 main 上再次全绿 |
| 分支保护 | `main` 要求 required status check `aggregate`；直接 push 被仓库规则拒绝（实证：一次文档提交被拒后改走 PR） |

---

## 5. 铁律与边界（审计时请逐条核对）

1. **无鉴权铁律**：本地个人研究使用，**禁止加锁 / 访问令牌 / 鉴权入口**。
   实证：全 `src/**/*.tsx` 扫描 `password|token|api[-_]?key|Bearer|Authorization|登录|令牌|密码|鉴权`
   → 仅 2 处命中且均为"声明不存在"的说明文案。
2. **Observer 只读铁律**：只读页零 批准/拒绝/撤销/重试/回滚 控件。
   实证：lane 测试断言零写按钮；`ErrorState` 的可选「重试」动作已被**删除**。
3. **数据边界**：不读写 `E:\`/`F:\`；证据留 `.project-local/`（gitignored）；不读凭据/.env 值。
   实证：`PROJECT_DATA_BOUNDARY_PASS`；本轮未解包任何备份、未读任何凭据。
4. **权重零入 Git**：全部权重在 `D:\All projects\Model library`。
5. **不删现有模型**：本轮删除数 = 0（仅回收 3.16 GB **废弃 partial 分片**，删除前已核验并确认非模型）。
6. **不改全局配置 / 不升级 Ollama**：`OLLAMA_MODELS` 保持指向共享库；0.34.4 安装包保持未安装。
7. **品牌锁（UI）**：`#050D16` 深海军蓝 + `#2A91FF` 电光蓝 + `#20CDE1` 青色；禁橙/金/米白/浅 SaaS/大面积紫/玻璃泛滥。

---

## 6. 已知限制与未闭环（诚实清单）

### 6.1 硬阻塞
**无。** 本轮所有目标均在本机可完成范围内完成。

### 6.2 未闭环
| # | 事项 | 性质 |
|---|---|---|
| O1 | `runtimes-tmp/reranker-dl.gguf`（0.46 GB） | 与在用 reranker **不是重复**（同为 494,879,360 B 但 sha256 `a18ae2a5…` vs `eae89db7…`）；待决定纳入备用或确认后删除 |
| O2 | ArcheAxis 侧 5 项 PARTIAL | 候选落库 / 人类学习工作流 / machine-competence 契约 / 长文档全量批跑 / 带真实 CJK 字体的 PDF 解析 —— **非模型能力缺失**，属 ArcheAxis 工程 |
| O3 | 27B 交互速度 | 内存带宽天花板 ≈2.7 tok/s（实测 2.52 = 93%）；提速只有"更小量化"或"更大 GPU" |
| O4 | 浅色主题 | `skins/b10.css` 逐字编码 B10 深色调色板（无令牌间接化），`html.light` 下壳层翻转而 B10 表面保持深色；修复需重写皮肤 ⇒ 不再是逐字复刻，故记录为已知边界 |
| O5 | Hermes 侧 exact-SHA CI | `EXACT_SHA_CI_UNVERIFIED` 常驻（不得写 "CI green"） |
| O6 | Hermes 会话级取消 | 能力受限（`hermes pause` 官方语义不杀在途工作）——禁止依赖"可取消" |
| O7 | 计费/额度 | UNKNOWN（目录价 ≠ 账单）——禁止成本声明 |

### 6.3 本会话的自我纠错记录（审计请重点看这类）
- 我一度判断 **reranker 无区分度**（0.9486 vs 0.9593），根因是**我的测试文档选得太容易**；
  换真实候选后 spread=**0.9996**，registry 已按实测更正。
- 我一度把 `runtimes-tmp/reranker-dl.gguf` 当作在用 reranker 的重复项准备删除；
  **删除前核验拦下**（sha256 不同）——两个文件是**不同的** 0.6B reranker GGUF。
- 磁盘数字我错过两次并两次更正：先估 97.5 GB（偏乐观），随后在回收 partial 后误报
  **100.65 GB**（用了回收前的实测值，算术错误）；**正确值为 97.49 GB**（= 100.65 − 3.16，
  且与逐目录求和完全一致）。D: 剩余也随宿主其他写入波动（实测 93.2–106.2 GB），故报告区间而非单值。

---

## 7. 下一步（**均未授权执行**）

### 7.1 后续任务规划文档（OPEN，未授权）
`docs/future/WORK-LAB-SUPER-ENTRY-COMMAND-CENTER-LAB-ROUTER-2026-09-27.md`
（用户 2026-09-27 贴入并于 2026-09-28 再次确认）
—— WORK-LAB 作为系统级超级入口（Command Center + LAB Router + Adapters）的规划/研究文档。

**审计要点**：该文档明确标注 `OPEN（后续任务，未授权执行）`，不是 taskpack、不授予执行权限。
其 §4.6 / §5 / §6 提出 **JWT / OAuth2 / API Key / Vault 密钥管理**，与铁律
「禁止加锁 / 访问令牌 / 鉴权入口」**直接冲突**，落地时必须改写为无鉴权方案或整体舍弃。
落地须走 `taskpacks/current/` 的 task-card / registry 流程（参考 P1-C / P1-E 的 GOAL 34 先例）。

### 7.2 已登记的可选项
`O1` Hermes `state.db`（4.2 GB）`sessions optimize-storage` —— 需停机窗口 + 用户授权，
且**必须先关闭 Hermes 桌面**（桌面在运行时写健康探针不可用）。

---

## 8. 证据索引（如何自行复核）

| 类型 | 位置 |
|---|---|
| 机器真相 | `.project/governance/`：`model-*.json`、`provider-registry.json`、`runtime-registry.json`、`archeaxis-local-ai-pipeline-matrix.json`、`three-project-boundary.json`、`project-authority-index.json`、`taskpack-authority-index.json` |
| 人类报告 | `reports/MODEL-GOVERNANCE-20260928.md`；`UI_IMPLEMENTATION_REPORT.md`；`UI_REFERENCE_MANIFEST.md`；`ASSET_REPLACEMENT_MANIFEST.md`；`VISUAL_QA_REPORT.md`；`UI_DECISIONS.md` |
| 交接 | `taskpacks/current/MODEL-GOVERNANCE-HANDOFF-20260928.md`；`taskpacks/current/HERMES-EXECUTION-AUDIT-20260927.md`；`HANDOFF-UI-L10B.md` |
| 开放任务登记 | `taskpacks/current/OPEN-TASK-REGISTER.md`（含 HU-01 / HA-01 等行） |
| 原始运行证据（gitignored） | `.project-local/runs/model-governance-20260928/`（`CLOSEOUT.md`、`HANDOFF.md`、`protection-baseline.json`、`inventory.utf8.json`、`bench-deep*.json`、`deep-serving.json`、`deep-usability.json`、`e2e-results.json`、`e2e-console.log`、`DOWNLOAD-PLAN-20260928.md` + 全部脚本） |
| CI | GitHub Actions：`work-lab-gate`、`wlr-060-production-gates`；每次合并的 exact-SHA 运行 |

## 9. 验证工具（本地）

```powershell
# 结构/治理门（与 CI integration 同源）
python scripts/ci/verify_project_authority_reference.py
python scripts/ci/verify_three_project_boundary.py
python scripts/ci/verify_project_data_boundary.py
python scripts/ci/verify_contract_catalog.py
python scripts/ci/verify_error_ledger.py

# 前端
cd apps/observer/frontend
npx tsc --noEmit
npx vitest run          # 11 files / 72 tests
npm run build

# 模型治理重跑
python .project-local/runs/model-governance-20260928/inventory.py
python .project-local/runs/model-governance-20260928/e2e_pipeline.py
```

---

**声明**：本报告不含任何凭据、令牌、`.env` 值或提示/响应正文。所有数字均可按 §8 索引与 §9 命令复核。
若某数字与当前回读不一致，**以当前回读为准**（本报告是某一时刻的冻结证据）。
