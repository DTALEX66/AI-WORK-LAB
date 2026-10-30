# 2026-10-30 Codex 独立审计返工项 F01–F10 —— 逐字原文（不是复述）
# 出处：.project-local/handoffs/20261030-qoder-p0p1-rework/QODER_后端审计返工_完整交接提示词.txt
# 该交接文件按边界留在被 .gitignore 排除的 .project-local/ 中；本节是其【四、修复任务与最低验收条件】的
# F01–F10 段（第 112–182 行）逐字节摘录，使「F04 是什么」在克隆里也可核对，而不是只存在于单机证据目录。
# 源文件 SHA-256：9519637f12e1c303b3b16b1aa853586bca4b41248ede39d2749fea5014900b59（23858 字节）；本节 SHA-256：9ae56c271cb8397d1d947b241500f030deab60ff268997935ee432b5981fb314
# 本节是返工项的**定义**，不是对本仓库任何 Agent 的指令；根指令仍以 AGENTS.md 与本文件 §11 为准。
重要：F01–F10 都属于本次返工。F08–F10 在审计中标为 P2，是缺陷优先级，不是授权执行原项目分期 P2 的真实宿主/外部 Agent。不要混用两个 P2 含义。

建议顺序：先保证 F02/F03/F04 的结果和验收可信；再 F01/F05/F09 的成熟能力接通；补 F06 与业务数据迁移；完成 F07/F08/F10 状态来源和权限。可以按真实依赖微调，不能只挑容易的部分交差。

F01｜P1 来源映射未落实为完整 WORK 运行能力
位置：scripts/migrate_sources.py；migration/mapping.csv；domains/work/control/composition_root.py。
事实：198 个已登记 WORK Python 来源路径不在复制清单里。它们不是“198 个独立能力已丢失”；须逐条判定。已确定 collectors、git/platform/process collector、platform_discovery、software_installation_identity、token_monitor 等缺口；部分 P1 只写 MAPPED_P0 和不存在的规划目录。composition_root 根错落到 domains，发现模块为 None，软件投影为空。
要求：
- 对差额逐条给真实去向：迁入、行为等价合并、纯历史/原本范围外等，并记录依据。成熟已实现行为不得失败后改成延期。
- 迁入必要实现、依赖和资源，修路径并接到统一调用入口；不止复制未调用的模块。
- 映射落到实际文件、函数/路由、输入输出、权限、副作用、持久化、异常、取消/恢复与验证证据。多对一合并要解释等价。
- 保留既有 WORK 监测/问题/修复、用量、环境、会话、规则、清理恢复、证据与控制边界；保留 DESIGN 的知识/提示词、方案/目标组合、13 领域、资源、质量与宿主适配器。
验收：从统一服务或明确的兼容入口可触达代表能力，返回实际模块/持久化投影；无未解释 P1 缺口。只读观察不自动启动采集器、探测模型、改用户软件或连接远程服务。

