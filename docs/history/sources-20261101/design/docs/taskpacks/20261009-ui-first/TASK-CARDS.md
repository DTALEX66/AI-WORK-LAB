# 后续任务卡（冻结定义的阅读投影）

状态请只在design-lab/config/task-ledger-r3.json → currentExecution编辑；本页不维护状态。

## DL-FINAL-T01 — 现状复核与作品证据保全

类型：PARENT_TASK；批次：B0；优先级：FOLLOWUP。
实施依赖：无；先完成接收会话基线只读检查.
验收依赖：本任务独立证据.
旧任务：DL-R5-001, DL-R5-002, DL-R5-007.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 实际HEAD/远端/分支/增量及其他Agent占用
- 用户工程与.project-local/projects备份/恢复入口

验收：
- 历史基线仅作参考；不覆盖未提交增量
- 清单与备份可读取，不清理真实作品

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：docs, design-lab/config/task-ledger-r3.json；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T02 — 最新定义、边界、权威与既有任务映射

类型：PARENT_TASK；批次：B0；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T01.
验收依赖：DL-FINAL-T01.
旧任务：DL-R5-001.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 定位、全品类、自有执行、三项目协作与教学增量
- 22项交接任务映射既有唯一账本；旧条款替代

验收：
- 目标/实现/任务/授权分开
- 无第二权威/账本；已完成证据不全重置

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：AUTHORITY.md, AGENTS.md, docs/current, docs/architecture, .project/governance；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T03 — 所有Agent发现入口与历史隔离

类型：PARENT_TASK；批次：B0；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T01, DL-FINAL-T02.
验收依赖：DL-FINAL-T01, DL-FINAL-T02.
旧任务：DL-R5-002, DL-R5-023.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 根/子AGENTS、Skill、规则、模板和旧包发现范围
- 历史原字节保全、外层索引与替代关系

验收：
- 旧AGENTS/SKILL不从资料目录自动加载
- 第三方源材料不获执行权；历史可追溯

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：docs, design-lab/config/task-document-states.json；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T04 — 机器配置、生成器、校验和CI同步

类型：PARENT_TASK；批次：B0；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T02.
验收依赖：DL-FINAL-T02.
旧任务：DL-R5-003, DL-R5-023.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- Authority ID/hash替代链和索引
- 能力/适配/功能配置、上游生成来源、报告投影

验收：
- 重新生成不写回旧定义
- 保留真实性与安全守卫，不删门禁求绿

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：scripts, design-lab/config, .github/workflows；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T05 — 能力库安装资源与干净wheel核心链

类型：PARENT_TASK；批次：B1；优先级：UI_SUPPORT。
实施依赖：DL-FINAL-T01.
验收依赖：DL-FINAL-T01.
旧任务：DL-R5-003, DL-R5-009.

当前观察：本地pyproject已打包4份能力资源，capability_library已有packaged-first；剩余为离repoCWD禁源码兜底实测。
**2026-10-10 实测更正**：这条"剩余"已经做完了。`test_capability_library_clean_install.py`
用 uv 现建 wheel 到临时目录，在 `cwd=mkdtemp()` 且剥掉 `PYTHONPATH` 的子进程里跑投影，
断言 `repo_root != REPO`（源码兜底一旦被读到就红）与缺资源 fail-closed；4 条用例全跑、
无 skip。缺的只是记录，不是实现。仍留 PARTIAL：验收里"声明核心旅程在干净安装可用"
只覆盖到投影与路由两层，真实宿主旅程不在本会话授权内。

交付：
- 最小只读资源或明确Provider装载
- 安装测试脱离repoCWD并禁用源码兜底

验收：
- /api/capabilities及声明核心旅程在干净安装可用
- 不打包整候选池、模型和用户素材

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：pyproject.toml, src/design_lab/analysis/capability_library.py, design-lab/tests；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T06 — 多维分类与资格证据真实投影

类型：PARENT_TASK；批次：B1；优先级：UI_SUPPORT。
实施依赖：DL-FINAL-T02, DL-FINAL-T05.
验收依赖：DL-FINAL-T02, DL-FINAL-T05.
旧任务：DL-R5-006.

当前观察：七轴函数未透传轴实际值；qualified/qualificationEvidence仍固定为空。
**2026-10-10 实测更正**：这句过期了。`capability_library.py:145/174` 就是本任务要的按轴取值
透传，`_qualification()`（:78）读回已登记判定而不是硬编码空；
`test_capability_library.py` 已在验：种子行 `axes.domains==['brand']` 与 `tier=='T2'` 存活、
有值的轴不再出现在 `unclassifiedAxes`、已登记时 `qualificationEvidence` 原样读回、
未登记时保持 null 并带原因（14 条用例、无 skip）。
因此线上读回"七个轴全为空、`counts.qualified=0`"是**出厂数据为空**，不是投影丢值。
仍留 PARTIAL：非空轴值只在种子 fixture 上证过，不能当作真实数据已投影。

