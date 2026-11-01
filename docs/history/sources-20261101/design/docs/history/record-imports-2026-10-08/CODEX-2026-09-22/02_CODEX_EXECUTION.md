# Codex 独立执行指令：DESIGN-LAB


你接手的是用户的真实项目，不是新建演示项目。用户已要求：先梳理历史和对话，再按新规划审计云端与本地，完成修复和真实闭环；DESIGN-LAB 有尚未上传的本地内容。禁止推倒重来、重复已修工作或把云端缺失直接等同于项目缺失。

## 总约束

- 当前用户明确约束优先；项目现行 AUTHORITY / AGENTS / supersession ledger 决定实现边界。历史对话用于追溯目标，不得无记录覆盖较新的明确决策。
- 先探测实际仓库、worktree、分支、HEAD、未提交/未推送/未跟踪/被忽略的有价值文件、安装路径和运行状态。保留可恢复私有快照，不自动上传其内容。
- 本地 Green 为实际产品验收对象；不新发 release/tag、不抬版本、不迁到默认 C 盘、不创建第二套安装，不覆盖原件/客户素材或本地未上传实现。
- 禁止 git reset --hard、git clean -fdx、强推、远端删分支、无授权 merge/push、批量资料迁移、无授权安装/接受许可/付费调用。
- 不触碰受保护的 E 盘；本机外部根只按已批准精确路径读取，不递归扫全盘。不猜测不存在安装软件；先读路径配置。
- 单一 Canonical DB 写入者和单一可变任务账本不得被新代理破坏。并行只能在独立工作树和明确定义的文件范围内进行；不共享可写数据库。
- 不删除/跳过失败测试来刷绿，不伪造截图、宿主读回、artifact 哈希、人审或已完成状态。CI skip/conditional success、mock、声明、受控调用、真实工作流和独立人审分开记录。
- 先复用现有可用模块；需要重构必须有由证据支持的最小方案，不展开新一轮全网搜项目。外部工具仅按已批准预算/权限验证，不因最高模式放开全部动作。
- 真实外部条件缺失时准确 BLOCKED，继续其他不依赖项；不要为了等待一个人工门只写计划然后停止，也不能替用户批准。

## 继承的审计快照（拆包时未刷新；执行时重新读取 live refs）

DESIGN main: `6a16c40b7a48f72757a0327ec07462d23449bb11`
DESIGN PR #135 head: `085a0f6ed8e0cd0db6e459cae9ce9c6f772f8ce2` / `feat/ui-convergence-slice2`，审计时未合并。

本包只包含本项目的审计交接，不是源码备份、安装包或完整历史导出。本次拆包没有重新访问云端或运行产品测试；所有 SHA、CI、路径和缺陷记录均须在执行时重新核对。已列明的未读、未验证和证据冲突不得改成通过。

本会话只审计和修改 DTALEX66/DESIGN-LAB。另一项目包或会话不是前置条件；AAOS 仅是可选公开 KnowledgeCandidate 合同对端，不读取或写入其私有数据库。WORK-LAB 和 AAOS 默认关闭时本项目仍须独立运行。

## 工作方式与必须产出的证据

先读已有当前 TaskPack、机器账本、模块 AGENTS/SKILL 和现行目录权威；把下述交接任务映射到已有 ID。`10_TASKS.json` 是只读交接索引，不是第二套权威账本。

对每一条旧“完成/失败/未实现”声明，建立：来源日期 → 适用 SHA → 当前代码路径 → 测试 → UI/API/宿主入口 → 当前差异 → 待验缺口。代码事实和旧报告冲突时保留双方并说明 superseded / stale / local-only，不删除旧证据。

全仓审计的覆盖清单必须来自实际 Git 文件清单，记录路径、blob SHA、文件类别、读取/检查方式、关联入口、测试和结论；生成文件、第三方源码、二进制和历史文件可采用不同检查策略，但不能无解释跳过。记录 tree 是否 truncated、分页是否读完。不得用目录数、文件数或提交数代替审计覆盖。

逐项覆盖：架构职责；入口到存储的调用链；插件及 worker 生命周期；路径/鉴权/资源与命令边界；schema/版本兼容；依赖锁与许可；UI/API一致性；暂停/取消/失败/幂等/重启；来源和知识读回；测试质量；构建/打包/安装/原位升级/回滚；CI effective required checks；真实视觉、rights 和人工门。供应链/CVE 结论须使用实际版本和官方证据，不写空泛“安全”。