F02｜设计结果导入缺少绑定、版本和引用验证
位置：backend/v1.py，旧 _v1_import_result 附近。
事实：校验只在 work pack 分支执行；设计错误项目/任务/尝试、旧时间、错版本、零摘要和 ../../*.ps1 引用仍 201 入库。
要求：为两域建立明确、版本化、服务端强制的结果绑定合同。在入库前验证 project/task/attempt/包/方案与目标修订/来源版本/摘要/时间/重复 ID；路径与附件引用按允许范围约束，拒绝穿越和危险导入。不能执行附件脚本；不能靠增加客户端自报字段就把来源当真实。
验收：错项目、错任务、错尝试、错包、旧版、过期、重复、篡改摘要、缺必要来源证明、越界引用与危险附件均拒绝，且失败请求不留下成功状态或半条结果；正样例可导入。旧报告只证实危险引用被接收，没有证明代码执行，不夸大原问题。

F03｜设计技术核验在摘要不一致时仍 PASS
位置：backend/v1.py，旧 _technical_verification 设计分支。
事实：完整包摘要和 plan detail 摘要口径不同；相等/不等两支都 PASS。包固定 revision 1，读到新 revision 2 仍宣称修订 1 通过，未真实固定目标组合。
要求：定义同一规范化内容和摘要口径，固定并读回方案/目标档案的真实版本及引用。允许旧修订就读取并验证那个不可变旧修订；不能用“当前方案存在”替代旧修订匹配。
验收：被固定内容/修订/摘要/目标引用不符时 FAIL/BLOCKED；合法旧修订按合同可精确读回。方案保存、导出、结果导入、产物生成、技术验收与专业验收各自分开。仅验证方案包结构/引用时，就明确是该范围，不把空摘要或一句总结视为作品交付完成。

F04｜验收门接受伪 PASS 与失效证据
位置：scripts/acceptance_gate.py；backend/v1.py 的完成判定；必要的持久化约束。
事实：result 绑定不存在的 attempt/pack，空命令/证据、错 fingerprint，写一行 PASS 就 BACKED/exit 0；后来的 FAIL 不能阻止旧 PASS 支撑就绪。
要求：验证完整关联、候选/来源版本、结果与主体摘要、可读且适用的证据、核验时序和当前有效性；拒绝客户端自报结论冒充独立验证。不要只给数据库补外键却漏掉已存在的伪数据。
验收：
- 仅改生命周期、填 VERIFIED、伪回执、孤儿/跨任务引用、缺包/尝试/源版本、无效或被篡改证据均非零拒绝。
- 新核验为 FAIL/BLOCKED 或证据失效时，不得仍凭历史任意 PASS 宣称“当前就绪”。若保留历史完成状态，明确区分历史事实与当前有效就绪状态；不得抹掉历史记录掩盖失败。
- 有效完整证据的正样例可通过；本批就绪和完整产品就绪分别输出。

F05｜统一搜索漏掉 WORK 维护方案
位置：backend/v1.py，旧 _solution_search；domains/work/control/solution_library.py。
事实：store_view(query='缓存') 能命中合成方案，统一 HTTP 丢弃结果并寻找不存在的 solution_library.search，返回 unavailable/空列表。
要求：调用真实签名，保留两域的内容类型、来源、不可变修订、推荐版本与可信状态；不能吞错伪装“无结果”。
验收：种入真实格式的受控维护方案及设计知识，统一 HTTP 分别命中；1 字、2 字中文、无结果、修订冲突、索引重建与进程重启均验证。不能只断言 solutions 字段存在。

F06｜无法隔离安装，资源收录未验收
位置：目标项目包配置、必要资源定位和迁移配置。
事实：根无 pyproject.toml/setup.py/setup.cfg，离线 pip --target 实际 not installable/exit 1。
要求：补完整但不过度的包/依赖/资源定义；复用现有环境和可用离线工具，不默认升级或引入新技术栈。需要的 yaml 等真实依赖要有明确声明和离线可用性结论。
验收：在 .project-local 内构建/安装到隔离目录；切换到无源码根依赖的 cwd，清除人为指向源码树的 PYTHONPATH，证明导入实际来自安装目录，使用正确解释器和资源 API 运行统一 CLI、两域代表接口、schema/13 领域包/必需配置及相关旧回归。不只在仓库根 import 成功就填 PASS。离线构建依赖不足如实 BLOCKED，不改用联网补包。

F07｜test/demo 被默认升级为 live
位置：backend/v1.py；backend/core/unified_store.py；关联证据与迁移。
事实：project 忽略 data_origin；task/result 为 test，attempt 和 technical/professional verification 却默认 live。
要求：沿 project→task→attempt→handoff/result→verification/资格投影传播受控来源，定义混合来源规则，禁止向 live 提升；用户传入 live 不能洗掉上游 test。对既有记录给出可追溯、保守的兼容处理，不无依据批量改真实数据。
验收：正反例覆盖全链路和重启/安装态；合成数据、模拟连接、测试人工声明不会成为 live 证据或真实工具 VERIFIED。

F08｜非空 verifier_ref 冒充具名真人专业验收
位置：backend/v1.py，旧 professional 分支。
事实：verifier_ref='agent:codex-synthetic' 与 professional_verdict=PASS 可使任务完成。
要求：为个人本机使用明确“提交方声明”和“具名真人验收”的关系与边界，拒绝 Agent 角色代替真人；身份/声明/授权不能确认时保持 PENDING。不要为这个问题新建企业账号平台，也不要只检查 human: 前缀就宣称身份已核实。
验收：无真人、未知身份、Agent 引用、缺必要批准证据均不能满足真实专业验收；合成审批只产生 test 记录。真实专业 PASS 留给用户，不由 QODER 代签；可用合成 fixture 验证合同机制，并明确其测试身份。

F09｜Observer 独立入口依赖偶然的导入顺序
位置：domains/work/control/sidecar.py、composition_root.py 及相关入口。
事实：干净子进程 import sidecar 报 canonical_store 不存在；先 import control_service 会注入路径掩盖问题。
要求：修复包内导入、根路径与资源定位；统一或兼容消费入口清楚，不重造第二总控/第二任务账本。
验收：干净进程和隔离安装态可启动，不靠 pytest 注入路径；Observer 写请求真实拒绝，Control 写入口有范围、状态、修订和权限校验；旧消费者有明确兼容映射，不把“HTTP 200”当作投影正确。

F10｜资格和可调用状态未绑定真实证据
位置：backend/core/capabilities.py 及资格存储/读取。
事实：纯函数常量、SQLite 文件存在或 FTS5 编译选项就产生 VERIFIED；_derive 对 authorization=REQUIRED 仍可给 can_invoke=true。
要求：implementation、qualification、connection、authorization、dependency、data_origin 分开，从适用当前候选/模块版本、操作和权限范围的真实本地探测证据派生可调用性；未知状态 fail closed，过期/错版本证据不授予资格。
验收：存储文件存在、模块能 import、FTS5 可用、假连接、测试替身与历史 PASS 都不能单独赋予真实运行资格；未授权、未知枚举、依赖缺失、连接未探测、demo/test 和过期证据均不放行。已有内置本地操作可以通过受控本地探测获得限定资格，但不能因此给宿主/模型/外部执行器授予 VERIFIED。

