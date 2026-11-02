# 监控汇总审计与三项目分流
核验日期：2026-09-15
审计标识：MONITORING-INTAKE-20260915
状态：AUDIT_RECOMMENDATION_ONLY；不是新的权威TaskPack；没有任何执行或生产批准。

## 1. 总结
这批材料值得保留，可以作为三项目的研究候选、模型提供方候选、回归测试供体与Radar入库样本。
不能把全部文件合成一个执行包直接开跑，也不应根据主观适配分自动替换三个项目的核心。
研究包11个候选；模型工作簿17条混合类型记录；研究任务20条+工作簿任务23条=43条原任务记录。
43条是待去重的来源记录，不是43个独立新功能。本审计保留全部原任务并建立对应映射。

### 审计范围
完整阅读本次6个HTML/Markdown附件；读取价格工作簿全部10个工作表并进行7组内存中公式边界试验；
对重点原始论文、模型卡、官方价格、发布说明进行外部复核；
只读复查三个已知候选分支的AGENTS，以及WORK-LAB radar_core.py和DESIGN-LAB penpot.py的指定代码范围。
本轮不是新一轮全分支/全代码审计，未查询用户实时权益，未运行收费API/模型/宿主软件，未改仓库。
所有原上传文件保持不变。哈希和确切读取范围见05与04文件。

## 2. 附件完整性与信息治理
1. 两类报告独立：研究生态与模型/API/价格；都使用S01等来源编号，但指向完全不同网页。必须使用带来源包标识的引用。
2. 研究HTML与研究Markdown大段重复，是同一报告的不同表现形式，不能算两个独立证据来源。
3. 总览含14条相对链接在当前扁平上传目录无法解析；其中3个TaskPack正文有对应附件，不能说正文完全缺失。
   三个TASKS.json、验收设计、执行门禁、交接提示词等未随当前上传出现。模型报告的05_来源与覆盖范围.md也未上传。
   这不证明用户从未生成那些文件，只证明本次交付不是自包含的可执行包。
4. 研究包20条与工作簿23条不共享编号；“详见对应TaskPack”不能自动将A01匹配AX-R01。
5. 保留原始不可变材料+哈希；分别建立发现、文档核验、代码/权重资格、账户权益、运行证据、项目验收状态。
6. 原报告已经声明个人知识可保存、计划未执行、费用需授权、PNG/MP4仍有价值，这些边界应保留。
7. 接入清单采用建议优先级，不把8.5/9.5等主观分当实测置信度，不让评分绕过许可、账户、资源和数据边界。

## 3. 独立复核的重要变化
- DeepSeek实时价格页本轮成功读取：deepseek-flash对应V4.1-Flash，1M上下文与384K最大输出已见官方说明；
  低峰普通输入/缓存读取/输出为0.15/0.003/0.60美元每百万词元，高峰0.30/0.006/1.20。
  老alias可继续响应但所指模型已经变化；V4-Pro继续服务。更新“本轮读取失败”的旧状态，而非新造退役结论。
- Gemini3.8Flash价格页支持2026优惠和2027已公告价格分栏；免费层数据使用与付费层不同，免费层Search grounding不可用。
- Astra标准短档与Fable5.1工作簿核心单价与本轮官方价格一致；Astra超过272K输入是整次请求长上下文计价。
- NeoMME使用检索专门权重Hcompany/NeoMME-260M-Retriever。其卡片列Apache-2.0和MeanMaxSim依赖约束；
  当前没有HF Inference Provider，所以HF免费0.10美元不能直接替代这个模型的自托管/本地环境。
  页级检索只证明找到候选页，区域坐标和证据片段需额外真实定位；不伪造bbox。
- RefVerifier分阶段指标可确认，但F1=0.990不是事实核验准确率；开放全文覆盖、定位和最终判定应分开。
- GRACE作者仓库当前为空，暂停代码依赖；CLAIM-CAL论文可确认，但Zenodo材料本轮仍未读取成功，不升级到可复现。
- tracelab有参考源码与合成基准，但作者也报告廉价scratchpad可以达到相同顺序任务准确率。
  先在现有WORK-LAB事件上旁路重放与生成Observer视图；真实私有会话不要成为默认数据源，模型实验另计成本。
