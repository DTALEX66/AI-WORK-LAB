# DESIGN-LAB 云端复审与后续任务深化 · 2026-09-14

本轮已实际通过 GitHub 读取分支、开放PR、Git树、检查结果、AGENTS、Authority TaskPack与机器台账，并 git fetch 候选提交，在独立 detached worktree 阅读源码与执行隔离反例。不是复述附件。

## 结论

项目身份未发现偏离；候选开发成果真实存在，但完成口径与验收机制仍有缺口，不应认定58项结构任务全部验收完成，也尚不支持无条件合并通过。产品投影明确28项PARTIAL、NOT_RELEASED。当前需要修验收基础和接入资源预检，随后独立合并审计；不重写已存在的产品实现。

## 本轮云端快照

- main：c4dccd58331bc4561eb89265283d924b7630d113。
- 候选：codex/deepseek-authority-r1 @ f82f17ee5ec1d0e2973414ad673b00191324c68b。
- Git DAG实算相对main：ahead 115 / behind 0；tracked 1907文件。
- 开放PR：0（实际GET返回空数组）。分支列表30条，不代表30条都要合并。
- 五项CI结论success；run 34790686395。工作流范围主要Linux静态/单元/fixture，不能证明Windows宿主E3。
- 当前DeepSeek权威包SHA256校验一致，台账58项DONE。R5投影28项PARTIAL。
- Final Audit subject仍为a6d65d636ffe1b7fb2d8c5a023cbe5c338f9d220；PROJECT_STATUS也以此为WORKTREE基准，worktreeClean=false、fresh=false。文件自身有范围声明，因此不能称它谎报当前HEAD，但不能拿它作为最终候选新验收。

## 独立发现

### F01 / P0：Authority摘要没有绑定内容（已复现）
`scripts/deepseek_authority_ledger.py::worktree_digest`只hash HEAD和git status --porcelain文本。对同一已跟踪文件两次写入不同内容，状态路径相同，摘要相同。当前摘要不能证明实际测试了哪份未提交源码。应复用/统一按内容计算的实现，覆盖新增、修改、删除和任务授权未跟踪文件。

### F02 / P0：DONE证据只检查列表非空（已复现）
`verify`只检查TaskPack哈希、任务key集合、状态枚举及DONE有非空evidence。隔离内存副本中把全部证据替换为不存在路径，仍LEDGER=PASS tasks=58。未修改真实账本。完整任务ID、逐项验收结果、证据存在性/哈希/源码绑定需要真正验证；远端原件不能访问时是UNVERIFIED，不是不存在或通过。

### F03 / P0：零外溢漏报（两个反例已复现）
`verify_zero_spill.py`只对new路径判违规；changed/removed仅统计。修改模拟HOME/.hermes内已存在的项目文件，changed=1但NO_SPILL_DETECTED且exit0。仓库内新建.hermes/task-output同样exit0，因为整个REPO都在允许根。它没有完整覆盖任意外部路径；声明范围大于实际观察范围。应输出观察范围与截断状态，针对授权路径判新增/修改/删除，并区分项目旧目录与Agent原生数据。不要因此扫描用户私人内容。

### F04 / P0：干净安装未验却总体PASS（源码确认）
`verify_fresh_clone.py`固定使用原仓库.venv/Scripts/python.exe，install阶段硬编码NOT_VERIFIABLE，汇总仅看FAIL列表，因此无失败就PASS。可证明部分干净源码检查，不证明独立可安装。Final Audit第29条仍标MET，需拆分源码检查和安装验收。CI确有uv sync --locked成功，这是Linux依赖安装证据，不能直接替代Windows/安装包外运行证据。

