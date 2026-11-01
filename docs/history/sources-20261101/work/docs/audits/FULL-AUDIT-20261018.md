# 全量审计 · 2026-10-18（定位漂移 / 前端 / 后端 / 门禁）

> **审计对象**：`main` = `76350ee4`（本轮审计起点；审计期间新增 W06 探针改动在分支上，尚未合并）。
> **权威依据**：`WORK-LAB-AUTHORITY.md`（TOP/NORMATIVE，20261009 UI 优先）→
> `.project/governance/project-authority-index.json` → `AGENTS.md` →
> `taskpacks/current/WORK-LAB-UI-PRIORITY-TASKPACK-20261009.md` →
> `taskpacks/current/OPEN-TASK-REGISTER.md` → 作用域机器合同。
> **本文不是权威**：它只记录"声明与现场差在哪、证据是什么"。冲突以机器为准。
> **审计方式**：只读。每一条都写了证据位置；**凡是我没有亲自复核、只由子审计报告的，标 `◐`**；
> 亲自读过/跑过的标 `✅`。这不影响结论强度，但影响你该不该直接据此改代码。

---

## 0. 一句话结论

**定位没有漂，承诺漂了。** 产品身份（软件中立、本地优先、外部软件执行业务、本仓只观察与治理）在
CURRENT 任务包与 authority 里是清楚的，前端也确实没有一条写路径。漂的是**实现对自己承诺的兑现**：
"严格只读""单写者""LIVE 只来自 live gate""无假绿"这四条，代码里各有一处反例，
而**最有价值的三道门恰好没进 CI**（见 §4）。

---

## 1. 定位漂移评估（声明 vs 现场）

| 声明（来源） | 现场 | 判定 |
|---|---|---|
| 用户在外部 AI 软件执行项目，本仓不执行业务（AUTHORITY §2） | 前端零写动词（实测 `method:POST/PUT/PATCH/DELETE` 命中 0）；唯一的副作用是本地草稿 `localStorage` 与窗口控制 | **一致** ✅ |
| Observer 与 sidecar 严格只读，不执行/apply/rollback/批准/重试（AUTHORITY §3） | HTTP 层 4 个写动词 405；但 sidecar 构造即 `register_project()` 写库，`start-observer.cmd` 默认起 worker（写） | **漂移** ✅ |
| 一个 write set 一个 writer（AUTHORITY §5） | 三处裸 `sqlite3` 写 canonical 库、`control` 不取锁（§3 B-02/B-03） | **漂移** ✅ |
| 不采集私人提示词/回复（AUTHORITY §4） | `services/session-federation/` 三个 provider 默认读 `~/.codex`、`~/.dsh`、`~/.hermes`，并把 prompt/response 正文复制进 `messages[].text`（无产品调用方，但代码在交付树里） | **漂移** ✅ |
| LIVE 只来自 live gate，不造 partial（`live_gate.py`） | 采集器"跑了但没交付"仍记成功 → coverage 恒 N/N → 可判 LIVE（§3 B-01） | **漂移** ✅ |
| 模块根恰好两个；观察器只以 `observed-by` 观察（`module-ownership.json`、`module-dependencies.json` `runtimeEdges: []`） | `apps/observer/src/observer_store.py` 运行时 `from composition_root import ...`（跨模块运行边）；声明为空但代码有一条 | **漂移** ✅ |
| 支撑面是支撑，不是第二运行时（AUTHORITY §5） | `services/` 15 个子域、23,186 行；其中 `session-federation` 3,909 行、`execution-federation` 1,572、`radar` 1,266 都不在 WUI 范围里 | **需 owner 判断** ✅ |
| 手机端不做、不设延后任务（AUTHORITY §3） | 未见移动端代码或任务卡 | **一致** ✅ |
| 无第二 UI / 第二 TaskLedger / 第二 Usage 真源 | 存在两套 SSE hub、两套 telemetry 存储、三处独立 usage 写路径（§3 B-06） | **漂移** ✅ |

