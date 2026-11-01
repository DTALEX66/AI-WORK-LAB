# T1 账本逐任务复核 · 第四项：DL-R5-004

- 观测 SHA：`ee2cf1fafb487588b09dfdee993f9b1d28f668e6`（本次读回的 `refs/remotes/origin/main`）
- 复核日期：2026-10-07
- 账本：`design-lab/config/task-ledger-r3.json`（唯一状态编辑源，本次**只读**）
- 范围：只复核 DL-R5-004 一个任务，不批量翻转 `reassessment`
- 顶层权威：`/AUTHORITY.md`（DL-AUTHORITY-2026-09-18-R2）→ `.project/governance/authority-index.json` → `AGENTS.md` → 本账本

## 一、任务实况（从账本直接读回，不是摘要）

| 字段 | 值 |
|---|---|
| title | 运行状态与宿主异常恢复 |
| priority | P0 |
| depends_on | `DL-R5-001`（已在 main 上复核，见 001 记录） |
| predecessor_task_ids | `R3-05` |
| reassessment | `PENDING_EVIDENCE_REVIEW` |
| required_axes | implementation / unit / **host_live** |
| implementation | `PARTIAL`，证据 `r5-004-static-unit-20260928` |
| unit | `PARTIAL`，同上 |
| host_live | `PARTIAL`，证据数组**为空** |
| delivery | `PARTIAL`，证据数组为空 |

acceptance 三条：A1「在 dispatch 后、receipt 后、publish 后注入中断」；A2「重启可对账且不重复建对象」；
A3「未证明停止不解锁」。

`evidence_required` 六项：`source_sha` / `environment_versions` / `commands_and_exit_codes` /
`artifact_hashes` / `limitations` / `rollback_record`。

**先说结论：三条 acceptance 里 A3 成立、A1 部分成立、A2 不成立。**
所以本项**不抬升任何轴**，并且和 002/003 一样，记录本身发现了一条会被误当成证据的**空转闸门**（§四）。

## 二、逐条核验

### A1「三个相位边界注入中断」— 部分成立（publish 有真崩溃证据，dispatch→receipt 没有）

相位边界的真实位置（`src/design_lab/native_tasks.py`，382 行的文件）：

- **dispatch**：`_claim`（`:109`）在一个 `BEGIN IMMEDIATE` 事务里**先**写入 host guard INSERT +
  attempt `RUNNING` + operation `DISPATCHING`，**然后**才 `_dispatch`（`:24`）调用 COM 适配器。
  顺序是对的：外部副作用之前，可追查的状态已经落盘。
- **receipt**：`_verify_receipt`（`:137`）之后才 `UPDATE native_execution_v1 SET receipt_json`
  （`:375-376`）。校验失败会留下 `receipt_json` 为 NULL。
- **publish**：`_publish`（`:149`）→ `assets.acquire_writer`/`writer_token` → `publish_version`
  （`runtime/asset_store.py:306`，两个中间缝 `_after_stage` / `_after_rename`）→ `_finish`（`:174`）
  在一个事务里写 `result_json`、置 `RECEIPTED`、删 guard。

真崩溃证据（不是 mock、不是"断言方法存在"）：

| 注入点 | 位置 | 断言 |
|---|---|---|
| publish 之后子进程真死 | `tests/test_native_tasks.py:367-391` | 子进程 `os._exit(43)`，父进程用**同一个** `version_id` 接续，guard 仍为 1 |
| 暂存阶段中断 | `:393-419` | `_after_stage` / `_after_rename` 崩溃 → `COMMITTED` + `QUARANTINED` |
| 落盘后真死 | `tests/test_runtime_attempt_safety.py:196-224` | 先 fsync 真实副作用再 `os._exit(23)` |
| OS 锁被活进程持有 | `tests/test_native_recovery_lock.py:15-51` | 持有者活着时**偷不走** |

