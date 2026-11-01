# DESIGN-LAB 阶段总览报告（供云端 GPT 审计）

- **生成时间：** 2026-09-27（Asia/Shanghai）
- **观察 exact SHA：** `d116b14995fcdbba1b165ec5bc3124f5daed3d15`（`main` = `origin/main` = 本地 HEAD）
- **性质：** 只读汇总。**不是** Authority；权威一律以 `/AUTHORITY.md` (`DL-AUTHORITY-2026-09-18-R2`)
  与 `/.project/governance/authority-index.json` 为准。
- **live 事实原始 dump：** `.project-local/task-artifacts/project-survey-2026-09-27/audit-live-facts.json`（未入仓）

> ⚠️ **给审计方：** 本报告所有动态事实（SHA / 分支数 / PR / CI / required checks）都是
> **2026-09-27 的时点读数**。按 AUTHORITY §16，审计**必须**自行 live-read 复核，
> 不得以本报告替代 live remote 读回。本报告已标明每项的可复核来源。

---

## 0. 上传与双端一致性（live 核验）

| 项 | 值 | 复核命令 |
|---|---|---|
| local HEAD | `d116b14995fcdbba1b165ec5bc3124f5daed3d15` | `git rev-parse HEAD` |
| local main | 同上 | `git rev-parse main` |
| origin/main | 同上 | `git rev-parse origin/main` |
| ahead / behind | **0 / 0** | `git rev-list --left-right --count main...origin/main` |
| 未推送提交 | **无** | `git log origin/main..HEAD --oneline` |
| 工作区 | **干净**（`git status --porcelain` 空） | — |
| stash / worktree | **0 / 1** | `git stash list` / `git worktree list` |
| 远端分支 | **仅 `main`** | `git ls-remote --heads origin` |
| 远端 tag | 16（`archive-evidence/2026-09-25/*`） | `git ls-remote --tags origin` |
| open PR | **0** | `gh pr list --state open` |
| branch protection | `enforce_admins=true`、`strict=true`、**9 项 required checks** | `gh api .../branches/main/protection` |
| main 最新 CI run | `36336694172` @ `d116b14995fc` = **success** | `gh run list --branch main` |
| 该 run artifacts | **2 个**：`workbench-e2-d116b14995fc…`(524 B)、`secret-history-report`(564 B)，均未过期 | `gh api .../runs/<id>/artifacts` |

**9 项 required checks（live 逐项读回）：** Python gate · MiniGame node gate · Generated-artifact
clean-tree gate · License & secret hygiene gate · Open Design host adapter gate · Top-level Authority
consistency gate · Workbench strict-TS product gate · Workbench browser E2E · DeepSeek authority gate chain

**结论：全部已上传，双端一致。** 未入仓的只有 `.project-local/**`（gitignored 的运行/证据根，
按 AUTHORITY §7 与 `.gitignore:71` 的设计如此）。

---

## 1. 项目身份与不变量（审计基线）

- **定位：** AI-native、Agent-platform-neutral、host-native 的职业视觉设计智能与生产能力层
- **拥有：** Brief / ReferenceSet / Research / Direction / Design System / Design IR / Domain Pack /
  Quality·Critique·Jury / rights·preflight / Host·Tool·Generator Adapter / editable delivery / BOM /
  provenance / readback / rollback / evidence
- **不拥有：** 第二画布、通用聊天、通用 Agent Runtime/Model Gateway、WORK-LAB 全局治理、
  ArcheAxis 长期知识真值、宿主私有 DB
- **宿主：** Open Design = 可选 Host Adapter；MiniGame = game-visual fixture，**不是产品线**
- **运行根：** `.project-local/`（唯一 active）；`.hermes` **不是**活跃写入根
- **Evidence 分级：** E0 DECLARED → E1 STRUCTURAL → E2 CONTROLLED_RUNTIME → E3 REAL_WORKFLOW →
  E4 INDEPENDENT_ACCEPTANCE → E5 RELEASED/REPEATABLE

---

## 2. 阶段总览（TaskPack `DL-TP-20260918-FINAL-AUTHORITY-CONVERGENCE-R2` A–O 段）

