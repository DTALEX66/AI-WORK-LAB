# DESIGN-LAB：DEEPSEEK 批量低风险任务执行包

> 给 DEEPSEEK：这是可直接转交的独立任务文档。先完成本文的接管检查，再按 DS-01—DS-12 执行；不要接管 GPT 的核心代码修复。本文件只拆分工作，不替代 R3 原任务定义，不代表任务已完成。

日期：2026-09-06。用户要求：高难度留给 GPT，大量低难度工作交给 DEEPSEEK。知识迁移继续延后。

## 1. 项目、现状与权威来源

DESIGN-LAB 是 AI 原生、平台中立、宿主原生的专业视觉设计能力层；拥有设计合同、拆解、质量与 rights、宿主适配和可编辑交付。它不是第二画布、通用 Agent runtime、模型网关或知识库。独立运行，不要求 WORK-LAB、ArcheAxis 或 Open Design 在线。

本地项目：`D:/All projects/DESIGN-LAB`。云端身份：`github.com/DTALEX66/DESIGN-LAB`，本次没有远端读回，不保证云端包含当前成果。

接管基线：分支 `codex/r3-runtime-correctness`，HEAD `c4dccd58331bc4561eb89265283d924b7630d113`。工作区有大量未提交修改及未跟踪文件；HEAD 不是当前完整代码快照。禁止 reset、restore、clean、覆盖、重新 clone 后假定成果已齐全。

必须读取本地以下文件；本文已给出工作内容，但实际状态以这些来源为准：

- `AGENTS.md`：根执行规则；有更近的 AGENTS 时也必须读取。
- `docs/taskpacks/DESIGN-LAB-CLOUD-REAUDIT-TASKPACK-2026-09-06.md`：当前权威任务包 DL-TP-20260906-R3。
- `design-lab/config/task-ledger-r3.json`：唯一任务状态编辑源，本包不授权 DEEPSEEK 修改。
- `reports/current/TASK_PROGRESS.json`：生成状态，不能手改。
- `.project/paths.json`：运行目录及共享输入边界。

当前 24 项的账本状态：R3-01/05/07 为 DONE_LOCAL；R3-02/04/06/08 为 PARTIAL；其余为 TODO。原 Codex 13 项范围为 01/02/03/04/05/06/07/08/09/10/13/16/24，其中 3 完成、4 部分、6 待完成。这些数量不是产品完成百分比。

最近已完成的测试记录时间为 2026-09-06 19:10:05 +08:00：281 个定向用例中 280 通过、1 个 Windows 原生符号链接用例因 WinError 1314 跳过；49 个统一检查通过。当前全量 Python 测试未重新跑完；历史 618 不能套到当前树。工具版本查询成功不代表 PS/AI/ComfyUI 工作流通过。

证据目录：`.project-local/task-artifacts/r3-execution/model-readiness-final/`，内有 `results.json`、`focused.log`、`unified.log`、`license.log`、`doctor-live.log`、`machine-sample.json`。证据是本地忽略文件，云端或另一台机器可能没有；缺少时明确记 MISSING，不能重建假日志。

## 2. 权限与交接规则（必须遵守）

