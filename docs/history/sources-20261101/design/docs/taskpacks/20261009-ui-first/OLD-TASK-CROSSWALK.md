# 旧任务处置与新任务映射

状态：冻结映射；不编辑执行状态。唯一状态源仍为原账本currentExecution。

|旧任务|处置|新任务|保留/冻结原因|
|---|---|---|---|
|DL-R5-001 分支收敛、账本与增量接入|MERGED|DL-FINAL-T01, DL-FINAL-T02, DL-FINAL-T21|分支/增量与证据真值继续使用；旧派工冻结|
|DL-R5-002 仓库路径规范与旧运行根治理|MERGED|DL-FINAL-T01, DL-FINAL-T03, DL-FINAL-T11, DL-FINAL-T15, DL-FINAL-T21|路径、旧根、作品保护仍是恢复前提，不重做已落地治理|
|DL-R5-003 CI 与验证环境补齐|MERGED|DL-FINAL-T04, DL-FINAL-T05, DL-FINAL-T21|CI、安装、真实证据守卫保留；只补当前任务所需差量|
|DL-R5-004 运行状态与宿主异常恢复|MERGED|DL-FINAL-T11, DL-FINAL-T13, DL-FINAL-T15|原生取消、租约、幂等与异常恢复|
|DL-R5-005 资产原子版本与完整交付清单|MERGED|DL-FINAL-T10, DL-FINAL-T14, DL-FINAL-T15|原子版本、依赖、BOM与恢复|
|DL-R5-006 软件与模型资格选择|MERGED|DL-FINAL-T06, DL-FINAL-T07, DL-FINAL-T09, DL-FINAL-T11|按动作/软件版本资格化；未测不启用|
|DL-R5-007 Doctor 与本机证据接续|MERGED|DL-FINAL-T01, DL-FINAL-T11, DL-FINAL-T13|Doctor与已知安装位置用于精确排查，不重新扫描全盘|
|DL-R5-008 ComfyUI 生产适配与可选本地 MCP|FROZEN_DEFERRED|DL-FINAL-T22|保留Comfy生产适配要求；不是桌面UI硬前置|
|DL-R5-009 Python 安装包与 RIR 门面|MERGED|DL-FINAL-T05, DL-FINAL-T10|干净wheel、已有RIR门面复用|
|DL-R5-010 工作台执行、修改、取消与导出|MERGED|DL-FINAL-T08, DL-FINAL-T09, DL-FINAL-T10, DL-FINAL-T11, DL-FINAL-T14|前端执行/改稿/取消/导出并入新旅程|
|DL-R5-011 Illustrator 产品链路|MERGED|DL-FINAL-T13, DL-FINAL-T14, DL-FINAL-T15|Illustrator完整保留，不能改单宿主关整项|
|DL-R5-012 Photoshop 产品链路|MERGED|DL-FINAL-T13, DL-FINAL-T14, DL-FINAL-T15|Photoshop完整保留，不能静态通过冒E3|
|DL-R5-013 真实参考到可修正对象计划|MERGED|DL-FINAL-T09, DL-FINAL-T10, DL-FINAL-T20|参考解析、纠正与原生对象计划|
|DL-R5-014 局部对比、Human Jury 与生产预检|MERGED|DL-FINAL-T12, DL-FINAL-T14|局部差分、Jury、rights、preflight|
|DL-R5-015 M1 首个可用研究版|MERGED|DL-FINAL-T15|M1/GOLDEN-001/002/E3/E4/E5验收语义保留|
|DL-R5-016 本地语音生成|FROZEN_DEFERRED|DL-FINAL-T22|语音长期范围保留，专项实现待核心桌面闭环后|
|DL-R5-017 音乐与音轨|FROZEN_DEFERRED|DL-FINAL-T22|音乐/音轨专项保留，当前不派工|
|DL-R5-018 H3 本地专项|FROZEN_DEFERRED|DL-FINAL-T22|H3专项与软件MiniMax Design分开；不作UI前置|
|DL-R5-019 Premiere 可编辑视频|FROZEN_DEFERRED|DL-FINAL-T22|Premiere原生视频专项保留与条件依赖，不作当前主批|
|DL-R5-020 Blender 可编辑场景|FROZEN_DEFERRED|DL-FINAL-T20, DL-FINAL-T22|Blender原生场景要求保留；无环境小样标NOT_RUN|
|DL-R5-021 可选宿主与 Agent 收敛|FROZEN_DEFERRED|DL-FINAL-T22|额外宿主/Agent候选只按真实缺口启动|
|DL-R5-022 跨媒体依赖更新|FROZEN_DEFERRED|DL-FINAL-T22|跨媒体依赖更新在扩展批恢复，不删验收|
|DL-R5-023 历史完整性、维护与扩展交付预检|MERGED|DL-FINAL-T03, DL-FINAL-T04, DL-FINAL-T21|历史完整性与可审计入口保留|
|DL-R5-024 UIA 与视觉控制后备|MERGED|DL-FINAL-T11, DL-FINAL-T13|UIA/有限GUI作为后备路线，不成为Adobe硬前置|
|DL-R5-025 Comfy 短视频动效|FROZEN_DEFERRED|DL-FINAL-T22|Comfy动效专项保留，核心闭环后|
|DL-R5-026 Comfy 提取与透明资产|FROZEN_DEFERRED|DL-FINAL-T22|透明资产/提取专项保留，按需求恢复|
|DL-R5-027 游戏交互资产交付|FROZEN_DEFERRED|DL-FINAL-T22|游戏视觉仅Domain fixture，非运行产品线|
|DL-R5-028 语言治理与渐进迁移|FROZEN_SUPERSEDED|无当前派工|保留已落地语言守卫；全语言迁移/Ruff强制专项不在新包当前目标内|

MERGED：旧ID冻结，剩余要求并入新任务；FROZEN_DEFERRED：保留未来范围但当前不派工；FROZEN_SUPERSEDED：旧派工退出，正确守卫继续使用。
所有旧状态/证据保存在pre-adoption整账本与OLD-TASK-CROSSWALK.json，不修改原receipt。手机端FROZEN_DEFERRED；保留素材，不建当前手机任务。

## 其他旧资料与潜在断点

OLD-DOCUMENT-CENSUS.json（docs/history/taskpacks/20261009-adoption/）逐件登记21份旧任务文档及58项DeepSeek记录。58项旧状态自述DONE不作本轮PASS，保留守卫，不重新派治理任务。

- 20261006采集包多轴分类/权利/中立能力提炼并入T06/T07/T22；≥120候选配额及全局部署退出当前批。
- MethodCard双形状、Brief模型、Jury模板版本和30项INERT合同并入U01/T04/T09/T12/T21：先读当前实现，需产品的接通，无用的冻结，不机械全部激活。
- 旧移动抽屉/390布局冻结；桌面字体/token/品牌/错误层级按新UI规格和可访问性对账，旧意见不能永久阻止新UI。
- tool-control/omniparser/其他review-required权利阻塞并入T07/T14/T16；采纳任务不是许可接受。
- 孤儿图/作品/junction清理无本轮删除授权，冻结清理动作，保留恢复要求。