**最实质的一条**：声明是"UI 优先、旧任务不独立派工"，但代码体量的重心仍然在 `services/` 的
非 UI 支撑面上（23k 行 vs 前端 81 个生产文件）。这不必然是错——支撑面被观察链路需要——但它意味着
"UI 优先"目前是**任务卡优先**，不是**工程量优先**。这一条只能由 owner 定，不由审计定。

---

## 2. 前端审计（`apps/observer/frontend`）

规模：81 个生产 `.ts/.tsx`、64 个测试文件、644 个 `it/test`；`any` 共 26 处（生产 16 处）。

| # | 级别 | 位置 | 问题 | 证据 |
|---|---|---|---|---|
| F-01 | **BLOCKER** | `src/lib/evidenceRange.ts:309-322` | **证据摘要是自己跟自己比**：`recorded` 与 `expected` 都取 `result.identity?.wholeDigest`，于是只要后端返回 OK，页面必然显示绿色"一致/AGREE"；调用方的 `expectedDigest` 从未参与。函数注释写的是"caller-supplied"，实现不是 | 两行同一表达式；`EvidenceView.test.tsx:75` 把两者设成同一个常量，所以测试永远抓不到 ✅ |
| F-02 | HIGH | `src/views/OverviewView.tsx:241` | 只要"无告警"就写"传输在线"，而告警只对 `transportState === 'OFFLINE'` 生成 → `CONNECTING/DELAYED/UNKNOWN` 全被说成在线 | 告警条件在同文件 `:60` ◐ |
| F-03 | HIGH | `src/views/Views.tsx:112,455` | 无快照时渲染"0 个项目 · 真实 registry"、"0 条证据引用"，把 unknown 变成 0 还加"真实"背书 | `snap?.projects || []`；`api.ts:271` 注释明令 unknown 不能变 0 ✅ |
| F-04 | HIGH | `src/laneTruth.sweep.test.tsx:52-55` | 防假绿的"零值探测器"只扫 `.kpi strong/.metric-box strong` 且要求整格 `"0"`，所以 F-03 那种"0 个项目…"在 `<span>` 里的写法**结构上不会被抓到** | 选择器与自检控件都只造两种形状 ◐ |
| F-05 | MEDIUM | `src/lib/api.ts:532` | 轮询周期 5000 是唯一没有名字的魔数（`SNAPSHOT_TIMEOUT_MS`、`MAX_STALENESS_MS` 都有名字）；与 45s 的 9 倍关系只写在注释里 | 对比 `:150`、`:158` ✅ |
| F-06 | MEDIUM | `src/lib/api.ts:571-580` | 签名用裸 `\|` 拼接不转义（`coverage.scope` 是自由字符串，可制造碰撞），且签名不含 projects/executions 内容 | 同 revision 内容变化会被静默丢弃 ◐ |
| F-07 | MEDIUM | `src/lib/api.ts:615` | 读失败也刷新 `lastReadAt` → 失败一次后健康流场景最长 45s 不再重试，恢复被拖慢 | `lastReadAt = Date.now()` 在判 null 之前 ◐ |
| F-08 | MEDIUM | `src/views/{ApprovalsView,AuditTrailView,IntegrationsView,RulesPolicyView,SoftwareView,TaskPacksView}.tsx` + `lib/viewRegistry.ts:63` | 6 条泳道整份快照 `snap: any` + registry `ComponentType<any>`，`SnapshotV3` 契约在这些页完全失效 | 类型检查形同虚设 ◐ |
| F-09 | MEDIUM | `src/views/Views.tsx`（500 行/11 个导出）、`lib/api.ts`（678 行/传输+格式化+投影+hook 混在一起） | 单文件多职责；`STATE_TEXT` 复制 3 份、`toneVariant` 复制 2 份、`fmtTokensSafe` 重实现 `fmtTokens` | 违反"组件/页面/hooks 分离"的常规分层 ◐ |
| F-10 | MEDIUM | `src/components/dashboard/{ProjectPanel,ExecutionTable,TokenPanel}.tsx` | 三个"生产组件"的唯一引用者是测试：**测试断言的对象不是用户看到的那条渲染路径** | `grep` 仅命中 `truth.test.tsx` / `renderTruthContract.test.tsx` ◐ |
| F-11 | LOW | `frontend/dist/`（工作区，未提交） | 陈旧构建：生成于 10-17 03:35，`api.ts` 已于 10-18 改过 W06；用 `--frontend-root` 起服务会拿到缺 W06 的 UI | `find src -newer dist/index.html` ◐ |
| F-12 | INFO | 全局 | **前端无任何写路径**（零 POST/PUT/PATCH/DELETE、零表单提交、零 `invoke()` 业务命令）；`writeUrlParams` 是死代码 | 见 §1 第一行 ✅ |