1. 本轮只允许读取公开项目源码、任务文档及明确列出的非敏感证据；只新增下述交付目录内的文件。已有原件、历史基线和所有未提交源码均保留。
2. 持久交付目录：`docs/handoffs/deepseek-r3-20260906/`；运行日志、临时脚本、缓存：`.project-local/task-artifacts/deepseek-r3-20260906/` 和 `.project-local/task-runtime/deepseek-r3-20260906/`。首次使用先核对无 reparse 越界，运行目录须 Git ignored。目录若已有同名成果，创建新的 run 子目录，不覆盖。
3. 不写 `.hermes/`、用户目录、桌面、共享库或其他项目；不访问 E 盘。共享根只作身份信息：`D:/All projects/Design assets`、`Model library`、`Design External Configuration`、`OS External Configuration`，本包不授权递归扫描或改写。
4. 不读取 `.env`、认证、私钥、tokens、浏览器、Agent 私有目录、会话数据库或原始私密对话。历史恢复只核对已公开/已脱敏归档的 locator、大小和 hash；涉及原始对话正文或权属不清数据时留队列交用户/GPT处理。
5. 不改 `src/`、`packages/`、`integrations/`、`apps/`、现有 tests、schemas、config、`.github/`、锁文件、根指令或 `reports/current/`。发现问题写候选补丁说明，不直接修核心行为。
6. 不安装软件/模型、不调用真实宿主或 GPU、不启动服务、不迁移缓存/DB、不删除文件、不全局改配置、不提交/push/PR/发布、不签署或代填 Human Gate、模型 trust 审批。
7. 同一 checkout 同时只能有一个写入者。开始前确认 GPT 已暂停写入；若仍在写，只读收集后等待交棒。不能以“只改不同目录”绕过单写规则。并行执行须独立 worktree，且应先由 GPT 处理当前未提交基线；本包不要求 DEEPSEEK自行搬运脏树。
8. DEEPSEEK 产出是候选材料，GPT 负责复核并更新正式账本。DS 完成不等于相应 R3 整项完成。

## 3. 接管检查与节省开销

- [ ] 在 PowerShell 从项目根执行以下只读命令，保存输出到本轮 evidence；读取文件时不把包含敏感内容的文件全文抄入报告。

```powershell
Set-Location -LiteralPath 'D:/All projects/DESIGN-LAB'
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
git diff --name-only
git diff --cached --name-only
git check-ignore .project-local/task-artifacts/deepseek-r3-20260906
& '.venv/Scripts/python.exe' -B -c 'import sys; print(sys.executable); print(sys.version)'
```

- [ ] 确认上述基线差异；新分支或 SHA 变化不自动判故障，但必须先核对上下文，不能按本文历史快照覆盖新成果。
- [ ] 对输入建立一次 SHA-256 清单，每行记录相对路径、大小、hash；不重复全文扫描整个仓库。JSON 用解析器，路径用 `rg --files` 首先定位，文档链接按所在目录解析。
- [ ] 每批最多处理 50 条资料。每批落盘后继续下一批；只汇报新增成果、具体阻塞，不反复复述整个项目。
- [ ] 不重复运行旧 `verify_model_readiness.py`：其固定输出目录会覆盖已登记证据。本包通常无需重跑测试；DS-10 只允许下列只读报告检查。

```powershell
& '.venv/Scripts/python.exe' -B 'scripts/generate_current_reports.py' --check
```

此命令失败只报告漂移，不能去掉 `--check` 生成覆盖。主环境先前为 Python 3.13.14；R3-09 要求的 Python 3.12 产品资格由 GPT 处理，不自行切换环境。项目中当前没有 `scripts/workflow/execution_preflight.py`，不能凭全局说明虚构可执行入口。

## 4. 统一输出格式

每个 DS 任务交付一个下文指定文件，UTF-8；数据文件采用 JSON，汇总采用 Markdown。所有路径相对项目根，外部公开来源使用完整 URL。

记录必须包含：`record_id`、`task_id`、`r3_ids`、`source_locator`、`observed_at`、`status`、`evidence_locator`、`notes`。无法证明的字段用 null 和明确原因，不填零 hash 或伪造时间。

状态限于 `VERIFIED`（仅说明该条材料核验）、`MISSING`、`CONFLICT`、`HISTORICAL`、`NOT_EXECUTED`、`NEEDS_GPT`。VERIFIED 必须写清“验证了什么”，不能泛指产品可用。公共网页只作来源证据；若联网不可用，该行记录失败后继续其他不依赖网络的任务。

## 5. DEEPSEEK 可立即执行的 12 项

### DS-01：24 项需求与当前状态对照（支持 R3-01/03）

输入：权威 R3 正文、冻结定义 `docs/history/taskpacks/r3-tasks-2026-09-06.json`、正式 ledger、生成进度。