缺口：**dispatch 返回之后、`receipt_json` 写入之前**这一段没有崩溃注入。这个状态目前只用
"dispatch 抛异常"来建模（`:305` 无回执 → guard 保留），而抛异常和进程消失不是同一件事——
前者会走 `_failed`（`:189`）的 `no_effect` 判定，后者什么都不会执行、只留下
`RUNNING` + `receipt_json IS NULL`。A1 因此记**部分成立**。

### A2「重启可对账」— **不成立**（对账代码存在，但没有任何生产调用点）

`src/design_lab/runtime/job_store.py:318` 的 `recover_interrupted(conn)` 会把所有
`attempt_state.state='RUNNING'` 改成 `OUTCOME_UNKNOWN`，它自己的 docstring 写着：

> "Stopped-worker recovery. Caller must stop old workers, not steal live work."

全仓检索该名字的调用点，结果只有三类：

1. **定义处**：`job_store.py:318`；
2. **测试**：`tests/test_runtime_attempt_safety.py`（3 处）；
3. **一个只检查函数名存不存在的地方**：`scripts/verify_recovery_safety.py:99,109`。

也就是说：**生产代码里没有任何地方调用它**。服务工作进程入口 `cli.py` 的 workbench/worker 分支
直接进 `execute_queued`，没有启动扫描。对账能力是**由调用方驱动的**
（`reconcile_receipted` `:204`、`_reconcile_receipted_locked` `:221`、`_quiesce_host` `:267`），
"重启"这个动作本身不触发任何东西。

所以 A2 的字面要求「重启可对账」不满足；`:367-391` 那条测试证明的是"**调用方**接续同一个
version_id 且 guard 保留"，它偷换了主语。这个区分很重要，否则一条 unit 证据会被读成 A2 已闭合。

顺带说清为什么不该无脑接线：`recover_interrupted` 扫的是**全表** `state='RUNNING'`，如果在工作进程
还活着的时候于启动处调用它，会把**在途**任务标成 `OUTCOME_UNKNOWN`——这正是 docstring 禁止的
"steal live work"。原计划的补救是"对每个 RUNNING 的 attempt 用 `native_recovery_lock.py:12`
（OS 级 `msvcrt`/`fcntl`、永不 unlink、永不过期）试探，拿得到锁才改状态"。
**2026-10-07 复核：这条补救本身不成立**，因为那把锁只被**恢复**路径持有、执行路径不持有，
而且 `native_workers.py`（全文 50 行）没有任何落盘 PID 或覆盖 worker 生命周期的 OS 锁——
**本机当前不存在可判"执行者已死"的信号**。缺的是前置件而不是接线，详见 §三 的自我更正。

### A3「未证明停止不解锁」— **成立**（而且比要求的更严）

宿主锁 `native_host_guard_v1`（`native_tasks.py:56-59`）的列只有
`host / attempt_id / acquired_at`，**没有过期列**。全文件删除该 guard 的语句恰好 3 处：

| 行 | 触发条件 |
|---|---|
| `:186` | `_finish`：publish 已校验完成 |
| `:198` | 证明是 dispatch **之前**被拒（无副作用） |
| `:312` | `_quiesce_host`：拿到了静默回执，且当场复核 `current['state']=='OUTCOME_UNKNOWN' and guard==(attempt_id,)`，整段包在 `except → QUIESCENCE_OUTCOME_UNKNOWN_GUARD_RETAINED` |

没有超时清锁、没有关闭共享宿主清锁的代码路径；`native_workers.py:47-49` 明确不杀子进程也不关宿主。
账本要求的「禁止靠过期或关闭共享宿主清锁」在宿主锁上**字面成立**。

