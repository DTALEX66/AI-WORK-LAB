# DESIGN-LAB Deep Audit — Child A：仓库核心审计（Authority / 后端 / State / H1–H10）

你是 DESIGN-LAB 的首席审计工程师。仓库：`D:/All projects/DESIGN-LAB`，remote `DTALEX66/DESIGN-LAB`。
冻结基线 main SHA = `6a16c40b7a48f72757a0327ec07462d23449bb11`（2026-09-21）。所有结论必须绑定此 SHA 或明确标注 live-read。

## 硬性规则
- **只读**：禁止 git commit / stash / push / 修改任何 tracked 文件。scratch 只写 `.hermes/task-runtime/dl-ad-audit-core/`。
- terminal 必须走项目包装器（每个调用单命令）：
  `python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单条命令>`，workdir = `D:/All projects/DESIGN-LAB`。
  批量/管道逻辑用 execute_code 包 hermes_tools.terminal。读文件优先用 read_file / search_files（不经过 terminal）。
- 证据 = 文件路径 + 行号 + 测试名 + commit SHA。"代码存在" ≠ "能力可运行"：区分 DECLARED / IMPLEMENTED / STRUCTURAL_TESTED / CONTROLLED_RUNTIME。
- 中文输出。

## 任务 1：Authority / Governance 漂移
逐一读并判断是否与当前 main 一致（stale 项列出具体漂移内容）：
- `AUTHORITY.md`、`.project/governance/authority-index.json`（stale drift 条目）、根 `AGENTS.md`
- `LANGUAGE-POLICY`（是否仍描述旧 Node/TypeScript 状态；同步 Python/TS/pnpm/Vite/lockfiles 现状）
- TaskPack / Roadmap：列出仍是 open 但实际已完成（已合入 main）的任务 → 应标 CLOSED_WITH_REGRESSION_GUARD
- `reports/current/**` 逐文件：subjectSha vs 6a16c40、generatedAt、fresh/dirty → LIVE_STATE / LAST_GENERATED_PROJECTION / STALE

## 任务 2：H1–H10 历史假设逐项复验（代码级）
每项给出 STILL_PRESENT / FIXED / PARTIALLY_FIXED / NOT_REPRODUCIBLE + 证据（文件:行 + 回归测试名 + commit）：
- H1: 一个 Brief 能否同时多个 chosen Direction（找单选择约束/partial unique index/应用层 invariant）
- H2: 无 chosen 时 chosen_direction 是否回退到最后一个 Direction
- H3: unchosen direction 能否 bind Design System（bind 前是否验证 chosen）
- H4: Brief constraints string/object 类型不一致（schema + 序列化 + 持久化两侧）
- H5: Reference 是已验证 asset 还是未验证字符串/空数组（asset 存在性/项目归属/active 校验）
- H9: version/superseded_by 是真实 revision 工作（INSERT v2 + 事件 + trigger）还是仅 schema 字段（v1 全表只有 version=1）
- H10: requiresRequalification=true 的旧 E3 证据能否仍满足 Release floor（读 release gate / effective evidence 逻辑，feat/f1-release-gate-effective 与 p1b-effective-evidence 已合入，验证其实际语义）

## 任务 3：Python 后端 + SQLite/State 全量审计
- HTTP service：routing、request validation、auth、Origin/Host/CSP、error contracts、fail-closed、drain-body 行为
- 项目隔离、asset ownership、idempotency（operation_intent scope）、transaction boundaries（BEGIN IMMEDIATE?）、concurrency
- SQLite：schema 全表清单、migration 链（guarded migrations）、design_layer 单写者边界、read path 是否都走 guarded connect
- 给出「全量发现大表」行：模块 | 文件/路径 | 当前实现 | 证据 | 状态(VERIFIED/PARTIAL/STRUCTURAL_ONLY/RUNTIME_VERIFIED/HOST_REQUIRED/STALE/BROKEN/NOT_IMPLEMENTED/UNKNOWN) | 风险 | 优先级
  覆盖：Authority / HTTP API / SQLite / Design Layer / Reference / Design Systems / Evidence / CI / Release

## 任务 4：TOP 10 缺陷（P0/P1/P2）
若上述 H 项或全量发现暴露真实缺陷，按 缺陷 | P级 | 复现 | 根因 | 影响 | 修复建议 | 回归测试 | 优先级理由 输出；已修项标 FIXED SINCE PRIOR AUDIT + commit。

## 输出格式（最终答案必须是该 JSON）
{"summary": "<8-15行中文核心结论，直接回答：当前产品状态/最大P0/H项状态>",
 "hypotheses": {"H1":"...","H2":"...","H3":"...","H4":"...","H5":"...","H9":"...","H10":"..."},
 "defects": ["[P0] ...（file:line, 证据）", ...],
 "findings_table": ["模块 | 路径 | 状态 | 证据 | 风险 | 优先级", ...],
 "evidence_refs": ["file:line 或 SHA 引用列表", ...],
 "blocked": ["未能完成项及原因", ...]}
