## 范围

**Batch F-2b：Workbench 的 revision 用户流程**（F-2a 的产品化另一半）。1 个 commit，基线 `8b2f49f`。

## 为什么需要它

F-2a 只把 revision 能力落在数据/API 层：人无法改版 brief/direction；而且**修订已选定方向后**，UI 无从表达"设计系统绑定已不再适用"。本 PR 补上用户可见的这一半。

## 交付内容

**`apps/workbench/{main.ts,index.html,style.css,contracts.ts}`**
- 每个 brief/direction 行新增「新版本」（按该版本自身内容预填）与「版本链」；提交走 project-scoped revisions 路由，读取 `.../lineage`
- 修订成功后重新读取**服务端 read model**、高亮并聚焦新版本行、自动展开其版本链
- 版本链渲染「版本 N · 当前」/「版本 N · 已取代 → 版本 M（短id）」+ 创建时间 + spec hash；已取代版本明示"服务端会拒绝本次修订（STALE_REVISION）"
- **绑定如实呈现**：只有 read model 的 `active_binding` 显示为生效中；其余绑定行标「未生效 · 绑定留在已被取代的方向版本上，需重新建立」；当 `active_binding` 为 null 而存在绑定历史时，`#design-binding-active` 明确要求重建绑定——**绝不把旧绑定显示为当前**。修订已选定方向后还会说明"选定结论随新版本带走、绑定未跟随"
- 409/404/401 走既有 `#status`（`class=error`），fail-closed 不静默
- `contracts.ts` 补齐 6 个 revision/lineage 响应类型（strict TS，`tsc --noEmit` 通过）
- 样式仅用既有令牌（teal `#146e65` / 墨色 / 纸色），新增少量 `.revision/.lineage/.highlight/.warn` 规则；**无紫色、无渐变、无第二套样式体系**

**构建确定性**（CI no-drift 门禁的等价证据）：连续两次 `pnpm --filter @design-lab/workbench build` 均产出
`sha256 bb13f6738a9a3d54fb86fa39ec0295b73f9c7750a52331bc36662bb2c470c4eb`（41.86 kB）；我在核验时**再重建一次**得到同一哈希 → 提交的 bundle 就是当前源码的真实构建产物。

**测试**
- `browser_design_layer_e2e.mjs` 扩展 4 步：revise brief / revise chosen direction / binding-rebuild readback / reload-persisted readback
- `test_workbench_native_ui.py` 新增 2 个 vm-DOM 用例（预填 + 真路由 + 可见的 STALE_REVISION/401 错误且不新增行；`active_binding` 为 null 时的重建渲染）

## 验证证据（主线独立重跑）

```
-m unittest discover … -p "test_workbench*.py"     Ran 16 tests  OK
verify_browser_e2e_ran.py                          BROWSER_E2E: PASS (ran=2 skipped=0 failed=0)   ← 真实 Chromium，非 SKIP
verify_workbench_packaging.py                      WORKBENCH PACKAGING: all 5 checks passed
verify_design_lab.py                               VERIFY_DESIGN_LAB=OK total=49 failed=0
scripts/verify_authority_gates.py --zero-spill     AUTHORITY_GATES=PASS gates=7 failed=none
pnpm --filter @design-lab/workbench build          sha256 与提交产物一致（重建）
```

浏览器 E2E 实跑读回（真实服务 + 真浏览器）包含：

```
brief  : "… · 参考 1 · v2 · 当前 · sha256:0c30c276…"
链     : ["版本 1 · 已取代 → 版本 2（e0b14e36）…", "版本 2 · 当前 …"]
direction: "… · CHOSEN by workbench-user · v2 · 当前 …"
binding: "… · 未生效 · 绑定留在已被取代的方向版本上，需重新建立"
active : "当前选定方向「Warm Gradient II · 版本 2」没有生效的设计契约：…绑定需重新建立…"
```

## 未做（保持 OPEN）

F-3（release-preflight 真实 API 回读）在另一路并行进行；Batch F 其余（Host E3 预置脚手架）、真实 Host E3 / 人工 E4（owner 排除）。
