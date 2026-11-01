# WORK-LAB → DeepSeek Harness 交接文档（2026-08-15）

> 本文件是 Hermes 向 DeepSeek Harness（DSH）的**完整工作交接**。DSH 接手 WORK-LAB
> 后续工作时，以本文件 + 仓库内 AGENTS.md + 50-taskpacks 下的任务包为唯一权威，
> **不得**依赖与 Hermes 的历史对话上下文。
>
> 交接人：Hermes（WORK-LAB 唯一 Writer） · 接手方：DeepSeek Harness（受限 Agent Runtime）

---

## 0. 交接摘要（TL;DR）

- **项目**：`D:/All projects/WORK-LAB`（GitHub `DTALEX66/WORK-LAB`），单根 monorepo，客户端中立的工作流控制面，管理 6 个 AI 客户端（Hermes / Codex / CC Switch / GitHub / OpenHuman / Open Design）+ 未来所有 AI 软件的 USER_GLOBAL 期望态配置。
- **两活动模块**：`10-workflow/workflow-assistance`（唯一主动 Writer）；`30-observer/work-lab-observer`（严格只读投影，不执行/不批准/不写账本）。
- **当前已完成并 merge**：三项任务收口 = 规则减重（PR #113/#116）+ 配置减重（skill 精简 PR #117）+ 模型满血字段登记，`main` = `de29e583`（merge commit）。
- **DSH 已安装并运行**：`127.0.0.1:3080`（loopback），pin `47f94385`。
- **待办（下一步优先级）**：① 体积膨胀 WL3-810 处理；② DSH adapter 交付物 review+commit；③ WL3-100/110 收编；④ DSH-040 付费 smoke（需用户填 key + 批准）。

---

## 1. 项目定位与硬边界（必须遵守）

### 1.1 边界（违反即失败，fail-closed）

1. **E:\ 盘受保护**：未经用户在本请求内**逐路径、逐操作**明确授权，禁止任何访问（枚举/读取/写入/运行/压缩/同步/上传）。
2. **秘密/凭据**：禁止读取、打印、复制、提交或上传任何 credential、token、key、password、`.env` 正文、auth/session 库、浏览器私有数据、prompt/response body、私有状态。
3. **防外溢**：所有任务数据（临时文件、缓存、日志、测试产物）必须留在 `.hermes/task-runtime/` 或 `.hermes/task-artifacts/` 内，不得写入用户 Home、桌面、系统临时目录、其他项目。`.hermes/` 已 git-ignored。
4. **Observer 只读契约**：`30-observer/` 只读投影，`CanonicalStore(readonly=True)`，SQLite URI `mode=ro`，不建目录/不迁移/不写 WAL，写操作 fail-closed。
5. **DSH 自身边界**（任务包 §0/§4.1）：DSH 是**可替换 Agent Runtime**，不是 WORK-LAB 第三个活跃模块、不是 Hermes 替代品、不接管真实 Hermes/Codex/CC Switch 配置、不写 Task Ledger 状态、不 commit/push/PR/merge/release 除非用户逐动作明确批准。
6. **不 commit/push/merge/release**：默认不授权。每个 commit/push/PR/merge 动作需显式批准。禁止 destructive reset/clean/force-push。

### 1.2 五维运行时基线（强制，audited）

每个受管软件面必须满足：① 软件入口唯一（每工具一条 canonical 启动路径）；② 桌面可达（快捷方式 target 链 resolve）；③ 官方标准 + 用户配置（官方基线赢，只管理声明的 overlay 字段，不覆盖用户 provider/model/auth/桌面状态）；④ 配置不过重无阻塞（skills <10KB 每个、guidance+rules <20KB 总、按需加载）；⑤ 模型满血（无限速/无限额/reasoning_effort 不低于官方默认 medium，cost_multiplier=1.0，无日/月 caps）。

### 1.3 Open Design 双身份

WORK-LAB 管理 Open Design **client** USER_GLOBAL 期望态（`MANAGE` + `apply_supported=false`）；Design **capability**（模型/工具/资产生成参数）属于 `DTALEX66/DESIGN-LAB` 项目，`IGNORE`，不在此收集/管理。

---

## 2. 当前精确状态（git）