交付：
- 原七轴实际值API/UI透传
- 已有资格记录/证据读回与未知状态

验收：
- 非空轴值不丢失；qualified不永久硬编码null
- 规范/经验/偏好/软件限制/权利条件分开

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：src/design_lab/analysis/capability_library.py, apps/workbench/contracts.ts, apps/workbench/shell.ts；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T07 — 少量来源知识提炼和中立能力适配

类型：PARENT_TASK；批次：B1；优先级：UI_SUPPORT。
实施依赖：DL-FINAL-T06.
验收依赖：DL-FINAL-T06.
旧任务：DL-R5-006.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 用途、来源版本、许可、方法/反例、落点、执行资格
- 复用DomainPack/Method/Adapter/Quality

验收：
- 热度仅筛选；来源登记不算接入
- 选定来源有任务测试及撤回/恢复，不要求980项全吸收

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：packages/capabilities, research, vendor；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T08 — 迁移前端核心入口和辅助信息

类型：PARENT_TASK；批次：B1；优先级：UI_SUPPORT。
实施依赖：无；先完成接收会话基线只读检查.
验收依赖：DL-FINAL-T02, DL-FINAL-T06, DL-UI-U02, DL-UI-U03.
旧任务：DL-R5-010.

当前观察：桌面UI先行；U01完成精确对象/API映射，U02给出可评审桌面壳与组件；其余真实链分批接入，未支持动作禁用并解释。

交付：
- 能力资产/分析与制作/成果与反馈旅程
- 视觉Token一致与现有数据兼容

验收：
- 不固定菜单数量；不为旧DOM回退产品
- 新页可生产而不依赖旧工作台；React非前置

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T09 — 多模态需求、原创分析及目标生成包

类型：PARENT_TASK；批次：B1；优先级：UI_SUPPORT。
实施依赖：DL-FINAL-T07, DL-FINAL-T08.
验收依赖：DL-FINAL-T07, DL-FINAL-T08, DL-FINAL-T16, DL-UI-U04, DL-UI-U05.
旧任务：DL-R5-006, DL-R5-010, DL-R5-013.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。 无AAOS时先跑独立输入链；知识增强验收仍依赖T16，不假装实联。

交付：
- 文字/截图/文件/多图/音视频输入及目标合同
- 结构/风格/局部范围/真实参数/检查方式

验收：
- 至少一条实际输入→分析→目标包→纠正路径
- 精准文字强约束有真实路线；提示词不冒充原生工程

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/design_layer.py, src/design_lab/analysis；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T10 — 设计意图与已有原生任务接续

类型：PARENT_TASK；批次：B2；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T09.
验收依赖：DL-FINAL-T09, DL-UI-U05.
旧任务：DL-R5-005, DL-R5-009, DL-R5-010, DL-R5-013.

当前观察：native_plan/submit接收RIR；普通用户意图接续需全链验证。

交付：
- 现有方向/DesignSystem/知识/brief引用到计划和产物
- 可校正结构计划、输出合同和版本

验收：
- 普通用户无需手写RIR/JSON接断点
- 简短任务不强制完整项目流程

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：src/design_lab/native_plan.py, src/design_lab/native_submissions.py, apps/workbench/workbench.ts；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T11 — 设计执行路线、租约、幂等与恢复

类型：PARENT_TASK；批次：B2；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T01, DL-FINAL-T02.
验收依赖：DL-FINAL-T01, DL-FINAL-T02, DL-UI-U06.
旧任务：DL-R5-002, DL-R5-004, DL-R5-006, DL-R5-007, DL-R5-010, DL-R5-024.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 扩展现有NativeWorkers及Adapter Observe/Plan/Execute/Verify/Recover
- 桌面/宿主/文档跨进程占用、预算与取消

验收：
- API/GUI不争抢同文档；超时先对账
- 同键异输入冲突、不重复对象/导出/付费；外部能力真实声明

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：src/design_lab/native_workers.py, src/design_lab/runtime, integrations；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T12 — Human Jury真实API和用户入口

类型：PARENT_TASK；批次：B2；优先级：UI_SUPPORT。
实施依赖：DL-FINAL-T08.
验收依赖：DL-FINAL-T08, DL-UI-U08.
旧任务：DL-R5-014.

当前观察：本地已有GET jury与POST verdict/proposal、store和UI表单；补词汇映射、身份/时间/回执、版本失效与真人验收。

交付：
- 评审对象/产物版本/差分/意见/Accept Reject Request changes及回执
- 与产物更新后的资格状态关联

验收：
- 由真人作真实决定，Agent不代签
- 产物更新不复用旧版本接受