### F05 / P0：附件所述资源联邦与任务Doctor未落仓（源码与命令确认）
候选完整Git树未含.project/resources.yaml；GitHub文件读取404。已有.project/paths.json登记四个外置根，根AGENTS已要求先读取路径及LOCAL_ENVIRONMENT，这部分保留。Doctor常规探测只查PATH上的uv/git/ffmpeg/node；支持paths/model-manifest等，但不支持--task，实际返回exit2。安装CLI子命令中也无doctor。不得再把`design-lab doctor --task`写成可直接执行的现有命令。共享注册须可选，不把WORK-LAB变成启动前置。

### F06 / P0：Sources Lock字段覆盖缺口被允许通过（源码确认）
46来源，URL39/46，commit或revision 0/46。sources_lock_check只强制id/path/disposition/license，URL/revision仅统计。所以G000 DONE不代表锁定要求完成。优先锁定实际执行/吸收路径；无法恢复的历史来源隔离标未解决，不猜revision，也不因所有历史文献未补齐阻塞首次产品使用。

### F07 / P1：TaskPack与DONE口径仍存在范围收缩
C030原文要求pytest/ruff；当前pyproject无ruff依赖或配置，pytest仅ini配置，CI跑unittest。旧报告“ruff已声明”本轮未在当前pyproject找到支持。H010要求Full Test Gate，现有关键220测试的多顺序及重复有记录，但全量顺序延期仍DONE。H020含安装却未验证安装。延期理由可以保留，不能静默把子集改成原任务全部验收；用明确例外/拆分/正式范围变更处理。

### F08 / P1：新增治理检查未在canonical入口显式接入
审阅canonical-verify.yml和verify_design_lab.py，未见Authority ledger、verify_zero_spill、verify_language_boundary、verify_contract_graph、verify_supply_chain这些新增入口被显式调用；不能仅凭文件存在和5绿证明它们是必过门。后续应建立检查清单与调用链，用故意破坏夹具验证对应CI拒绝，而不只搜索脚本名。

### F09 / P1：交接仍以大纲为主且过度关闭结构项
Real-Host Handoff明确命令为outline，正确不冒充实测；但首页仍把治理/供应链等写closed，与遗留项和本轮反例不相容。将交接改成实际入口、版本、fixture哈希、环境、动作、期望读回、恢复命令和限制。不得要求Codex从零重做治理，也不能要求其忽略未解决结构缺陷。

## 保留的成果与证据边界

现有Python产品服务、工作台、Adobe适配与四轴台账均保留；根AGENTS明确独立运行和三项目边界，Comfy/H3/UIA不阻塞Adobe M1。现有路径登记和历史原件不重置。34项针对性测试本轮通过：Doctor 11、Runtime Attempt Safety 23。creative migration测试因本环境缺jsonschema未加载，此项环境阻塞，不列代码回归。未运行1392全量、未完成干净安装、本轮无Windows宿主操作、无GPU推理、无用户D盘清理、无人工设计评审。Git工作树在检查后仍无tracked修改。

本轮没有独立验证316.79MiB释放和10对象迁移的本机字节，只核对提交中的报告；不把这些数值当新的实测。services空目录也不能仅凭Git确认，Git不跟踪空目录。

## 后续执行原则

这是审计增量建议，状态PROPOSED_NOT_ACTIVATED。遵循现行AGENTS、DeepSeek Authority及R5产品账本；新建议应映射并落仓，不另起冲突的完成状态源。任务别名中的R5-NNN对应DL-R5-NNN；DLDS键须带现行完整TaskPack ID。不得批量重置原任务。

优先修F01/F02/F03/F04/F06及CI，完善任务Doctor；冻结候选后独立审计。结构合并与宿主开发可分别推进，产品验收按现有权限与工作窗口。无须先做全仓Rust改写或扩大模型清单。设计参考库、学习库、Golden Corpus、Interop库保留为产品任务所需资源，优先每个首验案例的有权参考与验收标准，不等待全库铺满。

对外标准与模型选型本轮没有新一轮官方调研；DTCG/OTIO/C2PA/Penpot等只确认仓库现行声明，不声称已重新认证全部规范兼容。后续新增依赖、宿主接口变化和模型许可需要定向官方核验。