- AG-UI应按具体子包核查；Strands有CORS/auth/resume/终态破坏性变更，不等于所有AG-UI使用方都紧急受影响。
- codex-acp实现版本不等于ACP协议版本；会话加载/分叉不证明任意软件的原生会话都可无损迁移。
- Deep Agents Code 0.1.69的嵌套用量、凭据隔离、dotenv归因适合作为测试供体，不是重建运行时的理由。
- Penpot MCP操作当前聚焦页面；活动tab、目标文件/页/对象、恢复后的写入目标必须验证。Figma案例节省不能外推。
- Dots3-Note指定免费端点已标2026-09-30退出；不要新增长期依赖。TokenRouter指定免费页面本轮读取失败，继续待核验。
以上来源的逐条核验范围见04_来源与核验范围.json。未复读的来源明确标UPLOAD_REFERENCE_ONLY。

## 4. 11项研究候选分流
|候选|归属|复用方式|建议|接入边界|
|---|---|---|---|---|
|GRACE|ArcheAxis|REFERENCE_ONLY|观察|作者仓库当前为空；保存论文方法，不创建生产依赖或为填空仓库重写系统。|
|RefVerifier|ArcheAxis|ALGORITHM_DONOR|优先方法验证|优先吸收引用链与证据片段的分阶段评测，不将局部F1解释为端到端准确率。|
|CLAIM-CAL|ArcheAxis|REFERENCE_ONLY|材料待核验|论文可确认；Zenodo材料本轮读取失败，不能声称复现或代码许可通过。|
|NeoMME-Retriever|ArcheAxis|PROVIDER_CANDIDATE|有条件POC|检索应使用Hcompany/NeoMME-260M-Retriever；不替换全部OCR、不重建知识库。|
|tracelab / Live Trace Model|WORK-LAB|ALGORITHM_DONOR|先离线旁路对照|优先用现有脱敏/合成事件重放并生成Observer只读视图；不要新建任务真值库。|
|GitHub Agentic Workflows|WORK-LAB|TEST_DONOR|优先补回归|吸收受控工作区与外部写入分离、工具审计、凭据隔离等测试模式。|
|codex-acp / ACP|WORK-LAB|ADAPTER_CANDIDATE|先查实际依赖|实现版本与ACP协议版本分开；逐端验证加载、分页、分叉、取消和权限。|
|AG-UI|WORK-LAB|CONDITIONAL_COMPATIBILITY|按使用情况修复|9月Strands等子包存在破坏性变更；先查锁文件、imports及实际请求。|
|Deep Agents Code|WORK-LAB|TEST_DONOR|优先选取小测试|0.1.69嵌套用量、追踪凭据隔离、dotenv来源适合做缺陷测试供体。|
|Penpot / Penpot MCP|DESIGN-LAB|ADAPTER_CANDIDATE|Codex有条件实机|复用已有interop/penpot.py结构合同；补文件/页面/对象绑定、聚焦误写防护及重开。|
|Figma MCP / Code Connect|DESIGN-LAB|OPTIONAL_PROVIDER|已有权益才对照|以账户实际可读/写/组件映射/导出权限为准；22.5%为客户案例非项目收益。|