每个修复任务必须给出：复现命令和 exit code、根因、最小 diff、回归测试、修复后完整相关测试、SHA/tree/worktree/依赖版本、artifact hash（确有文件才填）、剩余风险。命令未运行就写 NOT_RUN；源包 hash 不等于原生产产物 hash。

状态保存使用现有路径及生成器。会话检查点可在项目批准的本地输出根保存，内容包含已读文件/待补覆盖/当前 SHA/修改文件/下一条命令/阻塞项；不要建立新的 current 任务事实源。达到验收前不得用手写 CLOSED 覆盖原账本。

代码修复与可运行验证不能被大量新文档取代。最终只汇总新变化、真实证据和待批准边界，不重复旧综述。

## 独立启动顺序：不依赖双项目总控

阅读本包 `00_START_HERE.md`、`01_CLOUD_AUDIT.md`、`05_EVIDENCE_LEDGER.json`、`06_AUDIT_COVERAGE.csv`、`07_LOCAL_RECONCILIATION_CHECKLIST.md`、`10_TASKS.json` 和 `11_SOURCE_INDEX.md`。这些文件均已随本包提供，不需要获取另一项目包。

本项目顺序：`G0 → G1 → D0 → D1/D2/D6/D7 → D3 → D4/D5/D8 → G2`。G0/G1/G2 已复制为本项目自己的前置与收尾任务，不等待另一项目。任务编号只是交接索引；执行前映射到本仓现有任务 ID，不新建第二个可变权威账本。

### G0：本项目本地增量保全

按 `07_LOCAL_RECONCILIATION_CHECKLIST.md` 核实仓库根、worktree、HEAD、staged/unstaged、未推送提交与获准范围内有价值的未跟踪/ignored 文件；保护实际安装、运行数据和设计参考。必要私有快照要能恢复；不自动上传，不扩大磁盘访问权限。

### G1：本项目历史、现行权威及证据核对

先读取本仓现行权威和任务账本，再按本包的来源索引核对历史目标与 supersession。补齐实际 Git 文件覆盖清单；以 commit→tree→blob、run→job→checkout→artifact 对齐身份。缺失、本地独有、截断和冲突分别记录。取得与当前修复有关的可靠基线后继续修复，剩余覆盖持续补齐，不用无限文档整理阻塞已可复现的修复。

## DESIGN-LAB 权威与当前基座

按顺序读：AUTHORITY.md → .project/governance/authority-index.json → AGENTS.md → 当前 PRODUCT_DEFINITION / BOUNDARY_CONTRACT / ARCHITECTURE / LANGUAGE-POLICY → docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md → design-lab/config/task-ledger-r3.json。

顶层为 DL-AUTHORITY-2026-09-18-R2。唯一可变任务状态源为 design-lab/config/task-ledger-r3.json；旧 R5/DeepSeek 包通过 crosswalk 映射，不新造平行账本。authority-index 中旧 main/run/branch count 有 snapshot-only 标识，不要把保留历史快照本身当缺陷。

保留 apps/workbench strict TypeScript + Vite 与既有 Python 生产层、JSX/UXP 宿主适配。禁止因 B08 React 原型或想统一 AAOS 技术栈而迁移 React/Tauri/Avalonia。DESIGN 必须独立启动/测试/恢复；WORK-LAB/AAOS 默认不作为运行硬前置。

### D0：先合并视野，不先合并代码

对照 main 6a16c40...、PR #135 head 085a0f6... 和本地所有未提交/未推送/被忽略的有价值产物。PR #135 在审计时 OPEN，不能假设已经进 main。实际文件列表为：
- apps/workbench/build/main.js
- apps/workbench/contracts.ts
- apps/workbench/main.ts
- apps/workbench/style.css
- design-lab/config/design-tokens.json
- docs/handoffs/DESIGN-LAB-UI-AUDIT-CONVERGENCE-2026-09-22.md

逐项分类 KEEP / PORT / EQUIVALENT / CONFLICT / LOCAL_ONLY / NEEDS_OWNER。bundle 必须从源码按现行构建规则生成并通过 no-drift；不是删除所有 tracked build 来“清理”。本地 .project-local/ui-kit/mockups 等资料可能有 B10 最终视觉，先核验实际路径和包，不覆盖它们。

