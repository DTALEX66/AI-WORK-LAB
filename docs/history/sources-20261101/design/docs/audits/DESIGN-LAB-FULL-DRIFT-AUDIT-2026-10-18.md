# DESIGN-LAB 全量漂移审计（前端 + 后端 + 治理层）

**审计基线**（全部为本机实测，非摘抄文档数字）

| 项 | 实测值 |
|:---|:---|
| 审计 SHA | `0d9041a3b8be6c0ad725dde27145c90eb61a8908` |
| 工作树 | `git status --porcelain` 为空（干净） |
| 该 SHA 的 CI | run `39128580612`，`conclusion=success`，12 作业全 success |
| Python 文件 | 已提交 666 个：运行时 `src/design_lab` 102 · 治理脚本 `design-lab/scripts` 116 · 测试 `design-lab/tests` 258 · `scripts` 68 |
| 前端 TS | `apps/workbench`（`shell.ts` 7531 行，D07 第一批拆分后） |
| 校验脚本 | `verify_*.py` 共 103 个 |

---

## 0. 总判定

> **未发生架构漂移。** 项目定位（本地优先、单进程 loopback 元数据服务、SQLite 状态机、提交式单文件前端产物）在代码里仍然成立，且被 103 个校验脚本 + 多道双向闸机械看守。
>
> 但存在 **1 个 P1 结构性债务**（后端路由无集中注册表，导致前后端路由无法机械双向核对）与 **12+1 条 P2**。无 P0。

判定依据不是"看起来还行"，而是下面每一项都给出了可复算的命令与证据行。

---

## 1. 后端审计（八项检查）

### 检查 1 — 第二 runtime / 平行实现 → **无漂移**

`design-lab/` 的 382 个 `.py` 拆解后为：scripts 116 + tests 258 + core 7 + production 1。
**运行时只有 `src/design_lab` 一份（102 文件）。** `service.py`（107 行）暴露 `list_projects/create_project/get_project` 等服务层方法，`http_service.py` 是唯一 HTTP 适配器，不存在第二套路由。

关于 `design-lab/core/`（353 行，无人 import）：`docs/architecture/DIRECTORY-AUTHORITY.md:65` 明文规定
**「stays a reference/contract artefact. It must not gain new consumers.」** —— 这是**有意冻结的契约参考件，
不是待清理的死代码**，10-18 早些时候的清理工作已据此判定保留。本次审计的独立取证方向（"是否被 import"）
会把它误判为死代码，故在此更正：正确结论是"冻结且合规"，残留风险只剩**命名误导**（见 P2 表）。

### 检查 2 — fail-closed 真实性 → **健康，且有意为之**

`except` 行 565 处，但吞错（`except Exception` 后紧跟 `pass`）**仅 1 处**。关键位置的容错都带显式理由，例如：

- `domain_packs.py:115` — `# noqa: BLE001 - a broken checker must not fail the route`
- `domain_packs.py:186` — `# a checker crash is a finding, not a verdict`
- `production_preflight.py:226` — the container is simply not readable here
- `native_tasks.py:330/520/549` — 转 `NativeTaskError(...)` 抛出（fail-closed，非吞错）

### 检查 3 — 合同真值 → **P2：同一词汇表 5 处各写一份，无交叉闸**

| 定义位置 | 形态 | 值 |
|:---|:---|:---|
| `src/design_lab/assurance/qa_plane.py:126` | tuple | E0–E5 |
| `src/design_lab/creative/media/__init__.py:53` | tuple | E0–E5 |
| `design-lab/scripts/verify_product_manifest_v3.py:26` | list | E0–E5 |
| `design-lab/scripts/verify_runtime_contracts_v3.py:21` | set | E0–E5 |
| `scripts/verify_evidence_levels.py` | — | E0–E5 |

**当前 5 份值完全一致（未漂移），但没有任何一道闸断言它们互相相等。** `test_assurance_qa_plane.py` 只测 qa_plane，`test_media_*` 只测 creative.media，中间没有桥接测试。这是"还没漂移但没有看守"的典型形状。

### 检查 4 — 证据等级诚实性 → **通过**