需要写清的一处**相邻但不违反**的细节：资产写入租约确实**会**过期
（`asset_store.py:194` `lease_seconds=60`；`_lease_live` `:184`），且 `acquire_writer` 在过期后
会静默放行新持有者（`:198-200` 只对"legacy HELD 且无过期时间"强制显式 takeover）。
这**不构成**双写：`acquire_writer` 每次 `generation+1`（`:196`），而
`writer_token`（`:209`）与 `_fence`（`:216`）要求 `(holder, generation)` 与租约同时匹配，
过期持有者手里那个旧 generation 在发布时会被 `expired or stale writer fencing token` 拒掉。
所以"靠过期清锁"在这里清掉的是**互斥**，不是**写入授权**——fencing 才是 A2「不重复建对象」的守门人。
我核到这里而不是停在"有 60 秒过期"，因为后者会指向一条不成立的缺陷。

## 三、为什么不抬升任何轴

- `implementation`：A2 的主语错位说明"持久化对账"这一半只完成了**函数**，没完成**接上产品**。
  维持 `PARTIAL`。
- `unit`：现有测试是真的（真 SQLite、真文件、真子进程、真 OS 锁），但按**逐条 acceptance** 对齐，
  A1 少一个相位、A2 零个测试（没有"重启后对账"的测试，因为根本没有那条路径）。
  证据记录 `r5-004-static-unit-20260928` 的 `commands_and_exit_codes` 是
  `scripts/run_python_tests.py -> exit 0`，即**整套跑通**，不是**逐条判定**。
  按 001/002 已确立的口径，套件通过只支持"unit 有进展"，不足以把三条 acceptance 一起抬成 PASS。
  维持 `PARTIAL`。
- `host_live`：`required_axes` 含 host_live，证据数组为空，且需要真实 Illustrator/Photoshop
  宿主 E3；owner 侧授权仍是"只读探针、不拉起 GUI"。本次**未触碰宿主**。维持 `PARTIAL`。
- `delivery`：无交付包验收。维持 `PARTIAL`。

**抬升 unit 的最小充分动作**（按序，均可自动化）：