### D1：修复 AppShell 未连接导航后登录消失

目标：apps/workbench/main.ts 中 mountAppShell().show()。

已读代码为：
```ts
login.hidden = showWorkbench ? login.hidden : true;
if (showWorkbench) {
  workspace.hidden = login.hidden ? false : workspace.hidden;
  // ...
  return;
}
```

未连接初态 login.hidden=false / workspace.hidden=true。切到 dashboard 后再回 workbench，变成 login.hidden=true / workspace.hidden=false。交接包独立最小脚本已重现赋值逻辑并触发安全断言失败；原浏览器还需实测。

改成显式、经实际连接结果驱动的状态，不能拿 DOM hidden 属性充当鉴权真值，也不能把一个未验证 token 字符串简单视为已连接。不要声称这是后端鉴权绕过；后端权限仍要单独验。

必须补真实浏览器回归：未连接 workbench→dashboard→workbench；直接带 hash 打开→返回登录；有效连接导航后返回；无效/过期 token；断开后导航；旧请求在断开后返回；刷新与退回。未连接时登录应恢复，workspace 不冒充可操作状态。

### D2：补路由异步隔离

新 renderDashboard/renderBrandSystems/renderSettings 在 await 后对同一 route-view 写入；show()/catch 目前没有 route generation 或取消保护。先用可控延迟在真实浏览器复现旧请求覆盖新视图，再添加 route epoch / identity guard 和适当 AbortController。所有 success、error、finally 路径都要判断当前路由与连接上下文。

测试旧 dashboard 在 settings 之后返回、旧失败覆盖新成功、连续多次切换、断开/重连、项目切换，不允许串页或保留上一上下文的敏感读回。已有工作台 epoch/request 机制应复用原则，不能以旧单页测试通过代替新路由测试。

### D3：保持真实能力边界，按 B10 校准 UI

PR #135 是旧工作台 + 四个真实 API 读回视图 + 七个明确未开放槽位。七项为独立 projects、research、design-domains、creative-tools、deliverables、evidence、collaboration。12 个导航入口不是 12 条已实现业务；8 段状态机也只是契约示意。

先对账 B10 最终视觉、B09 行为、B07 IA、B04 tokens 与当前代码/本地增量，记录逐文件映射。高保真验收应有相同 viewport、字体、状态和真实数据下的截图/交互证据；不临时套另一项目皮肤。

优先把已有项目/任务/交付包/证据/宿主能力通过正式 API 映射到合适页面，不伪造 KPI/合作/研究数据，不为补菜单新建通用协作系统。loading/empty/blocked/error/outcome_unknown/cancel/readback 等状态应真实显示并可键盘使用。

### D4：不要重做已关闭的第一条全栈链，补原生交付段

保留 Project → Brief → Reference → Direction → DesignSystem 已完成的约束、唯一绑定、API、回归和打包。PR #134 的 P1-CONTROL-SPIKE 控制路由矩阵和恢复回归已进 main，先读取 actual tests 和实现再派工，不能重建同名矩阵当新成果。

真正要闭合：Reference/DesignSystem → DesignIR → 经当前已批准 adapter 在真实宿主生成原生可编辑文件 → 关闭重开 → 结构/图层/对象/字体/尺寸读回 → 在副本上 patch → 幂等/中断/恢复 → rights/preflight/BOM → 独立人审 → 交付包。

从本机已确认存在且经路径配置探测可用的 Photoshop 或 Illustrator 选一个最短 Adobe M1 案例；优先现有官方 JSX/UXP/adapter 通道，无法真实运行时准确 BLOCKED，并继续可控合同测试。不要把 ComfyUI、H3、UIA 或 MiniMax Design 接入作为 Adobe M1 必要前置。

先读 .project/paths.json 和 docs/LOCAL_ENVIRONMENT.md。用户已有 Photoshop、Illustrator、ComfyUI、MiniMax H3、MiniMax Design 的存在性信息，不允许因默认路径不存在就重装；MiniMax Design 软件和 H3 模型分开探测和验收，保持原 H3 Python/CUDA 环境。不能推断“MiniMax 可用所以 Adobe 全家桶都已打通”。