## 深化任务（18项）

### DL-AUDIT-20260914-01 · 证据摘要绑定修复

优先级：P0；负责人：DeepSeek；映射：DLDS-H000/B050；R5-001。

依赖：无。

实施：以规范化路径、文件内容哈希、删除标记、基准提交生成工作树摘要；覆盖 tracked 修改和任务授权 untracked；统一两套摘要实现，显式声明生成文件排除范围。

验收：同路径不同内容必须不同摘要；同内容重算相同；删除与未跟踪内容变化可识别。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-02 · 完成状态与验收证据核验

优先级：P0；负责人：DeepSeek；映射：DLDS-A000/H030/K040；R5-001。

依赖：DL-AUDIT-20260914-01。

实施：逐项对照58任务原文；DONE必须有可解析证据、内容哈希、源码绑定、验收项与执行结果；本地缺失证据记MISSING/UNVERIFIED；完整性与语义通过分开。不得把现有58项一律清零。

验收：不存在证据、旧源码、只完成子集、缺安装验收不能总体DONE；C030/G000/H010/H020逐项裁定；任何缩小范围需明确变更记录。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-03 · 零外溢检测修复

优先级：P0；负责人：DeepSeek；映射：DLDS-E010/E050/K010；R5-002。

依赖：DL-AUDIT-20260914-01。

实施：区分仓库代码允许写路径与禁止的项目旧运行目录；对授权观察范围内新增、修改、删除判定；路径规范化与链接边界；检测深度/数量截断返回不完整。仅对项目所有文件哈希，不读取私人会话。

验收：仓库.hermes新增与已有外部项目文件修改都被检出；显式合法根通过；观察范围外不得宣称零外溢；代理原生数据保持排除。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-04 · 任务资源预检落地

优先级：P0；负责人：DeepSeek；映射：R5-006/007；DLDS-J000。

依赖：DL-AUDIT-20260914-02。

实施：保留.project/paths.json；设计可选资源注册引用与版本契约；增加CLI doctor --task FULL_ID及工作台/worker入口调用；输出工具真实路径、任务权威、权限、机器和宿主范围。注册不可达时仍支持独立运行的本地配置。

验收：临时Windows路径夹具验证非默认安装位置；缺资源只阻塞依赖该资源的任务；CLI和工作台结果一致；不重复安装已登记软件。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-05 · 来源锁与启用资格

优先级：P0；负责人：DeepSeek；映射：DLDS-D010/G000/G040；R5-006/023。

依赖：DL-AUDIT-20260914-02。

实施：46条来源逐项追溯；当前实际启用供体必须URL、精确revision、内容digest和许可证证据；不可恢复旧副本标UNRESOLVED/INERT并禁止执行，不编造commit，不要求无关历史资料阻塞M1。

验收：实际启用来源缺任一身份字段被拒绝；39/46 URL、0/46 revision债务有逐项处置；改动绑定到CI。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-06 · 可安装与干净环境验证

优先级：P0；负责人：DeepSeek；映射：DLDS-H020/C030；R5-003/009。

依赖：DL-AUDIT-20260914-02。

实施：用新虚拟环境由锁文件安装；构建wheel并在仓库之外执行资源加载/CLI/最小任务；移除测试验证器对旧.venv/Scripts/python.exe的硬依赖；安装未执行输出PARTIAL/NOT_VERIFIED。

验收：不继承原工作区依赖、PYTHONPATH、缓存；缺包真实失败；Linux基础门和Windows路径门分别记录；安装缺失不能总PASS。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-07 · CI接入与延期测试拆分

优先级：P0；负责人：DeepSeek；映射：DLDS-H010/H030；R5-003。

依赖：DL-AUDIT-20260914-01, DL-AUDIT-20260914-02, DL-AUDIT-20260914-03, DL-AUDIT-20260914-05, DL-AUDIT-20260914-06。

