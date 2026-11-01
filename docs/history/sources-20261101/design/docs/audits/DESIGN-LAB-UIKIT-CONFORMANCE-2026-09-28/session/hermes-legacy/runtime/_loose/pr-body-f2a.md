## 范围

**Batch F-2a：真实 revision（内容 immutable + 事件 append-only）**。3 个 commit，基线 `d89e93f`。

| commit | 内容 |
|---|---|
| `a47b868` | 迁移 v3 `design_layer_event`（DDL 级 append-only）+ 写路径事件化 + `revise_*`/`lineage_*` + HTTP 路由 + 14 用例 |
| `48a2c60` | 契约图重录（新增 state SQL 进入 `declared_tables`） |
| `c20e861` | reports 绑定输入重绑 + language 扫描重录（1957 文件） |

## 为什么需要它

审计报告第 257–267 行：`Brief v1→v2`/`Direction v1→v2`/`Binding v1→v2` 必须成为**真实 revision**；**不要**用 `superseded_by` 把 append-only history 偷换成随意可变的行——成熟设计是**内容对象 immutable + choice/binding/revision 事件 append-only**，`chosen` 作 materialized state。

改动前的事实：所有写路径 `INSERT ... version=1`、`superseded_by` 恒 NULL、无事件表 = "version-ready schema, not complete versioning"。

## 实现要点

- **append-only 是 DDL 属性不是约定**：`BEFORE UPDATE`/`BEFORE DELETE` 触发器 `RAISE(ABORT)`；模块用 plain `INSERT`（无 `OR REPLACE`/`OR IGNORE`），重复 `event_id` 直接主键冲突而非静默覆盖历史。
- **内容 immutable**：`revise_*` INSERT 新行 `version=parent+1`，旧行**只**动 `superseded_by`（源码注释标为"The ONLY column a revision may touch on the parent row"，测试对内容列含 goals/style JSON 与 `spec_sha256` 做逐字节断言）。
- **事件与状态同事务**：`create_brief`/`create_direction`/`choose_direction`（payload 记录 `previous_chosen_direction_id`，释放的兄弟产生 `direction-unchosen`）/`bind_design_system`（`binding-created` vs `binding-rebound` 携带 `replaced_binding_id`）。
- **血缘从事件边解析**：`lineage_brief`/`lineage_direction` 从任一成员都能得到 root/live/版本链。

## 验证证据（主线独立重跑）

```
design-lab/tests/test_design_layer_revision.py      Ran 14 tests  OK      ← F-2a 新测试
design-lab/tests/test_design_layer_http.py          Ran 18 tests  OK      ← 既有契约测试无回归
design-lab/scripts/verify_design_lab.py             VERIFY_DESIGN_LAB=OK total=49 failed=0
scripts/verify_authority_gates.py --zero-spill      AUTHORITY_GATES=PASS gates=7 failed=none
```

契约图漂移的取证与修复（**不是**绕过）：

```
修复前: FAIL contract-graph CONTRACT_GRAPH=DRIFT fields changed since generation: ['declared_tables']  ← 唯一失败项
根因  : grep -c design_layer_event reports/current/CONTRACT-GRAPH.json → 0（快照生成于 v3 之前）
修复后: CONTRACT_GRAPH=NO_BROKEN_LINK concepts=11 complete=11 breaks=0（用其自身生成器重录）
```

## 诚实标注

1. **本 PR 不含 Workbench 前端 revise 流程**（F-2b 紧随其后）——**不声明 revision 能力已产品完备**，只声明数据/API 语义已落地并有回归守卫。
2. 两处规格未覆盖、由实现方决定并已写进 docstring + 测试的设计选择，请审阅：
   - 修订一个**已 superseded** 的版本 → fail-closed `409 STALE_REVISION`（拒绝分叉链）；
   - 修订一个**已 chosen** 的方向 → 人类选择随新版本带走（父行释放 `chosen`/`actor`，payload 记 `chosen_moved`），而 append-only 的 `design_system_binding` 仍留在原绑定版本上，故 `active_binding` 在重新绑定前为 null —— 即「选择是 materialized state，绑定是 history」。
3. `reports/current/LANGUAGE-BOUNDARY-SCAN.json` 由门禁每次重写，链跑后已 `git checkout --` 还原，本 PR 只含其**真实内容变化**（1957 文件）。
4. 新增 state SQL 触发契约图漂移是**结构性必然**（`declared_tables` 快照），已按仓库先例（`c331fed`）用其自身生成器重录并在独立 commit 中记录前后证据。

## 未做（保持 OPEN）

F-2b（Workbench revise 前端 + bundle 重建 + E2E）、P1-A 余项、Batch F 其余（release-preflight 强化、Host E3 预置脚手架）、真实 Host E3 / 人工 E4（owner 排除）。