- **main**：`de29e583`（PR #117 merge），上游 origin/main 已同步。历史（倒序）：`de29e58` → `c01e408`(#115) → `c1d94ea`(#116) → `a9d0373`(#113) → `9843e85`(#114) → `1c0e25f`(#111) → `45263f7`(#112) → `9583d3d`(#110)。
- **当前分支**：`feat/wl-dsh-001`（从 main `de29e58` 切出），**未 push**，工作树含 5 个未 commit 的 DSH 交付物（见 §6）。
- **未跟踪 foreign 文件**：`pre_tool_call_hook_diagnosis_2026-08-13.md`（**必须保持未读/未改/未暂存/未提交/未删除**）。

### 已完成 PR（可信任，勿重做）

- #110（全局配置 WL3-200）、#111、#112、#113（规则减重）、#114、#115（平台发现扩展）、#116（规则减重）、#117（skill 精简 + 全局配置收口）。

---

## 3. 已完成工作（本阶段，勿重做）

### 3.1 三项任务收口（PR #117，merged `de29e583`）

1. **受管 skill 精简**（WL3-810 P5）：3 个超限 SKILL.md 压到 <10KB，内容"搬家不删"——详细规则/案例移入同目录 `references/`，零内容丢失：
   - `python-testing/SKILL.md` 52.6KB→5.2KB，pitfalls 移 `references/python-testing-pitfalls.md`
   - `agent-workflow-fortress/SKILL.md` 21.9KB→5.7KB，5 个 references
   - `windows-development-environment/SKILL.md` 31.9KB→8.6KB，`references/validated-cases.md`（**保留两处安全 marker**：`### PowerShell selection policy` + `PATH shadowing` 段落，两个契约测试锁定，不得改写/删除）
   - `skill-provenance.yaml` 的 `source_sha256` 更新（**CRLF 规范化 hash 口径**，见 §7.2）
2. **全局配置收口**（WL3-200/330）：`config-ownership.json` 的 `14 Skills`→`13 Skills`（对齐 `test_managed_set_is_exactly_thirteen`）；补 4 个模型满血 OBSERVE 字段（`hermes.agent.reasoning_effort`、`hermes.model.temperature`、`cc_switch.provider.cost_multiplier`、`cc_switch.provider.rate_limits`）。
3. 验证：`measure_p5` → `skill_md_over_10kb=[]`（13 个全 <10KB）；`check_skill_provenance` PASS；`test_workflow_governance` 795 tests；`test_config_ownership` 10/10；CI 双 run 全 success。

### 3.2 DSH 接入（WL-DSH-001，本会话）

- **WL-DSH-010 发现**：上游 `deepseek-ai/deepseek-harness@47f943859bef60e4160492346772ded9b24f765a`，version `0.1.0-rc.5`（developer preview, MIT），`packageManager: pnpm@11.7.0`，`engines.node: ^22.19.0 || >=24.0.0`。
- **WL-DSH-020 交付物**（未 commit，见 §6）。
- **WL-DSH-030 隔离安装 + 启动**：已完成，web 运行在 `127.0.0.1:3080`（见 §5）。

---

## 4. 待办任务（下一步，按优先级）

### 4.1 体积膨胀 WL3-810（FAIL，最优先）

- **现状**：tracked 599 文件 / 4.95MiB vs 基线 438 / 2.65MiB（+86.8%）；`git size-pack` ≈ 404.9MiB。
- **来源**：`90-archive-manifests` 三份约 0.2–0.6MiB 清单 + 254 个 `.py`。
- **处置**：需用户批准归档或人工批准后才可清理。**不**擅自删除。

### 4.2 DSH adapter 交付物 review + commit（见 §6）

- 5 个交付物在 `feat/wl-dsh-001` 未 commit。review 通过后 commit + push + 开 PR（每动作需批准）。

### 4.3 WL3-100/110 收编

- 能力矩阵 + 身份模型的子代理产出待收编（历史挂起）。

### 4.4 DSH-040 付费 smoke

- 默认 `LOCAL_SMOKE_ONLY`；真实付费调用需用户在 DSH UI 填 DeepSeek key + 明确批准。

### 4.5 其余 WL3 任务

- WL3-120/210/220/300-330/400-420/500/510-520/610/620/720/820（详见 50-taskpacks 任务图 + Task Ledger）。

### 4.6 历史挂起

- frontend F2/F3 PARTIAL；native app.exe 重建（cargo 授权未答复）；SQLite 执行核心（400/410/420/500/510/520）。

---