实施：把Authority、来源、契约、语言和边界所需检查显式纳入流水线或可追溯调用链；绑定测试清单hash、平台、顺序、seed、失败/skip；全量多顺序在健康执行环境补验。

验收：新增门的反例能使对应CI失败；关键220重复结果保留；1392全量顺序延期单独记状态；不能把Linux通过当Windows专业宿主通过。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-08 · 语言与遗留目录收尾

优先级：P1；负责人：DeepSeek；映射：DLDS-B010/C030/C040/C050/D040；R5-028。

依赖：DL-AUDIT-20260914-02, DL-AUDIT-20260914-06。

实施：保留Python/TS/Host JS职责；ruff/pytest按当前TaskPack落实，或用正式变更批准unittest方案；117编码点按子进程实际编码分批修；旧core/备份按引用核验迁移；明确workbench TS检查或源码可执行约束。

验收：未授权新主语言为0；lint实际执行；中文子进程正常、失败输出可诊断；安装/测试不依赖旧core；空目录问题区分本地与Git树。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-09 · 运行证据持久保存与回收

优先级：P1；负责人：DeepSeek；映射：DLDS-D030/E020/E040；R5-002/023。

依赖：DL-AUDIT-20260914-03。

实施：对本机证据目录做新census；记录资产归属、持久位置、digest、重开与恢复；先保留替代副本再回收。历史316.79MiB只作为清单回收量，不伪造目录before/after。

验收：每个拟处理对象有保留/迁移/删除理由和恢复路径；无法证明归属的.hermes文件不动；不得在云端声称已清理用户D盘。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-10 · 最终候选独立审计与PR收敛

优先级：P0；负责人：独立GPT审计；执行者准备PR；映射：DLDS-H050/K040；R5-001。

依赖：DL-AUDIT-20260914-07。

实施：固定代码候选SHA/源码树摘要；更新Final Audit并区分生成提交；审查本轮发现及剩余例外；创建PR后核查合并结果与提交绑定；合并后分类旧分支。08/09非关键遗留须明确例外，不隐藏。

验收：无未处置P0；每个例外有owner/范围/截止与不阻塞理由；main含被审成果；不得等所有E3才合结构；不得按分支名称批量合并/删除。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-11 · 工作台到原生任务全过程

优先级：P0产品；负责人：Codex；映射：R5-004/005/010。

依赖：DL-AUDIT-20260914-04, DL-AUDIT-20260914-06。

实施：核验现有提交、授权、worker、事件、取消、未知结果对账和导出；补真实缺口而非重写；UI显示能力与证据范围。

验收：从页面运行任务，重启服务仍可恢复状态；未知结果先对账；取消有确认；资产版本原子更新，失败不遗留假ACTIVE。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-12 · Photoshop真实可编辑闭环

优先级：P0产品；负责人：Codex；映射：R5-012/013。

依赖：DL-AUDIT-20260914-11。

实施：使用已登记PS版本；受控fixture后跑一个真实brief；读回文本/图层/图像对象，连续两次局部修改，保存重开；失败与恢复；保留PSD与动作记录。

验收：对象可独立修改；未选中对象保持预期；宿主读回与保存重开验证通过；不能用扁平图片或截图替代PSD验收。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-13 · Illustrator真实可编辑闭环

优先级：P0产品；负责人：Codex；映射：R5-011/013。

依赖：DL-AUDIT-20260914-11。

实施：使用已登记AI版本；验证文本、路径、图层、链接图像；两次局部修改，保存重开与故障恢复。

验收：文字真实可编辑、路径对象存在、尺寸与布局符合brief；修改影响范围可核查；独立保存AI与读回证据。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-14 · M1人工验收与交付

优先级：P0产品；负责人：Codex+用户；映射：R5-014/015。

依赖：DL-AUDIT-20260914-12, DL-AUDIT-20260914-13。