证据：implementation, unit, human_review；真实宿主/真人/三方/学习分别验收。
建议write set：src/design_lab/jury_review.py, src/design_lab/assurance/jury_store.py, apps/workbench/shell.ts；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：真人对实际版本审美/权利/交付的决定.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T13 — 双宿主真实原生往返与异常恢复

类型：PARENT_TASK；批次：B2；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T10, DL-FINAL-T11.
验收依赖：DL-FINAL-T10, DL-FINAL-T11, DL-UI-U06, DL-UI-U07.
旧任务：DL-R5-004, DL-R5-007, DL-R5-011, DL-R5-012, DL-R5-024.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 当前已安装PS/AI实际版本及许可样本
- 两次局部patch、保存关闭重开、对账回滚

验收：
- 文字/路径/图层实际可编辑、不重建无关对象
- 单宿主阶段不关闭双宿主/M1整体要求

证据：implementation, unit, host_live；真实宿主/真人/三方/学习分别验收。
建议write set：integrations/hosts/adobe, src/design_lab/native_tasks.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：用户已安装且获准的软件与测试工程.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T14 — 正式交付、权利、预检与隔离重开

类型：PARENT_TASK；批次：B2；优先级：UI_SUPPORT。
实施依赖：DL-FINAL-T12, DL-FINAL-T13.
验收依赖：DL-FINAL-T12, DL-FINAL-T13, DL-UI-U08.
旧任务：DL-R5-005, DL-R5-010, DL-R5-011, DL-R5-012, DL-R5-014.

当前观察：本地已有rights、production_preflight、delivery_bom与交付模块；复用，核验真实接入和隔离重开。

交付：
- 测试/草稿与正式交付scope分离
- rights Jury preflight BOM依赖字体规格版本hash

验收：
- 实际产物与真人结论绑定；缺证据不签正式合格
- 交付离开开发目录解包重开可复用

证据：implementation, unit, host_live, human_review；真实宿主/真人/三方/学习分别验收。
建议write set：src/design_lab/native_delivery.py, src/design_lab/assurance, apps/workbench/shell.ts；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：真人对实际版本审美/权利/交付的决定.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T15 — 黄金工作流、固定安装版与资产恢复

类型：PARENT_TASK；批次：B3；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T05, DL-FINAL-T14.
验收依赖：DL-FINAL-T05, DL-FINAL-T14, DL-UI-U06, DL-UI-U07, DL-UI-U08.
旧任务：DL-R5-002, DL-R5-004, DL-R5-005, DL-R5-011, DL-R5-012, DL-R5-015.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 保留GOLDEN-001/002和当前E5语义
- Windows真实安装/重启及资产备份恢复摘要

验收：
- 固定源码/安装包/产物/证据一致
- 恢复后hash与引用核对；公开Release无许可不发

证据：implementation, unit, host_live, human_review；真实宿主/真人/三方/学习分别验收。
建议write set：scripts, design-lab/tests, .project-local/task-artifacts；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T16 — AAOS版本知识、候选回执及离线边界

类型：PARENT_TASK；批次：B1-contract；优先级：UI_SUPPORT。
实施依赖：DL-FINAL-T02, DL-FINAL-T05.
验收依赖：DL-FINAL-T02, DL-FINAL-T05, DL-UI-U09.
旧任务：新增需求.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 复用知识读取、候选/纠正、回执/变更合同
- 授权有界快照；迁移ID/hash/权限/恢复方案

验收：
- 在途版本固定；撤销/新鲜度如实处理
- 候选可先保存；不跨DB/不双主/不默认全库迁移；替身不冒实联

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：src/design_lab/interop, design-lab/schemas, apps/workbench；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T17 — 教学需求、表达制作与可修订内容交付

类型：PARENT_TASK；批次：B4；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T09, DL-FINAL-T16.
验收依赖：DL-FINAL-T09, DL-FINAL-T16, DL-UI-U10.
旧任务：新增需求.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 同制作体系接人群/前置/目标/误解/知识引用
- 按需图解动画互动/练习、文本字幕视觉描述、源工程与依赖

验收：
- 目标先于形式；动画不冒仿真；专业简化可追踪
- AAOS管学习，DL管源与配方；H5P等仅实测后称兼容

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：src/design_lab/design_layer.py, apps/workbench；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T18 — 知识、教学和运行反馈闭环

类型：PARENT_TASK；批次：B4；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T16, DL-FINAL-T17.
验收依赖：DL-FINAL-T16, DL-FINAL-T17, DL-UI-U09, DL-UI-U10.
旧任务：新增需求.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 版本/场景/题目/观察/许可/责任/回执
- 三类问题路由和同源派生证据关系

验收：
- 播放不等于掌握；同源媒体不当独立证据
- 客户与元数据隔离；教学代码不继承执行权限

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：src/design_lab/interop, apps/workbench；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T19 — 三方真实实践到学习的一轮修订