图例：**CLOSED** = 已落地且有 regression guard ｜ **PARTIAL** = 部分落地 ｜ **OPEN** = 未开始 ｜
**BLOCKED** = 前置未满足

| 段 | 内容 | 优先级 | 状态 | 守卫 / 证据 |
|---|---|---|---|---|
| **A** | 顶层 Authority 落仓与激活（A001–A005） | P0 | **CLOSED** | `AUTHORITY.md`、authority-index、`scripts/verify_top_level_authority.py`（10 checks）+ required check `Top-level Authority consistency gate` |
| **B** | 历史/冲突冻结（B001–B004） | P0 | **CLOSED** | `docs/current/HISTORY-FREEZE-RULES.md`；UCR handoff 已加 `HISTORICAL_EXECUTION_RECORD / NON_AUTHORITATIVE` banner（verifier check `handoff-demoted`） |
| **C** | 已关闭项只做 regression guard | — | **CLOSED** | 见 §3 的守卫清单；无新 regression evidence 不得重开 |
| **D** | Workbench strict TypeScript 产品化（D001–D006） | P0 | **CLOSED** | required check `Workbench strict-TS product gate` + `git diff --exit-code -- apps/workbench/build` + `verify_workbench_packaging.py` + `Workbench browser E2E` |
| **D+** | **B10 UI 套件 1:1 视觉复刻**（本轮新增，非 TaskPack 原条目） | P1 | **CLOSED** | PR #171/#172/#173；见 §4 |
| **E** | 第一条全栈 Vertical Slice：`Project→Brief→Reference→Direction→DesignSystem` | P0 | **CLOSED_WITH_REGRESSION_GUARD** | `design-lab/tests/test_design_layer_http.py`（18 用例）+ browser E2E；PR #123/#124 |
| **F** | Native production Vertical Slice：`DesignSystem→DesignIR→PS/Illustrator→可编辑产物→readback→patch/recovery` | P1 | **OPEN** | 部分结构存在；**无真实 Host E3** |
| **G** | Quality / Jury / Rights / Preflight / Handoff | P1 | **PARTIAL** | 有 capability 与 preflight 读回；Automated Assessment 与 Human Jury 的**分离**未完成 |
| **H** | Evidence / CI（H001–H003） | P1 | **PARTIAL** | H003 CLOSED（Authority + Workbench gate 已入 required）；H001 **本轮首次真正满足**（见下） |
| **I** | Language 小收口 | P1 | **PARTIAL** | `LANGUAGE-POLICY` 残留句已清（verifier `single-ruff-fact` 守卫）；**Ruff 是否 enforce 仍未决策** |
| **J** | Branch cleanup | P1 | **CLOSED** | 远端 28 → **1**（仅 `main`）；open PR 0 |
| **K** | Golden Workflows `GOLDEN-001` / `GOLDEN-002` | P1 | **NOT EXECUTED** | 无 golden 运行记录 |
| **L** | P2 扩展（UI/UX、Packaging、Spatial、Motion、Video、Audio、3D/VFX…） | P2 | **BLOCKED** | TaskPack 明文：核心 Vertical Slice 未工作前禁止「全都支持」 |
| **M** | Permanent anti-drift gates（17 条） | 常驻 | **ACTIVE** | 见 §5 |
| **N** | 固定执行汇报（17 字段） | 常驻 | **ACTIVE** | 见 §6 |
| **O** | Closeout | — | **PARTIAL** | Authority/index/AGENTS/gate 已闭环；产品链路（F/G/K）未闭环 |

### 2.1 H001 artifact proof —— 本轮发生实质变化

TaskPack H001 原文：*「main run #182 artifacts=0。如要求 artifact proof，必须真实
`upload → GitHub API query → identity → download/readback → hash → run/SHA binding`」*。

**live 现状：** main run `36336694172` @ `d116b14995fc` 有 **2 个 artifacts**，且
`workbench-e2-d116b14995fcdbba1b165ec5bc3124f5daed3d15` **名称内嵌 subject SHA**，即
**run/SHA 绑定是真实可核验的**。→ H001 的「artifacts=0」前提对当前 main **已不成立**。