实施：统一参考、需求约束、对象结构、原生工程、预览、rights与交付清单；检验一次完整工作台体验；保留人工意见与修订版本。

验收：真实参考→AI及PSD→两次修改→保存重开→交付完成；字体/链接/尺寸等预检通过；人工确认设计质量。Comfy/H3/UIA不是前置。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-15 · Comfy真实生成与局部重跑

优先级：P1扩展；负责人：Codex；映射：R5-008/025/026。

依赖：DL-AUDIT-20260914-04, DL-AUDIT-20260914-11。

实施：保留模型无关HTTP证据并单独验收模型推理；固定checkpoint/workflow/node版本；取消ACK、断线恢复、结果hash、局部重跑与透明通道。

验收：10次完整记录含失败；真实模型推理与空图传输分开；透明度逐像素检查；不把本地MCP配置当生产完成。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-16 · 音频视频原生工程

优先级：P1扩展；负责人：Codex；映射：R5-016/017/019。

依赖：DL-AUDIT-20260914-04, DL-AUDIT-20260914-11。

实施：按资源可用性选择一个TTS与音乐方案；产物回收入项目；Premiere验证独立轨道、字幕、时间线、重开与导出；OTIO按宿主往返验收。

验收：逐句重做、音轨独立编辑；PRPROJ重开与MP4播放有效；音视频同步、素材缺失与失败恢复可检查。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-17 · Blender与跨媒体更新

优先级：P1扩展；负责人：Codex；映射：R5-020/022/027。

依赖：DL-AUDIT-20260914-04, DL-AUDIT-20260914-11。

实施：在已核验模型/场景上验证对象、材质、相机、单位与局部修改；平面变动仅更新关联场景/镜头；游戏交互按独立案例验收。

验收：BLEND重开保留对象结构，GLB结构验证不替代宿主验收；未关联对象不受影响；游戏可运行和资产可编辑分别证明。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

### DL-AUDIT-20260914-18 · 可选宿主、H3与控制后备

优先级：P2按需；负责人：Codex；DeepSeek仅结构；映射：R5-018/021/024；DLDS-J000。

依赖：DL-AUDIT-20260914-04。

实施：OpenDesign/Penpot/MiniMax Design逐宿主资格验证；H3保持仓库rights限制；UIA仅原生接口不足时按案例启用；为每个领域提供真实命令、fixture与回退，不再只交大纲。

验收：每宿主独立create/edit/readback/reopen；不可用明确记录；H3模型与MiniMax软件分开；不拖慢M1。

回退：按独立任务提交回退；保留原始台账与证据；数据变更须先备份并验证恢复，不删除未归属对象。

## 云端来源

- [冻结候选](https://github.com/DTALEX66/DESIGN-LAB/tree/f82f17ee5ec1d0e2973414ad673b00191324c68b)
- [CI](https://github.com/DTALEX66/DESIGN-LAB/actions/runs/34790686395)
- [Authority账本实现](https://github.com/DTALEX66/DESIGN-LAB/blob/f82f17ee5ec1d0e2973414ad673b00191324c68b/scripts/deepseek_authority_ledger.py)
- [零外溢检查](https://github.com/DTALEX66/DESIGN-LAB/blob/f82f17ee5ec1d0e2973414ad673b00191324c68b/scripts/verify_zero_spill.py)
- [干净克隆检查](https://github.com/DTALEX66/DESIGN-LAB/blob/f82f17ee5ec1d0e2973414ad673b00191324c68b/scripts/verify_fresh_clone.py)
- [现行最终报告](https://github.com/DTALEX66/DESIGN-LAB/blob/f82f17ee5ec1d0e2973414ad673b00191324c68b/reports/current/DEEPSEEK-FINAL-AUDIT.md)

包内evidence含本轮云端快照、隔离复现结果、命令退出码与实际输出。机器任务图已核验唯一ID、依赖引用及无环；机器文件是建议图，不声称已成为仓库执行权威。