类型：PARENT_TASK；批次：B4；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T17, DL-FINAL-T18.
验收依赖：DL-FINAL-T17, DL-FINAL-T18, DL-UI-U10.
旧任务：新增需求.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- WL真实获准实践→AAOS知识目标→DL内容
- AAOS实际加载/练习/应用反馈→正确方修订

验收：
- 至少一轮可追踪修订与版本读回
- 三报告不替闭环；无真实材料标假设，无实联标PARTIAL

证据：implementation, unit, integration, real_learning；真实宿主/真人/三方/学习分别验收。
建议write set：docs, .project-local/task-artifacts；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：AAOS / WORK-LAB各自实际服务与材料; 真实学习与版本修订.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T20 — 执行路线公平对照及两版24用例映射

类型：PARENT_TASK；批次：B5；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T09, DL-FINAL-T11.
验收依赖：DL-FINAL-T09, DL-FINAL-T11.
旧任务：DL-R5-013, DL-R5-020.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 六类小样后扩24及早版独有要求
- A外部 B同Agent+DL C原生 D混合

验收：
- 复合来源身份区分同名ID
- 模型/工具/输入/预算/权限公平；只按操作族结论

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：design-lab/evals, evals；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T21 — 新会话、防漂移与部署副本核验

类型：PARENT_TASK；批次：B5；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T03, DL-FINAL-T04, DL-FINAL-T08, DL-FINAL-T16.
验收依赖：DL-FINAL-T03, DL-FINAL-T04, DL-FINAL-T08, DL-FINAL-T16, DL-UI-U11, DL-UI-U12.
旧任务：DL-R5-001, DL-R5-002, DL-R5-003, DL-R5-023.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 入口一致、旧包不复活、生成源不回写、旅程负向验收
- 实际Windows/Agent/安装规则版本清单与恢复

验收：
- 不靠关键词判断；不宣称未查部署全同步
- 目标/事实/任务/许可一致；旧数据工程可恢复

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：scripts, design-lab/tests, docs；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-FINAL-T22 — 按真实覆盖缺口扩品类与未来路线

类型：PARENT_TASK；批次：B5；优先级：FOLLOWUP。
实施依赖：DL-FINAL-T07, DL-FINAL-T20.
验收依赖：DL-FINAL-T07, DL-FINAL-T20.
旧任务：DL-R5-008, DL-R5-016, DL-R5-017, DL-R5-018, DL-R5-019, DL-R5-020, DL-R5-021, DL-R5-022, DL-R5-025, DL-R5-026, DL-R5-027.

当前观察：存在性与剩余差距须对照最新源码，不继承历史完成声明。

交付：
- 各领域分析/提示词/执行/原生交付覆盖矩阵
- 后续学科教学和更多软件/模型的有限路线

验收：
- 全品类保留但未测不称支持
- 大型市场/图谱/全模型常驻/多Agent平台延后，当前低成本优先

证据：implementation, unit；真实宿主/真人/三方/学习分别验收。
建议write set：docs, design-lab/domain-packs；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：仅回退本任务自有变更；状态迁移先备份及版本读回；保留输入/作品/失败证据。宿主未知动作先对账，不关闭共享进程、不清理用户工程。

范围：DESKTOP_ONLY; mobile frozen; no implicit install/payment/cross-repo writes/release

## DL-UI-U01 — 现状、权威与路由对账

类型：UI_SUBTASK；批次：B1-UI；优先级：UI_FIRST。
实施依赖：无；先完成接收会话基线只读检查.
验收依赖：本任务独立证据.
旧任务：DL-R5-001, DL-R5-002, DL-R5-003, DL-R5-010, DL-R5-023.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 入口、历史发现范围、旧新路由、唯一账本映射
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U02 — 设计变量、组件与响应式

类型：UI_SUBTASK；批次：B1-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U01.
验收依赖：DL-UI-U01.
旧任务：DL-R5-001, DL-R5-002, DL-R5-003, DL-R5-010, DL-R5-023.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 深浅变量、交互控件、焦点、中文长文案、窄屏布局
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U03 — 能力查询与资格投影

类型：UI_SUBTASK；批次：B1-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U01, DL-UI-U02.
验收依赖：DL-UI-U01, DL-UI-U02.
旧任务：DL-R5-003, DL-R5-006, DL-R5-009, DL-R5-010.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 真实七轴、资格依据、权限前置过滤、能力详情
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U04 — 输入、目标与分析纠正

类型：UI_SUBTASK；批次：B1-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U02, DL-UI-U03.
验收依赖：DL-UI-U02, DL-UI-U03.
旧任务：DL-R5-006, DL-R5-010, DL-R5-013.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 多模态边界、参考职责、目标、强约束、知识版本、本次纠正
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U05 — 目标包与已有原生计划接续

