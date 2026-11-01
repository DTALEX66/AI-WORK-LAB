# T1 账本逐任务复核 · 第八项：DL-R5-008

**复核对象**：`design-lab/config/task-ledger-r3.json` → `DL-R5-008`「ComfyUI 生产适配与可选本地 MCP」
**观测 exact SHA**：`origin/main` = `f98d9371`（`gh api`/`git rev-parse` 实读）
**观察窗口**：2026-10-06T22:47Z–22:53Z
**结论**：四条验收句里，**只有第 1 条在代码与测试两层都成立，而且它守的是一条还没有产品入口的路径**——
`comfy_task.py` / `comfy_http.py` 在 `src/`、`scripts/`、`integrations/`、`packages/` 里**没有任何生产导入方**。
本轮修掉了第 1 条里一个真实的假 hash 漏洞（附变异测试），其余不抬升。

| 轴 | 现状 | 证据 | required |
|---|---|---|---|
| `implementation` | PARTIAL | `r5-008-static-unit-20260928` | 是 |
| `unit` | PARTIAL | `r5-comfy-structural-rejection-20260909` | 是 |
| `host_live` | PARTIAL | `r5-comfy-http-model-free-live-20260909` | 是 |
| `delivery` | PARTIAL | 空 | 否 |

---

## 0. 最重要的一条：这套适配器还没接到任何产品路径上

全仓检索（排除自身与测试）：

```
grep -rln "comfy_task\|comfy_http" --include=*.py .   →
  ./design-lab/tests/test_comfy_http.py
  ./design-lab/tests/test_comfy_task_protocol.py
  ./docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/harness/w00-evidence-scan.py
```

即：**只有它的两个测试文件和一个 09-28 审计脚本提到它**。`src/` 里没有任何模块导入它，
`scripts/`、`integrations/`、`packages/` 同样没有。因此：

- 验收句 1「路径穿越、假 hash 拒绝」的守卫**当前不保护任何真实调用路径**；
- `comfy_task.py:115-116` 的注释把职责明确推给运行时——
  「the runtime must independently resolve the approved output root, reject links and verify actual
  artifact bytes」——而**那个运行时不存在**。所以"输出根未校验"不是遗漏，是**已声明但无人兑现的边界**。

账本 `baseline_observation` 写「comfy_task.py 缺陷仍在」，本轮确认：缺陷在，
且比"有缺陷"更根本的是**没有消费者**。删或接是 owner 判断（删等于销毁已写协议与 25 条测试），
本轮只记录，不动。

## 1. 验收句逐条

| 句 | 状态 | 证据 | 缺什么 |
|---|---|---|---|
| 1 路径穿越、假 hash 拒绝 | **实现+测试，但此前不完整（本轮补）** | 词法路径检查 `generators/comfy_task.py:117-124`；节点 `source_hash` 零值拒绝 `:66`；结果指纹零值拒绝 `:122-126`；测试 `test_comfy_task_protocol.py:32-45`、`:40-45` | 无 realpath/符号链接校验（注释已声明推给运行时）；无批准输出根白名单 |
| 2 图像 golden 连续 10 次记录完整 | **未实现、未测试** | 仅 `docs/handoffs/R5-COMFY-HTTP-LIVE-2026-09-09.md:3,8` 的一次**无模型** HTTP 运行 | 真机 ComfyUI + 合格 checkpoint + 跨运行记录器；仓内 `grep golden` 只命中无关重建语料 |
| 3 另测取消/失败/重连 | 状态机**实现+测试**；传输层**未实现** | `comfy_task.py:158-165`、`:193-194`；测试 `:144-151` | `comfy_http.py:5` 自述无重试无取消；全仓无 WS、`/interrupt`、`/queue` 客户端 |
| 4 正常失败也须记录 | 仅"缓存命中诚实性"实现+测试 | `comfy_task.py:84`、`:142-152`；测试 `:97-115` | 没有区分"记录完整"与"十次全成功"的运行记录 schema；`CANCELLED` 可无原因、`FAILED` 可携带可认领工件 |

## 2. 本轮真的修了一条：`inputs_hash` 接受全零假 hash

`comfy_task.py:100-101` 原来只验形状不验非零：

```
-        if not _SHA256.fullmatch(self.inputs_hash):
-            raise ComfyTaskError("inputs_hash must be sha256:...")
+        if not _SHA256.fullmatch(self.inputs_hash) or self.inputs_hash == 'sha256:' + '0' * 64:
+            raise ComfyTaskError("inputs_hash must be a nonzero sha256:...")
```

同一个规则在 `node.source_hash`（`:66`）与 `workflow_fingerprint`（`:122-126`）都已生效，
唯独 `inputs_hash` 漏掉——于是一个任务可以声称它哈希过输入，而实际什么都没哈希。

