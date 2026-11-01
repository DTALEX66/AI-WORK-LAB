# WORK-LAB UI 优先后续执行任务包 — 2026-10-09

> **SUPERSEDED_20261019 / FROZEN_20261019。** 用户 2026-10-19 冻结其他任务，并把
> `taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md` 设为唯一 CURRENT。
> 本文件保留原计划、状态与历史证据，不再派工；未完成 WUI 项不因本冻结关闭，也不得无证标记完成。
> 当前定位、冻结范围和路线图见 `docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md`
> 与 `docs/current/authority-convergence-20261019/ROADMAP.md`。

**TaskPack ID:** `WORK-LAB-UI-PRIORITY-TASKPACK-20261009`
**CURRENT:** 唯一当前执行计划；替代 `WORK-LAB-UNIFIED-PRODUCT-CONVERGENCE-TASKPACK-20260918` 及其旧派工顺序。
**依据:** 用户2026-10-09最新明确请求、两个原件任务包；顶层仍为WORK-LAB-AUTHORITY.md与既有机器索引。
**本轮交付:** 任务整理、归档、定义与索引切换、交接；产品实现NOT_EXECUTED。

## 当前产品及执行边界

软件中立、本地优先的AI工作观测与配置治理工作台。外部软件执行业务项目，默认按项目观察参与软件、活动、阻碍、来源和资源。
能力资产以源评价、可迁移性、目标验证和版本维护为中心；配置按声明所有权、三方差异、原生读回及恢复处理。
Observer/sidecar严格只读，搜索筛选复制展开是正常阅读；受管写仅走既有独立Control边界及服务端授权。
AAOS拥有完整知识/人的知识工作学习/AI学习资产/双向学习及长期项目记忆；DESIGN-LAB拥有专业设计、原生作品、设计内核与专业接受。
三方独立运行发布，协作按需。WORK-LAB不建学习中心、知识主库、三方总控制器或第二运行时。

**不做手机端，且没有手机端延后/冻结任务。** 16张桌面母版与浅深主题用于对照；原件17_mobile及窄屏断点仅保留来源，不派工。
保留React/TypeScript/Vite + Tauri/Rust + Python + JSON Schema；复用品牌、组件及主题，有意义文字≥12px。
main默认1280×820、下限900×600；既有HUD440×680是桌面浮窗，不是手机端。五目的地是建议，不是永久数字断言。

## UI优先路线

WUI-00做必要基线后立即开始WUI-01/02/03桌面UI。缺真实数据时做正确空态和明确隔离的测试fixture，不能生产默认塞演示数字。
随后接WUI-04/05/06读模型和页面、WUI-07/08能力、WUI-09/10规则。状态/设置/深链/键盘/DPI分别验收。
WUI-16/17完成生成与剩余历史消费者整理，不以先做全仓历史治理为UI前置。WUI-19是核心桌面最终验收。
WUI-20按需协作独立推进，不阻塞核心；公共回执/安全缺陷若影响核心调用链，按其真实影响优先修。

## 任务分解

每个任务分别交付实际diff、输入/源码/构建/客户端版本、读回断言、正负路径、截图或证据、恢复点和限制。
旧任务记录的历史PASS不赋给新任务。NOT_EXECUTED不等于代码缺失；先读当前实现，保留已工作的功能和回归保护。
旧未完成事项的范围继承见`docs/current/ui-priority-20261009/UNFINISHED-LEGACY-SUMMARY.md`，逐场景验收映射见`docs/current/ui-priority-20261009/ACCEPTANCE-MAPPING.csv`。
验收映射包含UI 44条、原40条与新增30条来源场景，存在重叠；114条来源映射不是114项独立功能或已通过测试。

### WUI-00 — 接手基线与最小对账

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：无。范围：.project/governance; taskpacks/current; apps/observer。