- [ ] 提取全部 24 项 ID、标题、原依赖、旧任务 ID、交付物、每条验收条件。
- [ ] 对照当前四轴状态及缺口，不修改原文字段；一个验收条件一行，不以任务标题代替覆盖。
- [ ] 输出 `01-requirements-matrix.json`。每条以 R3 ID + 验收序号为稳定键，列入尚无证据的条件。

验收：24 个 ID 无缺漏/重复；依赖和冻结定义完全一致；每条原验收都有对应记录。发现原包内部矛盾标 CONFLICT 交 GPT，不自行重写 DAG。

### DS-02：历史原件定位与缺失清单（支持 R3-03）

原包引用 `evidence/history-current-tree-coverage.json`，但本轮已确认项目根没有 `evidence/`。原包提到 536 条 manifest、1450 条 occurrence、276 匹配/260未匹配，这些是待复核的基线数字，不可直接作为当前完整性证明。

- [ ] 先列用户指定 ZIP `C:/Users/ALEX/Desktop/DESIGN-LAB-CLOUD-REAUDIT-TASKPACK-2026-09-06.zip` 的成员名，不运行任何成员脚本、不直接 ExtractAll；检查绝对路径/父目录/reparse/超大解压风险。仅公开文档和索引可读。
- [ ] 在仓库 `docs/history/`、`reports/history/` 和 Git 已跟踪文件名中定位原清单；旧 Git 只查询明确文档路径，不遍历整个用户磁盘或私有历史数据库。
- [ ] 输出 `02-history-locators.json`，标注 archive/member 或 commit/path、大小、hash、来源状态；没找到要列实际查过的范围。

验收：每个引用来源有可复核定位或 MISSING；不创建空的“恢复原文”，不读取/转存私密对话正文。若 ZIP 不在执行机器，直接标 MISSING 并继续 DS-04。

### DS-03：逐条历史记录状态与旧任务映射（支持 R3-03）

前置：DS-02 找到合法且非敏感的原清单；未找到则本项记录 MISSING，不虚构 536 行。

- [ ] 保留 `original_id` / `occurrence_key`，追加候选状态，区分同内容多次出现与重复 ID。
- [ ] 用明确旧任务引用建立历史记录→旧任务→R3 的映射；无依据不靠同名强行匹配。
- [ ] 输出 `03-history-crosswalk.json`；如能核对 536/1450，则附实际计数与源 hash；否则写观测数量及差额。重复原件可共享 locator，但不删除 occurrence。

验收：原清单字节不变，输入记录逐条有输出/排除理由；无法取回或权属不清的记录进入 unresolved，不宣称 history_complete。

### DS-04：路径、入口与链接清单（支持 R3-02）

输入范围：根 AGENTS/README、`.project/manifest.yaml`、`.project/paths.json`、`docs/taskpacks/`、`docs/decisions/`、`scripts/`、`src/design_lab/runtime/`；排除 `.git`、环境、缓存和历史归档正文。

- [ ] 批量找 `.hermes` / `.project-local` / 外置目录引用，按活跃代码、活跃说明、历史引用分类。
- [ ] 检查本轮三份交接和当前 R3 文档中的本地 Markdown 链接；不将计划创建路径当成已存在链接。
- [ ] 输出 `04-path-link-findings.json`，记录文件/行号、解析后目标、存在性、分类和最小修改建议。

验收：每个缺陷可定位；历史 `.hermes` 不一律当错误。静态引用不冒充实际写入进程追踪；不自动替换或改启动器。

### DS-05：现有 CI 触发覆盖表（支持 R3-04）

输入：`.github/workflows/canonical-verify.yml`、`release-gate.yml`。