## 5. 模型与服务不是同一类依赖
|记录|归属|建议处置|关键条件|
|---|---|---|---|
|GPT-6 Astra|WORK-LAB;ArcheAxis;DESIGN-LAB|AUDIT_BASELINE_CANDIDATE|仅疑难样例/独立复核，记录source model、effort、tokens与工具费。|
|Claude Fable 5.1|WORK-LAB;ArcheAxis;DESIGN-LAB|AUDIT_BASELINE_CANDIDATE|核验请求/思考块/工具协议；不得由被测模型自签完成。|
|Gemini 3.8 Flash|ArcheAxis;WORK-LAB;DESIGN-LAB|PROVIDER_CANDIDATE|只用授权脱敏输入；区分输入理解与图像/音频生成；按当前实际账户额度。|
|DeepSeek V4.1-Flash|ArcheAxis;WORK-LAB;DESIGN-LAB|PROVIDER_CANDIDATE|旧别名响应不证明原模型未变；记录resolved model、API、effort、usage与价格有效期。|
|DeepSeek V4-Pro|WORK-LAB;ArcheAxis|LIFECYCLE_WATCH|无需因旧公告强制迁移；未批准默认更换。|
|Agents API|WORK-LAB|EXPERIMENTAL_EXECUTOR|保留本地任务状态、产物导出和费用/会话边界；AA/DL独立运行。|
|GPT-Live-1|ArcheAxis;DESIGN-LAB|OPTIONAL_PROVIDER|先验证停顿/复述/取消；语音非AA首个Green闭环硬前置。|
|GPT-Image-2.5 Flare|DESIGN-LAB|PROVIDER_CANDIDATE|测试非目标区域差分、字形、比例、材质与真实alpha；保留原件及可编辑结构。|
|GPT-Image-2.5 Sunburst|DESIGN-LAB|PROVIDER_CANDIDATE|不把直接生成位图说成PSD/AI工程或精确场景重建。|
|Kimi K2.8 Preview / Kimi Code|WORK-LAB|ENTITLEMENT_GATED_PROVIDER|订阅不是通用免费API；确认允许的客户端与用途、额外用量开关。|
|Bolt Forge|WORK-LAB;DESIGN-LAB|SANITIZED_PROTOTYPE_ONLY|非私有仓库搬迁底座；只允许经批准的脱敏一次性原型，不能依赖去标识化承诺当保密保证。|
|OpenRouter 免费模型池|WORK-LAB;ArcheAxis;DESIGN-LAB|FALLBACK_TEST_POOL|固定模型与提供方再做对照；不把自动路由池当固定模型或稳定无限执行后端。|
|Nemotron 3 Ultra（OpenRouter 免费接口）|WORK-LAB;ArcheAxis|IDENTITY_UNRESOLVED|先补canonical ID/提供方/条款/账户/上下文事实，不猜拼写。|
|Dots3-Note Preview 免费接口|WORK-LAB|DEPRECATION_WATCH|只监控既有使用及替代测试；不要推导整个模型家族/权重退役。|
|NVIDIA NIM 开发者计划|WORK-LAB;ArcheAxis;DESIGN-LAB|RESEARCH_ONLY_RESOURCE|生产/真实用户服务需要另核许可；逐模型资格与托管容量不作保证。|
|Hugging Face Inference Providers|WORK-LAB;ArcheAxis;DESIGN-LAB|TRIAL_CREDIT_RESOURCE|有模型权重不等于能用免费API；不绕额度、不自动充值。|
|TokenRouter GLM-5.3免费候选|WORK-LAB|UNVERIFIED_WATCH|精确ID、价、期限、限速、数据条款与账户权限明确后再验证。|

## 6. WORK-LAB实际Radar代码的可定位问题
本轮读取：services/radar/radar_core.py，ref=r4-recovery-exec，
blob=42e62052753d91df1343806a12a5889c501d36db。
这是该模块的静态检查，不代表本轮已验证整个Radar运行链。

1. discover()按canonical_url去重，first-writer wins；相同URL后续价格/许可/版本或更正数据会被丢弃。
   改进：稳定实体+观测版本+来源证据集合；保留原观察，产生new/superseded/conflict关系。
2. Candidate将stars/downloads默认0，windows/local/api/cli/mcp默认false；未知与确定不支持混在一起。
   改进：unknown/null与confirmed_false分离，不以缺失值降低所有新模型/论文优先级。
3. StaticSourceAdapter.available()用是否有候选决定可用性；合法空结果和源不可用容易混淆。
   discover()跳过不可用源又仅返回候选列表，调用方仅凭空列表无法区分“无更新”和“未覆盖”。
   改进：独立fetch_status、coverage、items_count和last_success_at。
4. Candidate当前记录偏GitHub仓库，没有结构化的价格有效期、账户权益、规范/论文版本与三项目fit。
   改进：在原类型后做兼容增量映射/sidecar，不推倒原框架，不直接把来源报告写成完成状态。