**前端判读**：真正的风险不是"能写"，而是**"读出来的结论会骗自己"**——F-01 是其中最坏的一种
（自证摘要），F-03/F-04 说明防假绿的测试在结构上有盲区。F-10 说明"测试绿"与"用户看到的那条路径"之间
还隔着一层。

---

## 3. 后端审计（`services/` + `packages/client-neutral-core`）

| # | 级别 | 位置 | 问题 | 证据 |
|---|---|---|---|---|
| B-01 | **BLOCKER** | `packages/client-neutral-core/scripts/collectors.py:110` + `services/orchestration/durable_worker.py:144` + `sidecar.py:261-295` | **"跑了"被记成"交付了"**：采集器读不到源时返回 `ok=True, records=[]`；worker 的判据 `ok = outcome.ok and not (stored == 0 and bool(outcome.records))` 在空 records 时仍为 True → 健康表写 `last_success_at=now` → `_collector_coverage` 判 fresh → coverage N/N → live gate 可判 **LIVE**。一个零真实遥测的实例能合法自称实时 | 三处均已读；`live_gate.py:47-72` 只要求 `numerator >= denominator` ✅ |
| B-02 | **BLOCKER** | `services/receipts/usage_estimator.py:13,81`、`execution_recorder.py:11,53` | **绕过单写者**：裸 `sqlite3.connect()` 直写 canonical 库，硬编码 `D:\All projects\WORK-LAB\.hermes\task-runtime\canonical.sqlite`；无 `validate_record`（无密钥扫描）、无锁、无 `__main__` 保护（`import` 即写库） | grep 与读文件确认；两者都无 main guard ✅ |
| B-03 | HIGH | `services/control/control_service.py:1201` | Control 以读写模式打开同一 canonical 库，不取 `sidecar.lock`/`worker.lock`，可与 sidecar 同时成为 writer | 全文无 `SingleInstanceLock` ◐ |
| B-04 | HIGH | `services/orchestration/sidecar.py:488-494` | `close()` 遇到 `worker_shutdown_timeout` 抛错，但 `finally` 无条件 `release()` 锁 → 旧 worker 仍可能在写，新实例已能启动。代码注释自己说了"必须保留锁" | 注释与实现矛盾 ◐ |
| B-05 | HIGH | `services/session-federation/{dsh,hermes,codex}_provider.py`（`:115/:54/:89`） | 默认构造读 `~/.dsh`、`~/.hermes`、`~/.codex` 并把 prompt/response 正文复制进会话模型，直接违反 AUTHORITY §4 | `Path.home()` 三处 + `dsh_provider.py:178-180` ✅ |
| B-06 | HIGH | `sse_hub.py:50` vs `sse_revision.py:34`；`services/receipts/telemetry_ledger.py:57` vs `canonical_store.py:586` | **概念重复**：两套 SSE hub（双写）、两套 telemetry 存储（JSONL + SQLite）、三处 usage 写路径 → "无第二真源"不成立 | 均已读 ✅ |
| B-07 | MEDIUM | `services/orchestration/sidecar.py:725-739` | 只覆写 POST/PUT/PATCH/DELETE；HEAD/OPTIONS/TRACE/CONNECT 落到 `http.server` 默认 **501**，与"每个非 GET 都是 405"的契约不符；`verify_observer_readonly_boundary.py:96` 的正则也只匹配 4 个动词 | ✅ |
| B-08 | MEDIUM | `sidecar.py:528-529,746`；`_is_loopback_host` `:408-411` | `--host localhost` 通过校验并按名字绑定；`*.localhost` 子域也被当作可信 Origin；无 `Host` 头校验（对照 `control_service.py:1123` 会在 bind 后复核地址） | ✅ |
| B-09 | MEDIUM | `apps/observer/src/observer_store.py:14-21` vs `apps/observer/start-observer.cmd:19` | Observer 门面硬要求 `.hermes/task-runtime/workflow/canonical.sqlite`，文档化启动器写的是 `.project-local/runs/workflow/canonical.sqlite` → 两者永不相等，用启动器的库调门面必抛 `ValueError` | ✅ |
| B-10 | MEDIUM | `packages/client-neutral-core/scripts/canonical_store.py:838-917` | 租约与 `claim_expired_tasks` 是"先 SELECT 再 UPDATE"，无 `BEGIN IMMEDIATE`/条件写 → 跨进程可双拿租约、fencing token 可重复 | ◐ |
| B-11 | MEDIUM | `services/orchestration/composition_root.py:66-67,536-537` | 注册表读取失败 `return []`（读不到 → "没有软件"）；无任务时注入占位 id `"UNRESOLVED"` 参与 read model | ◐ |
| B-12 | MEDIUM | `services/receipts/metrics_exporter.py:44,70-81` | 硬编码 9100 端口；`COALESCE(SUM(...),0)` + `or 0` 把"无样本"变成 0 成本，同时该指标又用 `truth="UNKNOWN"` 标注 | ◐ |
| B-13 | LOW | `packages/client-neutral-core/scripts/artifact_flow_policy.py:53-58` | 密钥"值"扫描只匹配整串形状（`^Bearer…$`、`sk-`、`AKIA…`、≥64 base64），嵌在句子里的密钥、JWT、40 位 secret 会漏过 | ◐ |
| B-14 | INFO | 全仓 | 未发现硬编码 40 位 SHA、裸 `except:`；`_git_match_state` 的 MATCH 需 local/remote/ci 三者相等，缺一即 `NO_LOCAL_CLAIM`（不是伪造） | ✅ |