- [ ] 分别提取 push、pull_request、workflow_dispatch 的触发条件及 jobs；不要将 YAML 的 `on` 错解成布尔键。
- [ ] 对 `apps/workbench/example.ts`、`src/design_lab/runtime/paths.py`、`integrations/hosts/adobe/adapter.manifest.json`、`packages/capabilities/reconstruction/contracts.py`、`pyproject.toml`、`uv.lock`、`AGENTS.md`、`.project/paths.json`、`scripts/design_lab_doctor.py` 逐一给出两个事件是否覆盖及匹配规则。
- [ ] 输出 `05-ci-trigger-matrix.json`，缺口另附 `05-ci-proposal.md`，只提出候选修改，不改 workflow。

验收：push 与 PR 分列；静态匹配明确不是已触发 CI 的证据；保留既有 gate；正式 CI 变更、renderer 来源/hash、Python 环境取舍归 GPT。

### DS-06：现有测试证据目录化（支持 R3-04/05/06/07/08）

输入仅限本包第 1 节列出的 `model-readiness-final/` 六个文件。

- [ ] 读取 results 中实际命令、退出码、耗时、时间、源文件 hash；核对日志尾部结果。
- [ ] 将 280 PASS 与 1 skipped 分开，记录 WinError 1314 环境失败；将 49 gates 与 unit 数量分开，不相加算成功数。
- [ ] 输出 `06-test-evidence-catalog.json`；对 results 声明的公开项目源文件重新比对 hash，变动标 STALE（用 CONFLICT 状态并写原因），不重新给旧证据盖时间戳。

验收：每项结论可回到实际日志；没有日志的机器只能填 MISSING；旧 618 不冒充当前全量。

### DS-07：软件与模型声明差异表（支持 R3-07/08/19）

输入：`design-lab/config/external-assets-index.json`、`capability-evidence-index.json`、`profiles.json`、`model-manifest-trust.json`、`machine-sample.json` 及已有公开模型卡链接。

- [ ] 分列“索引声明、文件观测、校验、加载、推理、宿主工作流”，缺哪项就写哪项，不能写笼统 READY。
- [ ] 整理模型 ID/revision、文件名、已声明 hash、来源 URL 和证据日期；不用本地随便算出的 hash 代填上游身份。
- [ ] 输出 `07-capability-evidence-gaps.json`。仅整理元数据，不扫描/加载约 42.5 GB H3 权重、不安装 ASR 环境、不签许可。

验收：profiles 默认禁用不被修改；license、region、resources、dependencies 四类问题分开；PS 进程名查询无结果不能写“PS 未打开”。法律适用与模型资格结论留 GPT/用户确认。

### DS-08：参考图测试候选与验收记录表（支持 R3-13/14/22）

- [ ] 整理 5—10 个公开设计作品页面 URL，覆盖文字几何海报、电商主图、照片+蒙版、2D、复杂纹理、3D/空间参考；同时覆盖 R3-13 必需三类。优先作者/品牌原站或知名设计平台的作者原作页。
- [ ] 每条记录作者、页面、类别、可见许可/权利不明、文字密度、潜在可矢量化区域、栅格区域、预期测点。页面可访问不等于有下载/复刻/再发布权。
- [ ] 输出 `08-reference-candidates.json` 和 `08-reconstruction-acceptance.md`，验收表包括文字准确、对象层级、矢量路径、透明图层、局部修改、重开读回、视觉误差及人工判断。

验收：5—10 个不同作品，不把同一图的裁切当多样性；只提供链接与元数据，不下载付费/受限素材、不开始复刻、不上传用户图。联网不可用则明确本项尚未满足数量要求，不编造链接。GPT 决定采用及 rights 门。

### DS-09：既有接口、命令与运行说明目录化（支持 R3-09/10/16）

输入：`pyproject.toml`、`src/design_lab/runtime/`、`scripts/design_lab_doctor.py`、`packages/capabilities/reconstruction/`、`integrations/generators/comfyui/`。

