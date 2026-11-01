# DESIGN-LAB｜后续执行任务包

本文件是研究结论到当前仓库任务的映射建议。下列W编号仅为本次工作分组，不能新建平行mutable ledger。执行状态继续写design-lab/config/task-ledger-r3.json；新需求按其schema和现有管理流程映射/扩展，禁止修改冻结任务定义来假造完成。

## 0. 执行规则

1. 开始先重读live main和本地HEAD/dirty；本次研究基线为d116b14995fcdbba1b165ec5bc3124f5daed3d15，不是永久HEAD。
2. Authority和Owner最新明确决定优先。上传2026-09-28任务清单补充目标，不恢复已关闭P0、不覆盖standalone-first、不建立新模型底座。
3. 已实现且证据缺失：补证据；存在可复现缺陷：修缺陷；缺实现：补实现。三者分别派工。
4. 每个产品波次都要有可见页面/操作进展，不能连续用治理报告代替产品改进。
5. 一次闭合一个真实Host；旧R5跨宿主依赖不能静默删除。单宿主首例通过不等于R5-014/015全部PASS；如需调整里程碑，走现有case/依赖决策记录。
6. 已有CI门禁保留；新增测试聚焦具体风险。不要为排版变化反复跑无差异全仓审计。

## 1. 工作包与依赖

### W00｜继承当前实现并生成差异映射（P0）

- 依赖：无。
- 映射：DL-00/01；R5-001/002/003/007/028。
- 读取：AUTHORITY、authority-index、AGENTS、现行产品/架构/边界/Neutrality/Adapter/Evidence、当前taskpack/ledger、paths与本机环境；live PR/CI/artifacts/分支保护。403记未知，不以旧数值填充。
- 动作：区分用户本地未推送与云端；保护dirty/资产，记录worktree。28项账本逐条找现有证据，不把PARTIAL当从零开发。
- 产出：原41项→R5→真实文件/接口→实现/证据缺口→首批范围的映射。
- 验收：每个首批项有真实路径；已关闭strict TS/首条设计链不重开；无hard reset/覆盖；极短启动回执后进入产品任务。

### W01｜视觉资产与Token基线（P0）

- 依赖：W00。
- 映射：DL-UI-04/09/10；R5-010/028；GOLDEN-001。
- 目标位置：apps/workbench/style.css、packages/design-system及现有Token来源；新增位置经现有目录规范确认。
- 动作：读取仅DESIGN-LAB的原UI套件，核对B04/B07/B10；建立页面/状态/组件/Token矩阵。工作台Token和项目DesignSystem分域。
- 产出：颜色/字体/间距/密度/圆角/图标/动效语义；原稿与当前页面差异清单；缺失素材标记。
- 验收：无跨项目串色；既有Electric Blue品牌延续；原件缺失不声明1:1；一组实际项目数据可用于后续视觉验收。

### W02｜组件体系生产兼容验证与裁决（P0）

- 依赖：W00/W01。
- 映射：DL-UI-09/10；R5-010/028。
- 首选Spectrum Web Components，备选Web Awesome Core；选定上游稳定代际并锁版本。React/shadcn只形成有成本/收益/回滚的ADR候选。
- 在一个现有页面上接10类基础控件；真实生产Python服务、wheel安装态、CSP、Shadow DOM、中文IME、Tab/Escape/焦点归还、离线、单文件build/VM契约逐项验证。
- 产出：单一选型决策，source/revision/license/组件覆盖/实测资源开销，保留与移除项。
- 验收：不靠unsafe-inline、全目录静态服务或删除旧测试通过；未过门则回退现有组件并切备选。兼容裁决完成后只保留一个主体系。

### W03｜项目中心与壳统一（P0，首个用户可见交付）

- 依赖：W02。
- 映射：DL-UI-01/09/10、DL-BE-01/03；R5-010。
- 位置：shell.ts/main.ts/workbench.ts/index.html/design.ts及现有HTTP层。
- 动作：导航、项目/版本上下文、最近项目、待审/失败列表；create/open；保存状态、焦点和错误定位；统一旧单页与新路由的用户流程。个人版隐藏协作入口或说明未开放。
- 验收：从项目卡进入真实Brief并保存读回；刷新保留项目上下文；失败不弹“保存成功”；旧工作入口在迁移完成前可用；无假KPI。

### W04｜参考与资产管理（P0）