**变异测试**（先证伪再用）：

```
带修复： unittest discover -p "test_comfy*"  → Ran 25 tests, OK
回退源码后： 同命令 → Ran 25 tests, FAILED (failures=1)   # 新增断言确实会红
```

## 3. 其余在码缺陷（记录，未改）

1. `:132-134` 死条件：`CANCELLED` 可无原因通过校验；
2. `:159` `QUEUED → FAILED` 被状态机禁止，于是"起跑前就失败"只能记成 cancelled；
3. `:142-152` `classify_result("BOGUS")` 返回 `"in progress (BOGUS)"`，未知状态永不报错；
4. `:83` 与 `:166` 两份终态集合重复定义。

第 2 与第 1 条合起来正对着验收句 4：失败形状被系统**引导**成另一种状态，而不是被如实记录。

## 4. 两条 2026-09-09 证据记录实际绑了什么

按 id 直读账本 `evidence[]`（39 条中命中的两条），不用行号——行号会随任何一次插写漂移：

| 字段 | `r5-comfy-structural-rejection-20260909` | `r5-comfy-http-model-free-live-20260909` |
|---|---|---|
| `subject_sha` | `a06c1db01944…`（`f98d9371` 的祖先） | 同左 |
| `binding` | `WORKTREE_FILES` | `WORKTREE_FILES` |
| `subject_files` | `comfy_task.py d25591f9…`、测试 `c0106a00…` | `comfy_http.py d8bb2404…` |
| 顶层 `commands_and_exit_codes` | **无此字段** | **无此字段** |
| 顶层 `limitations` | **无此字段**（限制写在 `note` 里） | 同左 |

两点必须公平地说：

1. **记录本身是诚实的**。结构性那条的 `note` 自己写明「仅词法路径/指纹、零 checksum 和重复 node ID，
   不能证明产物实际 hash 或 Comfy 传输」，还写了「新增拒绝测试先出现 16 个 subtest 失败再修复」
   ——这正是本仓"先证伪再用"的先例。HTTP 那条的 `note` 也直说 64x64 PNG「不是模型生成」，
   并把 WS、取消 ACK、10 次基准列为未完成。
2. **不合规的是 schema 而非措辞**：`evidence_required` 要求 `commands_and_exit_codes` 与
   `limitations` 两个结构化字段，而两条记录都只有自由文本 `note`。命令与退出码因此不可机检，
   限制条件因此不可机检——把它们写在 `note` 里是诚实，但诚实不等于可验证。

**主题漂移**：结构性那条绑的 `comfy_task.py` 哈希是 `d25591f9…`，当前 blob 是 `7a4d43ef…`
（本轮 §2 修复前）；测试文件同样从 `c0106a00…` 变成 `9e478473…`。HTTP 那条的
`comfy_http.py d8bb2404…` 仍与当前一致。所以前者连"它验过的那份字节"都不再存在，
至多算 `HISTORICAL_VALID`（`design-lab/scripts/verify_comfyui_gate.py:59-69` 的口径），
**不能抬升当前轴**。HTTP 那条的 `note` 还自报「ignored 原件换机缺失应 MISSING」——
即它绑的原始工件在 `.project-local/` 里，换机即丢，这也是 §6 第 4 步要求新工件只绑 tracked 路径的原因。

## 5. 为什么仍然不抬升任何轴

1. `host_live` 属 `required_axes`，其证据是一次**无模型** HTTP 运行；句 2 要求的十次图像 golden
   需要真机 ComfyUI 与合格 checkpoint，属宿主/真人项，本轮目标明确排除。
2. 句 1 的守卫没有产品入口（§0），给它记"已验证"等于给一条没人走的路记安全分。
3. 本轮新增的当期证据只覆盖一个校验分支（§2 变异测试），不足以支撑任何整轴提升。

## 6. 抬升 008 所需的最小动作（按序）

1. **先定身份**：这套适配器是"未来的真适配器"还是"协议夹具"。若是后者，
   账本与 `docs/` 应把它写成 protocol-only，别让 `host_live` 轴暗示它跑过；
2. 若要成真适配器：接一个消费者（服务路由或 CLI），并兑现 `:115-116` 承诺的
   输出根解析、符号链接拒绝与工件字节复核；
3. 修 §3 的四条（尤其 `QUEUED → FAILED`，它直接扭曲句 4 要求的失败形状）；
4. 补跨运行记录器，按句 2 跑十次并**如实记录失败**，工件哈希只绑 tracked 路径
   （别再写进 `.project-local/`，那正是 §4 里已经丢失的那个 `result.json` 的成因）；
5. 给两条 2026-09-09 记录补 `commands_and_exit_codes` 与 `limitations` 字段，
   或显式降级为历史证据。