## 5. DSH 运行状态（当前）

- **进程**：`dsh web` 运行中，监听 **`127.0.0.1:3080`**（netstat 确认 `TCP 127.0.0.1:3080 LISTENING`，非 0.0.0.0）。监听 PID `18688`，wrapper `proc_1bc2d4597d4d`。
- **DSH_HOME**：`.hermes/task-runtime/deepseek-harness/dsh-home`（profiles/ + storages/）。
- **source**：`.hermes/task-runtime/deepseek-harness/source`（detached HEAD @ `47f94385`）。
- **访问**：浏览器打开 `http://127.0.0.1:3080`，用户在 UI 填 DeepSeek key（Hermes/DSH 不读不显示）。
- **遥测**：已禁用（`DSH_TELEMETRY_DISABLED=1` 摘除 otel row）。
- **停止**：kill `proc_1bc2d4597d4d` 或 PID 18688，确认端口 3080 关闭。
- **回滚**：停进程 → 保留 source + receipt 只读 → 标记 runtime QUARANTINED；**不**杀未知 PID，**不**在 source checkout 里 `git reset/clean`。

---

## 6. DSH adapter 交付物（未 commit，在 feat/wl-dsh-001）

| 文件 | 说明 |
|---|---|
| `10-workflow/workflow-assistance/config/adapter-registry.json` | + `deepseek-harness` 条目（support_level=experimental，operations=[detect,capabilities,observe]，status=quarantined）|
| `10-workflow/workflow-assistance/schemas/workflow/agent-runtime-adapter.schema.json` | agent_runtime 合同 schema（§4.1 字段）|
| `10-workflow/workflow-assistance/scripts/workflow/deepseek_harness_adapter.py` | adapter：contract() + validate_commit_pin/loopback/workspace_scope/receipt/secret_redaction + detect/capabilities/observe/plan/apply(默认 UNSUPPORTED)/rollback |
| `10-workflow/workflow-assistance/tests/test_deepseek_harness_adapter.py` | 10 tests（含 schema 校验 + 公网 host/commit 漂移/scope 越界/secret 序列化/无批准 apply 拒绝）|
| `10-workflow/workflow-assistance/docs/runtime-adapters/deepseek-harness.md` | 使用/停止/健康/权限/证据/回滚/升级 |

**验证已通过**：test_deepseek_harness_adapter 10/10、test_adapter_registry 2/2、test_client_neutral_manifest 5/5、test_tiered_adapters 6/6、adapter-registry gate PASS（entries=10）、adapter-conformance 4/4、core-schemas PASS。

**路径映射说明**：任务包 §4 假设的 `config/runtime-adapters/` 目录**不存在**，已按"不建平行标准"原则映射到现有 `adapter-registry.json` + `scripts/workflow/` + `schemas/workflow/` 结构。

---

## 7. 强制约束与纪律

### 7.1 测试铁律

- 测试命令：`env -u PYTHONPATH uv run --frozen --group ci --group ci-adapters pytest`（防 Hermes venv jsonschema 污染）。
- 质量门：`python 10-workflow/workflow-assistance/scripts/workflow/run_quality_gate.py verify`（canonical gate）。从**模块路径**运行。
- 区分结构检查 vs 活执行检查；任何 failed/cancelled/missing/skipped 的必需 job = aggregate 失败。

### 7.2 skill-provenance hash 口径

- `check_skill_provenance.py` 先对文件内容做 **CRLF 规范化**（`\r\n`/`\r`→`\n`）再算 SHA-256；更新 `source_sha256` 必须用此口径，不能用 raw bytes hash。
- 直接跑需带参数：`check_skill_provenance.py --repo 10-workflow/workflow-assistance --manifest 10-workflow/workflow-assistance/config/skill-provenance.yaml`（否则 exit 2）。

### 7.3 CI 纪律

- `wait-runs` **exit 1 = 读超时，非 CI 失败**；merge 前必须显式回读 runs/jobs `conclusion`（用 `github-delivery.py checks --sha <sha>`）。
- GitHub cron = UTC；判断 workflow 未触发前用提交时间戳交叉验证时区（nightly 03:17 UTC = 本地 11:17 +0800）。
- actionlint 在 Windows 扫 `.github/workflows/` 目录报 `Incorrect function`，须**逐文件**指定；`git rev-parse 'HEAD^{tree}'` 单引号防 SC1083 + export/赋值分两行防 SC2155。