- 依赖：W03。
- 映射：DL-UI-02、DL-BE-05；R5-005/013。
- 动作：本地导入/选择、缩略图/完整预览、来源/授权、hash、版本、missing/error；鉴权图像路径与缓存；大图按需生成预览；需要Uppy/PhotoSwipe时先过W02类资源测试。
- 验收：图片不被默认裁剪；alpha可见；缺失引用可定位；未知rights可研究但阻止生产认证；跨项目资产ID不能读取；批量导入可取消并报告部分失败。

### W05｜Direction与可修正对象计划（P0）

- 依赖：W04；AI辅助可等待W12，手工流程不等待。
- 映射：DL-UI-03、DL-BE-01/04；R5-013。
- 动作：Brief/Reference绑定的方向卡、约束、候选对比和人工选择；与DesignIR/RIR转换映射；以对象属性表单支持标题/图片/图形修正、锁定区域，raw JSON仅Advanced。
- 验收：版本链、chosen和active binding一致；AI候选不能自动替代人选；改变Brief使相关审查状态显式过期；整图背景不能冒充可编辑重建。

### W06｜DesignSystem/Token编辑与读回（P0）

- 依赖：W05。
- 映射：DL-UI-04、DL-BE-01；R5-010/013及现有设计链映射。
- 动作：先复用catalog/bind；核查Token写API缺口，新增必要schema/版本存储/校验/权限；表单编辑与即时预览、版本diff、发布到项目、回滚。复用已有DTCG转换器与测试，不另造格式。
- 验收：颜色/字号等改动真实保存；重启一致；冲突返回可恢复状态；工作台品牌不随项目Token改变；非法Token有字段级错误。

### W07｜生产任务与一个真实宿主（P0）

- 依赖：W06；沿用R5依赖检查。
- 映射：DL-UI-05、DL-BE-02/03；R5-004/005/009/010/011或012。
- 位置：native_*、task_*、integrations/hosts/adobe与Python creative层，禁止第二runtime。
- 动作：读取本机路径记录、probe当前版本/授权；在Illustrator或Photoshop中择一完成prepare→execute→observe/readback→failure/recovery→rollback。任务进度来自真实job；cancel/retry绑定attempt/idempotency；原件保护，生成新版本。
- 验收：至少标题可编辑、图形/图片结构符合交付；保存、关闭、重开并读回对象/版本/hash；一次局部改字或换图；一次失败与恢复。无宿主实机条件标HOST_BLOCKED，保留其余可执行工作。

### W08｜Review / Quality / Human Jury（P0）

- 依赖：W07。
- 映射：DL-UI-06、DL-BE-06；R5-014。
- 动作：复用assurance/human_jury、quality_record、qa_plane；对比、批注、版本定位、接受/拒绝、修订再审；确定性检查/模型建议/人工裁决分开。
- 验收：意见绑定artifact/version；新版本不继承旧PASS；至少一次人工拒绝并修订；模型自评分不升E4；单人Owner验收如非独立评审应如实记录。

### W09｜真实生产预检（P0）

- 依赖：W08。
- 映射：DL-UI-07、DL-BE-05/06；R5-014/023。
- 动作：按媒介profile检查尺寸/有效分辨率/色彩/出血/字体/链接/rights/可编辑性/BOM，error/warning/NA语义明确。任务资源预检与成品生产预检分开，不把/api/task-preflight可用当成交付预检完成。
- 验收：故意缺字体/链接或错误尺寸→定位到对象/文件→修复→重跑；不是固定PASS；屏幕UI不套印刷规则，印刷参数以实际交付方规格为准。

### W10｜可编辑Handoff与恢复（P0）

- 依赖：W09。
- 映射：DL-UI-08、DL-BE-07；R5-005/014/015。
- 动作：复用native_delivery；生成源文件+预览+BOM+许可/限制+manifest+证据引用；稳定版本/hash关联；中断导出清理与重试；打开交付目录/重开宿主源文件。
- 验收：下载长度/hash与内容一致；读取manifest并验证每个成员；源文件能重开编辑；断开工具或重启服务后可恢复；ZIP存在不算交付通过。

### W11｜WORK-LAB边界契约（P1，可与W03起交错推进）