验收：现场 root/HEAD/main/worktrees/dirty/写者；保护现有修改；读取新CURRENT；只做与UI有关的定向发现，不先跑全仓治理。

继承：A00/A03; UI/Qoder cards。源任务：T00,T02,T03,T04。

### WUI-01 — 桌面项目首页与信息架构

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-00。范围：apps/observer/frontend/src/App.tsx; views; apps/observer/frontend/src/lib/viewRegistry.ts。

验收：以项目监控为首页；五目的地建议＋设置；协作进入对象详情；工作流编辑器退出默认导航；缺真实来源就显示正确空态，截图不冒充数据接通。

继承：U04; P1-01; AG-14; UI-PRODUCT-PROMPT。源任务：T11。

### WUI-02 — 桌面导航、搜索与对象详情骨架

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-01。范围：apps/observer/frontend/src/components/layout/Sidebar.tsx; command palette; views。

验收：所有当前日用目标可达、唯一ID；同对象详情；导航可滚可辨；不是永久必须5组；保留旧链接入口。

继承：UI-RAIL-REACHABILITY; P1-02-RECORD-FOCUS。源任务：T11,T12。

### WUI-03 — 主题组件与桌面密度

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-01。范围：apps/observer/frontend/src/theme/tokens.ts; existing components; skins; apps/observer/frontend/DESIGN.md; apps/observer/frontend/SCREEN_SPEC.md。

验收：按新母版层级适配已有VI/组件；不重造LOGO；深浅主题与有意义文字≥12px；24×24目标地板及例外；仅桌面main和既有HUD，不做手机端。

继承：UI-LEGIBILITY; CONTRAST; BRAND-MARK; U05。源任务：T11,T12。

### WUI-04 — 项目身份、参与软件与三轴读模型

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-02。范围：packages/client-neutral-core/scripts/snapshot_api.py; project schemas; frontend types; project views。

验收：非Git/多目录/worktree/同名不合并；多软件集合；工作/健康/观测分开；断连不推出停止；序列/last-good/来源时间；两真实支持来源另验，不阻塞页面骨架。

继承：U06/U07/U13/U16; F02。源任务：T05,T06。

### WUI-05 — 用量缓存与质量页面

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-04。范围：packages/client-neutral-core/scripts/snapshot_api.py; usage ingestion; usage schemas; usage views。

验收：字段精度和完整性统一；精确/估算/未知子集保留；真实0/缺失分开；Token/Credits/费用/资源分开；delta/cumulative/修订/父子/fork/replay去重守恒；缓存占比与请求命中分母正确。

继承：U09/U13; F03/F04。源任务：T07。

### WUI-06 — 软件环境页与首次接入资格

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-04。范围：software views; adapter registry; collector read models。

验收：版本/形态/适配器/字段绑定资格；有限支持与更新待复验明确；原生启动可观察，不强制本方派工；选择两个实际获准来源做读回；不探读私人会话和浏览器。

继承：U17; B3; C1; P1-03 capability cards。源任务：T05,T08。

### WUI-07 — 能力资产与评价详情

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-02。范围：tools/capability views; capability contracts; managed asset declarations。

验收：区分原创/定制/收藏/第三方/客户端形成成果；源和修订身份不混；许可/依赖/权限/适用条件/反例/用户判断；发现安装加载调用结果分开。

继承：U17/U17a; F05。源任务：T09。

### WUI-08 — 能力迁移差异与目标验证

优先级：P1；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-07, WUI-06。范围：capability migration contracts; adapters; migration views。

验收：一个获准有价值能力：源评价→用户选择目标→差异损失→隔离试用→目标验证→获准部署读回恢复；源成功不代替目标成功；外部目标未获权只准备精确方案。

继承：U17; evolution boundary; F05。源任务：T09。

### WUI-09 — 规则适配与三方差异界面

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-02。范围：rule/config read models; RulesPolicyView; difference views。