`design-lab/tests/test_claim_honesty_gates.py` → **6 tests, OK（13.0s）**。其中含 `("scripts/verify_evidence_levels.py", "EVIDENCE_LEVELS=PASS")` 的回执断言。

### 检查 5 — 权限与安全 → **健康**

| 面 | 实测 |
|:---|:---|
| 绑定 | `HTTPServer(('127.0.0.1', port), Handler)` — 仅 loopback |
| 鉴权 | `hmac.compare_digest`（`http_service.py:139`）+ Bearer，token 强制 `re.fullmatch(r'[0-9a-f]{64}')`（:73） |
| 危险调用 | `shell=True` / `os.system` / `eval(` / `exec(` 在生产代码 **0 处**（仅测试里 `ast.literal_eval`） |
| SQL | 318 处 `execute(` 全部参数化；`executescript()` 14 处均为读取内置 DDL 文件 |
| 产物泄漏 | `__pycache__`/`.pyc` 提交数 **0**；`.project-local/` 已被 `.gitignore:75` 忽略 |

唯一可疑项：`creative/store.py:194` 的 f-string SQL `f"SELECT 1 FROM {probe} LIMIT 1"`。追查后 `probe` 来自 `_migrate_once(...)` 的唯一调用点（:175）传入的内部 schema 常量表，**当前安全**，但该模式可被复制 → 记 P3 防御性提醒。
`version_guard.py:93` 的 `query + " ORDER BY ..."` 拼接经核查只拼接字面量，`asset_id` 仍走 `?` 占位符 → **无注入**。

### 检查 6 — 依赖与语言漂移 → **极干净**

`src/design_lab` 的全部 import：**仅标准库 + `jsonschema`(10) + `sqlite3`(27)**。无 HTTP 客户端、无 Web 框架、无 ORM。与技术约束"本地优先、零外部服务"一致。

### 检查 7 — 死路由双向清单 → **P1（结构性）**

后端 `http_service.py` 的 30+ 条 API 路由**没有任何集中注册表**，全部以 `if self.path == ...` 与 `re.fullmatch(...)` 的链条硬编码在 `make_server()` 内部的闭包 `dispatch` 方法中（**167 行起至文件末尾，单方法约 478 行**）。`workbench.ROUTES` 只含 3 条静态资源路由。

后果：前后端路由**无法机械双向核对**，只能靠人工 grep。本次人工核对结果：

- 前端引用的 `/api/button` 是误报（TS 中的 helper 名，非路由）。
- 前端主动标注缺失的 2 条：`shell.ts:383`「宿主探测路由（缺）」、`shell.ts:390`「`GET /api/mcp/…`（缺）」；`shell.ts:714` 注明 `/api/quality` 不存在。
- **结论：没有静默死路由。** 缺口是被诚实声明的，不是漂移。

但"只能人工核对"本身就是债务：下一次加路由，没人能自动发现对不上。

### 检查 8 — 闸的看守缺口 → **通过（含一次自我纠错）**

`design-lab/tests/test_gate_reachability.py` → **9 tests, OK（4.07s）**。
该测试强制"不可达 verifier 集合 **必须双向等于** 显式豁免清单 `MANUAL_GATES`"，每条豁免都带理由（如 `verify_fresh_clone.py` 因克隆 236 MiB 属本地净室检查）。新增孤岛会失败，豁免过期也会失败。

> **审计过程中的自我纠错**：我先用"workflow + 4 个聚合器"做文本包含扫描，得出 8 个"孤立闸"（`verify_evidence_levels` / `verify_supply_chain` / `verify_no_overclaim` 等）。跑完真正的闸后发现是**误报**——我的检索范围漏了 `verify_projection_freshness.py` 等中间聚合器。以闸的结论为准：**闸可达性当前成立**。此记录保留，以免后人重复踩同一个推断陷阱。

---

## 2. 前端审计（承接上一轮子代理报告）