- 依赖：W00；不成为单机UI和手工生产阻塞。
- 映射：DL-WL-01至06；R5-021/023下现有联邦范围确认，不擅自修改冻结定义。
- 动作：读取WORK-LAB实际公共合同，完成capability/intent/action/context/result/evidence/observer；refs含版本与有效期，最少上下文，幂等与失败语义；只读观察和写控制凭证分离；高风险两侧审批。
- 验收：Quick Entry打开项目→获准动作→结果引用→Observer读回；拒绝/过期/跨项目ref fail closed；Observer写入被拒；WORK-LAB不直写DB/资产。WORK-LAB不可用只阻塞联邦验收。

### W12｜共享FAST/DEEP消费与故障（P1）

- 依赖：W11契约可用；本地数据编辑不依赖本项。
- 映射：DL-AI-01/02/03/05、DL-BE-04；R5-006及已有provider模块映射。
- 动作：Python侧logical Provider client，health/invoke/timeout/cancel/provenance；小任务FAST、复杂方案比较DEEP；必要上下文最小化；fallback须预授权并可见；浏览器不存Provider密钥。
- 验收：各一个真实设计调用；超时/OOM/restart/unavailable状态；取消后迟到结果不能覆盖新版本；显示或receipt保存实际provider/model；AI失败仍可手工继续。

### W13｜研究与领域能力产品化（P1）

- 依赖：W04/W08；按真实需求，不阻塞首个交付。
- 映射：产品六能力域、DL-UI-02/03/06、R5-013/014/023。
- 动作：ResearchFinding/MethodCard最小持久化或复用现有内容索引；来源/revision/license与Brief关联。DomainPack列表读取真实manifest和证据，区分声明/受控/实机。
- 验收：研究结论有来源且可回到对应项目；无后端时诚实未开放；领域目录数量不当作生产能力数；无通用向量库/知识服务重建。

### W14｜Windows交互、性能与安装态（P0横切）

- 依赖：W03开始持续，W10前完成关键路径。
- 映射：DL-UI-09/10、DL-BE-03；R5-009/010/015/028。
- 动作：全部状态矩阵、中文IME、keyboard/focus/菜单/拖放、undo范围；1920×1080和2560×1440，100/125/150/200%缩放；离线、任务中断、字体缺失；安装wheel加载实际资源。
- 拟定性能目标：热路由交互P95≤200ms、本地首屏可交互≤2s、千资产索引不全量加载原图、持续滚动无明显卡顿。先采样现状；此为项目拟定目标，非现有实测或上游承诺。
- 验收：无阻断级溢出/遮挡/键盘陷阱；取消响应及时且语义真实；axe严重问题清零或有明确处理；人工键盘/缩放检查。桌面壳只有实际需求后ADR另行引入。

### W15｜两条黄金流程与证据复审（P0收口）

- 依赖：W10/W14；联邦部分另依赖W11/W12。
- 映射：DL-GJ-01至10；R5-003/014/015。
- G-A：用DESIGN-LAB自己的Brief/Reference/Direction/Token产出本工作台页面，生产包真实操作、视觉差异、可访问性、人审、交付。
- G-B：实际商业物料经一个宿主生成可编辑源文件、局部修订、预检失败修复、交付、完全退出重启读回。
- G-C：WORK-LAB Quick Entry→Action→ResultRef/EvidenceRef→只读Observer；独立于G-A/G-B单机链。
- 验收：E2/E3/E4/E5分别记录；同SHA/环境/输入/工具版本/产物hash；不借其他能力历史证据晋级。旧R5-014/015依赖未全满足时保持PARTIAL，即使首单宿主成功。

### W16｜按需扩展专业工具与媒介（P2）

- 依赖：W15的单机黄金流程通过；各项仍遵循原R5依赖。
- 映射：DL-AI-04、R5-008/016–022/024–027。
- 第一后续：ComfyUI图像/透明资产真实workflow，登记GPU/runtime关系；Figma或Penpot只选一个UI宿主试点。
- 再后续：Blender场景、视频/动效工程、配音/音乐、游戏视觉资产；保留源工程、依赖/字体/贴图/模型权利、可复现参数与回滚。
- 验收：每新增一能力至少一个实际任务和一个失败场景；不将视频成片等同于可编辑时间线；不启动第二共享模型runtime；不一次全接。

### W17｜可选知识桥接与清理（P2/条件性）

- 依赖：W15；ArcheAxis桥接需明确需求。
- 映射：DL-GJ-11、R5-021/023。
- 动作：仅受控ResultRef/EvidenceRef/获准知识候选；ArcheAxis自行治理。闭环后处理重复目录/旧资产，不删除未核验残留或用户原件。
- 验收：无跨项目直写，无原始客户资产自动外发；可撤回桥接；清理有恢复路径。

