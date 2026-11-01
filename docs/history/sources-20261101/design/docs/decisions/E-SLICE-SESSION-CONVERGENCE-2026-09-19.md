# DESIGN-LAB E-SLICE 会话收敛记录（D 段 + E-SLICE-01/02）

**日期**：2026-09-19
**Authority**：`DL-AUTHORITY-2026-09-18-R2`（顶层）；前驱 `DLDS-H010 / DL-AUDIT-20260914-07`
**类型**：`SESSION_CONVERGENCE_RECORD / EXECUTION`（跟踪本次会话的推进与闭环证据；不作为新的顶层权威，权威恒为 `/AUTHORITY.md`）
**落仓 main**：`cb2163a2ad6db7bd12ee1ca07c1d3eb2badc328e`

## 0. 范围声明

本会话执行常设目标「授权全部推进（除去实操软件任务环节）」。
- **范围内**：Authority 防漂移、前端 P0（strict-TS / pnpm / Vite / browser E2E）、首条全栈 Vertical Slice、以及 P1 中非 host 的 LANGUAGE-POLICY 收口。
- **排除**：真实 Host 运行（E3）、Human Jury 验收（E4）、DesignIR→Adobe 生成链路、远端分支删除等 owner-authorized 动作。

## 1. 三个落 main 的切片（按序）

| 切片 | PR | merge commit | 内容 | 证据等级 |
|---|---|---|---|---|
| D 段 | #122 | `51f222f` | Workbench strict-TS 产品路径 + D003 Build Output Truth + `workbench-gate`（7 项 required checks） | E1 |
| E-SLICE-01 | #123 | `b664dd4` | 设计层垂直切片 Project→Brief→Reference→Direction→DesignSystem（additive 迁移 + `design_layer.py` + 7 路由 + Workbench 05 面板 + 契约测试） | E1 |
| E-SLICE-02 | #124 | `cb2163a` | 浏览器级 E2E：真实 Chromium 驱动 05 设计层全链，起真实 loopback 服务，断言持久化 DOM 回读 | **E2 受控运行** |

三个 PR 的 head 与 merge commit 的 Canonical Verify 均 `conclusion=success`，绑定 merged SHA。

## 2. E-SLICE-01 关键根因修复（真实证据）

- **WinError 10053**（错误响应前未排空请求体 → socket RST）：`http_service.py` 加 `drain_body()`，160 请求压测 0 transport error。
- **503 `no such table`**（读路径裸 `sqlite3.connect(mode=ro)` 跳过 guarded 迁移链）：读路径改走 `cstore.connect()`，probe 证实新建项目读 `design_brief` 返回 `[]` 而非 503。
- **前驱 `contract-graph` DRIFT**（新 additive 迁移表让 `declared_tables` 漂移）：重生成 `reports/current/CONTRACT-GRAPH.json` 吸收，diff 恰好 = 3 张设计层新表 + 生成时间戳；非绕过门。

## 3. E-SLICE-02 关键根因修复（真实证据）

- **修订版不匹配、零浏览器下载**：仓内 `playwright 1.63.0-alpha` 期望 `chromium-1243`，本机已装 1208/1228。用 `launch({ executablePath })` 显式指向已装二进制，绕过修订版检查，`LAUNCH_OK` 探针证实。
- **异步 settle 陷阱**：`create-form` 提交后 `#project` select 须等 create POST + `projects()` 回读才填充；驱动脚本改为等待新 `<option>` attach 再 select。
- **诚实 SKIP 设计**：Python 壳（`run_python_tests.py` 自动发现）探测 `node` + 仓内 gitignored npm-cache + 本地 Chromium 三者齐备则真跑，否则 `self.skipTest` 报缺哪一项——干净 CI runner 两者皆缺，诚实跳过而非假绿或强制下载。

## 4. P0 收敛判定（对照 AUTHORITY §15）

- ✅ **P0 Authority/防漂移**：R2 顶层 verifier（`verify_top_level_authority.py` 10 checks PASS）+ 前驱 7 门链（`verify_authority_gates.py --zero-spill` gates=7 PASS）。
- ✅ **P0 Frontend**：strict-TS + pnpm + Vite + **browser E2E**（E-SLICE-02 补齐最后一块；`workbench-gate` CI 注释委托项 "NOT silently dropped" 已落实）。
- ✅ **P0 首条全栈 Vertical Slice**：E-SLICE-01 落仓。
- ✅ **P1 非 host**：LANGUAGE-POLICY 残留单句在 R2 落仓时已闭环——本轮实测 `single-ruff-fact` check **PASS**（`docs/architecture/LANGUAGE-POLICY.md` 已是 `CONFIGURED_NOT_ENFORCED`，无 stale `DECLARED_NOT_ENFORCED`），按"已闭环项不得无证据重做"铁律不重做；`workbench-gate` 已在 7 项 required checks 中。

## 5. 剩余项（owner 门控，本会话未执行，待 owner 决策）

1. **远端分支删除**：识别出 8 个已合并进 `origin/main` 的删除候选（`codex/deepseek-authority-r1`、`docs/ucr-handoff-20260918`、`feat/dl-authority-convergence-r2`、`feat/e-slice-browser-e2e`、`feat/e-slice-vertical-1`、`feat/ucr-convergence`、`feat/ucr-p0a-truth`、`feat/ucr-report-truth`）；其余 23 个未合并分支须逐项 semantic 定级。删除属 owner-authorized，本会话仅识别、不删。
2. **Ruff 是否真正 enforce**：AUTHORITY §15 明文"单独决策，不重开全语言迁移"，属 owner 决策点。
3. **Host 层（E3/E4、DesignIR→Adobe）**：被当前请求排除，另行安排。

## 6. 本地/CI 证据索引

- 全量 Python：`1412 tests OK (skipped=2)`（+2 为 E-SLICE-02 新增，本机均真跑；`ZERO_SPILL` 行为 `test_oda4_0101` 既有安全自测 fixture，非回归）。
- 前驱 7 门：`AUTHORITY_GATES=PASS gates=7 failed=none`。
- License 覆盖：两新增 E2E 文件 SPDX 全过（`LICENSE_COVERAGE=OK`）。
- main CI：run `35390771963`（head `cb2163a`）`success / completed`。
