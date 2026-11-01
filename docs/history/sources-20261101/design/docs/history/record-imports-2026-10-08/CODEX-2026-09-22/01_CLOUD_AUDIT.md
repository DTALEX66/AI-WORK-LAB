# DESIGN-LAB 独立审计交接

日期：2026-09-22。整理方式：从此前已交付的审计总包按项目拆分；本轮没有刷新云端，也没有执行仓库产品测试。

## 1. 结论与范围

先保护本地未上传内容并对账 PR #135，修新 AppShell 状态与路由风险；保留已有第一条全栈链，再推进真实原生可编辑产物、读回、恢复、质量与交付。

这是已列明范围的审计记录和待执行任务，不是“全仓、完整原始对话及用户实机全部验收通过”。拆分没有提升证据等级。

## 2. 本项目快照

| 对象 | 此前观察值 |
|---|---|
| 仓库 | `DTALEX66/DESIGN-LAB` |
| main | `6a16c40b7a48f72757a0327ec07462d23449bb11` |
| UI 候选 | `085a0f6ed8e0cd0db6e459cae9ce9c6f772f8ce2` |
| 候选入口 | `PR #135 / feat/ui-convergence-slice2（原审计快照：OPEN）` |

以上均是继承快照，执行时刷新。未提交、未推送与本地独有内容要作为单独状态比较；不能因 main 中未出现就覆盖或重做。

## 3. 历史与边界

当前入口是本仓 AUTHORITY、authority-index、AGENTS 与统一任务包。保留 strict TypeScript/Vite/pnpm 的 Workbench 和 Python 生产层，不以旧报告或另一项目的技术栈重写本项目。[S18,S19,S20]

本项目应 standalone-first。WORK-LAB/AAOS 默认关闭不影响启动、测试和恢复；KnowledgeCandidate 仅通过获准公共合同导出，不读写对方私有数据库，也不外传客户 brief 或原始商业素材。[S20]

保护已安装的 Adobe/Comfy/H3/MiniMax 环境，先读路径配置再受限探测。存在性声明不等于实机 E3/E4。B10/B09/B07/B04 需逐文件核对真实设计包，不因 B08 原型而换栈。[S20,H03,H04]

## 4. DESIGN-LAB：不重做第一条链路，但新 UI 还不能直接放行

### D-01：已经存在的工作，必须保留

当前 AUTHORITY 把 `Project → Brief → Reference → Direction → DesignSystem` 第一条全栈链路列为 CLOSED，并有 strict-TS、API/浏览器/打包等回归保护。此次读取了 AUTHORITY、AGENTS、authority-index、main 的九个 job 状态及 PR 新前端片段；这些支持“不是只写了 README”，但本次没有逐行独立复验整条后端链路。[S18–S21,S24]

main run `35546749035` 九个 job conclusion 为 success；其中 Open Design host adapter job 内的依赖安装和 structural gate 步骤实际被条件跳过。Workbench browser E2E 则实际运行成功。成功的 job 名称不等于里面所有步骤运行，更不等于真实 Photoshop/Illustrator 验收。

PR #135 head 的检查中，本次确认看到 Python 和 browser E2E success；接口 total_count=18，但显示内容截断，本报告不把未展开的 18 项全部标绿。[S23]

### D-02：新 AppShell 登录可见性缺陷，独立最小逻辑复现已完成

范围：PR #135 的 `apps/workbench/main.ts`，`mountAppShell().show()`。[S24]

代码先按路由把 `login.hidden` 设为 true；返回工作台时又把该 DOM 可见性当作连接状态，令 `workspace.hidden=false`，却不恢复 login。

显式初态为“未连接、登录可见、工作区隐藏”，序列为：

| 动作 | login.hidden | workspace.hidden |
|---|---:|---:|
| 初始工作台 | false | true |
| 点仪表盘 | true | true |
| 返回工作台 | true | false |