5. min_stars与stars优先排序不能通用于模型、论文、标准、免费计划。
   改进：先按entity_kind选择信号；同一个高热度指标不能替代可复用资格。

优先实施范围：离线附件导入→带来源合并→差分→覆盖状态→中文展示→候选分流。
先补这条已有代码链，比重新建立一个大爬虫或Agent平台更直接。

## 7. 工作簿实测结论
原文件未修改；所有输入变更仅在导入的内存对象上进行，随后恢复。
默认值未见公式错误。Astra超过阈值拒用短档、未知缓存创建价显示待核实、零通过率不产生“每成功任务价格”，这些保护有效。
|测试|输入|结果|结论|
|---|---|---|---|
|Astra阈值保护|B4=272001|{"F18": "需长上下文价", "G18": "不适用", "K18": "待处理"}|保护有效|
|未知缓存写入保护|B6=1|{"G22": "待核实", "G24": "待核实"}|保护有效|
|零通过率保护|B9=0|{"L18": "无通过任务"}|保护有效|
|小数尝试次数|B8=0.5|{"G18": 0.2, "K18": 0.1, "L18": 0.2}|需要加固|
|计价除数为零|B11=0|{"G18": "#DIV/0!", "K18": "待处理"}|需要加固|
|语音负时长|B31=-60|{"D31": -0.05, "F31": -0.05}|需要加固|
|语音换算除数为零|B14=0|{"D31": "#DIV/0!", "F31": "#DIV/0!"}|需要加固|

该计算页未配置Excel数据验证和工作表保护。应增加非负数、整数调用次数、0–1通过率验证，并锁定计价换算常量。
语音负时长必须拒绝；分母误改为零必须给明确错误而非传播#DIV/0!。
这不是推翻全部价格数据：工作簿适合人工情景试算，但不能原样成为WORK-LAB执行预算引擎。
运行账单还需真实provider/model、effort、cache、time/region、嵌套调用、工具/存储/容器/平台附加费与重试。
未来价格、历史价格和今天适用价格可并列展示，但自动选择必须校验有效期。
Nemotron3Ultra行在精确model ID为空时不应整体标成可执行“已核实”；拆开身份、价格、权益和运行状态。
不把单价或相同示例Token下的费用比例当成真实任务质量、成功率或节省比例。

## 8. 三项目增量安排

### ArcheAxis：先Green闭环，证据方法优先；视觉检索是可选路线
- 把AX-R00与G00/G01/L01对齐现有R5身份/资源准备，不重新定义四库。
- 原始学习资料库只读；使用已有外置测试副本给Green TEST profile输入，输出到测试四库。
  保留首次进入选择四库中文路径设计；不猜四库名称，不因监控新增另一套资料库。
- 用户最新明确要求绿色版滚动修复集成，而本轮读到的AGENTS仍把Green v0.6.14写为恢复参考。
  这是owner意图与仓内已登记规则待对账，不是“绿色版应删除”。先正式记录差分，再依源码构建/刷新测试。
- AX-R03+A02/A03/A06：优先在现有解析链做引用证据片段、证据不足、原文不可得、修订/撤销回归。
- AX-R01/02+A01/A04：NeoMME在原Retriever后增可选Python provider，做文本/视觉/混合对照；收益不足允许淘汰。
- AX-R05+A05：必须测阅读/练习/复习与机器调用、纠错后的来源版本；不要把项目缩成PDF问答。
  GPT-Live语音放在文本Green闭环后，不让新模型/语音成为首个可用版本前置。
- AX-R04只保留研究，不阻塞人机主链。DeepSeek/Gemini只作为低成本可替换提供方，高端模型只评疑难样例。
- 正式知识/任务验收由现有Core与独立Gate管理，模型自称支持不改变知识验证状态。