类型：UI_SUBTASK；批次：B1-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U04.
验收依赖：DL-UI-U04.
旧任务：DL-R5-005, DL-R5-006, DL-R5-009, DL-R5-010, DL-R5-013.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 普通用户无需JSON、真实工具条件、降级交接
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U06 — 运行、观察与恢复控制

类型：UI_SUBTASK；批次：B2-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U05.
验收依赖：DL-UI-U05.
旧任务：DL-R5-002, DL-R5-004, DL-R5-005, DL-R5-006, DL-R5-007, DL-R5-009, DL-R5-010, DL-R5-011, DL-R5-012, DL-R5-013, DL-R5-015, DL-R5-024.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 实际动作状态、占用/预算、暂停/取消、对账、幂等与恢复
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U07 — 成果版本与局部改稿

类型：UI_SUBTASK；批次：B2-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U05.
验收依赖：DL-UI-U05.
旧任务：DL-R5-004, DL-R5-005, DL-R5-007, DL-R5-009, DL-R5-010, DL-R5-011, DL-R5-012, DL-R5-013, DL-R5-014, DL-R5-024.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 实际格式、版本、patch、视觉与结构检查分离
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U08 — 真人评审与交付预检

类型：UI_SUBTASK；批次：B2-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U07.
验收依赖：DL-UI-U07.
旧任务：DL-R5-002, DL-R5-004, DL-R5-005, DL-R5-010, DL-R5-011, DL-R5-012, DL-R5-014, DL-R5-015.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 真人回执、确切版本、测试/正式范围、rights/preflight/BOM
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U09 — 知识回执、离线与反馈

类型：UI_SUBTASK；批次：B4-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U04.
验收依赖：DL-UI-U04.
旧任务：新增需求.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 候选/偏好/纠正、允许回流、真实回执、撤销/冲突/待发
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U10 — 教学需求接入同一制作流

类型：UI_SUBTASK；批次：B4-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U05, DL-UI-U09.
验收依赖：DL-UI-U05, DL-UI-U09.
旧任务：新增需求.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 学习目标、知识案例版本、交付引用、字幕与视觉说明、正确归属
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U11 — 辅助连接、状态与旧入口退出

类型：UI_SUBTASK；批次：B3-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U03, DL-UI-U06, DL-UI-U09.
验收依赖：DL-UI-U03, DL-UI-U06, DL-UI-U09.
旧任务：DL-R5-001, DL-R5-002, DL-R5-003, DL-R5-009, DL-R5-010, DL-R5-023.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 真实支持范围、独立降级、旧入口兼容及退出条件
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

## DL-UI-U12 — 真实旅程与视觉验收

类型：UI_SUBTASK；批次：B3-UI；优先级：UI_FIRST。
实施依赖：DL-UI-U06, DL-UI-U08, DL-UI-U10, DL-UI-U11, DL-FINAL-T13, DL-FINAL-T14, DL-FINAL-T19.
验收依赖：DL-UI-U06, DL-UI-U08, DL-UI-U10, DL-UI-U11, DL-FINAL-T13, DL-FINAL-T14, DL-FINAL-T19.
旧任务：DL-R5-001, DL-R5-002, DL-R5-003, DL-R5-004, DL-R5-005, DL-R5-010, DL-R5-011, DL-R5-012, DL-R5-014, DL-R5-015, DL-R5-023.

当前观察：HTML/CSS/JS原型仅作参考；复用TS/Vite/Python与真实对象，不复制假动作。

交付：
- 桌面实际页面/组件与API映射
- 必要行为与视觉核对证据

验收：
- 核心可用链、权限负向、长页、真实宿主/评审/实联状态报告
- 覆盖loading/empty/unknown/offline/forbidden/error/timeout/conflict；演示数据不进入生产状态
- 以本包桌面规格/素材为目标，键盘、中文长文案、200%缩放、减少动态与深浅主题语义一致；手机端不实施

证据：implementation, unit, browser, visual_review；真实宿主/真人/三方/学习分别验收。
建议write set：apps/workbench, src/design_lab/http_service.py；先读取实际调用方和合同，清单不授予跨目录高风险权限。
外部条件：按实际动作判定；未实现外部接口不阻塞可逆UI材料.
回退：保留旧链接与数据；按组件/路由变更回退，版本迁移有备份；不整段覆盖shell.ts或删除既有作品。

范围：DESKTOP_ONLY; no mobile implementation

---

# 2026-10-09 Design QA 增量（折进既有卡，不新建卡、不建第二账）