- **P0：0 条**
- **P1：2 条**
  1. **UI 量化门禁"跑得到但不生效"**（机制经 2026-10-18 复核后修正，与"孤立闸"不是一回事）：
     `design-lab/tests/test_workbench_ui_audit_gate.py` **确实接线**——它 shell 出去跑
     `scripts/audit_workbench_ui.py`（后者 :28 再包 `design-lab/tests/e2e/audit_workbench_ui.mjs`），
     所以 `test_gate_reachability` 判它可达是**正确的**（经 `test_workbench_ui_audit_gate.py:34` 命名），
     它**不该**被登记为 `MANUAL_GATES` 豁免。真正的问题有两处：
     - 它依赖 node + `playwright` + Chromium，缺失即 `skipTest`；而 CI 的 Chromium **只在
       `workbench-browser-e2e` 作业安装**（`canonical-verify.yml` 260–287），跑全量 Python 套件的
       `python-gate` 没有 → 在那里它必然 skip。
     - 防跳过的 `design-lab/scripts/verify_browser_e2e_ran.py` 用**显式元组** `TEST_MODULES`（非 glob）
       只盯 5 个模块，**不含**这一个；该文件 docstring 自己写明
       「an unlisted browser suite would skip forever without a finding」。
     **净效果**：它 2026-10-07 报的 `violations=12`（同一元素 `button#navToggle` 62x23，手机端唯一
     离页控件）不会让任何提交变红。**修法**：把它加入 `TEST_MODULES`（推荐，浏览器作业已装 Chromium），
     或让它不依赖浏览器。
  2. skip-link `href="#content"` 在两种状态下都到不了可见内容。
- **P2：12 条**（摘要）：`as never` 四处 · 29 处内联 px · 26 色值中 3 处误判 · 19 个死选择器 · 5 处机器状态词未裹 `lang="en"` · dev 模式双实现 · design-layer 无分页 · 单文件 bundle 代价 · 两份下载 hash 校验 · `DESIGN.md` 三个数字与实测不符 · 对比度门禁漏两个详情路由 · `PreflightError` 原文上屏。
- 另有 **13 条"没有问题的项"** 与 **6 条"本机无法确认的项"**。

---

## 3. 四技能交叉判定

### vibe-coding-architect（架构）

| 6 问 | 代码中的实际答案 | 是否漂移 |
|:---|:---|:---|
| 产品形态 | 桌面/CLI + 本地 Workbench（loopback HTTP） | 否 |
| 运行环境 | 本地运行（127.0.0.1，SQLite） | 否 |
| 项目规模 | 完整产品（666 py + 103 闸） | 否 |
| 数据方案 | SQLite 本地文件 + 提交式 JSON | 否 |
| 前后端分工 | 前后端分离，单一 loopback API | 否 |
| 扩展预期 | 已扩展（integrations 9 hosts、capabilities 分包） | 否 |

反模式对照：**未命中**"技术栈来回变"（依赖面只有 stdlib+2）、**未命中**"不告诉 AI 约束"（103 闸即约束）、**命中一条**"跳过测试直接推进"的变体——`audit_workbench_ui.mjs` 写了却不接线。

### frontend-spec（企业级前端规范）

强项：CSP 无 `unsafe-inline`、`style` 走 `cssText`、`lang` 标注意识、bundle 字节级守卫。
弱项：`as never` 逃逸、内联 px/色值未收敛到 token、死选择器 19 个——规范有文档但缺机械执行（与 P1-1 同源：**规范写了，闸没接线**）。

### 114514（前端设计）

19 个死选择器 + 3 处色值误判说明视觉层存在"实现先于设计系统"的沉淀；skip-link 失效是真实的可用性缺陷（P1-2）。

### product-manager（成果导向）

**成果侧结论**：用户可见成果（Workbench 可读回、路由诚实标注「缺」、证据等级可验证）全部成立。
**权衡**：项目把大量产能投在治理闸（103 个）上，换来了"声明可被机械证伪"这一真实资产；代价是前端体验门禁长期欠账（P1-1/P1-2）。这是**自觉的取舍**，不是失控——但取舍的天平已经偏了一档，建议下一轮补回。

---

## 4. 优先级建议