本包 `08_DESIGN_APPSHELL_MIN_REPRO.mjs` 在当前容器 Node v22.16.0 执行，预期安全断言失败，exit code=1；完整 stdout/stderr 在 `09_...RESULT.json`。这是抽取可见性赋值的最小逻辑复现，不是原 bundle 的浏览器 E2E，不证明后端鉴权被绕过。后端仍有 Bearer API 路径，不能把 UI 状态错误夸大成未授权访问。[S24]

修复方向：连接/鉴权状态必须显式持有，不能由 `login.hidden` 反向推导；未连接导航后返回应恢复登录并隐藏 workspace。补真实浏览器用例，再允许合并候选。

### D-03：异步路由读回存在串页风险，尚待产品浏览器复现

多个 renderer 持有同一个 `route-view` DOM，await 后直接 `replaceChildren`。新 `show()` 没有 route generation、取消或 stale-response 判定。因而旧 dashboard 请求晚于 settings 返回时，可能把旧视图写回新路由。catch 错误路径也需要相同保护。[S24]

此项是源码可推导的竞态风险，不是已观察到的用户数据泄露。测试需控制旧请求延迟，快速换路由，验证最后成功/失败响应都不会污染新视图；同时覆盖断开连接、重新连接、项目切换。已有主工作台 epoch/request 保护不能自动覆盖新 AppShell renderer。

### D-04：12 路由不是 12 条完整业务能力

实际新代码保留旧工作台，并新增四个真实 API 读回视图；另外七个槽位明确写着未开放：独立 projects、research、design-domains、creative-tools、deliverables、evidence、collaboration。状态机组件也明确只是契约可视化，不代表真实进度。[S22,S24]

这是诚实的能力边界，不应为了补齐菜单虚构后端、KPI 或“已交付”状态。后续优先把当前已有任务/交付/证据能力通过服务合同连接到合适页面，不先造团队协作、第二画布或通用 Agent 系统。

### D-05：真正剩余的是原生编辑产物与可恢复闭环

AUTHORITY 的下一段是 `Reference / DesignSystem → DesignIR → 原生可编辑产物`，再加 reopen/readback、patch、幂等恢复、rights/preflight、独立人工质量验收。不能把 controlled-runtime E2 或控制路由矩阵当成 E3/E4。MiniMax Design 软件、H3 模型、ComfyUI 与 Adobe 宿主各自有能力和证据边界；不能推导“全家桶全部可控”。Comfy/H3/UIA 不是 Adobe M1 的强制前置。[S18,S20]

## 5. 覆盖限制

完整 raw chat（包括 9/14–9/15）、所有文件语义检查、所有历史分支/tags、完整供应链/历史密钥扫描、全部 CI artifacts 和实机闭环仍须按覆盖表补齐。CI 报告数字不是本次产品测试；快照不是实时状态。

本地未上传代码、设计包、商业素材和宿主实机尚未读取；原项目浏览器回归与独立人审未在本次拆包重跑。

## 6. 单项目执行

顺序：`G0 → G1 → D0 → D1/D2/D6/D7 → D3 → D4/D5/D8 → G2`。完整指令在 `02_CODEX_EXECUTION.md`，本地保护在 `07_LOCAL_RECONCILIATION_CHECKLIST.md`，只读任务索引在 `10_TASKS.json`。不需要另一项目包，也不需要双项目总控会话。

## 7. 证据索引

来源见 `11_SOURCE_INDEX.md`，机器记录见 `05_EVIDENCE_LEDGER.json`，覆盖见 `06_AUDIT_COVERAGE.csv`。本包不含完整源码克隆、完整原始对话、所有 Actions 日志或 B10 视觉素材；source locator 仅用于复核来源。

## 8. 同日早一轮的本项目附件

为避免拆包漏项，保留资产版本 SQL 反例、宿主环境冲突与实际故障注入检查，以及已下载的一个受控浏览器 E2 artifact。见 `13_PREVIOUS_EVIDENCE_NOTES.md`。这些不替代当前代码回归或原生宿主验收；原始附件已在拆包时校验字节一致性。