来源：`docs/audits/DESIGNLAB-UI-R2-DESIGN-QA-2026-10-09.md`（design-review:design-qa，
判定 Pass with warnings）。下面每条都是**已落地界面与 R2 §2–§11 之间的覆盖差**，不是还原度
缺陷；归属沿用本文件既有卡号，验收仍走各卡自己的 `implementation/unit/browser/visual_review`
四轴。手机端仍按 owner 的 FROZEN_DEFERRED，不在任何一条里被重新激活。

## → DL-UI-U03（能力查询与资格投影）

- 资产类型 tabs（R2 §4）：全部资产 / 可调用能力 / 规范与方法 / 案例与参考 / 模板与配方。
  取值必须来自既有分类轴，不新建字典。
  **2026-10-09 先量了再决定怎么做（`.project-local/task-artifacts/ui-first-20261009/measure-r2-asset-tabs.log`）：**
  七个分类轴（domains / artifactTypes / capabilityLayers / aestheticAxes / styleArchetypes /
  tier / designQuality）在 60 条记录上**全部为空**，服务端自己的 note 写着"填轴是人工分类工作，
  不是界面工作"。所以 §4 的五张 tab 里，规范与方法／案例与参考／模板与配方**没有可选字段**，
  只能按 §2 的规则保留入口并给诚实空态。
  特别注意"可调用能力"：唯一看似能填它的是 `kind`（source 46 / model 14 = 60 条全命中），
  但 `kind` 回答的是"这条记录是什么类型"，不是"运行时能不能调用"；真正回答可调用性的
  `qualified` 实测 `counts.qualified = 0`。把 tab 映射到 `kind` 会凭空宣称 60 条能力可调用，
  因此这张也必须走空态，理由写"尚无资格记录"，不是"0 条能力"。
  唯一有真实取值的是 `disposition`（LOCK_REFERENCE 6 / CONDITIONAL_POC 37 / ABSORB_MINIMAL 3 /
  BLOCKED_BY_LICENSE 4 / EVALUATING 2 / REJECTED 1 / WATCH 7），它是上游生命周期词，
  与 §4 的五类资产不是一回事，不得拿来充当资产类型轴。
- 已选条件条 + 去重结果数（R2 §4）：当前组合条件下的去重记录数；每个条件可单独移除；
  "清除筛选"只清检索条件，不清领域选择、不删任务。**2026-10-09 第三批已落地**
  （`#capability-active` chip 条 + 按 ID 收敛的计数）。
- 11 个领域成为可导航二级入口（R2 §2）：从现有领域配置与稳定 ID 生成；领域无资产时保留
  入口显示空结果，不因零条移除分类。
  **2026-10-09 第七批落了一半，另一半是量出来的 owner 裁决，不是遗漏：**
  1. 已落地 — 每个域包有了自己的可贴地址 `#/domains/<packId>`（与 `#/capabilities/<id>`
     同一形状、同一个 `.cap-drawer` 组件，零新 CSS），`#/domains` 行内"查看详情"与全局搜索
     "设计领域"组都直接落到那一条记录，不再一律回落到列表；详情面板逐项显示这个目录自己声明的
     directory/pack_id/领域/版本/清单 schema/依赖/判定与判定原因。顺带修了一个既有缺陷：
     `#/projects/:id` 以前会让侧栏丢掉高亮，现在三个参数化地址都由 `DETAIL_NAV_OWNER` 认领父项。
  2. 数量以读回为准 — `GET /api/domains` 给出 **13 个目录、12 个声明 slug**（§2 写的是 11，
     且 §2 自己说"不是永久硬编码的总共 11 类……生产读取现有领域配置和稳定 ID"），
     `minigame-design` 声明 `workflow/domain-pack/v1`，`domain=null` 且校验 INVALID。
  3. **没有领域→能力的关联轴**（实测：60 条能力的 `domains` 分类轴全为空；能力记录的
     `domain` 字段装的是模型雷达 family，与包 slug 的唯一字面重合是 `3d`）。所以第七批把
     "按该领域筛选能力"做成**禁用按钮 + 屏上写明原因**，而不是画一张 0 条的假列表：
     把"没有关联"显示成"该领域 0 条资产"本身就是 §2 禁止的那种伪造。
     证据 `.project-local/task-artifacts/ui-first-20261009/qa-20261009g/domain-join-measurement.log`。
  4. **仍需 owner 裁定（§2 二级导航的标签）**：把 §2 的 11 个中文名逐条对上真实 slug，实测结果是
     2 个名字没有域包（字体与出版、游戏视觉）、2 个名字各命中 2 个包
     （平面设计→graphic/visual，UI 与交互→ui-ux/product-ui）、1 个包无人认领（ecommerce），
     而游戏视觉唯一候选 minigame-design 的清单无效。界面不许替这四处猜。
     算术见同目录 `r2-domain-nav-mapping.log`。
  5. 仍待做：在 owner 命名裁定之后，把二级导航做成 §2 要求的"当前入口上下文侧栏 =
     全部领域 + 各领域"，并按 §2 的"显示空结果、保留入口"给领域一个真正的资产面
     （要读第二次 `GET /api/capabilities`，措辞必须区分"没有已接线关联"与"该领域没有能力"）。