| 优先级 | 项 | 理由 |
|:---|:---|:---|
| **P1-1** | 把 `test_workbench_ui_audit_gate` 加进 `verify_browser_e2e_ran.py` 的 `TEST_MODULES`（**不是**加进 `MANUAL_GATES`——它已经接线，登记豁免反而是错的） | 浏览器作业已装 Chromium，加入后它会真正执行；当前 skip 无人察觉，是已知 12 处违规的复发通道 |
| **P1-2** | 修 skip-link 落点 | 真实可用性缺陷，成本低 |
| **P1-3（新）** | 后端路由抽成集中注册表（从 478 行 `dispatch` 中提出 `ROUTES` 表），并加一道"前端调用 ↔ 后端注册"双向闸 | 让 P1 类问题从人工 grep 变成机械可证伪；同时卸掉单方法 478 行的维护债 |
| **P2** | EVIDENCE_LEVELS 收敛为单一真源 + 交叉一致性闸 | 当前一致但无看守 |
| **P2** | `design-lab/core/` **保持冻结不动**（架构明文规定），只做消歧：其 `STAGES`/`VALID_MODES` 与运行时同名常量（`model_manifest.py:19` 的 `STAGES`）语义不同却同名，且它内部 `VALID_MODES` 自写两份（`project_state.py:37` 与 `user_modes.py:18`）。建议加一行"此为契约参考件，勿引用"的头注 | 冻结是正确的架构决定，问题不是"该不该存在"，而是"读者会不会误当成活实现" |
| **P3** | `creative/store.py:194` 的 f-string SQL 改为白名单校验 | 防御性，当前实参为内部常量 |

---

## 5. 收尾

**已做决策**
- 判定为"未漂移"，依据是可复算命令而非文档表述。
- P1 三条中，P1-3（路由注册表）是本次新发现，且是 P1-1/P1-2 类问题的**根因共因**：前端门禁接不上、路由核对靠人工，本质都是"没有可枚举的清单"。

**需验证的假设**
- 前端 P2 中的 6 条"本机无法确认项"需在有浏览器环境的机器上复核。
- `design-lab/core/` 冻结条款是否仍适用于当前阶段（`DIRECTORY-AUTHORITY.md:65` 未标注失效条件；若未来解冻，需先解决其与运行时的同名常量冲突）。

**下一步（建议顺序）**
1. P1-3 路由注册表 + 双向闸（解锁其余 P1 的可机械性）
2. P1-1 接线或登记豁免（二选一，不可留空）
3. P1-2 skip-link
4. P2 收敛 EVIDENCE_LEVELS / 清理 `design-lab/core`

---

## 6. 审计诚实性声明

本次审计中我产生过 **3 次误判**，均原样保留以示警戒：

1. **8 个"孤立闸"** —— 用"workflow + 4 个聚合器"做文本包含扫描得出，被 `test_gate_reachability` 9/9 通过**证伪**
   （检索范围漏了 `verify_projection_freshness.py` 等中间聚合器）。记录在检查 8。
2. **`design-lab/core/` 判为死代码** —— 纯按 import 关系推断，被 `DIRECTORY-AUTHORITY.md:65` 的
   **明示冻结条款**证伪（它是契约参考件，本就不该有消费者）。记录在检查 1。

3. **P1-1 的"从不执行"说错了机制**（复核后修正）：我据"workflow 里匹配数 0 + 不在 `MANUAL_GATES`"
   推出它是孤立闸。实际它经 `test_workbench_ui_audit_gate.py:34` 被命名而可达，登记豁免反而是错的；
   真问题是"能跑但缺浏览器就 skip，且不在防跳过元组里"。**净效果相同，但修法完全不同**——
   按我原来的写法去"接线或登记豁免"，会错误地把一个已接线的闸登记成手动闸。

前两条同源：**用"有没有人引用/有没有出现在文本里"代替"权威文档怎么规定"**。这与项目 Authority 优先链
（`/AUTHORITY.md` > authority-index > AGENTS.md > TaskPack > currentExecution）相悖，下轮应先读权威口径再取证。

凡本节标注"实测"的数字均可由对应命令复算；凡标注"摘要"的部分来自上一轮前端子代理报告，未在本次重新逐条复核。