⚠️ 但审计方须注意：**advisory** 门禁 `CI artifact proof (H001)` 在本轮两个 PR run 上
**一 pass 一 fail**（自标 `CI_ARTIFACT_PROOF=BLOCKED gate=ADVISORY`，原因是 `RUN-SHA-MISMATCH`
——它比对到另一次 run 的 artifact）。该门禁**不在 9 项 required checks 内**，且 #173/#174/#175
三轮表现完全相同，属**既有 flaky**，非本轮引入。这一点请独立复核。

---

## 3. 已交付 PR 历史（live 读回，latest 15）

| PR | 合并时间 | merge commit | 主题 |
|---|---|---|---|
| #175 | 2026-09-27T17:22:27Z | `d116b14995fc` | 证据根允许集合对齐 AUTHORITY §7 |
| #174 | 2026-09-27T15:47:28Z | `cae840d2a45d` | 真值对齐：R5 证据回填 + Authority 动态事实 + 投影重绑 |
| #173 | 2026-09-27T14:40:41Z | `634071f3c8ff` | B10 1:1 外壳：真实 `.app/.main/.content` + B10 浮层 |
| #172 | 2026-09-27T13:51:23Z | `e273436aa547` | B10 1:1 结构收敛 |
| #171 | 2026-09-27T07:18:09Z | `5686feaf320b` | UI B10 最终视觉系统落仓 |
| #170 | 2026-09-27T06:13:41Z | `752486073e2a` | no-overclaim：browser-host E2 加同对象 evidence_ref |
| #169 | 2026-09-27T05:54:56Z | `adf178328fec` | 09-27 全量审计 close-out + cloud-reachability upload |
| #168 | 2026-09-27T03:54:38Z | `6ba2578a3458` | 摄取 09-27 云端审计 + 投影重绑 |
| #167 | 2026-09-26T14:39:23Z | `03086b8fb207` | 终局上传：全量 close-out ledger |
| #166 | 2026-09-26T11:54:19Z | `b7fa8f9a2e54` | 非操作性全量清扫闭环 |
| #165 | 2026-09-26T14:24:01Z | `d8edddc38d30` | Lane-C：workbench 模块化拆分 |
| #164 | 2026-09-26T01:08:07Z | `f9d885e62dda` | 摄取第 4 次 GPT 云端审计 + 重绑 current-report |
| #163 | 2026-09-26T00:17:17Z | `f1fbbb377b17` | 09-25 审计闭环交接 #159–#162 |
| #162 | 2026-09-25T23:54:08Z | `41f8ab63ba25` | Prompt I：Handoff Readiness combiner（5 层闭环） |
| #161 | 2026-09-25T17:25:04Z | `9c1e90f42c1c` | Prompt F：context capsule + session receipt + context-integrity gate |

**每次 main 合并后 Canonical Verify 全部 `success`**（最近 8 个 run 逐项 live 读回，见 §0）。

---

## 4. 本轮三件事的实质变化（便于审计聚焦）

### 4.1 PR #173 — B10 1:1 视觉复刻（真实缺陷修复）

- **根因**：B10 外壳以 `position:fixed; z-index:65` 不透明覆盖层贴上去，把 `z-index:20` 的视图宿主整个盖住；
  topbar 是 body 级兄弟节点被 `~ header{display:none}` 隐藏；B10 的 `main.main`/`section.content` **从未生成**。
  → 路由态只渲染出侧栏 + 一片空黑（有 Chromium 实拍为证）。
- **另修**：`kpiCard` 形参顺序与全部 13 处调用点相反（B10 的 35px 主色大数字显示的是**标签**而非数值）。
- **另修（CI 才发现）**：`el()` 用 `setAttribute('style')` → 服务端 CSP `style-src 'self'`（无 `unsafe-inline`）
  阻断内联样式属性并产生 console error，`workbench-browser-e2e` 因此失败（9 门禁全绿、唯此项红）。
  改为走 CSSOM（`style.cssText`）——**对精确 CSP 做过浏览器实测**：`setAttribute` BLOCKED，
  `cssText`/`setProperty`/属性赋值均生效。