### 7.4 wrapper 边界（terminal 必须遵守）

- terminal 必须经 `python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单命令>`。
- 禁 chaining/重定向/展开/项目外绝对路径/多行 `python -c`。
- 绕行 = 写脚本到 `.hermes/task-runtime/`，脚本内可引用外部路径（脚本执行不经命令解析）。
- `.cmd` 文件（corepack/pnpm/npx）不能经 wrapper 直接 spawn，需用 `node <js入口>` 或项目内脚本（本会话已备 `run-pnpm.js`/`run-dsh.js`）。

### 7.5 Git/Windows 陷阱

- CRLF hash 须规范化；force-push 后 CI push-run 误报看 pull_request run；多分支共享工作树须 stash + `--no-verify`；GHA actionlint 集成 shellcheck（warning 也 FAIL）。

---

## 8. 工具与命令速查

- **DSH CLI**（经项目内脚本，cwd=source）：
  - `node .hermes/task-runtime/run-dsh.js .hermes/task-runtime/deepseek-harness/source .hermes/task-runtime/deepseek-harness/dsh-home <dsh命令>`
  - dsh 命令：`web`（=`--profile web`）、`--profile headless "<任务>"`、`--dump-default-config --profile web`、`--dump-config --profile web`。
- **pnpm**（逐次 pin，不改全局）：`node .hermes/task-runtime/run-pnpm.js <cwd> <pnpm args>`。
- **github-delivery.py**（`.hermes/task-runtime/`）：`checks --sha`、`jobs --run-id`、`create-pr`、`update-pr --number --body-file`、`merge --number --sha`、`wait-runs`。
- **质量门**：`run_quality_gate.py verify` / 单项 `governance`、`skill-provenance`、`context-pack`、`core-schemas`、`client-neutral-manifest`、`adapter-registry`、`adapter-conformance`、`compile`、`security`。
- **generate_current_state.py**：`scripts/ci/generate_current_state.py`（source_digest 只追踪 skills + canonical 文件，不含 config-ownership）。

---

## 9. 关键决策记录（沿用，勿推翻）

1. **Skill 精简原则**："搬家不删"——SKILL.md 只留 frontmatter + 触发条件 + 顶层纪律 + 症状索引，详细内容移 `references/`，零丢失，不删任何 WRONG/RIGHT 代码/日期/PR 号。
2. **CC Switch 契约定案（WL3-700）**：registry operations = `[detect, capabilities, observe]`；manifest `writes: unavailable`；CC Switch 路由配置 = 用户私有仅 OBSERVE 不写。
3. **openhuman/open-design 客户端**：USER_GLOBAL desired = `MANAGE` + `apply_supported=false`；DESIGN-LAB 项目配置 = `PROJECT_OVERLAY/OBSERVE`。
4. **DSH 定位**：可替换 Runtime Adapter / Agent Runtime，不是 Hermes 替代品，先 WL-DSH-010/020 只读发现+合同测试，030/040 外部/付费动作逐项批准。
5. **skill 精简先做 python-testing 一份验证范式，再批量**（已完成）。
6. **全局配置收口**：`14 Skills`→`13 Skills` + 模型满血字段（已 merge）。

---

## 10. DSH 接手后的建议执行顺序

1. **先读** AGENTS.md + 本文件 + `50-taskpacks/TASKPACK_SUMMARY.md` + `WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md`，核对 Task Ledger 与当前 git 状态。
2. **处理体积膨胀 WL3-810**（最优先 FAIL）：定位三份 archive-manifests + 254 个 .py 的归属，产出归档/清理建议，**等用户批准**后执行。
3. **review DSH adapter 交付物**（§6 的 5 个文件），通过后向用户申请 commit/push/PR。
4. **WL3-100/110 收编**：合并子代理能力矩阵 + 身份模型产出。
5. **DSH-040**：用户在 UI 填 key 后，按批准做付费 smoke（默认 LOCAL_SMOKE_ONLY）。
6. **其余 WL3 任务**按 Task Ledger 顺序推进。

> 每步涉及外部变更（commit/push/PR/merge/下载/付费调用/系统级改动）前，必须向用户列出精确动作并等批准；不得自我授权。

---

*交接完成。DSH 若对任何状态有疑问，以本文件 + 仓库 git 历史 + AGENTS.md 为准，不臆测。*