### WORK-LAB：先修真实候选数据链和恢复门禁
- 根AGENTS本轮仍含10-workflow/workflow-assistance旧路径，不能把它复制进新候选包；先映射到实际树与现有任务。
- WL-R01是直接价值最高的入口：用本次上传作离线Radar样本，在现有radar_core上补证据/差分/覆盖而非再建后台。
- WL-R02/WL-R06/W01/W04：只查实际使用的ACP/MCP/AG-UI及模型别名；按提供方测试load/fork/cancel/perms。
- WL-R04/WL-R05/W03：先用假工具、假凭据、合成事件测试越权拒绝、重复事件、并发与恢复。
  UNKNOWN外部动作结果先对账；界面停了不等于进程停止；托管环境拒绝不是放宽权限理由。
- WL-R07/W07：将模型/API表改成有时效、供应方、币种、地域、计费模式的价格记录；未知费用不填0。
- WL-R03先旁路观察/确定性重放；只有必要时再跑收费四臂实验，不重建TaskStore或TelemetryStore。
- W02是模型对照，WL-R03是状态架构对照，不混成一个因果实验。
- Agents API/Kimi/Bolt分别是执行服务/订阅权益/训练共享原型，不同于裸模型Provider。
- 每实验初始预算0不是改变整个WORK-LAB全局模型政策；仍按现有任务级预算和授权决定。
- Observer保持只读，候选“值得POC”不能自动触发安装、写TaskPack、提交PR或生产替换。

### DESIGN-LAB：补现有资产验收，不把Penpot升级成默认底座
- 本轮源码src/design_lab/interop/penpot.py明确只做声明、归档结构验证和计划；没有真实import/export/host call。
  所以DL-R01应接现有Codex真实宿主队列，不重复让DeepSeek写第二套Penpot骨架。
- DL-R00与D01合入已有Requirement/DesignIR/环境盘点；先查.project/paths.json和LOCAL_ENVIRONMENT，别误判没安装。
- DL-R02+D04：补语义损失、原生源文件/交换文件/预览文件区别。PNG/MP4可以有价值，但不能替代约定的可编辑对象。
- DL-R01：写入前后验证目标file/page/object，跨tab焦点切换要拒绝或重新确认，副本中重开与恢复。
- D02/D03/D05：Flare/Sunburst模型对照测局部编辑、字形、真实alpha、非目标区域变动、比例/透视；
  原件与可编辑几何/文本由产品和宿主保留，不能让生成图像成为唯一尺寸真值。
- DL-R04+D06：Codex真实操作/原生重开证据与独立专业质量分别验收。
- DL-R03 Figma只在已有权益时可选；不新增订阅、不卡住Adobe第一条生产闭环。
- DSH只做结构、离线测试、素材清单与回归准备；实际Adobe/Penpot/GPU/质量交Codex和Human。
- 原生资产、客户Brief与试验输出留本项目；只按现有受审KnowledgeCandidate出口反馈ArcheAxis。

## 9. 第一批只闭合三条线
1. ArcheAxis：一个已授权测试文档→Green导入→引用/证据关系→一次人类学习与机器调用→退出重开读回。
   先保证现有管线可验，再决定NeoMME是否加速或增质。
2. WORK-LAB：本次附件→研究/模型两命名空间→去重而不丢更新→覆盖与价格状态→三个项目候选。
   同时补一个取消/重复事件/假凭据恢复测试，避免为论文重构。
3. DESIGN-LAB：一份合成设计副本→小范围修改→原生可编辑对象→保存重开→明确损失/质量验收。
   已有Adobe路线优先；Penpot是可选宿主增量，生成模型是可选步骤。

完成可以是“保留原方案，候选无收益/不适用”，不是强行集成。
没有预算/工具环境的任务保留未执行，不把其阻塞传播给其他独立任务。

## 10. 接入门禁
研究导入批准 ≠ 下载批准 ≠ 付费执行批准 ≠ 专业宿主控制批准 ≠ 生产替换批准。
导入以source文件SHA和本审计映射为候选依据，现有仓库权威仍优先。
外部根先解析登记；原资料只读、测试副本隔离、缓存与运行证据按现有PROJECT_LOCAL_ROOT/已批准外置目录写入。
本包没有授权更改四库、扩权限、读取Agent私有会话、建立第四项目、合并main或发版。