## 2. 原41任务的完整覆盖

|原任务|工作包|备注|
|---|---|---|
|DL-00 / DL-01|W00|继承已有，不重复建设|
|DL-WL-01 / 02 / 03 / 04 / 05 / 06|W11|逐项合同/映射/上下文/结果/观察/审批|
|DL-AI-01 / 02 / 03 / 05|W12|client/FAST/DEEP/故障|
|DL-AI-04|W16|视觉能力条件性引入|
|DL-UI-01|W03|项目与Brief|
|DL-UI-02|W04|参考与资产|
|DL-UI-03|W05|方向|
|DL-UI-04|W01/W06|工作台Token与项目DesignSystem分开|
|DL-UI-05|W07|一个真实宿主|
|DL-UI-06|W08|质量与人工审查|
|DL-UI-07|W09|生产预检|
|DL-UI-08|W10|交付|
|DL-UI-09 / DL-UI-10|W02/W03/W14|状态与交互|
|DL-BE-01|W03/W05/W06|核心对象持久化与版本|
|DL-BE-02|W07|Adapter|
|DL-BE-03|W03/W07/W14|真实任务状态与恢复|
|DL-BE-04|W12|AI逻辑Provider|
|DL-BE-05|W04/W09|资产权利|
|DL-BE-06|W08/W09|审查预检版本绑定|
|DL-BE-07|W10|交付与回读|
|DL-GJ-01 / 02 / 03 / 04 / 05 / 06 / 07 / 08 / 09 / 10|W15|包含各能力工作包的串联验收|
|DL-GJ-11|W17|条件桥接|

## 3. 交付波次

|波次|任务|用户能看到什么|放行条件|
|---|---|---|---|
|A|W00–03|统一、可操作的项目/Brief页面|继承真值、选型过门、真实保存|
|B|W04–06|参考、方向、Token编辑|数据版本读回、状态真实|
|C|W07–10|工具生成、修改、审查、可编辑交付|真实宿主/失败修复/重开|
|联邦支线|W11–12|从WORK-LAB打开调用；FAST/DEEP辅助|合同一致、双侧权限、故障可见|
|D|W13–15|研究来源、稳定Windows体验、两条黄金例|证据复审、视觉与安装态验收|
|E|W16–17|按需扩展媒介和知识桥接|前链完成、真实业务需求|

每个波次提交最小有用变化和对应证据。受阻时推进不依赖该阻塞的工作；不以等待WORK-LAB或一个模型为理由停下全部UI/设计生产。

## 4. 验收记录格式

每项记录：当前SHA/tree、工作树差异、任务映射、输入/fixture hash、项目/产物版本、OS/Host/Adapter/Provider版本、动作与权限、命令/exit或job结果、产物hash、readback、失败恢复、reviewer、证据等级、限制、回滚入口。

产品轴：CONTRACT/BACKEND/FRONTEND/PERSISTENCE/HOST_OR_GENERATOR/READBACK/QUALITY/RIGHTS/PREFLIGHT/DELIVERY/EVIDENCE。账本已有implementation/unit/host_live/delivery四轴保持其schema，详细产品轴附在证据中，禁止未经迁移直接改字段。

五个最终状态继续输出PASS/PARTIAL/BLOCKED：PRODUCT_VERTICAL_SLICE、WORKBENCH_BACKEND、SHARED_AI_CONSUMPTION、WORKLAB_INTEGRATION、PREFLIGHT_HANDOFF，统一DESIGNLAB_前缀。另写E级与未满足依赖，不用五个PASS代替独立E4/E5认证。

状态矩阵：empty/loading/partial/offline/tool-unavailable/provider-degraded/permission-denied/error/retry/long-running/cancelled/version-conflict。重试需区分可重试传输错误与不可重试权限/权利/格式错误。

## 5. 首批立即执行的具体顺序

1. W00核对本地HEAD/dirty并确认原有UI任务是否还在运行，避免覆盖另一执行器未提交工作。
2. W01读取DESIGN-LAB专属UI原件，固定一页Project/Brief作为视觉和业务基准。
3. W02完成生产包兼容试验并选一个组件体系；测试结果不满足则选备选，不无限研究。
4. W03交付真实可用的项目/Brief界面；同时形成W11合同缺口清单但不复制WORK-LAB代码。
5. 按W04–10推进首条可编辑商业交付，并持续完成W14，最后W15核验。