**后端判读**：HTTP 动词层的只读是真的；**进程层的只读不是**。最危险的不是"有人能写"，而是
**"没人写也能宣布 LIVE"**（B-01）：采集器空转 → 健康表新鲜 → coverage 满分 → live gate 放行。
这条链一旦被真实环境触发，UI 会把"什么都没采到"显示成"实时、健康、覆盖完整"。

---

## 4. 门禁审计：承诺与强制之间的差

| 承诺 | 有没有机器门 | 结论 |
|---|---|---|
| 13 skills | 有（`test_current_state.py`、`generate_skills_inventory.py`） | **强制** ✅ |
| 6 bin launchers | 只查单个文件存在（`test_authority_index_paths_resolve.py:33` 只查 `bin/codex`） | **仅散文** ◐ |
| single writer | 门 `canonical-single-writer` 存在，但**两个 workflow 里出现 0 次**；且它只跑迁移/备份测试 | **未在 CI 执行** ✅ |
| read-only projection | CI 里真正跑的是 `verify_observer_readonly.py`：只断言源码出现 `"raise"` 与 `"Observer is read-only"` 字样 | **形同虚设**（把 `append()` 改成 `return 0` 也照样 PASS）✅ |
| no fake LIVE | 单测在 CI（`test_snapshot_sse_live.py` 的 `LiveGateTests`），但驱动真 sidecar 的 `test_sidecar_v3_snapshot.py` 不被任何门引用 | **半覆盖** ◐ |
| loopback-only | `test_sidecar.py:77-78` 覆盖"拒绝 `0.0.0.0`" | **部分**（不覆盖绑定后地址复核与 Host 头）✅ |