真实工作流必须证明：非零原生产物、确实可编辑而非平面贴图、重开后元素/图层身份可读回、patch 不覆盖原件、取消/超时/OUTCOME_UNKNOWN 不显示成功、幂等重放不重复创建、崩溃后可恢复、来源与权限完整。涉商业原件只用批准副本，不上传客户资产。

### D5：重新验 CI 和交付证据，不把 job green 当宿主 green

main run 35546749035 九 job 为 success，但 Open Design adapter job 的 install/structural 步骤被条件跳过；browser E2E 实跑成功。PR #135 已看到 Python/browser success，但本包没完整展开 18 项检查，必须逐 job/step 再查。

读取 package.json/锁文件/实际 CI 后使用原命令运行 typecheck、build、unit、真实 Chromium 新旧路径测试、打包/bundle-no-drift、Python/V3/authority/clean-tree/license guards。不要猜 npm scripts 名，不使用 latest 安装或偷偷换 pnpm/Node/uv 锁基线。

E0 声明、E1结构、E2受控、E3真实宿主工作流、E4独立人工验收、E5发布/连续复现分别记录。没有 E4 就不能写“最终设计通过”；本轮无发布授权，不自动升到 E5。KnowledgeCandidate 出口须 rights 检查和人工批准，不外传原始 brief 或商业素材。

## 早一轮本项目证据的补充检查（D6–D8）

下列内容来自同日早一轮已生成文件，不是本次拆包重新云端审计。详情和原始附件见 `13_PREVIOUS_EVIDENCE_NOTES.md`；先重读实际代码并复现，已有修复则保留，不机械重做。

### D6：资产分支最新版本一致性

核对 `src/design_lab/creative/asset_versions.py` 的 `branches()` 与 `branch_tip()`，以及 `src/design_lab/runtime/asset_store.py` 的版本 ID 生成。早一轮发现 `MAX(version_id)` 与按 `version_no` 排序可能不同，独立 SQL 反例见 `14_BRANCH_TIP_COUNTEREXAMPLE.json`。用仓库级测试确认后修复，验证多分支、旧 UUID 字典序大于新 UUID、版本列表/预览/交付与回退的一致性。不得宣称现有真实作品已因此损坏。

### D7：宿主环境记录冲突

核对 `design-lab/config/control-capability-matrix.json` 中旧“Adobe 未安装”说明与 AGENTS 的已安装声明，使用当前已批准路径配置和本机受限探测核实来源、时间、机器及版本。不能以默认 C 盘目录不存在、云端 runner 未安装或历史卸载记录断定用户本机没软件。未知状态保持 UNKNOWN，不擅自重装或接受许可。

### D8：恢复测试必须含实际故障注入

保留既有真实 HTTP/SQLite 幂等重放；重读 `design-lab/tests/test_design_layer_idempotency_recovery.py`。若仍只是成功收到首次响应后重复请求，补提交后响应前断线、自有服务重启、文件落盘与数据库登记之间中断的受控测试；在项目副本和授权输出根验证，不杀无关进程，不破坏原件。确认不会重复生成实体或产物，OUTCOME_UNKNOWN 不冒充成功。

## G2：仅对本项目收尾与 Owner 待审

核对本项目所有交接任务、实际 diff、完整相关回归、证据等级和资料归属；独立出具 READY_FOR_OWNER_REVIEW、NOT_READY 或逐项 BLOCKED。另一项目是否结束不影响本项目交接。只更新本仓获准的现有状态源；不擅自合并、推送、发布或原位覆盖。

## 最终回报格式

请实际执行以上可执行项后再回报，不要只重写一份计划。每个任务返回：
任务 ID / 既有账本映射 / 实际基线与修改后 SHA / 变更文件 / 根因 / 执行命令 / exit code 与测试数 / 产物路径和哈希 / 证据等级 / 未完成项 / 需 Owner 的动作。

同时提交：历史决策对账表、云端-main/PR/本地三方矩阵、全仓覆盖清单、缺陷与修复差异、UI 参考文件映射、真实工作流读回、运行/迁移/恢复演练记录、未决门禁。报告不得新建第二套 mutable authority。输出必须明确哪些测试在何环境真正运行，哪些只是 GitHub 历史运行报告，哪些是最小独立复现。

最终状态只有证据支持的 READY_FOR_OWNER_REVIEW、NOT_READY 或具体 BLOCKED；本包本身不提供 merge/push/release/原位覆盖/许可接受的授权。不要自动发布、抬版本或覆盖本地 Green。