- [ ] 提取实际存在的入口、参数、模块职责、输入输出合同和对应测试路径，记录 source_locator。
- [ ] 标注 `package=false`、主环境版本、尚无受验产品服务/工作台的差距；不把存在的 adapter 文件当真实服务器联通。
- [ ] 输出 `09-existing-interfaces.json` 与 `09-operator-runbook.md`。说明只包含已核验存在的命令，未来产品 API 放在“待 GPT 提供”清单而非伪造调用示例。

验收：每个命令可在源码找到定义；不使用不存在的 preflight 脚本、不启动宿主服务。此项是接线资料，不实现新 API。

### DS-10：当前报告一致性复核（支持 R3-01/24）

- [ ] 从当前生成进度读取状态，与 DS-01 对照。
- [ ] 运行第 3 节唯一 `generate_current_reports.py --check` 命令，记录实际退出码/输出/解释器。
- [ ] 输出 `10-report-consistency.json`；如漂移列出涉及文件供 GPT 处理。

验收：不手改生成报告或正式 ledger；PASS 仅代表这次投影检查通过，不能提升任何 host_live/delivery 状态。

### DS-11：交付前维护材料（支持 R3-24，依赖满足前仅准备）

- [ ] 在 Git 跟踪文件列表中过滤非敏感公开源码/素材，统计扩展名、大小和最大的 20 个文件；不扫描 ignored 模型、DB、用户缓存。
- [ ] 对大于 1 MiB 且相同大小的候选计算 hash，列真实重复；没有候选就记录 0，不扩大范围。
- [ ] 从现有 `LICENSE`、`LICENSES/`、`NOTICE`、`pyproject.toml`、`uv.lock` 汇总已声明依赖/来源与缺口，不代做商业许可审批。
- [ ] 输出 `11-repository-maintenance.json` 和 `11-delivery-checklist.md`：列安装/升级/备份/恢复/冷暖启动/原生工程/CI/云端读回的所需证据及现有缺口。

验收：不删重复、不重写历史、不全迁 LFS、不把“有备份说明”写成恢复测试通过；不提前执行 R3-24 发布。

### DS-12：汇总与回交 GPT（依赖 DS-01—11 的结果或明确缺口）

- [ ] 输出 `12-DEEPSEEK-RETURN.md`：完成清单、未完成清单、具体 blocker、建议 GPT 首先处理的最多 5 项问题、所有新文件路径与 hash。
- [ ] 输出 `12-results.json`：12 项 DS 状态、映射 R3、证据和未满足条件；逐项说明低风险资料完成与 R3 主任务完成的区别。
- [ ] 复查 Git status：变更只在本文允许的新目录；将接管前后差异写入回交报告，发现其他写入立即报告，不能自作主张恢复。

验收：无越界改动；JSON 可解析；本地引用可解析或明确 MISSING；原文件 hash 未被本轮改写；GPT 能依据文件直接接续，不必重新扫仓库。

## 6. 不要分给 DEEPSEEK 的事项

事务/恢复/幂等/租约与 fencing、模型独立信任机制、真实 OCR/ASR/H3 推理、CUDA 与 native symlink 问题、产品 Python 版本迁移、服务安全/API设计、RuntimeAdapter、ComfyUI 取消与断线语义、Adobe 文档定位/原生读回/回滚、拆解算法及质量评估、人工审批、正式状态升级、GitHub交付，均交 GPT。

若任何 DS 项需要触及这些内容，交付已完成部分和精确问题即可；不要以“完成全部”为由越权改动，也不要让一条缺失档案阻塞其余低风险任务。

## 7. 可直接复制给 DEEPSEEK 的启动话术

请执行本文件的 DS-01—DS-12。先读取项目 AGENTS 和当前 R3 任务包，核对脏工作区与单写接管。只在允许的新交付/运行目录落盘，保留 GPT 的全部未提交成果。批量推进可核验的资料工作；模型推理、核心代码、宿主、全局设置和发布不要动。缺少来源就列出查过范围与 MISSING，不编造证据。完成后给我 `12-DEEPSEEK-RETURN.md` 和 `12-results.json`，由 GPT 复核整合。