**7 道核心门从未在 CI 执行**（对两个 workflow 逐个 grep，命中数全为 0）：
`canonical-single-writer`、`observer-no-business-write`、`field-quality-no-fabrication`、
`sse-browser-reconnect`、`snapshot-schema-v3`、`observer-readonly-boundary`、`privacy-redaction`。
它们都在 `run_quality_gate.py` 的 `VERIFY_ORDER` 里——**只有人手动跑 `verify` 才会全跑**。

这与本仓反复付学费的那一类失败同形：**门存在、名字漂亮、CI 不跑**。

---

## 5. 优先级建议（按"被假绿咬到的概率"排序）

**P0（能产生错误结论，且有真实路径）**
1. F-01 摘要自证：改成用调用方传入的 `expectedDigest` 与实测 `wholeDigest` 比较；补一例 `expectedDigest ≠ wholeDigest` 的测试（现有测试把它写死了）。
2. B-01 采集器"跑了≠交付了"：空 `records` 必须记未成功；健康判据改成"交付数 > 0 或显式声明空源"。
3. B-02/B-03 单写者旁路：三个裸 `sqlite3` 写者删掉或改走 `CanonicalStore`；Control 取同一把锁。
4. `start-observer.cmd` 三重矛盾（`--port 0` 却探测 61867、打开不存在的 `apps/observer/web`、`file://` 的 `Origin:null` 被拒）→ 一键入口目前**不可能连通**。（另：文档化 `sidecar.py` 直接启动的 `ModuleNotFoundError` 已于本轮修复，见 §6。）

**P1（会让下次审计再次误判）**
5. 把 7 道门接进 CI（至少 `observer-readonly-boundary`、`canonical-single-writer`、`snapshot-schema-v3`）。
6. `verify_observer_readonly.py` 升级为行为检查（AST/导入面/写语句），而不是字符串存在性。
7. F-03/F-04 把 unknown 保持 unknown，并让零值探测器覆盖 `<span>` 型文本。
8. B-05 三个 provider 改为显式传参、默认不读 home；或在 authority 里明确它们仍属"计划内"。
9. B-09 统一 canonical 库路径（Observer 门面 vs 启动器二选一）。

**P2（结构性债务，不阻塞）**
10. B-06 去重（SSE hub、telemetry 存储）；F-09/F-10 拆分 `Views.tsx`/`api.ts`、处理"只被测试引用"的组件；
11. F-05/F-06 命名常量、签名改结构化比较；B-13 加强值层密钥识别。

**需要 owner 决定（审计无权定）**
- `services/session-federation`、`execution-federation`、`radar` 是否仍在范围内（合计 ~6.7k 行，不在 WUI 包里）。
- "UI 优先"是否也包括工程量分配，还是仅任务卡优先。

---

## 6. 本轮审计中已修掉的（不是建议，是已改）

- 文档化启动方式 `python services/orchestration/sidecar.py …` 在干净 shell 里
  `ModuleNotFoundError: canonical_store`：根因是 `tests/conftest.py` 替测试注入模块根，
  发布出去的启动器从未被覆盖。已在 `sidecar.py` 顶部按自身位置推导模块根并写明理由，
  新增 `tests/ci/test_sidecar_documented_launch.py`（清空 `PYTHONPATH` 跑文档命令 + 要求
  `/api/v1/snapshot` 真的应答）。

## 7. 局限

- 未做**运行时**端到端：本报告的后端结论来自读码与既有测试，不是把 UI 跑起来观察。
  唯一的例外是 W06 的流成本探针（另文 `STREAM-COST-BASELINE-20261018.md`）。
- `◐` 标记的条目来自并行子审计、我未逐行复核；据此改代码前请先复读那几行。
- 未审计 `apps/token-monitor`、`integrations/` 全部适配器、`services/policy` 规则内容。
- 前端视觉/可访问性未审计（不在本次四技能范围内）。