> **2026-10-07 当天自我更正（写下本节之后、实施之前查证）**：下面第 1 步原写为
> "用 `native_recovery_lock.recovery_lock(paths, attempt_id)` 逐 attempt 试探"。**这条做法是错的**，
> 已作废，正确形态见 (1')。查证结果：
> - `recovery_lock(self.paths, attempt_id)` 在 `native_tasks.py:216` 只被
>   `reconcile_receipted`（`:204`，**恢复**路径）持有，**不是**执行路径持有；
>   `native_bundles.py:36` 同样是恢复路径。
> - `native_workers.py` 全文只有 50 行：进程内 `threading.Lock`（`:17`）+ 一个
>   `subprocess.Popen`（`:43`）。**没有落盘的 PID、没有覆盖 worker 生命周期的 OS 锁。**
>
> 结论：**"某 attempt 的锁空闲"只能证明"没有 recovery worker 在跑它"，不能证明执行它的进程已经死了。**
> 若照原第 1 步接线，启动对账会把**在途** RUNNING 误标 `OUTCOME_UNKNOWN`，
> 恰好违反它自己引用的那句 "Caller must stop old workers, not steal live work"。
> 这也解释了为什么 `recover_interrupted` 当初就没被接上：不是漏接，是**缺前置件**。

(1') **先造判活前置件**：让**执行**中的 attempt 全程持有
`recovery_lock(paths, attempt_id)`（从 `_claim` 到 `_finish`/`_failed` 为止）。OS 级锁随进程消失自动释放，
于是"锁空闲"才等价于"既没有执行者也没有 recovery 者在跑这个 attempt"。
接线前必须先核对**重入**：`reconcile_receipted` 与 `native_bundles.py:36` 已经在同 attempt_id 上取同一把锁，
`msvcrt.locking` 非重入，若某个持锁调用链再进 `run()` 就是自锁死。
(2') 逐 attempt 判活的启动对账：对每个 RUNNING 的 attempt 试探该锁，拿得到才改状态。
(3') 真子进程测试：崩溃留下 `RUNNING` + `receipt_json IS NULL` → 重启后 (a) 变 `OUTCOME_UNKNOWN`、
(b) `asset_version` 计数不变（不重复建对象）、(c) **有活执行者持锁时不改它的状态**——(c) 是这整节存在的理由。
(4') 把 §四那个空转闸门改成真断言：生产调用点 + "执行路径确实持锁" 的结构检查；这一步不做，
    新接的路径仍然没有对抗者。
(5') 在合并后的 exact SHA 上重跑套件，取 `commands_and_exit_codes` + `environment_versions`，
    新证据只绑定**入仓路径**。

`host_live` 不在最小动作内：它要真人授权宿主，不能自证。

## 四、本次复核的主要发现：一个从不在 CI 运行、且核心断言是 `hasattr` 的恢复安全闸门

`scripts/verify_recovery_safety.py` 看起来是 A2/A3 的守门人。实际情况：

1. **它不被任何地方执行。** 不在 `.github/workflows/canonical-verify.yml` 的步骤里，
   也不在 `scripts/run_python_tests.py` 发现的测试里。全仓唯一提到它的文件是
   `scripts/verify_contract_graph.py:66`——只是把它**列进一份清单**，不调用它。
2. **它对 A2 的核心断言是"函数存在"**：`:99` `if not hasattr(job_store, "recover_interrupted")`，
   `:109` 把它作为 `"recovery_entry_point"` 输出。函数定义着，所以这一项**永远为真**，
   与它是否被调用完全无关——正是 §一.2 那个"没有任何生产调用点"的事实能穿过它的原因。
3. **它对"测试覆盖了未知结局恢复"的判据是子串**：`:104-106` 只要某个文件全文里出现
   `"unknown"` 这个词就算覆盖。这不是行为断言，是关键词匹配。

三者叠加的效果：一份"恢复安全已审计"的印象，背后是一个不运行、且即便运行也只能检查
函数名和单词的脚本。按"闸门要拦谎、不拦易变计数"的既定口径，该文件应改成：
(a) 断言存在**生产调用点**（扫 `src/design_lab/` 而非测试，找到 `recover_interrupted(` 的调用），
(b) 断言调用是**逐 attempt 判活**的（存在 `recovery_lock` 组合使用的结构），
(c) 覆盖判据从"文件含 `unknown`"改为"该测试真的调用了 `recover_interrupted` / 启动对账入口"。
在 (a) 落地之前，§三 的 (4') 不许跳过——否则新接的启动对账仍然没有任何对抗者。
（并且 (a) 单独做也不够：若闸门只查"存在生产调用点"，它会放过一个**没有判活前置件**的错误接线，
所以 (a) 必须同时断言"执行路径确实持有 attempt 级 OS 锁"这一结构。）

（本记录只登记该发现，不改动该脚本：脚本自身的修改必须与新测试同批落地，且要先证伪。
留作 DL-R5-004 最小动作的第 3 步。）

## 五、诚实边界

- 本次**没有**运行宿主、**没有**触碰 `.project-local` 之外的路径、**没有**改账本。
- §二的行号在 `ee2cf1fa` 上逐条 grep 复验过（`recover_interrupted` `:318`、guard 表 `:56-59`、
  三处 DELETE `:186/:198/:312`、租约 `:194`、`_fence` `:216`、`native_tasks.py` 共 382 行）。
  行号是点状时间戳，后续改动该文件即失效，引用时先复验。
- A1 表格里"真崩溃"的判断来自阅读测试体（`os._exit`、真临时 SQLite、真 OS 锁），
  不是来自测试名字。
- "套件通过"不等于"三条 acceptance 成立"：`r5-004-static-unit-20260928` 的
  `outcome` 字段本身就是 `PARTIAL`，其 note 已声明"未绑定 host_live 与 delivery，不宣称完成"。
  本记录与它一致，不推翻它，只是把**为什么**逐条写清。