- 450px 详情抽屉（R2 §5）：打开后保留目录领域、条件、位置与焦点；完整详情要有独立地址，
  能被重新找到。当前行内展开关闭即失联。**2026-10-09 第四批已落地**：
  `#/capabilities/<id>` 真实地址 + 450px 非模态面板（未挂 role="dialog"），
  面板从 `--uif-topbar` 之下起算以免压住顶栏动作。
- 全局搜索补 R2 §9 的三对象组（能力资产 / 制作记录 / 成果）：先按权限过滤再统计返回，
  不得泄露无权对象的标题或计数；面板不得宣称自己做远程检索（现在它只做路由启动，这一点
  已经如实，别在补组时把它说大）。
- 闸门断言缺口：溢出/几何闸门只断言裁切、不可达与字号，**没有**元素间重叠断言，所以
  "侧栏底部溢出指示与分组标题同线"这类问题现在只能靠人眼。补一条 rect 重叠 +
  `elementFromPoint` 断言，并先证明栽进去的能量红。注意：QA 里同一屏的另一条"说明文字被折到
  视口外"已被源码否定（那一行在声明了浅色的色板下本就为空），不要照抄成缺陷。
  **2026-10-09 第四批已落地**：顶栏通知/工作区/搜索入口做 `elementFromPoint` 命中测试，
  被别的元素接走即 `OV_SPEC_BROKEN`；它当场抓到详情面板压住 `#topNotice`/`#openDrawer`，
  两次栽桩（8px 顶距、500px 宽）都复现了红，还原后字节一致且绿，
  证据在 `.project-local/task-artifacts/ui-first-20261009/qa-20261009d/`。
  侧栏底部溢出指示与分组标题是否同线仍未被断言——那是 nav 内部的排版问题，不是遮挡全局控件，
  留作后续。

## → DL-UI-U04（输入、目标与分析纠正）

- 输入四组补齐（R2 §6）：现有"需求与目标""参考素材与职责"之外，缺
  **交付目标**（分析 / 目标包 / 原生工程 / 最终媒体 + 工具、格式、尺寸、时长）与
  **能力与知识**（资产 revision、获准知识 revision、教学需要）。1920 下右栏约 60% 空白
  就是这两组的位置。交付目标只列有资格证据的路线，未知项显示"待核验"而不是消失。
  **2026-10-09 第三批已落地**：四档各带接线状态与依据，能力与知识读
  `GET /design-layer` 的真实 revision，获准知识与教学需要分别标未接线／禁用；
  两组输入编排进合同真正的 `constraints`，未新增字段。
- 草稿自动保存（R2 §6）：变更即写入正确任务身份，显示正在保存/已保存/保存失败；未保存
  离开给恢复机会；环境不支持持久保存时明确要求重选，不得只存文件名就声称原文件已恢复。
  接既有草稿接口，不新建第二套存储。
- 制作记录与待继续 + 底部任务条（R2 §7）：任务、领域标签、真实状态、最近确认点、继续
  操作；任务条只在实际存在当前/待继续任务时渲染，R2 原型的三条示例记录不得当作真实排队。
  **2026-10-09 第五批已落地**（`#/records` 读 `GET /projects/{id}/tasks`）：状态词原样、
  取消 requested/ack 两段、领域字段缺失如实说"无该字段"、展开才读一次 events、
  任务条只数进行中与待核对。**2026-10-10 第十一批**把这一行的"继续"拆成两件事：跳到目标
  生成包已经接线（只是换地址，发出 0 个请求），启动/取消仍禁用（真实宿主副作用，本会话无授权）。
  此前一个禁用按钮同时背着两个理由，把可逆跳转说成了需要宿主授权。

## → DL-UI-U05（目标包与已有原生计划接续）

- 结构/文本节点仍缺：`plan_to_rir` 在仓库里**没有生产调用方**（只有 `design-lab/tests/test_plan_to_rir.py`
  在调，8 处 import；服务与界面都不调），所以 `#/analysis` 的"已识别结构与推断"只能诚实显示
  "无来源可读回"。接通一条真实分析路径，或维持"结构节点由人在目标生成包里逐项给出"，二者都要
  在界面上说清，不得把空白读成"没有结构"。
  **2026-10-10 第十一批修正**：此前五处（`shell.ts` 四处含两处屏上文本 + 生成器
  `audit_ui_desktop_reconcile_20261009.py:86`）都写成"没有任何调用方"，那句话是错的；已统一为
  "没有生产调用方"，对账表由生成器重算（手写不会被接受）。