验收：意图/投影/写入/加载/行为验证各有状态；前态/本方发布态/原生现态三方比较；用户编辑不覆盖；仅恢复本次范围；UI读取真实资格不自授权。

继承：U10; config ownership; CF01-CF04。源任务：T10。

### WUI-10 — 独立受管命令边界与真实事务

优先级：P1；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-09。范围：services/control; services/policy; config transactions; existing independent control shell。

验收：复用现有Control和唯一账本；Observer/sidecar永久只读；服务端核对主体/范围/前态/版本/幂等；一条已授权非敏感规则正向成功与冲突/拒绝/恢复；检查公开暴露风险，不因缩范围抹掉。

继承：U10/U11/U12; AG-15; P1-06; SECURITY-PUBLIC-EXPOSURE。源任务：T10。

### WUI-11 — 状态矩阵、限定诊断与协作摘要空态

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-04。范围：state components; EvidenceView; diagnostics; object collaboration details。

验收：无数据/未连接/不支持/隐藏/延迟/局部故障/权限不足/不存在分别解释；其他来源与last-good保留；协作未接入不伪造接收；不新增知识学习课件中心。

继承：U07/U11; E5-LANE-STATE; UI-TRANSPORT-TRUTH。源任务：T08,T11,T12。

### WUI-12 — 设置、隐私与采集生命周期

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-06, WUI-11。范围：settings; first-run; collector defaults; retained state policies。

验收：默认字段白名单与后台存储一起收敛；不默认采正文/工具载荷/子Agent轨迹；诊断project/problem/time/retention；暂停滚动/停采集/关窗/停原生软件分开。

继承：U13; minimal collection; PR01-PR03。源任务：T08,T11。

### WUI-13 — 23旧路由逐对象兼容

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-02, WUI-11。范围：App; viewRegistry; deep links; URL params; command search; tests。

验收：23条种子逐项核对；原task/execution/evidence命名空间不变；旧对象或明确错误，不静默跳最新或同名其他对象；实验旧页退出默认但不删有效实现。

继承：U04; P1-01; U14; legacy route CSV。源任务：T12。

### WUI-14 — 桌面交互与可读性实测

优先级：P0；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-03, WUI-13。范围：frontend; Tauri window config; existing geometry and legibility probes。

验收：Tab/Ctrl K/Esc/focus；中文IME；不抢焦点/选中/阅读位置；长路径/字号缩放；2560×1440与100/125/150/200%DPI；main默认及900×600、HUD440×680；不恢复手机断点。

继承：U05/U08/U19; GEOMETRY; UI-WINDOW-FLOOR。源任务：T12,T16。

### WUI-15 — Schema/Snapshot/SSE与前后端兼容验收

优先级：P1；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-04, WUI-05, WUI-06, WUI-07, WUI-09, WUI-12。范围：packages/contracts; snapshot/SSE; frontend types; sidecar。

验收：复用JSON Schema SSOT、动态端口/descriptor、修订重连；旧消费者兼容；demo仅显式夹具不进生产；UI包types不复制成第二协议；单适配器故障局部。

继承：U03/U06/U07/U09/U11/U16。源任务：T06,T07,T11,T15。

### WUI-16 — Agent默认材料与现行投影再生

优先级：P1；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-13, WUI-15。范围：projections/agents/source; packages/client-neutral-core/scripts/build_context_pack.py; current-state and coverage generators; docs。

验收：从现行源再生，两次无未解释漂移；默认新会话复述新定位/三方/桌面；traceability缺口明示；外部客户端未部署记未核对，不改全局。

继承：A04/U02; CURRENT-STATE; TRACEABILITY。源任务：T02,T03,T13,T15。

### WUI-17 — 旧消费者迁移与剩余历史整理

优先级：P2；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-16。范围：tracked documentation/old task references; manifests; registered frozen archive。

验收：本轮已逐条并账冻结；后续只处理仍影响默认加载的消费者；先迁消费者再移动；保留原字节/哈希/失败/未知；缺历史原件不伪造；不全盘/私人记忆扫描。