- **验收**：真实 Chromium 同源对照 B10 参考页，逐视图 class 集合 gap
  `dashboard/brand-systems/preflight/settings = 0/0/0/0`，union gap 33 → 5。
  剩余 5 项为有据豁免：`editProject`（B10 无此 CSS 规则）、collaboration 槽（本项目 `VIEW_NOT_OPEN`，照搬即伪造）。

### 4.2 PR #174 — 真值对齐

- `reports/current/**` 投影漂移：观察 SHA `6ba2578` ≠ main，且写的任务包不是 current integrated 包 → 重生成
- R5 账本 112 轴仅 3 轴有证据 → 回填至 **10 轴**（本轮终态），**全部保持 `PARTIAL`**
  （契约 `r5_contract.py:100-101` 禁止在 `reassessment != REVIEWED` 时置 `PASS`）
- `AUTHORITY.md` §13 建立时快照被当现状读 → §13 原文保留 + 新增 **§13.1** live 读回；
  §15 三处现在时陈述修正；按 §17 **同步再钉** verifier byte-pin

### 4.3 PR #175 — 证据根授权修复

- `reporting.py` 的 `allowed` 集合缺 `apps`（§3 声明的前端）→ **任何 receipt 都无法引用前端**
- 审计发现 `research`/`vendor` 同类缺失 → 一次补齐到与 **§7 声明的 13 根完全对齐**
- **密钥防护未放宽**：`denied` 对每个路径分量生效，实测 `.env`/`apps/workbench/.env`/`apps/auth.json` 仍全部 DENY
- 解锁 2 条此前被迫跳过的 receipt（DL-R5-028 / DL-R5-010）

---

## 5. Permanent anti-drift gates（M 段，17 条，ACTIVE）

1. audit 必须 live remote AUTHORITY first　2. exact SHA 必须写　3. handoff 永不成为顶层 Authority
4. history 只能经 index/crosswalk　5. old TaskPack 不经 mapping 不复活　6. 不跨 ledger 假算总完成度
7. E1 不冒充 E3　8. VLM 不冒充 Human E4　9. old/candidate PASS 不冒充 current main PASS
10. commit/branch 数不等于 capability　11. 不建第二 runtime/backend/ledger
12. 没用户可见设计进展不得无限扩治理　13. 禁旧架构回流
14. merge/delete/release/force-push 保持 owner control　15. REUSE-FIRST = 真吸收，不是 Registry 堆积
16. 动态 branch/PR/CI 数永远 live-read　17. 已关闭问题无 regression evidence 不重开

---

## 6. Evidence 等级现状（诚实评估）

| 级 | 状态 | 依据 |
|---|---|---|
| **E0 DECLARED** | ✅ | 项目身份、许可候选、owner、Adapter 声明 |
| **E1 STRUCTURAL** | ✅ 大量 | 契约/schema/manifest、17 个 verifier、9 项 required checks、task-ledger 契约测试 |
| **E2 CONTROLLED_RUNTIME** | ✅ 部分 | `workbench-browser-e2e`（真实 Chromium + 固定 SHA artifact）、B10 1:1 实拍、Comfy HTTP model-free live（历史 receipt） |
| **E3 REAL_WORKFLOW** | ❌ **未达成** | 真实 Adobe Host 全链路（`DesignIR → PS/Illustrator → 可编辑产物 → 重开读回`）**未接通**；PNG-only 明文不算完成 |
| **E4 INDEPENDENT_ACCEPTANCE** | ❌ **未达成** | AUTHORITY §15 自陈残留：「**无人工视觉验收记录，属 E4**」 |
| **E5 RELEASED/REPEATABLE** | ❌ **未达成** | `PROJECT_STATUS` = `NOT_RELEASED` |

---

## 7. 未完成 / 未验证 / blocker（审计方应重点核查）