- 「与已有原生计划接续」此前是两个禁用按钮，理由还把"跳转"和"驱动宿主"混成一件事：
  **2026-10-10 第十一批已接线**（`#/records` 每条 `*-native` 记录一个可点的
  「接续：打开目标生成包」，素材导入行不给入口并说明原因；`#/intake` 的
  「到目标生成包继续」同理解禁）。行为证明是点击只改 hash、发出 0 个请求；启动/取消仍禁用，
  因为那是真实宿主副作用。简报字段不会自动变成目标包结构（属 DL-FINAL-T09/T10），屏上已写明。
- 已有原生计划不需要新存储：受理过的包都落在 `native_submission_v1` 与
  `projects/{pid}/native-plans/{uuid}/`，并由 `GET /api/projects/{id}/tasks` 原样投出
  `kind`/`state`/`attempt`/`cancel`。缺的是这条投影里没有 RIR 正文（只有 job_json/runRoot），
  所以接续面说清读不到什么，而不是画假节点。
- 状态类别修正（同一批）：409 幂等冲突上一批被画成 `forbidden`（标题说冲突、类别说"无权进行"），
  现改用 `STATE_SPECS` 里本就存在的 `conflict`，并要求两种 409 落在不同类别——忙可重试，
  幂等冲突不可复用同一个键。`NATIVE_SUBMISSION_BUSY` 维持 `unknown`。

## → DL-UI-U06（运行、观察与恢复控制）

- **观察面已落地（2026-10-10 第十三批）**：`native_tasks.py:59-76` 早就记着 U06 点名要的
  事实——哪个宿主被哪次尝试持有（`native_host_guard_v1`）、是否到达静默并带回执
  （`native_quiescence_v1`）、对账是否开着（`native_reconciliation_v1`）、恢复协议
  （`native_recovery_protocol_v2`）——但 `http_service.py` 里**没有任何路由投影它们**，
  只有动作路由（run/cancel/patch/bundle）。所以缺的是只读观察面，不是第二套 runtime。
  新增 `src/design_lab/native_runtime.py` + `GET /api/projects/{id}/native-runtime`：
  以 `mode=ro` 打开状态库且**绝不建表**（建表是 `native_tasks._connect` 的事），
  因此"表不存在"与"表存在且为空"是两句话；`budget` 为 null 并带理由（仓库里没有任何表
  记录预算/配额/成本，写 0 会被读成"还有预算"）；不造任何判定词
  （`proves_production_ready`/`is_host_action_performed` 恒为 false，`does_not_say` 逐条给界面）。
  `#/records` 的「运行与恢复现场」按这三种"没有"分别措辞，面板内零个可点按钮。
- **仍属 U06 而未做的**：暂停/取消/对账的**动作**与恢复实跑——那是真实宿主副作用，
  本会话无授权，界面上保持禁用并写明理由。占用/预算中的"预算"一侧在服务端无字段可读，
  补它属新 schema 决定，代理不自扩。

## → DL-FINAL-T07 / owner 裁决

- 强约束与偏好要"分别保存"（R2 §6），但简报合同只有 `constraints` 一个文本字段。
  先裁决 schema（新增 `hard_constraints` / `preferences` 两个数组，或声明本批仍走合成文本
  并把这条已知损失写进合同），再动界面。代理不自扩 schema。

## → DL-FINAL-T08（迁移前端核心入口和辅助信息）

- 组件拆分（R2 §11 的 25 个名字）：本批成形的只有壳层/导航/状态面/输入卡等一部分，其余
  仍是 `shell.ts` 内联函数。不要求照搬命名，要求同一语义不再各写一份。
- 深浅主题的语义一致性已由两主题各自的几何与对比度闸门覆盖（本批新加）；仍缺键盘全程
  走查、减少动画、200% 缩放的人审——这三项是真人验收，不由代理签。

## 本批已顺带修掉的证据问题（不需要再派工，读图时按新证据为准）

- 浅色主题实拍此前绑定的是旧 bundle（281680 / `4ce45da3`）且只有 16 张，缺
  `intake`/`plan`/`analysis`；现按当前 bundle（307355 / `10776c22`）重拍 19 张，
  `SUBJECT.json` 记 head + worktree digest + 未提交 deviation。
- 溢出/几何闸门此前只跑默认配色；现支持 `UI_PALETTE`/`UI_SCHEME`，并逐路由记录
  `railW/mainW/mainLeft/tableW/narrow760`。两主题各 19 路由：0 裁切 / 0 不可达 / 0 小于 11px。
- 两条初判被实测推翻，记录以免下一个人重新发现：浅色主题的能力表**没有**被挤成竖排
  （rect 与 PNG 墨迹横向范围双重否定，错的是裁剪回读）；顶栏搜索框**不是**装饰
  （`#openPalette` 有 click、`Ctrl/Cmd+K`、Esc 归还焦点）。
