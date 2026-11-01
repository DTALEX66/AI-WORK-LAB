# P1-B 规格：release gate 计算 effectiveEvidence（recorded vs effective 分离）

## 背景（事实，勿凭记忆）
- `design-lab/config/capability-evidence-index.json`：capability `creative-toolchain` 记录 `actualEvidence=E3` 且 `requiresRequalification=true`；`lastVerifiedTree=70dfc35c...`（STALE，非当前 HEAD）。`visual-quality`/`style-master-method` 也带 `requiresRequalification=true`（它们 actual=E1，floor 不同，勿动语义）。
- 报告 `docs/research/full-maturity-audit-2026-09-19.md` 第 780-818 行给了参考实现：recorded 与 effective 分离；`requiresRequalification=true` 或 `subjectSha!=currentSha` 时 effective 降为 `E1`（若当前 structural pass）否则 `E0`；release gate 比较的是 `LEVEL[effectiveEvidence] >= LEVEL[minimumRequiredEvidence]`，不是 recorded。

## 交付物（全部在仓库内；不 commit/push，改动留给主线）
1. **新增** `design-lab/scripts/effective_evidence.py`（纯 stdlib、确定性、无网络）：
   - `LEVEL = {"E0":0,"E1":1,"E2":2,"E3":3,"E4":4,"E5":5}`
   - `effective_evidence(record, current_sha, structural_pass)`：按报告参考实现——`record` 含 `evidenceLevel`(recorded)、可选 `requiresRequalification`、可选 `subjectSha`。命中任一降级条件 → `"E1" if structural_pass else "E0"`；否则返回 recorded。
   - `load_index(repo)`：读 `design-lab/config/capability-evidence-index.json`；`requalified(index) -> {capability_id: True}`（capabilities 里 requiresRequalification=true 的 id）。
   - `meets_floor(level, floor)`：`LEVEL[level] >= LEVEL[floor]`。
2. **改** `design-lab/scripts/verify_capability_evidence_v4.py`（只加、不删现有逻辑）：
   - main() 里 build `capability_levels` 后：对每个带 requiresRequalification 的 capability，用 `effective_evidence` 计算 effective（structural_pass 代理 = 该 capability recorded 级别 >= E1，确定性），打印注释行 `EFFECTIVE_EVIDENCE <id> recorded=<rec> effective=<eff> requiresRequalification=true`（仅信息，不计入 errors）。
   - 新增一条硬检查（今天必须 PASS）：recorded 声称满足 floor 但 effective 不满足的 capability **必须**带 requiresRequalification 标记（creative-toolchain 已带 → 不新增失败）。缺标记才 ERROR。
   - 结尾输出格式保持 `CAPABILITY_EVIDENCE_V4=PASS records=N`（errors 非空则 FAIL 不变）。
3. **改** `design-lab/scripts/verify_release_evidence.py`：
   - 在现有 git 事实检查之后：`load_index` + 若该 evidence record 的 `capability_id` 在 requalified 集合内且 `record.evidence_level` 高于 "E1"（即声称 E2-E5）→ 追加 failure：`"requalified capability cannot certify {level} on the current tree (effective floor E1); requiresRequalification=true in capability-evidence-index"`。
   - 现有契约/git/CI 逻辑不动；usage 分支(无参)行为不动。当前仓库没有对 creative-toolchain 发 E2+ 的 release claim → CI 保持绿。
4. **新增测试** `design-lab/tests/test_effective_evidence.py`（unittest、stdlib，跑法与仓库其他测试一致：文件可直接 `python design-lab/tests/test_effective_evidence.py` 自跑）：
   - 覆盖：clean record 保持 recorded；requiresRequalification 降级 E1；subjectSha 不匹配降级；structural_pass=False → E0；`meets_floor` 边界；requalified capability 的 E3 release claim 被 `verify_release_evidence` 判 FAIL（用临时 evidence 文件 + 构造 REPO 路径的测试夹具，若 git 依赖不可注入则只测纯函数 + 该 failure 生成逻辑，不要为测试改产品代码结构）。
5. **视 schema 决定** `design-lab/config/capability-evidence-index.json`：先读 `design-lab/schemas/capability-status.schema.json` 的 `capabilityRecords` 是否 additionalProperties:false。若宽松，给 creative-toolchain record 加 `"effectiveEvidence":"E1"` + `"effectiveNote"`（注明 recorded E3 为 STALE 历史证据 lastVerifiedTree=70dfc35c）；若 schema 严格，则同步在 schema 里放行这两个属性（其余不动）。**不要**改任何 recorded 级别/枚举/promotion rules（P0-I 已对齐，勿动机器枚举）。

## 验证（贴原始输出）
- `.venv/Scripts/python.exe design-lab/scripts/verify_capability_evidence_v4.py` → PASS
- `.venv/Scripts/python.exe design-lab/tests/test_effective_evidence.py` → 全绿
- `.venv/Scripts/python.exe design-lab/scripts/verify_release_evidence.py`（无参 usage 分支）→ 行为不变
- `.venv/Scripts/python.exe design-lab/scripts/verify_design_lab.py` → `VERIFY_DESIGN_LAB=OK total=49 failed=0`

## 禁区
- 不碰：AUTHORITY.md、.project/、docs/architecture/、reports/、AGENTS.md、authority-index、LANGUAGE-POLICY（另一子代理的域）。
- 不 commit/stash/push；不装依赖；不联网；stdlib only。
