# Batch F-4 规格：Host E3 预置脚手架（可校验证据契约 + 探针 + 绝不伪造 E3）

## 背景（事实，先读代码再动）
- 报告明确：真实 Adobe E3 **不属本阶段默认完成条件**；没有 owner 授权和真实 Host 时，只能准备 **contract / test / evidence harness**，**不能制造 E3**。
- 现状取证：`design-lab/schemas/` 下**没有**任何 host/E3 证据契约（0 命中）；`integrations/hosts/adobe/photoshop-reconstruction/` 存在 UXP 适配器包，`design-lab/scripts/verify_{photoshop,illustrator}_reconstruction_adapter.py` 只做**静态结构**校验（`manifestVersion==5`、禁止 `https://*` 通配网络权限、必备 UXP token `executeAsModal`/`executionContext.isCancelled`/`prepareRunRelativeLayers`）。
- 已有通用契约 `design-lab/schemas/evidence-record.schema.json`（EvidenceRecord；required: evidenceId/level/boundTreeSha/owner/timestamp/command/environment/inputHash/result/approver；`additionalProperties: false`）→ **复用**它，不造第二套证据体系。

## 交付物
1. **扩展**（仅新增，保持既有记录仍合法）`design-lab/schemas/evidence-record.schema.json`：新增可选 `host` 对象（内层同样 `additionalProperties: false`），字段：`product`、`productVersion`、`adapterId`、`adapterVersion`、`adapterSha256`、`invocation`、`readback`（数组）、`artifacts`（数组，元素含 `path` + `sha256`）。并在 schema 内表达：`level == "E3"` 时 `host` **必须存在**（用 `if/then` 或等价的 draft 2020-12 表达）。
2. 新增 `design-lab/scripts/verify_host_e3_evidence.py`（stdlib only，不联网）：
   - `--record <path>`（可多次）；未给则扫描约定目录 `.project-local/task-artifacts/host-e3/*.json`（gitignored，缺失即无记录）
   - 语义校验（fail-closed）：契约校验（可用仓库既有 `jsonschema`，或手写等价校验并说明）+ 每个 artifact 的 `sha256` 必须与本地文件**实际哈希**一致 + `boundTreeSha` 必须等于 HEAD 或仍是其祖先 + `approver` 非空
   - 输出契约：`HOST_E3=<NO_RECORD|VALID|INVALID> records=N findings=[...]`
     - **无记录 → `NO_RECORD`**（诚实：既不是 E3、也不是失败），退出码 0，并显式打印「当前没有 host E3 证据，能力等级不得因此提升」
     - 有记录但不合法 → `INVALID` + 非 0
   - **绝不**自行生成或提升 E3
3. 新增 `design-lab/scripts/host_e3_probe.py`：探测本机是否存在真实 host 运行面（适配器包目录 + 可配置桥接入口，如 env `DL_HOST_E3_ENDPOINT`），输出 `HOST_E3_PROBE=<HOST_PRESENT|HOST_ABSENT> details=...`。**不得启动任何宿主软件**（不跑 Photoshop/Illustrator/任何 GUI）。
4. 新增测试 `design-lab/tests/test_host_e3_harness.py`（unittest，临时目录造记录）：
   - 伪造 E3（无 `host` 块）→ INVALID
   - 有 `host` 但 artifact sha256 不符 → INVALID
   - 有 `host` 且哈希正确、`boundTreeSha` 合法 → VALID
   - 无记录 → **NO_RECORD**（绝不 VALID/E3）
   - probe 在无 host 环境 → HOST_ABSENT
5. **不做**：不执行任何宿主软件；不创建真实 E3 证据；不改 `capability-evidence-index.json` 的 recorded 级别；不碰 `reports/`、`AUTHORITY.md`、`.project/`、`docs/`、`AGENTS.md`、`apps/workbench/**`、`design-lab/scripts/verify_release_preflight.py`（另一子代理的域）。

## 验证（贴原始输出）
- `.venv/Scripts/python.exe design-lab/tests/test_host_e3_harness.py` 全绿
- 无记录实跑：`verify_host_e3_evidence.py` → `HOST_E3=NO_RECORD`
- 探针实跑：`host_e3_probe.py` → `HOST_E3_PROBE=HOST_ABSENT`（本机）
- `.venv/Scripts/python.exe design-lab/scripts/verify_design_lab.py` → `VERIFY_DESIGN_LAB=OK total=49 failed=0`
- `.venv/Scripts/python.exe scripts/verify_authority_gates.py --zero-spill` → 若 schema 摘要进入契约图导致漂移，**原样上报主线**，不要手改 `reports/`
- `git status --short`、`git diff --stat`

## 命令纪律
- wrapper 单命令：`python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单命令>`，workdir=`D:/All projects/DESIGN-LAB`；禁 shell 串联。
- 不 commit / stash / push / 建分支；不装依赖；不联网；不启动宿主软件。