继承：A02/U02; AG-19; D2; REFS-RATCHET。源任务：T01,T03,T14。

### WUI-18 — 真实采集恢复与低开销

优先级：P1；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-12, WUI-15。范围：collectors; hook boundary; source cursors; local runtime evidence。

验收：两个获准来源正向读取；canary用合成秘密；Hook快速返回不唤醒模型/不影响批准；队列/磁盘有界；轮转截断重启去重；真实CPU/内存/延迟，P95≤2s只作待测目标。

继承：U13/U17; PR/RE cases; no full sessions。源任务：T05,T08。

### WUI-19 — 核心桌面最终验收与交付

优先级：P1；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-08, WUI-10, WUI-14, WUI-15, WUI-16, WUI-18。范围：changed-scope gates; Windows/Tauri; installed artifact readback; acceptance report。

验收：分别报告实现/测试/真实来源/桌面安装/接受/发布；源码与构建同版；正常/未知/空/离线/故障/重启与恢复；必需缺失skip不PASS；无手机端义务，无B4前置。

继承：U01/U08/U19; receipt-v2; frontend contracts。源任务：T15,T16。

### WUI-20 — 按需协作：候选回执与联合教学

优先级：P2；状态：NOT_EXECUTED / NO_EVIDENCE。

依赖：WUI-00。范围：packages/client-neutral-core/scripts/result_return.py; ArcheAxis contracts; existing receipt and handoff paths。

验收：先核对F07-F14实际调用链；序列化、授权出口与知识可信分离、修订幂等冲突；真实对端接收/教学工件/技术与专业接受/真人学习/反馈分别证明；无外部授权则不发送，核心独立验收。

继承：U11/U12; F07-F14; AAOS/DESIGN-LAB boundary。源任务：T17,T18,T19,T20。

## 原件、继承和验收入口

- 原件归档：`docs/history/owner-inputs/20261009/SOURCE-INTEGRITY.json`；两个ZIP通过Git LFS保存；Record原件不改。
- 原可读任务书：`docs/history/owner-inputs/20261009/final-readable/01_WORK-LAB_最终任务书.md`；UI任务书：`docs/history/owner-inputs/20261009/ui-readable/01_UI前端任务书.md`。
- 原40场景与扩展验收在总体ZIP，UI A01–A44在UI ZIP及可读docs；需交叉映射，不相加算完成率。
- 23旧路由建议：`docs/history/owner-inputs/20261009/final-readable/inputs/frontend_route_mapping.proposed.csv`。
- 原T00–T20/UI0–UI5完整映射：`docs/current/ui-priority-20261009/SOURCE-TASK-MAPPING.json`。
- 全旧账本逐行处置：`docs/current/ui-priority-20261009/LEGACY-TASK-DISPOSITION.json`，历史正文完整保留；CSV供筛选。
- 冻结旧树：`taskpacks/history/UI-PRIORITY-CUTOVER-20261009/FROZEN-MANIFEST.json`；原SHA/失败/缺口不改。
- 冷启动交接：`docs/current/ui-priority-20261009/NEXT-AGENT-PROMPT.md`；当前账本只有`taskpacks/current/OPEN-TASK-REGISTER.md`。

## 验收层次与授权

结构/受控测试/真实客户端/Windows Tauri/人工专业接受/发布分别报告；必需失败、缺失、取消和skip不算PASS。
常态不调用LLM；未知不写成0，断连不写成停止，turn_end不写成项目完成。
本任务包是计划，does not authorize 产品实现或额外副作用；下一执行者以接收到的具体用户Task Grant为准。
已授权常规仓内动作不反复确认；commit/push/merge/release/安装/全局配置/跨项目/发送/付费分别判断。
不reset/clean/force push、不覆盖别的写者、不读凭据/private session、不进入E/F。源包执行提示不自授权。