| # | 项 | 性质 | 说明 |
|---|---|---|---|
| B-1 | **E3 真实 Host 链路** | 产品 blocker | F 段 OPEN；无真实 Photoshop/Illustrator 可编辑产物重开读回 |
| B-2 | **E4 人工验收** | 流程 blocker | 无人工视觉/质量验收记录 |
| B-3 | **R5 账本无「已完成」语义** | 治理 | 28 任务全 `PLANNED_DELTA`；四轴全 `PARTIAL`；`reassessment` 全 `PENDING_EVIDENCE_REVIEW`；**需 owner 主导的正式 evidence reassessment** |
| B-4 | **`services/` 未在 AUTHORITY §7 声明** | 治理 | 存在但 **0 文件**；本轮**未**加入证据根（它不是 §7 的根）。要么声明，要么删 |
| B-5 | **`LICENSES/` 未在 §7 声明** | 治理 | 同上 |
| B-6 | **Ruff 是否 enforce 未决策** | 决策 | AUTHORITY §8 记 `CONFIGURED_NOT_ENFORCED` |
| B-7 | **K 段 Golden Workflows 未执行** | 未开始 | `GOLDEN-001/002` 无运行记录 |
| B-8 | **`ci-artifact-proof` 门禁 flaky** | 基础设施 | 见 §2.1；**advisory**，不在 required 内 |
| B-9 | **本机 `pnpm` 自身安装损坏** | 环境（非产品） | `DSH/pnpm-store/v11/links/@/pnpm/11.22.0/...` 缺失。本地门禁改用同一底层工具直调；CI 用可用 pnpm 跑权威命令 |
| B-10 | **HERMES `state.db` 4.51 GB** | 环境 | HERMES 全局范围，本轮零改动 |
| B-11 | **HERMES 侧无任何本项目作业** | 观察 | cron 作业 0、kanban 0、`project-local-runs` 无 DESIGN-LAB、`verification_events` 中 DESIGN-LAB 命中 **0 行** |

---

## 8. 审计方核查清单（建议 GPT 逐项 live-read）

1. `git rev-parse origin/main` 是否等于本报告 §0 的 `d116b14995fc…`
2. `.github/workflows/canonical-verify.yml` 的 10 个 job 是否与 §0 的 9 项 required 吻合（第 10 项 `ci-artifact-proof` 为 advisory）
3. `gh api .../branches/main/protection` 的 `required_status_checks.contexts` 是否为 9 项、`enforce_admins`/`strict` 是否为 true
4. main 最新 run 的 artifacts 是否存在且**名称内嵌 subject SHA**
5. `AUTHORITY.md` 是否含 §13.1；`scripts/verify_top_level_authority.py` 的 `R2_RELEASE_HASHES["AUTHORITY.md"]` 是否与文件实际 sha256 **一致**（再钉是否自洽）
6. `design-lab/config/task-ledger-r3.json` 是否 28 任务、`definition` 是否与 `docs/history/taskpacks/r5-20260908/tasks.json` 冻结源一致、轴状态是否**全部 `PARTIAL`**（有无越权宣称）
7. `src/design_lab/governance/reporting.py` 的 `allowed` 是否 = §7 声明的根；`denied` 是否**未被放宽**
8. `reports/current/**` 的 `--check` 状态（应可容忍 `STALE`；`FAIL`/`DRIFT` 才是问题）
9. E3/E4/E5 是否确有真实证据（**不应**有任何 E1→E3 或 VLM→E4 的冒充）

## 9. 不得采信项（声明）

- 本报告与任何 handoff / memory / 聊天摘要**都不是**顶层 Authority，不得用于覆盖 `/AUTHORITY.md`
- `reports/current/**` 是 **PROJECTION**，须经 fresh 校验才可用
- `docs/history/**`、`docs/handoffs/**` 是 **HISTORICAL**，只能经 authority-index/crosswalk 解释血统
- 任何「本地测试通过」**不等于** CI / merge / installed

---

**END — 2026-09-27 时点报告，exact SHA `d116b14995fcdbba1b165ec5bc3124f5daed3d15`。**
**审计必须自行 live-read 复核。**
