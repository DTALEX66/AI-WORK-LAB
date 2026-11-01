# DESIGN-LAB 启动连接 · 人工评审 · 产物预检 · 2026-10-08

同一波次内的三条链,基线 live main `fc03a3033e900a8066d863a223636cc68804c4fa`。
本轮接手时的第一个发现是交接前提反了:本地检出 `1d18ae80` 相对 live main 是
**0 ahead / 81 behind**,交接点名的"必须先修的门"(`test_workbench_css_single_definition.py`
50→47)在 main 上早已用 rendered-rows 语义正确修好(`37bd2622`,下限仍是 50)。
未提交增量按行比对后,真正 main 上没有的是备份一致性(见
`DESIGNLAB-BACKUP-CONSISTENCY-2026-10-08.md`)、官方启动自动连接、以及下面两条能力链。

## 1. 官方启动自动连接(提交 10bf16a3 / dcc27769)

`design-lab workbench` 以前把一次性令牌打到 stdout,要求人复制进页面。现在默认不打印任何
凭据:由本服务自己打开的页面通过 `GET /api/local-session` 取回会话,且仅当
`Sec-Fetch-Site` 恰为 `same-origin` 时作答。`--manual-connect` 保留旧行为给外部启动器。

这个端点比既有 `guard` 更窄,是刻意的:`guard` 允许缺失 `Sec-Fetch-Site`(普通 HTTP 客户端
本来就没有这个头),这对"服务一个页面"没问题,对"交出凭据"不行。测试用真实 socket 断言
四种拒绝:伪造 Host、外部 Origin、cross-site、无头,以及 auto-connect 关闭时端点不存在、
令牌不在服务出的 HTML 字节里。

`OSError` 的 winerror 206 从 `PROJECT_STORE_UNAVAILABLE` 里分出来成为
`PROJECT_PATH_TOO_LONG`。长路径是本项目在 Windows 上的真实故障形态,把它报成"存储不可用"
会把用户支去查数据库而不是查项目放在哪。

能力库打包缺陷:`capability_library.py` 用 `parents[3]` 推断仓库根,安装态即
`<venv>/Lib`,四份输入读不到 → `_read_json` 以 `FileNotFoundError`(OSError 子类)失败关闭
→ HTTP 层再报成 `PROJECT_STORE_UNAVAILABLE`,一个指向错误子系统的错误诊断。现在四份输入
随 wheel 打包并优先解析安装态。

安装态是**实测**的,不是推断:`uv build --wheel` → 干净 venv → `IMPORTS_OK` →
`DL_LAUNCH_INSTALLED=1` 下 `Ran 3 tests / OK` 且**无 skip**,其中安装态能力库投影与仓库态
逐条相等。这是依赖复用的本地安装验证,不是清洁房间发布,因此不构成 E5。

CI 的 wheel 门断言 `Ran 3 tests` 且禁止 skip,所以这条读回是**扩写已有用例**而不是新增方法。

## 2. Human Jury 从合同变成可用能力(提交 0c36669f / c2e74aac)

`human_jury.py` 校验裁决已有一段时间,但没有表、没有端点、没有界面:评审无法留存,
重启即丢,UI 只能显示空占位。补齐的链:

- `design-lab-state-jury-v1.sql`:append-only,`UPDATE`/`DELETE` 触发器直接拒绝。人工签署的
  凭据被就地改写等于重写项目引用的验收历史。
- `jury_store.record()`:裁决必须绑定**同一项目内 ACTIVE 版本**且摘要与该版本一致;
  Agent 署名按类型名拒绝;已取代的记录不能被再次取代(否则验收链分叉,"当前裁决"无定义);
  proposal 永远不进 `verdict` 列。
- `connect()` 委托 `asset_store.connect()`,不在这里第二次实现路径策略与 assets-v2 迁移。
- 端点 `GET/POST /api/projects/{id}/jury{,/verdict,/proposal}`;读回带
  `reviewable_versions`(含摘要),所以评审人不需要手抄哈希。
- `JuryReviewError` 在通用 `ValueError` 分支之前映射:拒绝原因是有用信息
  ("artifact_sha256 does not match the version being judged"),塌成 `INVALID_REQUEST`
  就等于告诉用户"你的判断有问题"。
- 同一提交重发是重放(返回已存记录),同 id 不同内容是 409。浏览器在丢响应后重试
  不该产生第二份签署。

界面挂在预检页的新段落下:读回当前裁决、Agent 建议数、是否真的存在人工验收,空态明说
"尚无人签署的裁决"。签署表单从 `reviewable_versions` 取版本与摘要。

两条门抓到我自己写错的东西:
1. 表单只收了说明没收 `score`,而合同要求每条准则有 0–5 分值 —— 每次提交都会 400。
   新增 `test_jury_review_form_contract.py` 把页面自己声明的轴/权重/文档形状送进
   `record_verdict`,UI 从此不可能发出合同拒绝的表单。
2. 两个新 seam 起初没有 `shapeNotice`,并把拒绝 catch 成 toast。appshell 门要求读回被拒时
   整个路由以失败开头,屏上不能留着旧内容 —— 改为让拒绝冒泡到路由,该批失败路径覆盖
   从 8 个视图涨到 9 个。

## 3. 产物级预检:能量多少就说多少(提交 d74e7c41)

`design-lab/production/profiles/*.json` 声明了 print 11 项、digital 9 项、video 9 项的
`pass|warning|fail` × `blocker|high|medium`,而树里唯一的"检查器"只走目录并返回五个字符串码。
`/api/task-preflight` 探的是任务工具与资源,是另一件事 —— 页面以前也这么标,没撒谎,但
产品确实没有产物预检。声明了却发不出的词表是假绿灯发生器:读者看到清单就以为检查跑过。

现在的发射器守三条:

* 只报 profile 声明过的检查项。漏报一项就是靠省略变绿,多报一项同样错,两个方向都有断言;
* 每条结论带 `criterion`,写明判据;profile 自己没给阈值时,直接说明判据来自本模块;
* `PASS` 要求每条适用检查都被真量过且通过。出现任何 `NOT_MEASURED` 结论封顶
  `INCOMPLETE` —— 一个本构建读不了透明合并的 PSD 报 `INCOMPLETE` 并给出原因,
  而不是沿用其它检查的绿灯。

用 Pillow 从真实字节量到的:像素尺寸、有 DPI 时的物理尺寸与有效 PPI、色彩模式对 profile
意图、alpha、容器格式、以及按归档自带清单核对的链接存在性与摘要。
明确标为未量的:出血、安全区、叠印、透明合并、PDF 配置、页序、字体嵌入/转曲、时长、
帧率、响度、编解码器、以及没有声明上限的体积项。

端点 `POST /api/projects/{id}/bundles/{bundle-id}/preflight?profile=…`:bundle 从状态库按 id
解析并限定在本项目,归档字节按登记摘要校验,成员路径越界直接拒绝 —— 页面不接受文件路径。

一条 profile 覆盖度事实记在此处而不是藏起来:`missing-links` 只由 print profile 声明,
所以 digital 归档不做链接校验。这是 profile 的声明范围,不是本模块漏实现;链接图对
PNG/JPG 这类数字交付没有对象可查,把它加进 digital 只会凭空多出一条恒真的检查。要改
得改 profile,并由改的人负责那条检查在数字域里究竟量什么。

## 4. 本波次未闭合的(不假装做完)

* `asset_publication` 恢复日志跨根后仍指旧根,`recover_publications(store_root=新根)` 按
  `store_root=?` 选取会静默跳过 PREPARED 行。按 owner 既有裁决只重定位 `artifact.path`,
  签名执行记录不改。
* 重启对账的 continue/reconcile/pause 机器齐全且读回诚实,但 `reconcile_receipted` /
  `quiesce_*` 在产品代码里没有调用点,启动只做 `RUNNING→OUTCOME_UNKNOWN` 改名。
* Design System token 写路径、ResearchFinding/MethodCard 持久化:仍是合同/CLI 层,
  没有端点与界面。
* D-6(首屏壳统一)属 owner 待裁事项:一次尝试把它做掉后被回退,因为它打断了钉死的
  `.app-nav` 几何门(见 `5cc5380e`)。
* 真实宿主 E3、真人 Jury E4、发布 E5 需要人与宿主,不是工程量问题。

## 5. 第二段(2026-10-08 追加,提交 a8e0c67c / d5192069 / edf0c85a)

第 3 节的界面读回与第 4 节的取消语义在本段闭合;另外抓出一个我自己写坏的门和一个是
非门。

### 5.1 预检的界面读回(提交 d5192069)

挂在交付中心:选交付包 + 选 profile + 点预检,读回判定、未量计数、每条结论的 detail 与
**判据**,并保留 `NOT_MEASURED` 行 —— 过滤掉它们就是让 INCOMPLETE 冒充通过。页面不自动
预检:没有人选过的交付包,结论只能是猜测。

两条门,分工不同:
- `test_artifact_preflight_ui_contract.py`(静态合同):页面提供的 profile 集合与磁盘上
  的 profile 文件、路由自己的 `?profile=` 模式**三方相等**;URL 必须由 project id +
  bundle id 组成;判据必须上屏;服务的四个判定词都必须有对应着色。
- `appshell.mjs` 第 ⑥ 段(行为):对**已构建的 bundle** 驱动 —— 不点击就发出的请求算失败、
  一次点击恰好一个请求且落在所选交付包自己的路由、判据与未量项出现在屏上、被拒后旧判定
  被替换而不是叠加。

五个产品变异各自把对应的门改红(判据丢失、过滤 NOT_MEASURED、多提供一个 profile、未点
先显示判定、URL 改成传路径),门是有牙的。

这一段还抓到一条我自己的工具缺陷:**`vite build` 失败时旧 bundle 留在原地**,下一个门量的
就不是它声称的字节。第一次 falsify 就撞上这个 —— 我的变异把括号写坏了,构建失败,
appshell 报的是上一个变异的错。之后所有变异脚本都先断言构建返回 0。

### 5.2 我上一波写坏的门(提交 d5192069)

`0c36669f`/`c2e74aac` 的评审列用的是 `<div class="list">` + `<div class="list-item">`,
被 `ListItemIsReallyAListMember` 两条断言抓到:看着是列表,读屏软件里什么都不是,而且空态
`<p>` 直接坐在 `<ul>` 的位置上。改成真 `<ul>/<li>` + `emptyLi()`。该门把容器数钉成精确清单
(为了让迁移漏掉一处就必然报警),所以容器数 30→31 是**有意的清单增长**,注释里点明了新调用
点。全量运行确认这两条失败属于我,不是既有基线。

### 5.3 身份门把 wheel 当文本读(提交 a8e0c67c)

`verify_identity_gate.py` 遍历工作树时按 UTF-8 读 `dist/*.whl`,于是**每次本地打包都让门变红**,
而且它检测不到任何东西;CI 没有 `dist/`,所以 CI 永远看不见这个缺陷。同时 `.zip` 早就被
"二进制跳过"放行 —— 而 zip 正是旧包名会藏身的地方:成员名。现在 `.zip`/`.whl` 按成员名匹配,
打不开的容器按 fail-closed 记为违规。

发出去之前先量过:活动树里的两个容器(design-lab 自己构建的 wheel、docs/audits 下冻结的
任务包归档)成员名都干净,所以没有新的红。归档里的旧名字在成员**正文**里,这一门不声称读
正文,那条限制写在这里而不是藏起来。

### 5.4 取消未被确认却成功了(提交 edf0c85a)

`POST /tasks/<job>/cancel` 只把尝试推到 `CANCEL_REQUESTED` 并回 202;适配器没有任何"我停了"
的事件,所以 `acknowledge_cancel`(通往 RECONCILING 的唯一路径)在产品代码里**没有调用点**。
剩下的两种结局里,宿主仍交付的那一种会走 `_finish` 提交 `RECEIPTED`,备注里看不见那次取消,
任务读回也不带任何取消字段 —— 一个被拒绝的操作在所有界面上与一个没人反对的完成**无法区分**,
包括那句写着"请求取消不等于已取消"的页面。

改的是可读性,不是状态:`RECEIPTED` 保留,因为字节确实发布并读回了。现在尝试备注写明取消
未被适配器确认,`/tasks` 带 `cancel.requested/acknowledged`(用 COALESCE,因为 v2 之前的尝试
可能没有 resolution 行),交付中心把这一行标成 取消未确认。两条单测钉住后端 —— 含"普通完成
必须是 requested:false",这个新字段不能读成"总是被取消过";appshell 第 ⑥ 段两种载荷都真渲染。
删除标记会触发正向断言,`||` 代替 `&&` 会触发反向断言。

`acknowledge_cancel` 仍然没有生产调用点:那需要宿主协议先有一种"已停止"的事件,属于协议问题,
不是补一根线就能做完的事。

### 6. 链路逐条判定与本轮新抓到的事实(2026-10-08,含只读审计的交叉核对)

一个只读审计子智能体 gave me a table; I re-checked its claims instead of pasting it, because
two of them did not survive contact with the code.

| 链路 | 判定 | 依据 / 仍需 |
|---|---|---|
| 合同 | PARTIAL | `design-lab/schemas/contracts/*.json` 32 份在 `src/design_lab/` 里**一个读者都没有**;产物预检的 schema 与发射器字段名待对账(子任务进行中) |
| 后端 | REACHABLE | `http_service.py` 路由表 |
| 前端 | PARTIAL | `#/domains` 之前无任何后端;`#/collaboration` 属本地单机模型的诚实空页 |
| 持久化 | REACHABLE | 新增 `design_system_token`、`delivery_receipt_v1`、`jury_record` 三类真表 |
| 读回 | PARTIAL | 重启读回有;**启动恢复的摘要目前只上 stdout,没有路由也没有界面** |
| 质量 | MISSING | `assurance/qa_plane.py` + `quality_record.py` 只有测试与 handoff 脚本消费;产品里没有路由、没有 CLI 动词,门开不了 |
| 预检 | REACHABLE(不持久) | 交付中心真能跑并读回;结论**故意不落库**(见下) |
| 交付 | PARTIAL | 回执已落库并可 CLI 读回;`receipt()` 还没有 GET 路由;PDF/Video/3D 仍不产出 |
| 证据 | PARTIAL | `#/evidence` 只投影设计层与交付包计数,不显示 jury、预检、回执 |

我自己核对出来的四条:

1. **rights 不是门,是常量。** `native_assets.py:36,99`、`image_assets.py:72,140`、
   `native_bundles.py:126-156` 一律把 `'NOT_REVIEWED'` **注入**响应 —— 状态库里没有 rights 列,
   全仓没有任何 `UPDATE … rights`。所以 `shell.ts:814,1851` 那句
   `b.rights === 'NOT_REVIEWED' ? warn : b.rights` 的 else 分支是死代码:这个标签永远不会变。
   AGENTS.md 承诺的 Rights gate 因此是"声明了但没有实现",已列为待办,不是工程量之争。
2. **审计子智能体的一条结论是错的。** 它说 `#/research` 已接后端却仍写着"未开放"。实测
   `http_service.py` 里没有任何 research 路由,`shell.ts:296` 那句话是**诚实的**。
   W13(ResearchFinding/MethodCard)确实整体缺失 —— 结论方向不同,处理方式也不同:前者要改注释,
   后者要补链路。
3. **活动账本自 2026-09 的 R5 迁移起就没有 schema。** 唯一存在的
   `task-ledger-r3.schema.json` 钉的是 `r3-v1` / `DL-TP-20260906-R3` / `^R3-\d\d$` / 要求
   `acceptance`,拿它校验活账本得 105 条错(69 条 id 形态、28 条缺 `acceptance`、外加
   `predecessor`/`definition`/`reassessment` 未声明、artifact 形状不同、evidence 有 maxItems)。
   但把**冻结的 R3 前继账本**拿去校验同一份 schema,得 0 条错 —— 所以 r3 schema 不是烂文件,
   它管的是 r3 那份;真正的缺口是迁到 `r5-v1` 时没人写 r5 的 schema,而 AGENTS.md 早就把
   `r5-v1` 说成"只是版本标识,不是文件路径",等于把这个缺口写在文档里挂着。
   现在补 r5 schema,并让门按账本自己的 `schemaVersion` 选文件:`schemaVersion` 指不到文件就是
   硬失败(这次的根因正是一个没有文件背后的版本串)。
4. **`audit_event` 只写不读。** `asset_store.py:144,250` 在写,产品代码从不 SELECT,
   只有 `test_asset_store.py:99` 读。要么把它读出来,要么停止写 —— 一个只有写入的日志看起来
   像审计线索,其实不是。

一个我做的**不修**决定:预检结论不入库。预检是对**当前字节**的一次计算,重新跑很便宜;把
"PASS"存下来就等于给一份可能立刻改变的判定一个持久身份,反而制造陈旧绿灯。要留的是"跑过、
跑了什么、结论是什么"这一类**事件**,不是可被反复读取当成现状的判定值。`#/evidence` 因此应当
读回 jury 与回执,并让预检保持"当场跑"。

## 7. 第三段:入口与安装态(提交 181ce73a / faedcc27 / fa5db57d)

### 7.1 官方启动命令被自己打死了,而我的定向门全绿

`fa69afc0` 给 `cli.py` 加了 `native-recovery`,其中 `recovery = commands.add_parser(...)`。同一函数作用域里
workbench 分支打印的 LISTENING 行写的是 `'recovery': recovery` —— 打的是 **argparse 子解析器对象**,于是
`json.dumps` 抛 `Object of type ArgumentParser is not serializable`,**产品在打印端口之前就崩了**。
serve 分支三行之外打印的是 `recovery_summary`,只有 workbench 分支被同名变量吃掉。

我提交前跑了 `test_native_tasks`、`test_boot_reconciliation`、`test_service_cli`,全绿。漏掉的是启动器自己的
`test_workbench_launch` —— 因为"改了 cli.py"没有让我想到"跑启动器测试"。抓它的是**安装态复验**(见 7.3),
不是门集合。修的时候不止改那一行:把解析器改名 `recovery_command`,让"能被打错的东西"不存在。
修完做一次对照实验:把 bug 放回去,`test_workbench_launch` 在**源码态也 2 个失败** —— 门有牙,是我的
验证顺序没有。

### 7.2 `audit_event` 一直在写,没人读

`asset_store.py:144,250` 写 `asset_version_created:*` 与 `writer_takeover:*`,产品代码从不 SELECT,只有
`test_asset_store.py` 读。写不进问题的日志不是审计线索:它长得像,回答问题时什么都不答。最该被看见的是
`writer_takeover` —— `takeover_writer` 会主动递增 generation 并把资源交给新写者(卡死/崩溃的持有者就是靠它
不再阻塞项目),之后运维第一个问题是"谁在什么时候接管了什么"。

`runtime/audit_trail.py` 用存储自己的路径策略以 `mode=ro` 打开,所以它不可能变成第二个写者;三种"空"分开
(没有状态库 / 库里没有 journal 行 / 这一页读完);actor 保持是 attempt id,不翻译成人名;分页用
`(at, audit_id)` 行值比较,因为只按微秒时间戳排序无法保证不重复不丢。
三条常设断言防回退:src 里必须有人 SELECT 它、读路径必须被 CLI 调用、写必须还在写 —— 否则第一条会被
"把写删掉"这一手悄悄满足。两个削弱(永远报 PRESENT、按 offset 分页)都实测变红。

### 7.3 安装态必须在当前 HEAD 重测,而且要防"用到上一天的 wheel"

全量绑定跑里 `test_packaged_install_serves_the_committed_bundle` 在源码态**合法 skip**,所以本地那句
`OK (skipped=1)` 对安装态什么也不证明。本轮重测:删掉旧 wheel → `uv build --wheel --out-dir dist` → 干净
venv → 装 wheel → **把 wheel 内的 `design_lab/resources/workbench/build/main.js` 与仓内已提交 bundle 逐字节
比对**(相同,208231B)→ 四份能力库输入随包 → `DL_LAUNCH_INSTALLED=1` 下 `Ran 3 tests / OK` 且
**skip 行为 0**。

第一次尝试是假的:`uv build --out dist` 不是合法参数,构建失败,`install` 装的是**前一天的 wheel**,而
`INSTALL_RC=0` 和"导入成功"全都成立。这与 7.1 同族:**producer 失败后,下一个环节会安心地量残留物**。
所以校验脚本现在先删产物、比字节、要求 0 skip,并且失败时也要把日志落盘(第一版抛异常时把证据一起丢了)。

### 7.4 32 份 contracts/ schema 里,只有 1 份是真的

`design-lab/schemas/contracts/` 声明 32 份合同;`grep -rn "schemas/contracts" src/` 为空 —— 运行时一份都不读。
唯一名副其实的是 `design-lab/planar-decomposition/v1`(`analysis/decomposition.py:164` 真的产出它,测试校验的是
**产出的** JSON)。其余 31 份 INERT,其中几份不是"没读"而是**与实现相反**,继续留着就是让下一个读者误信:

- `contracts/delivery-receipt` 钉 v1 且要求 `delivery_id/delivered_at`、禁掉随包 v2 必需的
  `receipt_sha256/job_id/deliverables/axes`(我把两份文件的 const 与 required 并排读出来确认);
- `contracts/job-spec` 钉 v1,而 `creative_job.py` 写 v2,状态库 DEFAULT 还是 v1;
- `asset-manifest` 在同一个版本身份下有两份,字段大小写不同;
- `audit-event` / `operation-intent` 描述真表的必填字段里没有 `schemaVersion`,所以任何真实行都永远不满足
  那份 closed schema。

新门 `verify_contract_bindings.py` 是一张双向清单(32 schema 一行一条 + 48 条路由:6 条 BOUND_SCHEMA、
42 条 SCHEMA_LESS),并把**九条"发出 schemaVersion 但没有对应 schema"的路由记成具名债务** —— 其中一条是本轮
`domain-pack-readback/v1` 自己造的。记账而不是遮掉:本轮另一个门(§5.3)之所以存在,就是因为"声明了但没人
校验"和"没人声明"看起来一样。



每条 evidence 记录都带 `subject_sha` + `subject_files{路径: 摘要}`,这是**局外人唯一能复核
"这条证据到底绑的是哪份字节"**的机制。而 `verify_evidence_artifact_presence` 只看
`artifacts`(记录产出的文档),完全不读 `subject_files` —— 所以我实测了一遍:268 个声明里
201 个能对上所绑提交的 blob,67 个对不上。

对不上的两类原因不同,分开记:
- 4 条实质性过度声明,都在 2026-09-09 那批记录里:3 个摘要不等于所绑提交 a06c1db0 的字节
  (comfy_task.py、test_comfy_task_protocol.py、native_patch_submissions.py),1 个路径在那
  个提交里根本不存在(`generators/comfy_http.py`)。也就是说这些摘要取自当时的工作树,不是
  取自它声称绑定的提交。
- 63 条是"把磁盘上的东西当主体":57 个 `__pycache__/*.pyc`(从来没进过 git),6 个
  `fixtures/.../audio/*.wav`(记录绑 4c9f1849,而那些生成素材是之后才提交的)。

新增 `verify_ledger_subject_binding.py`:一律用 `git show <subject_sha>:<path>` 从对象库取
字节(不碰工作树,所以后来改同一个路径不会改变答案),摘要不符或路径不在所绑提交里就算缺陷;
`design-lab/config` 之外唯一的例外是一张**双向**的 KNOWN 清单 —— 出现新缺陷变红,已修的条目
还赖在清单上也变红,防止它慢慢变成一串"历史原因"。清单是按记录逐条写的,不给通配,别的记录
不能借用同一条豁免。

我没有去改那 4 条旧记录的摘要:把它们"改对"等于伪造证据。做法是把缺陷写在源码里并标日期,
让它阻塞任何新的。顺带一条好消息:我自己这批记录(备份、评审、预检)全部对得上,机制本身
是有牙的。

门自己也被反证过:11 条用例里包含"摘要不同必须报 MISMATCH""路径缺失必须报 ABSENT""提交取
不到必须报 NO_COMMIT 而不是当作通过""豁免是按记录生效不是按路径生效""清单里的条目变得可验证
时必须报 stale",以及一条专门防止 OK 空心化的断言 —— 它比较 `subject_files=` 与 `checked=`
两个计数并要求总数 > 200。该脚本已进 `verify_design_lab.py` 的聚合清单(条数随波次变动,
当前实测值记在 §8 末,不在此处钉一个会过期的数字)。

### 5.6 我的预检界面把 CI 的词表门改红了(而我所有的定向门都没抓到)

`d5192069` 之后直接跑 `verify_state_vocabularies.py` 是 FAIL:

```
ERROR: shell.ts advertises 'PASS' as a status; the service emits only ['BLOCKED', 'READY']
ERROR: build/main.js advertises 'PASS' as a status; the service emits only ['BLOCKED', 'READY']
```

而我把 UI 相关门全跑了一遍都是绿的。原因不是门太松,是我没跑它 —— 这条门只在
`canonical-verify.yml` 里单独调用,**不在聚合清单里**,所以本地绑定运行永远碰不到它。
先补结构:把它加进 `verify_design_lab.py`,让本地与 CI 见到同一套东西。

门的语义也要说清楚。它当初禁 'PASS',是因为 `runtime/task_resources.py` 只发 READY/BLOCKED,
而界面把预检判定写成 'PASS / BLOCKED'。现在有了**第二个发射器**
(`assurance/production_preflight.py`),它的判定真的是 PASS / WARN / BLOCKED / INCOMPLETE ——
所以"这个词本身是假的"不再成立。

改法不是把词加进白名单了事:
- 词表文件 `design-lab/config/state-vocabularies.json` 新增 `artifactPreflight`,带 `sources`
  指向发射它的模块;门双向核对该词表,`VERDICTS` 改了而词表不改就变红。
- 界面里的状态字面量必须属于**某个已声明词表**;没有发射器能产出的词(OKAY、APPROVED、
  自造的 SUPERB)照旧致命。
- 原来那个谎的**形状**继续点名禁止:'PASS / BLOCKED' 仍然致命,因为任务资源预检只发
  READY/BLOCKED。放宽的是词,不是那句假话。

这条门原先一个测试都没有,所以"它还能抓到东西"从来没人证明过。新增
`test_state_vocabularies_gate.py` 9 条,夹具一律是**真实文件 + 一处替换**,并且断言"这一处
替换确实改变了门解析到的集合"—— 我第一次写的 job_store 变异改的是转移表里的值而不是键,
门看不见,测试因此假绿;加了这条断言之后它就没法再假绿。9 条全过,含"历史谎形状仍致命"与
"真树的 PASS 是合法的"(门不能紧到把诚实读成违规)。


## 8. 第四段:"已接受"曾经由一个版本代表整个项目(2026-10-08 追加)

我自己发布的能力里有一个过度断言,读代码时抓到:`JuryReview.list()` 算
`human_acceptance` 用的是 `any(item['verdict'] == 'APPROVE' for item in current.values())`。
一个项目十次修订,只要在任何一次上签过 APPROVE,界面就报"人工验收 已接受"。
这一词是给**项目**下的结论,却由**单个版本**的签字满足。

顺着它查出第二层,而且是存储层的:`publish_version` 从不降级被替换的字节 —— 全仓没有任何
一条把 `asset_version.state` 写成 `SUPERSEDED` 的生产代码(只有测试直接 UPDATE)。
于是 `reviewable_versions` 取"所有 ACTIVE 版本"就等于取整条修订史:
一个资产改十次,评审清单上就摆着十张稿子,给废稿签字也会被记成有效判定。
产品其他位置早已按"当前版本 = 该资产 ACTIVE 里最大的 `version_no`"来读
(`native_assets.list`、`asset_store.current_version`),评审面是唯一没跟上的一处。

三处都是收紧,没有一处放宽:

- 谓词改成"每个在评审清单上的版本都带一个现行 APPROVE",并且**显式**要求清单非空:
  `0 of 0` 在数学上为真,但"还没发布任何东西的项目已被人工接受"是一句假话,所以报
  `NOT_ACCEPTED`。
- `reviewable_versions` 与产品其余读法对齐:每个资产一行,取 ACTIVE 中最大 `version_no`。
- `record()` 拒绝对"已被替换的修订"签字,并把两个 `version_no` 都点名 ——
  以前的拒绝理由只有 `state != 'ACTIVE'`,对废稿毫无约束力。

读回里加了 `accepted_versions` 与 `reviewable_active_versions`,"已接受"从此带着它的
分母;`design-lab/schemas/jury-readback.schema.json` 把这条语义写死(空清单必须
`NOT_ACCEPTED`,`ACCEPTED` 要求分母 ≥ 1)。

反证是三段变异(`.project-local/tmp/falsify_jury_acceptance.py`),每段都必须在指名用例上
以断言失败(不是 ERROR)变红、还原后回到 12 绿:
把谓词退回 `any(...)` → 两条用例红;删掉取最新 `version_no` 的子查询 → 降级签字用例红;
把 `record()` 里"被替换即拒绝"的判断短路 → 同一条用例红。第一次跑这个反证脚本时,第三段的
needle 是我按记忆写的 SQL 文本,和文件里的 Python 字符串拼接形式不一致,0 命中;脚本因此
报 `NEED NOT FOUND` 而不是假装"变异无影响"——这正是它该有的行为。

同族的第二处发射器已经定位、尚未处理:`assurance/quality_store.py:465` 的
`'human_acceptance': 'ACCEPTED' if accepted else 'NOT_ACCEPTED'` 是同一个 `if 非空` 过度断言,
它的 `assessable_versions()` 也仍在取全部 ACTIVE 版本。本轮不并行改它的原因是 worker 正在写
这个文件(见下)。

协作实况值得记一条:同一时间窗里,worker 正在创建
`design-lab/schemas/jury-readback.schema.json` 与
`design-lab/scripts/verify_route_payload_contracts.py`。我在几分钟内读到的是**两个不同版本**的
同一个 schema —— 第一版 `reviewableVersion` 不含 `version_no`,我在中间把它从发射器里删掉,
再跑新门就得到 `'version_no' is a required property` + `MISSING_FROM_EMITTER` 两条红。
补齐后 `VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=5 failures=0`。结论不是谁改错了,
而是共享工作树里"我刚才读到的字节"只是快照,不是事实:改合同之前要重读、改完要立刻用真门重跑。
另记:该门此刻尚未进 `verify_design_lab.py` 聚合清单 —— 一个没人调用的门等于文档,已列入待注册项。

注册状态实测(`ast` 数 `SCRIPTS` 列表元素,2026-10-08):聚合清单 **59** 项。本波把
`verify_artifact_preflight_contract.py` 注册了进去(它此前只在文档里被引用,没人调用),
`verify_ledger_schema_pairing.py` 由 ledger schema 那一路的 worker 同时注册。
**仍未注册**:`verify_route_payload_contracts.py`、`verify_contract_bindings.py` ——
两个脚本此刻正在被各自的作者改写(文件 mtime 在我读到它们之后又变过),把它们接进聚合前先
等其字节稳定,否则聚合变红的究竟是真缺陷还是并发写入就分不清了;这一条留给聚合轮。


## 9. 第五段:预检曾经量的是"碰巧先返回的那一行"(2026-10-08 追加)

`preflight_bundle` 把状态库里的登记解析成"要量哪个文件"时用的是

```sql
SELECT art.path, art.sha256 FROM artifact art JOIN ... WHERE ... ORDER BY v.version_no DESC
```
然后 `fetchone()`。`ORDER BY` 只管版本号,**同一版本登记多个 artifact 时没有任何次序**——
而 `creative/asset_versions.create_version(artifacts=[...])` 明确允许一个版本登记多个产物。
于是"这次交付的预检结论"其实取决于 SQLite 恰好先给哪一行。

这不是我推测出来的:反证脚本(`.project-local/tmp/falsify_preflight_artifact_scope.py`)把
查询退回原样之后,新增用例 `test_a_preview_registered_before_the_deliverable_does_not_become_the_verdict`
立刻变红——它按 `[preview, deliverable]` 的顺序登记两个产物,旧代码量了 **preview** 并把结论
当作整次交付。改法:`WHERE` 里显式取该资产 ACTIVE 中的最大 `version_no`(与 §8 里评审清单同一条
规则),`ORDER BY CASE art.role WHEN 'deliverable' THEN 0 ELSE 1 END, art.path, art.artifact_id`
把次序写死;同版本还登记着却没被量的字节,追加一条 `artifact-scope` 的 `NOT_MEASURED` finding
并**重新聚合** verdict —— `run_preflight` 里的聚合规则抽成 `_aggregate`/`_recount`,两处共用一个实现,
避免以后又长出第二个"结论怎么算"。

有一条必须说清楚,不然这条记录就是在给自己贴金:`test_a_newer_revision_is_preflighted_instead_of_the_one_it_replaced`
在旧查询下**仍然是绿的**——旧的 `ORDER BY v.version_no DESC` 本来就把改版取对了,所以这条用例
不是缺陷证明,它只是把"预检当前交付物"钉成契约。真正被反证出来的缺陷只有一个:同一版本内的产物选择。

33 条用例通过(29 原有 + 4 新增),两段变异都在指名用例上以断言失败变红、还原后回到 33 绿;
`verify_artifact_preflight_contract` / `verify_production_preflight` / `verify_state_vocabularies` /
`verify_route_payload_contracts` 四道门同批通过(新 finding 的 `NOT_MEASURED` 属于已声明词表,
没有引入界面可以说而服务发不出的词)。


## 10. 第六段:没人问过的 rights 门,不能写成"正在等答复"(2026-10-08 追加)

`creative/approval.py` 的投影把两件事用同一个词说:

```python
STATES = ("PENDING", "APPROVED", "REJECTED", "REVERSED")
def _projection_state(record):
    if record is None:
        return "PENDING"      # <- 从来没有提交过任何请求
```
`record is None` 是"这个门根本没被打开过",而 `PENDING` 的意思是"已经有人被问、正等人答复"。
RIGHTS 门最常见的真实状态恰恰是前者,于是它读起来像后者——交付前检查会以为审查正在进行,
而实际上没有一个人被要求看过许可证。这违反项目自己写在案的一条规则:**缺席的审查必须停在
NOT_REVIEWED,不能被措辞成已经在流程里**(`interop/delivery_receipt.py` 也正是这样把
`NOT_REVIEWED` 映射成 `NOT_RUN` 的)。

改法是加一个词并把两件事分开,而不是把 `PENDING` 说轻一点:
`NOT_REVIEWED`(没有任何记录 / 该请求已被替代 SUPERSEDED)与
`PENDING`(PROPOSED,已提交、等人答复)。`granted` 仍然只在 `state == "APPROVED"` 为真,
`require_approval` 的失败分支一个字都没动——所以这次改的只是"没做"要说成"没做"。

反证两头都要(`.project-local/tmp/falsify_approval_vocabulary.py`):
把 `None` 改回 `PENDING` → 未触碰门与门清单两条用例红;
把 `PROPOSED` 改成 `NOT_REVIEWED` → "问了才叫待答复"与清单用例红。
42 条用例通过(改动前这两个模块共 40 条:其中断言 `PENDING` 的那条被替换成 3 条语义正确的用例,
`test_an_untouched_gate_reports_not_reviewed_and_still_blocks` 保留了原有的阻断断言);
两次变异都在还原后回到 42 绿。

还没闭合的(如实标注,不假装做完):rights 目前只有这条**审批投影**,仍然
**没有** `rights` 状态表、没有 `/api/.../rights` 路由、没有界面面板、
`design-lab/schemas/contracts/rights-decision.schema.json` 在
`contract-bindings.json` 里仍是 `INERT`(74 个主体的 `config/rights-registry.json` 没有任何
`src/` 代码读取,`assurance/handoff_readiness._rights_gates` 会算裁决但**零个产品调用方**)。
把这条链按 Human Jury 的形状补齐(裁决器 → 只追加表 + 迁移登记 → HTTP 门面与路由 → 面板 →
词表声明 → 反证)是下一步,并且界面一旦要说 `APPROVED`,`state-vocabularies.json` 必须先有一个
真能发出该词的来源——否则 `verify_state_vocabularies.py` 会正确地把它判成界面谎。

> **2026-10-08 追正(提交 `747c14c5` + `4d0910df`,按 HEAD 复核过才写)**:上面这段里
> 除“界面面板”以外都过期了。现已存在:`assurance/rights_ledger.py`(契约从磁盘读取、
> 版本双向比对、封闭的拒绝码表)、`design-lab-state-rights-v1.sql` 的只追加表与
> UPDATE/DELETE 触发器、`rights_review.py` 门面 + GET/POST 两条路由(`http_service.py:301,412`)、
> `rights` CLI 动词、`state-vocabularies.json` 的 `rights` 词表(带真实 `sources`),
> 账本里 `rights-decision.schema.json` 已由 INERT 转 BINDING(带实例与测试行号)。
> 仍未闭合的三条,逐条按 HEAD 验证过:①**界面面板还没有**(任务 #16 正在做);
> ②`config/rights-registry.json` 的 74 个主体仍然没有任何 `src/` 读取者;
> ③`handoff_readiness._rights_gates` 仍然零个产品调用方(只剩注释里的提及)。
> ②③是“数据与一个会算裁决的函数都在,但没人把它们接到链上”,不是措辞问题;
> 把它们接进裁决流程需要 owner 对“什么算一个需要裁决的主体清单”给出判据,
> 我不会用一次自动读取替这个判断做主。


## 11. 本波次提交清单与仍未闭合的口(2026-10-08)

<!-- WAVE COMMITS:BEGIN -->
本波次落仓的提交(63 个,`fc03a303`..`d60edfe4`,由 `git log --reverse --format=%h %s` 直接生成,不手抄):

| 提交 | 说明 |
|---|---|
| `7ee682d9` | fix(runtime): snapshot the state database, and stage what a restore installs |
| `707c067b` | chore(reports): rebind the projections to the backup inputs they describe |
| `701ace9c` | fix(runtime): make a backup prove no production writer moved |
| `71a5e974` | docs(audit): record the backup fixes, and name the new stale artefact instead of hiding it |
| `b713bf3e` | chore(ledger): bind the backup-consistency evidence to the run that proves it |
| `10bf16a3` | feat(runtime): the official launch connects its own page, and the library ships its inputs |
| `1b928576` | fix(workbench): the landing view stops being a second shell, and the bundle follows |
| `5cc5380e` | Revert "fix(workbench): the landing view stops being a second shell" -- D-6 is the owner's call |
| `dcc27769` | test(launch): read the token through the handshake, so the tests cannot keep the leak alive |
| `9c208c78` | test(evidence): name the third stale artefact the launcher change produced |
| `c78ff19b` | test(evidence): compare the drift set without depending on record order |
| `3fb13115` | fix(test): repair the syntax error committed in c78ff19b |
| `e84aabf9` | fix(workbench): stop offering delivery formats the bundle writer cannot produce |
| `0c36669f` | feat(assurance): make a Human Jury verdict storable, serveable and readable back |
| `c2e74aac` | feat(workbench): a reviewer can read and sign jury verdicts from the preflight page |
| `d74e7c41` | feat(assurance): artifact preflight that measures what it can and admits the rest |
| `a8e0c67c` | fix(governance): read a wheel by member name instead of decoding it as text |
| `d5192069` | fix(workbench): the jury rows are a real list, and 交付中心 can preflight a delivery |
| `edf0c85a` | fix(native): a cancel the host never acknowledged stops disappearing into a success |
| `a91d6a27` | feat(governance): check a record's subject bytes against the commit it claims to bind |
| `ed6d84f0` | fix(assurance): a jury proposal is checked against the contract, not just its key set |
| `775eff60` | fix(governance): a second verdict emitter, declared -- and the gate that never had a test |
| `894c526a` | feat(design-system): a token document can now be written, versioned, read back and seen |
| `29c97c3d` | fix(runtime): a restored project rebases its publication journal, and cannot claim clean otherwise |
| `1ea64bbe` | fix(assurance): the preflight payload gets a schema, and the claimed drift was a false positive |
| `23bb997a` | fix(runtime): commit the writer-fence assertion the token append already calls |
| `fa69afc0` | feat(runtime): recovery decisions and delivery receipts are now reachable, not just callable |
| `fda18e93` | test(recovery): make the journal fixtures survive a deeper checkout |
| `27624963` | docs(audit): record the nine-link verdict, and which audit claims did not survive checking |
| `faedcc27` | feat(runtime): the writer journal can be read back, so it becomes an audit trail |
| `17a770a9` | feat(domains): 设计领域 reads the packs that are actually on disk |
| `fa5db57d` | feat(governance): name which contract schemas the product actually honours -- one of 32 |
| `181ce73a` | fix(launch): the official workbench command was serializing its own argparse object |
| `3d12c3f7` | docs(audit): entry-point death, a write-only journal, a fake install proof, and 31 of 32 inert contracts |
| `de9601ed` | fix(jury): one signature no longer stands for the whole project |
| `a587f339` | chore(verify): the preflight contract gate had no caller, and my doc pinned a stale count |
| `47aa7d01` | fix(verify): the aggregate gained a registration before the verifier existed |
| `87524737` | fix(preflight): the registered delivery is now measured, not whichever row came first |
| `76fa17b0` | fix(rights): a gate nobody opened no longer reads as one awaiting an answer |
| `88ea30c1` | feat(governance): five route payloads gain schemas written from live captures, and both gates get callers |
| `0cb1397b` | feat(evidence): the delivery receipt is readable over HTTP, and 证据系统 reads it back |
| `5b8e7d51` | feat(quality): a sealed QualityRecord is stored, readable and reachable from the CLI |
| `14269a36` | feat(workbench): 已接受 now states its denominator on screen |
| `4003ac29` | docs(audit): wave section 11 -- the commit table regenerated from git, and the open ends split by who can close them |
| `08d0a01d` | fix(assets): the raster library read a revision history as if it were one current version |
| `cd14f0e4` | fix(assets): a raster asset registering a second file was listed twice and could not be served |
| `81c51812` | fix(native): one asset that registers a preview was listed twice and answered 404 on verify |
| `072dab84` | fix(delivery): a bundle that registered a preview could not be downloaded |
| `601a6422` | fix(backup): a signature that landed inside the backup window was not seen by the quiescence proof |
| `747c14c5` | feat(rights): the RIGHTS human gate gets a store, a route, a verb and a word for "nobody filed" |
| `4d0910df` | fix(backup): PROVED_QUIESCENT only ever covered the tables it happened to name |
| `e5e697fa` | docs(audit): correct my own rights status claims against HEAD, not against memory |
| `0ddfa2d3` | fix(rights): resending a decision that stated nothing for an optional field is a replay |
| `53fbecb1` | test(evidence): register the fourth drifted binding the ledger now carries |
| `8f0d4f98` | fix(verify): the identity gate could report a clean tree after examining no files |
| `575df868` | docs(audit): retract my own falsification claim about the identity gate |
| `9760a888` | docs(audit): the record's own citations were measured, and why that check is not a gate |
| `3da7bbe4` | docs(audit): a mis-anchored falsifier produced the mirror error -- a false "not enforced" |
| `f9626391` | docs(verify): measure the identity floor against the environment that actually runs it |
| `d5b5b1d6` | fix(rights): an unruled licence state could reach READY_FOR_HANDOFF |
| `80d2241c` | feat(research): ResearchFinding becomes persisted, routable state with its own read-back |
| `3548bc52` | feat(rights): the Human RIGHTS gate gets a Workbench panel that can decide it |
| `d60edfe4` | feat(workbench): 研究洞察 reads its findings, and its own capability table can no longer lie |
<!-- WAVE COMMITS:END -->

仍未闭合,按"能不能由我自己关掉"分开列:

**我这边继续做的:**
- ~~rights 链:裁决器 → 只追加表 + 迁移登记 → HTTP 门面与路由 → `rights` CLI → 词表声明 →
  `contract-bindings` 行由 INERT 转 BOUND → 界面面板 → 反证(§10 末的清单)~~ —— 除**界面面板**
  外已在 `747c14c5`/`4d0910df` 闭合;逐条按 HEAD 复核的追正见 §10 末。
- ResearchFinding / MethodCard 仍无端到端持久化与读回。
- 聚合清单现在 62 项(本波注册 5 处:artifact preflight 合同、ledger schema 配对、
  contract bindings、route payload、current-version 约定);所有新门都要在最终 HEAD 上随聚合与绑定运行再跑一遍。
- 绑定运行的证据追加 + `reports/current/*` 投影再生成(`--check` 目前报 DRIFT,因为本波
  新增了测试模块与门)。

**必须由人或外部条件闭合的(BLOCKED,不伪造):**
- 真实宿主 E3(Photoshop / Illustrator 实拍读回):需要 owner 明确授权去操作正在使用的宿主文档。
- 真人 Jury E4:需要真人签署;我不会代签或伪造 attestation。
- 发布 E5:需要 release 与 exact-SHA CI 上下文;推送与发布按授权逐次判断。
- D-6:落地工作台与主壳统一 —— `apps/workbench/shell.ts` 的 `.app-nav` 几何门钉住了现状,
  这是两个壳的合同问题,不是顺手能改的样式。
- 本地浏览器门会**按名跳过**(`test_workbench_ui_audit_gate` 需要 bundle 与 HEAD 一致且需要
  playwright)。跳过记为跳过,不算覆盖;绑定运行里 `skipped=0` 只在非浏览器集合上成立。


## 12. 第七段:同一个缺陷今天犯了四次,于是它变成一条门(2026-10-08 追加)

§8(评审清单给了废稿)、§9(预检量了碰巧先返回的行)、§10/5b8e7d51(一个主体替整个项目出证)
是同一个问题的四个面:**`publish_version` 从不降级被替换的字节,全仓没有任何生产代码把
`asset_version.state` 写成 `SUPERSEDED`,所以 `state='ACTIVE'` 等于整条修订史。**
第四次是本轮扫描时新抓到的:`image_assets._read` 也只筛 `state='ACTIVE'`,于是
- `list()` 把同一个 raster 资产按修订次数重复列出(**实测**:去掉规则后新用例就在这条断言上红);
- `content()` 要求 `len(rows) == 1`,否则 `raise ImageAssetError(404, 'ASSET_NOT_FOUND')`
  —— 一个存在的资产没有确定的读取结果(**这是读代码得到的事实**,不是我测到的现象,
  因为同一用例里前面的重复断言先失败)。

产品其他位置早已按"`version_no` 最大的 ACTIVE 行 = 当前版本"来读(`native_assets.list` 两处、
`asset_store.current_version`),所以修法不是发明新约定,而是**把已有约定写成必须说出来的话**:

`design-lab/scripts/verify_current_version_rule.py` 用 AST 取每个模块里的字符串常量,找出同时含
`asset_version` 与 `state='ACTIVE'` 的 SQL,要求**同一条语句**里出现
`MAX(<别名>.version_no)` 或 `ORDER BY <别名>.version_no DESC`,或者它本就钉在某一个
`version_id = ?` / `sha256 = ?` 上(重发布同一次字节不需要回答"哪个是当前版本")。
它拒绝的是谎,不是数字:新增一个合规读取器不会动任何计数;扫描到零条语句判 FAIL(空扫描和干净
树不能共用一个结论);豁免表若指向已经不存在的语句判 `STALE_EXEMPTION`。

实测 11 条 ACTIVE 读取:`RULED=8 / PINNED=3 / UNRULED=0`。`test_current_version_rule.py` 8 条
用例用**合成夹具**逐条打出各分支(合规两类、两种钉法、裸 ACTIVE 必须点名 `UNRULED: offender.py`、
空目录、不存在的目录、失效豁免),另外两条真的断言"活树干净"和"这条门已在聚合清单里"
—— 一条没人调用的门只是文档。门已注册,聚合现为 62 项;`test_gate_reachability` 4 条仍绿。


## 13. 第八段:同一约定还有两处没人测过的读取,这次是实测到的(2026-10-08 追加)

§12 的门只保证"语句里说了哪个版本是当前版本",它不检查**一个资产登记多个文件**的情形。
顺着这条线又找到两处同类读取,而且 `NativeAssets.list` / `Bundles.list` / `verify()`
**过去没有任何测试**(仓里只剩 `test_bundles_list.py` 的 `__pycache__` 残骸,源文件早已不在):

- 两处列表都 `JOIN artifact`,于是一个资产登记了 preview 就在清单里出现两次;
- `verify()` 与 `content()` 一样要求 `len(rows) == 1`,否则 `NATIVE_ASSET_NOT_FOUND`。

区别是这次缺陷是**测出来的**,不是读出来的:
`.project-local/tmp/falsify_native_listing_rows.py` 把新增的"取 deliverable、按 role 再按 path
的唯一 artifact 子查询"删掉之后,`test_verify_still_answers_for_an_asset_that_registered_a_preview`
以产品自己抛的 `ImageAssetError(404)` 变红 —— 一个就在磁盘上的资产回答"不存在";清单重复那条同批变红。

修法是同一句约定:`f.artifact_id = (SELECT g.artifact_id FROM artifact g WHERE g.version_id =
v.version_id ORDER BY CASE g.role WHEN 'deliverable' THEN 0 ELSE 1 END, g.path LIMIT 1)`。
预览文件的**名字故意排在 `native.psd` 之前**,所以只按 path 排序的写法会送错字节。
5 条新用例通过(含"未知资产仍按正确理由 404",防止修复把"没有行"偷换成"成功");
`verify_current_version_rule` 仍 `OK statements=11 RULED=8 PINNED=3 UNRULED=0`。

两条反证脚本自己也各修了一次分类错误,记下来是因为它们都会伪装成"门有效":
1. 我原先把"以 ERROR 变红"一律当成可疑(纪律是"断言失败而不是 ERROR 才算感到"),但这里 ERROR
   恰是产品自己抛的 404。把 SyntaxError/ImportError/sqlite 错误与产品异常分开之后判定才正确。
2. `falsify_acceptance_denominator_ui.py` 第一次跑出两个假"感到",因为它只改 `shell.ts`,而
   appshell 门在 vm 里执行的是 `build/main.js`(源码只在另一段里被 grep)。它现在先 `vite build`,
   构建失败就拒绝跑门。

顺着这条约定还查到第三处:`NativeDelivery.content()` 虽然钉住了 `v.version_id=?`,但它同样
`JOIN artifact` 并要求 `len(rows) == 1`,所以一个登记了预览文件的交付包**下载时回答
`404 BUNDLE_NOT_FOUND`** —— 这次不是读出来的,是删掉子查询后由产品自己抛出来实测到的
(`.project-local/tmp/falsify_bundle_content_row.py`)。修法与上面同一句约定。
`RECEIPT_QUERY` 里的 `JOIN artifact` 则是有意为之(用连接当"该版本确实发布过产物"的过滤条件),
读取用 `fetchone`,重复行不改变结论,因此不动它 —— 记录在此是为了让下一个人不必再猜。
46 条 delivery 范围用例通过。


## 14. 第九段:备份的"没有人在写"证明,看不见人工签署(2026-10-08 追加)

`project_backup.py` 的静默证明由两部分组成:活动查询(租约、未完成 attempt、宿主守卫)
加 `COUNTER_QUERIES`(只增计数器的前后对比,用来抓"在抓取窗口里开始并完成"的写入)。
但 **`jury_record` 与 `quality_record` 都不取写租约** —— `jury_store.record()` /
`quality_store.record()` 直接 commit —— 也不在任何活动查询里。于是:一次人在页面上签裁决的
动作正好落在备份窗口内时,前后两次读取的活动集合仍然为空,归档照样写着
`productionQuiescence=PROVED_QUIESCENT`,而那份签名**不在这个包里**。
这是"用一次证明掩盖另一类写入",与 §5.4 那个"取消未确认却报成功"是同族。

修法是把这两张表加进计数器集合(缺表时 `_read_activity` 本来就跳过,所以对旧库安全),
并让用例真的在窗口里签一条:`_database_snapshot` 被包住,签名落在前后两次读取之间,
`create_backup` 必须以 `moved during the backup window` 拒绝,且**不留半成品归档**。
反证:删掉这两行计数器,用例立刻在"备份没在看的表,就看不见它动"这条断言上红
(`.project-local/tmp/falsify_backup_watches_human_records.py`),还原后 43 条绿
(其中 1 条是本仓既有的按名跳过,不是本次新增)。

同一族里我此刻**不**动的两处,理由是它们不是谎而是设计选择:`RECEIPT_QUERY` 的 artifact 连接
是故意的 EXISTS 过滤并用 `fetchone` 读取(重复行不改变结论);
`delivery_receipt_v1` 有租约与代际围栏保护,已经在活动查询覆盖范围内。
rights 表落地之后必须同样进入计数器 —— 该要求已写进任务 #10 的验收条件,不是事后追认。


## 15. 第十段:"没有人在写"这句证明,覆盖面原本是猜的(2026-10-08 追加)

§14 修完两张表之后,把这条覆盖问题一次量清楚:用大小写不敏感、覆盖
`INSERT / INSERT OR REPLACE / INSERT OR IGNORE …` 全部拼法的正则,从 `src/design_lab/**` 抽出
**产品真的会写的状态表**,再与 `project_backup.py` 里出现过的表名相减。测得 18 张状态表、
14 张有产品写入路径,其中 8 张当时不在证明的视野里:
`project / asset / approval / audit_event / job / job_attempt / operation_intent / rights_decision`
(每张都带写入者文件名归属,不是我看着表名猜的)。

这些表全部不持写租约,却都会被产品直接 commit。也就是说 `PROVED_QUIESCENT` 这句话覆盖的
只是它列出的那些表,其余表在备份窗口里怎么动它都不知道 —— 一句关于整个状态库的结论,实际
建立在一部分库的观察上。八张全部加入 `COUNTER_QUERIES`(缺表时 `_read_activity` 本来跳过,
对旧库安全)。

覆盖关系本身变成一条测试:`test_backup_watches_written_tables.py` 双向检查 ——
"有写入但没被计数"判红,"豁免表指向一张已经不写入的表"也判红,空推导判红
(断言 written ≥ 12,否则正则一坏全套断言就假绿)。两个方向都反证过:删掉一行计数器 →
盲表用例红;把计数器名字改成 `approvals` → 同一用例红(真实表变盲)。
还原后同批绿:覆盖 5 条 + 备份 43 条(1 条既有按名跳过)+ rights 58 条。


## 16. 追正:`8f0d4f98` 那条提交对反证的说法是错的

那条提交写"把 walk 指向不存在的目录 → 改前会打印 OK total=0,改后以空洞原因失败"。
**这句不成立**,它撞的其实是两条不同路径:

- `os.walk(ROOT / 'no-such-directory')` 会让 `onerror` 回调把
  `active directory unreadable: [WinError 3]` 追加进 `hits`,而 hits 非空在**今天之前就已经失败**
  —— 它证明的是既有规则,不是我新加的地板线;
- 真正证明新地板线的是另一个变异:计数器 `SCANNED['files'] += 1` 改成 `+= 0`,于是 hits 为空
  而 scanned=0,才打印出
  `IDENTITY_GATE=FAIL scanned=0 total=0 reason=the walk examined too few files to be a check at all`。

我第一版反证脚本在**打印阶段**被 cp936 控制台打断(`UnicodeEncodeError: 'gbk' codec can't encode
character '\u03f5'`),而我从残留输出里看到"它红了"就写了提交说明 —— 红了不等于为正确的理由红。
修好的脚本(`.project-local/tmp/falsify_identity_scan_liveness.py`)现在显式跑两条变异、各自断言
reason 文本、并 `sys.stdout.reconfigure(encoding='utf-8')` 防止打印把自己先杀掉:两条都感到,
还原后 `OK total=0 scanned=3012`。

并入既有纪律:**反证必须断言失败的原因字符串,不能只断言"变红了"**。这与
"退出码/包装状态不是证据"以及"探针自己也要被反证"是同一族。

同一批还登记了账本漂移的第四条(`0cb1397b` 改写了 `test_service_http.py`,由
`r5-bundle-list-route-http-ui-20260929` 绑定的字节比它描述的代码更旧):做法是把条目**连同理由**
加进那份精确清单,并把清单头注释从"只报 2/4 条"补成 4 条 —— 少报覆盖面与不报是同一类问题。
双向反证:漏登记会红;留着一条已经不再漂移的借口也会红。


## 17. 这份记录自己的引用也被量了一次(2026-10-08)

审计文档是别人最不会去复核的那份产物,所以对本波两份文档做了引用检查
(`.project-local/tmp/check_audit_citations.py`):凡**仓库根限定的完整路径**都必须存在于
HEAD(或 gitignored 工作证据根),带 `:行号` 的还必须落在该文件的行数之内 ——
指向一个 120 行文件的第 164 行,和指向一个被删掉的文件,是同一类谎。
严格规则下共 **20 条**可核引用,**0 条问题**。

我**没有**把它注册成门,理由写在这里而不是藏在心里:宽松版(连简写文件名一起匹配)在同一份文档上
报出 15 条,其中大多数不是路径主张而是
①简写(`project_backup.py`、`rights_review.py` 这类只写文件名的提法),
②合成夹具名(我在 §12 写的 `offender.py` 是反证脚本里临时造的模块),
③**故意陈述某文件不存在**(§13 里的 `test_bundles_list.py` 只剩 `__pycache__` 残骸)。
一条门的判断对象如果需要先配一份"哪些提及不是主张"的豁免表,豁免表就会变成新的谎源。
因此它现在是自查工具,不是 CI 断言;地板线设在 15(今天实测 20),只用来抓"匹配器哪天不匹配了",
不承诺任何清单数量。


## 18. 反证脚本自己的锚点,错了两次(2026-10-08 追加)

今天两次被自己的反证脚本误导,方向刚好相反,所以都值得记:

1. **假"感到"**(`8f0d4f98` 的原始说法):变异 `os.walk` 的根目录,红是红了,但红的原因是
   **既有的** `onerror→hits` 规则,不是我新加的地板线。见 §16。
2. **假"没感到"**(本轮):`falsify_domain_readback.py` 第二条想证明"检查器没跑就不给判定"
   这条断言有没有被钉住,锚点挑了 `entry["validation"] = NOT_CHECKED` 那一行。测试全绿,
   脚本于是报"该断言无人执行"。**这是错的**:checker 不可用那条路径在更早的地方就用
   `_pack_entry` 的默认字典(第 126 行 `"validation": NOT_CHECKED,`)构造并返回,
   根本走不到我改的那一行。把锚点换成默认值本身之后:
   `TEETH a pack whose checker was not run is given a verdict anyway -> FAILED (failures=2)`,
   两条诚实断言都有效,`both honesty claims are enforced`。

差别只在锚点是否落在**断言所走的那条路径**上。规则并入 §16 的那一条:反证不仅要断言失败的
原因字符串,还要先确认被改的行确实是该断言的执行路径 —— 否则一次错锚会同时制造
"已证明"和"无人证明"两种假结论,而后者更危险,因为它看起来像是在自我批评。

同批把 §7 遗留的"反证脚本只查阅未重跑"清掉了:`falsify_delivery_receipt_wiring.py` 在当前树上
重跑,**7/7 感到**,每条都带 ran==1 与指名原因。

我自己在这段里也写坏过一次测试:先加的"每个被计数的名字必须是状态表"其实是**错的断言** ——
`native_host_guard_v1` 声明在 `native_tasks.py` 里而非 `.sql`,`FROM sqlite_master` / `PRAGMA`
也会被我的名字正则捞进来,于是它把四五个合法名字报成"不存在的表"。它同时还是**空断言**:
我先把 watched 与状态表集合取过交集,再去断言交集里的名字都在状态表里。删掉它,理由是
"名字打错"这件事已经被盲表断言覆盖了(打错 = 真表变盲),不需要一个建立在错误前提上的额外检查。


## 19. 第十一段:RIGHTS 的"未裁定"状态,原本只会警告(2026-10-08 追加,`d5b5b1d6`)

`handoff_readiness.py` 顶部把三个波段写成字面量,注释称其为
"the frozen rights-registry.json set"。它不是从那份文件读出来的,是一份**手抄的第二权威**;
而两份权威一旦分歧,分歧只朝一个方向暴露:落在三波段之外的状态值走 `else`,
产出一条 WARNING,而 `READY_FOR_HANDOFF` 的判据是 BLOCKER 为空。
于是"一个没人裁过的许可状态"与"没有任何东西阻塞交付"在同一个屏幕上同时成立。

现在未分类状态按名字阻塞。真正把它钉住的是反证而不是这段叙述:
`falsify_rights_band_fail_closed.py` 把四种失败模式逐条装回去,每种都必须由**指定那条断言**变红 ——

| 装回去的缺陷 | 指名的断言 | 首行报错 |
|---|---|---|
| 未分类仍只警告 | `test_unclassified_rights_state_blocks_the_handoff` | `'READY_FOR_HANDOFF' != 'BLOCKED'` |
| 未知值当作 CLEAN | 同上 | 同上 |
| `territory.state` 被平铺读取 | `test_nested_territory_state_is_read_through_its_path` | `'rights:model:h3:territory.state=FORBIDDEN' not found in []` |
| 阻塞波段被清空 | `test_every_state_the_shipped_registry_records_is_classified` | 逐条点名未被分类的状态 |

这份脚本的**第一版自己骗了我一次**:主案例的锚点用错了引号风格,匹配不到任何字节,
于是它把最重要的那条"已证明"静默跳过。现在锚点匹配不到字节会被报成 `NOT TESTED`,
而不是当作通过 —— 与 §18 是同一条病的另一种发作。

新增 `verify_rights_registry.py`,把这份抄本与它所声称的文件绑起来:
**74 条 × 4 个字段 = 296 次分类(284 阻塞 / 8 限制 / 4 干净 / 0 未分类)**;
`counts` 那四个手工维护的数字全部由 `entries` 重新算出并必须相等(74/4/70/4);
重复 subject 拒绝;`generated_from` 5 项与逐条 `evidence_source` 8 项引用路径必须存在。
空注册表被当作失败而不是干净。

**仍未闭合,且我没有替 owner 决定**:注册表列的是 74 个**许可主体**,而读回算的是**本项目提交过的
使用范围**。`cleared = bool(scopes) and len(approved) == len(scopes)` 说的是"提交过的都批了",
不是"该提交的都提交了"。哪一个项目实际用到 74 项中的哪些,是 owner 的 RIGHTS 判断,
本仓没有任何文件声明它,我也没有伪造一份。因此 `DOES_NOT_PROVE` 里那句"本台账不持有需求清单"
今天依然成立,并且现在有了门把它保持在成立状态(注册表一变,门就红)。


## 20. 第十二段:产品自述的能力表,可以是假的(2026-10-08 追加,`d60edfe4`)

`VIEW_NOT_OPEN` 与 `CAPABILITY_REGISTRY` 是 Workbench 里两份**机器可读的自我声明**
(某个 IA 槽有没有后端路由、某项能力是 PLANNED/BLOCKED/IMPLEMENTED)。它们的存在是因为任务包要求
"无 backend 的蓝图页不得声称可用"。但没有任何东西把它们与 `http_service.py` 实际 dispatch 的路由对比过。

研究结论的存储、门面、GET/POST 路由与 `research` verb 落进来之后:
槽位仍在告诉操作人"当前服务没有研究结论的持久化路由",登记表那一行仍写着 PLANNED、
route 仍是 `GET /api/research/…`。这是**反过来的假绿灯**:产品宣传一个它已经补上的缺口,
而且宣传的位置正是读者用来判断该信什么的那张表。

`verify_capability_self_description.py` 双向绑定:声称无路由的槽若有一条"终段字面量与槽同名"的路由
被 dispatch 就红;声称 IMPLEMENTED 的行若它命名的路由不存在也红(只查前一个方向,就能靠把
PLANNED 改成 IMPLEMENTED 来"修好"这张表)。行的 `route` 允许写成散文或省略号,那种值不可匹配,
所以给行加了显式 `slot` 字段 —— 这一条不是装饰:反证里专门有一个用例把 route 换回省略号形式,
此时**只有 slot  linkage 还能抓到谎**。路由清单复用
`verify_contract_bindings.route_tokens` 那台 AST 读路机,两个门不会在"服务 dispatch 了什么"上分歧。
实测:52 条路由 / 32 个终段资源 / 5 行 / 1 个合法无后端的槽(collaboration)。15 条牙测试,
含一份"把视图比对删掉的弱化门副本让同一个谎通过"的反证与四条空扫描地板线。

视图本身现在读这条路由:不画任何完成词(`research_verdict` 为 null 时上屏的是服务自己那句理由),
无来源的主张在本地就拒发而不是发给会拒它的存储,替代链接走查询参数,完全相同的重发保留
`finding_id` 让服务端能认成 replay,而改过的文档必须换新 id,响应没带下来的计数读作 `未读回` 而非 0。

反证(`falsify_research_panel.py`,4/4 感到)顺带抓出两处我自己的方法缺陷,值得记进 §18 那条规则:
1. 两个锚点在文件里**也匹配 rights 的辅助函数**,于是脚本改的是"排在前面的那个函数",
   研究代码一个字节都没动却报 `NOT FELT`。现在锚点必须**恰好匹配一次**,否则报 `NOT TESTED`。
2. 我写的 `/\b共 0 条\b/` 永远不会匹配任何东西 —— JavaScript 的 `\b` 是 `\w` 边界,
   CJK 字符不是词字符。断言改成匹配渲染后的字面形式,该变异随即变红。

`ul class="list"` 容器清单由测量得出 35 → **38**,并且这一批暴露了清单针脚的语义:
它只匹配**恰好** `'list'` 的类名,`'list research-findings'` 这种带钩子的写法会**逃出清单**却仍吃
`.list` 样式 —— 与 §滚动可见那条同形(门的计数针脚比它看起来窄)。三个容器统一改用裸 `list`。


## 21. 本轮的 BLOCKED 与未闭合(照实记,不当完成)

- **真实宿主 E3 / 真人 Jury E4 / 发布 E5**:仍为 owner 门,未自动化,未被任何绿灯冒充。
- **D-6 落地工作台壳统一**:第二个壳仍未收,保持 BLOCKED。
- **`#18` 交付收据承诺的 rollback 引用**(2026-10-08 已闭合,见第 22 段;下面保留的是当时的判断,没有改写):`native_bundles._rollback_of` 写入
  `backup_ref = asset:{id}/version:{version_id}`,procedure 文本声称源版本"未被导出改动且写收据时已核过摘要";
  读回侧从未解析这个引用。修它要把收据路由的响应换成信封(`receipt` 文档本身受 `receipt_sha256`
  自摘要约束,**不能**直接往里加字段,否则响应与它自己声明的摘要不再一致),连带 route payload schema、
  contract-bindings 行、UI 文本与双向反证。我没有把它拆成"先写一个没人调用的解析函数"入库 ——
  那正好是本文反复报告的"声明了但没人读"这一类。
- **MethodCard**:`design-lab/schemas/method-card.schema.json` 与 `asset-counts.json` 里 77 个
  `method_cards` 之外,`src/` 里没有任何生产/消费它的代码,两种不兼容的定义仍未裁定。
- **两条并行切片是靠我复核入库的**,不是靠它们的自述:两个子代理都在 150 轮上限处停住
  (rights 面板停在"还没有测试断言 chip 颜色"这句中间;research 停在"post-mutation 合并验证"),
  所以我按字节复核了它们的树(tsc / vite build / appshell / shape-notice / CSS 清单 / 词汇门 /
  53+19 条研究测试)才提交。


## 22. 回滚信封落地,以及它先把自己两处含糊照出来(2026-10-08 追加)

第 21 段把 #18 记成 BLOCKED 是因为我不知道要付多大代价;真做下来,链路本身不是难点,**难点是
我原来给它的验收方式**——先记录事实,再记录工具自己的三个错。

### 22.1 链路(每段都有人在读)

`native_delivery.py`: `BACKUP_REF` 只认写入方产出的 `asset:<id>/version:<id>`;
`_resolve_rollback` 一条查询(`ROLLBACK_LOOKUP`,一次 join)给出逐条状态
`RESOLVED / SOURCE_MISSING / OTHER_PROJECT / SOURCE_NOT_ACTIVE / REF_UNPARSED`;
`rollback_proofs` 汇总成 `ALL_RESOLVED / PARTLY_UNRESOLVED / NONE_RESOLVED / NOTHING_TO_CHECK`;
`_rollback_or_unreadable` 把"台账查不动"单独成词(见 22.3);`_load` 一次返回
(文档, 存储摘要, 汇总词, 逐条依据),`receipt()` 取文档,`readback()` 取信封。

路由 `GET /api/projects/<32hex>/bundles/<bundle-native-…>/versions/<v-…>/receipt` 现在答的是
`design-lab/delivery-receipt-readback/v1` 信封。文档本身**不加字段**——它用 `receipt_sha256` 给自己的
字节出证,加一个字段就等于让响应不再等于它自己声明的摘要;新事实住在信封里,信封版本被
`contract-bindings.json` 的那一行绑住(routes 51→53,含研究路由;未付版本清单 3→4)。
route payload schema 是从活体响应抓的,不是照抄的:`receipt` 走 `$ref` 指向
`interop-delivery-receipt-v2`,所以信封不可能把被包裹文档的形状抄歪;`$defs.proof` 的条件式要求
`RESOLVED` 必须带非空 id 且 `source_state: ACTIVE`,而 `REF_UNPARSED` 必须全空。
CLI `delivery-receipt` 与证据页(三张表 + 汇总词 chip + 两句不同空态)都读同一份信封。

词表是数据不是口径:5 个逐条状态 + 5 个汇总词,`state_meaning` 10 条,`does_not_prove` 3 条,
schema 用 const enum + `minItems` 把 5/5/10 三处钉死,`test_rollback_state_classifier.py` 断言
"每个词都带释义且没有孤儿释义",`test_delivery_evidence_ui_contract.py` 双向比对页面的配色表与
emitter 的两份词表(颜色是主张,`ok` 仍只允许给 `RESOLVED`)。

### 22.2 反证工具自己先报错,而不是产品先报错

第一版给出三个 `NOT FELT`,而模块确实红了。原因在工具:它从 ` ... FAIL` 进度行取测试名,而
`unittest -v` 遇到**多行 docstring** 时会把 ` ... FAIL` 缀在 docstring 的最后一行——于是它读到的是
一句话的第一个词(`failed=['The', 'The']`),不是测试名。改成解析末尾的 `FAIL:` / `ERROR:` 汇总头之后,
同样的六个变异全部具名判定。**我没有把这三条 `NOT FELT` 当成"变异没被覆盖"去加测试**——那会把
一个探针缺陷洗成一次虚假的能力补齐。

第二条错是我自己的期望不切实际,三条配对逐条核对可达性后各归各位:

- `NOTHING_TO_CHECK` 塌缩成 `ALL_RESOLVED`:真实交付永远有交付物条目,所以装配级用例结构上到不了
  这条分支。修法是删掉那条不可能的配对,只留两个空文档分类器用例,并把"为什么只在这里判定"写进
  工具,而不是把断言放宽。
- `BACKUP_REF` 被放宽成可选版本半段:`other_shapes_are_all_unparsed` 报 `NOT FELT` 是**清单的缺口**——
  那份"必须解析失败的引用"清单里恰好没有真实记录里存在的那种半写引用。补进清单(不是改期望)。
- 去掉存储列的摘要比较:已有的两个 409 用例改的是 `receipt_json`,会先被 `delivery_receipt.loads()`
  的自摘要校验拦下,列比较那一行**从未被执行**。补一个只改 `receipt_sha256` 列、且断言
  `loads()` 仍然接受文档的用例。

### 22.3 写空态测试,逼出一个词盖住两件事

我给页面补"空态也要渲染"的用例时才发现:`_load` 的 `except sqlite3.Error` 路径返回
`('NOTHING_TO_CHECK', [])`,而 `rollback_proofs` 在文档没有交付物时也返回同一个词。两者共用一个
空列表,含义相反——"这份收据没有条目可查" vs "台账这次查不动"。页面若照词直译,就会把"没查过"
说成"没有可查的东西"。因此新增第五个汇总词 `LEDGER_UNREADABLE`,并把 try/except 从 `_load` 提成
`_rollback_or_unreadable`,好让它可以被单测直接命中(真实路径反而构造不出:删掉任何一张被
`RECEIPT_QUERY` 自己 join 的表,读回在更早处就 404 了)。链路一次补齐:emitter 常量 → 释义 →
helper → 共用装载 → schema 三处枚举与它自述里的两个数字("四条"→"五条"、"九个键"→"十个键")→
页面配色表 → 聚合词 chip → 两句不同的空态。反向塌缩也写成一条变异(`LEDGER_UNREADABLE` 当万能兜底),
它由两条具名用例判定,其中一条是真实交付路径。

### 22.4 一个写在 schema 描述里的假承诺

`rollback_state_vocabulary` 的 description 原本写着"发布出来,好让 Workbench 渲染它收到的词表,
而不是手抄一份"。当时**页面根本没读这两个字段**——颜色来自一张被 Python 门钉住的手抄表。
一句描述不能替实现背书,所以两个调用点现在都对照响应自带词表着色:词在表内 → 照表配色,
词在表外 → 标 `bad` 并明说"不在响应公布的词表内";词表字段缺席 → 不等同于"词不在表内",两条分支
不合并。正反两条断言都在(appshell 主夹具禁止出现该句,变体夹具要求出现),两条各由一个变异判定。

### 22.5 我今天写坏了自己的工具

用 heredoc 修反证脚本里的锚点时,`\n` 被吃成真实换行,脚本自身变成无法解析的 Python——`ast.parse`
在写盘之后才跑到,于是坏文件留在了盘上。已用文件+定点编辑修回,并记进既有偏好:**带转义的改动不走
heredoc / `python -c`**。同一类错误第二次发生,所以它的归处是记忆,不是这段流水账。

### 22.6 本轮数字与仍未闭合

分类器 19 例、装配 13 例、页面契约与 HTTP 与 bindings 与 CSS 清单共 8 个模块 8/8 OK;
`tsc` 干净,`vite build` 确定性(重建前后 `build/main.js` 摘要一致),node 三门(unit / appshell /
shape-notice 31 条接缝)全绿;后端 6 条谎言 + 页面 6 条塌缩,每条具名判定,变异后源文件与 bundle
逐字节还原。`el('ul', { class: 'list'` 容器清单仍是 39(空态与 limits 都走 `<p>`/既有容器)。

不证明的事照旧:`does_not_prove` 三条随每次响应发出——没有执行过任何恢复;`axes.delivery` 仍是
`PARTIAL`,因为没有宿主重开过被交付的产物;真实台账里 `backup-1` / `backup://job-7` 这类写法会走
`REF_UNPARSED` 并原样报出文本,这是如实,不是修复。E3/E4/E5 仍是 owner 门。

新记一条待办(#20):`contract-bindings.json` 的 `emitter` 是 `path:line` 形式,而门只读 `path`——
实测 18 条指针里 11 条的行确实携带该版本字符串,7 条不携带;其中 4 条指向 `"schemaVersion":
SCHEMA_VERSION,` 这类"常量名"行(意图可辩护,但规则无法核验),3 条是真正的错位
(`production_preflight.py:324` 落在 `def _aggregate(findings)`、`jury_review.py:53` 落在 `return {`,
另一条是我今天挪动 docstring 后指向空行)。要么让门读这个行号(行内必须出现版本字符串或其所用
常量名),要么取消这个从不被读取的精度——不能继续留着它假装被检查过。(第 23 段:这条在同一轮里就闭合了。要么读它,要么别写它——留着当一个没人读的装饰,是最贵的那种注释。)

### 22.7 一条从不存在的字段里抄来的引用

写台账的临时装配器把 `software.runner` 拼成
`python scripts/run_bound_test_suite.py --label <标签> -> run_id=…`。但 `run_bound_test_suite.py`
收了 `--label` **却不把它写进回执**:回执里有 `command` 字段,没有 `label` 字段。于是装配器里
`run.get('label', '')` 永远是空串,66 条记录里 **25 条**的引用长成 `--label  ->`(两个空格,后面什么都没有)。
本轮那条我把它换成了回执真实记录的 `command`,后续运行不再产生空引用;那 25 条**不回填**——
标签对那几次运行已经丢了(只有 `run_id` 里那个时间戳还在),按现在的字节重发一遍等于替它们编造
一条当时没被记录下来的引用。可核对的部分仍然可核对:每条都带 `run_id`、`test_manifest_sha256`、
`worktree_digest` 与计数,引用的只是"用什么命令行跑的"这一件事。

教训是给工具而非给 prose 的:**回执里没有的键,就不要在引用里假装它存在**。装配器是
`.project-local` 下的未跟踪脚本,CI 看不见它,所以这类缺陷不可能被任何门抓住——只能靠读到一行
自己产出的记录时,真的去看它说的到底是什么。


## 23. 一个从来没人读的行号(2026-10-08 追加,记 #20 闭合)

`contract-bindings.json` 里 18 条 route 行都带 `emitter: "src/….py:NN"`。门只取冒号左边
(`instance_path()` 把 `:NN` 剥掉),所以那串数字从写进台账那天起就没被读过。今天它当场演示了一次代价:
我在 `native_delivery.py` 顶部多写了一段 docstring,`READBACK_SCHEMA_VERSION` 从第 65 行被推到 72 行,
台账里那一行仍然写着 `:65`,**VERIFY_CONTRACT_BINDINGS 全绿**。

先把事实量出来,再决定规则:18 条里 11 条的行确实携带版本字符串;7 条不携带,其中 4 条指向
`"schemaVersion": SCHEMA_VERSION,` 这种"常量引用"行(意图可辩护),另 3 条是真正的错位——
`production_preflight.py:324` 落在 `def _aggregate(findings)`,`jury_review.py:53` 落在 `return {`,
`native_delivery.py:65` 落在一行空白。

门现在读这个行号。规则与文件半边的规则保持同一口径:那一行要么把版本字面写在代码里,要么引用一个
模块级常量且其值等于该版本;行号缺失、越界、落在 docstring 里,是另外三种各自命名的失败
(`EMITTER_POINTER_SHAPE` / `_OUT_OF_RANGE` / `_IS_PROSE` / `_NOT_THE_VERSION`)。
"一个缺陷一条红"也被写进来:如果这个文件已经不写这个版本了,`ROUTE_EMITTER_MISSING` 才是具体结论,
指针问题不再重复报第二行——我第一次把这条检查插在 rule 7 之后,就违反了自己的 surgicality 约定,
既有那条"变异只应产出一行红"的断言因此变红。**断言是对的,改的是我的门。**

修数据的过程又教了一次同一课。第一版指针修补用的是"行内含版本字符串即可"这条宽规则,于是它把
preflight 行修到了 **文档字符串里的一句话**(:37),而真正的发射点在 :365。收紧后的做法是"在门认为可信的行里
选离原指针最近的一条",并且把 photoshop_com 那条被宽规则误挪的指针还原回 :155——那是一句
`baseline['schemaVersion']='design-lab/photoshop-native-job/v1'`,下标写,是真发射,门认它。
**权威必须是门自己的函数**:最后一遍是导入门、对 18 行逐条调用 `emitter_pointer_errors()` 来判定"要不要动",
而不是在修数据脚本里再抄一份略有不同的规则(抄的那份正好漏了下标写)。

测试 5 条,其中一条把门复制成一个削弱的副本(把 `emitter_pointer_errors` 短路成 `return []`),
证明三条指针用例的红来自规则而不是来自夹具——削弱后的门对同一份被改坏的台账报告零红。
数字:`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=53 dispatched=53 bound=14`,
`test_contract_bindings.py` 28 例 OK,台账 18 条指针现在全部可核验。

不在本轮做的:把 `emitter` 从 `path:line` 改成 `path`+`symbol`(行号天然会腐烂,哪怕有人读它)。
现在的规则让腐烂可见,这已经比装饰强;真要根治,该指的是符号而不是坐标,那需要另立一行合同字段与门的
一次改动,记在这里不当已完成。


## 24. 十七个跑了但一个测试也没执行的测试文件(2026-10-08 追加)

起因是我自己的一条误诊。逐模块验证给出 `204 OK / 1 TIMEOUT / 1 FAILED`,我把 FAILED 那条读成
"重建能力有 13 个错误",记进了待办 #19。真因不在能力,在**测试文件的自举**:
`test_reconstruction_semantics.py` 里 `import reconstruction`,而包在
`packages/capabilities/reconstruction`——它自己不插 sys.path,只靠 CI 那种**单进程 discover**
里先跑过的邻居把路径塞进去。单进程新起就 13 个 `ModuleNotFoundError`,13 个行为一个也没验过;
在 CI 里反倒一直是绿的。也就是说:**"这条能力有没有被验证"取决于谁先跑。**

顺手量了一下整个测试面,量出第二种更安静的形状:
**206 个测试模块里 17 个没有 `if __name__ == '__main__': unittest.main()`**。
`python design-lab/tests/test_x.py` 对它们来说是"导入文件、什么都不执行、退出 0"——
任何按退出码判定的逐模块扫描都会把它记成 pass,我今天记了两次。补上守卫之后,这 17 个文件
合计真的跑出 **184 个测试**,全绿,其中 COM/宿主相关用例是**带原因的 skipped**,不是静默缺席。

新落一个可跟踪的门 `design-lab/scripts/verify_test_selfsufficiency.py`(已挂进
`verify_design_lab.py`,所以 CI 会跑到),四种红各自命名:
`NOT_EXECUTABLE` / `NO_CASES` / `UNPARSEABLE` / `BORROWED_IMPORT_PATH`,并且**空扫描与空根 fail
closed**:声明的第二方根若一个可导入名字都产不出来,说明门在看错的树,此时所有 import 检查都只是
"无话可说",不能报绿。识别 import 自举用两种仓库里真实存在的拼法(`sys.path[:0]=[str(ROOT/'src'),…]`
切片赋值,以及先 `_PKG_ROOT = ROOT / "packages" / "capabilities"` 再 insert 的间接变量),
都从 AST 读——不 `find_spec`、不看 site-packages,因为"这台机器装了 design_lab"会让门的颜色随主机变。

规则本身也错了一次,值得记:第一版 `claims_root` 是"文件文本里出现过 src 或 capabilities 字样 +
有 sys.path 操作",报了 **35** 条违规;换成 AST 只读 sys.path 语句及其涉及的模块级赋值之后,
只剩 **1** 条真缺口(`test_workbench_launch.py`:它给子进程配 PYTHONPATH,自己却不插 src)。
**规则的宽度决定结论的宽度**——35 里有 34 是我的正则造成的假阳,如果照着它们去"修 34 个文件",
我就把一次真发现变成了一次大扫除。

代价也如实入账:补守卫动到了 5 个被 2026-09-27/28 记录当 artefact 的文件
(`test_comfy_http.py` 2 条、`test_illustrator_com_adapter.py`、`test_model_manifest.py`、
`test_photoshop_com_adapter.py` 各 1 条、`test_workbench_native_ui.py` 4 条),
漂移清单从 29 → **38**(11 个路径)。这一批不是文档引起的,是被修的就是代码本身;
处理法不变:不重写旧记录,新记录绑代码。

顺便把 #19 的另一半改口:逐方法计时(每方法一个子进程,90s 上限)显示
`test_reconstruction_evidence.py` 的 37 个方法里,
`test_structure_bounds_and_semantic_target_mapping_are_exact_not_containment_only`
单独用了 **86.2s 并且以 errors=1 结束**。所以那不是死循环,是一个慢且错的方法把整模块的墙钟
顶过了我给的时间盒。原来记的"hang"用词不准,按实测更正;这条错误的性质要单独查,不当本轮已闭合。

门的自测 13 条(`test_test_selfsufficiency_gate.py`),含两条"削弱副本"反证:把入口守卫规则或
自举规则从副本里抹掉,同一份被改坏的树就不再定罪——红来自规则,不来自夹具。当前树:
`TEST_SELF_SUFFICIENCY=OK scanned=207 executable=207 violations=0`。

### 24.1 追正(同日,写完 24 段立刻被打脸的那句)

24 段末尾我写了:"一个方法 86.2s 并以 errors=1 结束……这条错误仍开放"。**这句是错的**,按实测改口。

空闲、单进程、逐方法重跑同三条可疑用例:
`test_full_canvas_raster_overlay_is_rejected_even_when_hash_bound` → **16.384s OK**;
`test_structure_bounds_and_semantic_target_mapping_are_exact_not_containment_only` → **50.833s OK**;
`test_structure_projection_and_provenance_mutations_fail_closed` → **147.274s OK**。

为什么并发会造出红:这个模块的夹具根是**固定共享**的
`.project-local/task-runtime/reconstruction`(条目名 `c5-<pid>-c6-<uuid>`),而其中一条用例断言的恰是
"验证前后该目录里 `c6v-*` 集合不变"——并发的兄弟进程在同一时刻往里面放东西,断言就红;另一条 86.2s
的红同理(它单独跑 50.8s 就过)。第三条根本不是超时,是**我的时间盒比工作短**:90s vs 实测 147.3s。
所以 #19 换性:没有 hang,没有 error,只有"这个模块单进程需要很久(最慢一个方法 147s)",以及"我给
逐模块验证设的 240s/90s 上限本身没有依据"。这不是能力缺陷,是**我的仪器缺陷**,而它已经被写成了一条
待办和一段审计文字——所以这段追正必须留在文档里,而不是悄悄改口。

一并如实记录的残留:被我强杀的两次运行在 `task-runtime/reconstruction` 留下 **124 个 `c5-*` 目录**。
它们不归那条"无残留"断言管(那条只数 `c6v-*` 前缀),所以这个可见的债没有任何门在看。残留本身不是产品
问题——是被杀的进程没机会跑 tearDown。清理只能按 PID 存活判定,不能按名字或年龄:今天列进程时发现另外
两个 `http.server`(00:51 起,属于另一个项目)也挂在 python.exe 名下,**"idle" 不等于"我的"**。

还有一次我自己的操作错误,记在这里因为它是第二次:编辑这条记忆时我用 Edit 替换了段落首行,把该段开头
整句吃掉了,与今天更早那次"在 bullet 前缀上锚定插入"的错同类。已恢复,规则回到:**锚点必须是完整行,
改完重读行首**。

最后在**没有其他测试进程**的条件下重跑了一遍全量逐模块验证(head `cab1ac84`,每模块时间盒 900s,
总耗时 1236s):**207 个模块,206 个 OK,1 个 TIMEOUT** —— 被盒住的正是
`test_reconstruction_evidence.py`。也就是说"这个模块需要多久"仍然没有被量到:盒住的次数从 240s
提到 900s 它还是没跑完,而我唯一一次逐方法计时**被我自己用 `timeout 900` 包住了**,于是量盒子的
仪器先被盒子杀死,那份"每个方法多少秒"的清单永远没有出来——它现在仍是空缺,下一轮要测的是模块真实
总时长与逐方法预算,而不是再猜一个大一点的时间盒。**给测量设上限之前,先确认上限不是被测对象的一部分。**


## 25. 21 个声明对象里,产品真正校验的只有 5 个(2026-10-08 追加)

`design-lab/config/object-model.json` 声明 21 个对象,每个都指向一个 schema 文件。今天之前,所有门
只问过两句:"文件存在吗"(`verify_design_kernel.py`)、"路由返回的形状符合它吗"
(`verify_route_payload_contracts.py`)。从没问过的那句是:**产品代码里,到底有没有人按这个 schema
校验过任何东西?**——还是一个验证脚本在自我循环地读它?

度量口径刻意窄到可grep:一个对象算被引用,当且仅当它的 **schema 文件名** 或它 schema 里的
`properties.schemaVersion.const`(没有 const 时用 `$id`)这个字面串,出现在
`src/`、`packages/`、`apps/workbench/`(=产品)或 `design-lab/scripts/`(=门)。结果:

| 桶 | 数量 | 含义 |
|---|---|---|
| PRODUCT | 5 | research-finding、domain-pack、preflight-report、handoff-package、quality-report |
| TOOLING_ONLY | 9 | brief、command、direction、evidence-record、execution-result、extraction-job、memory-record、project、quality-assessment |
| UNREFERENCED | 7 | artifact、candidate-knowledge、delivery-manifest、design-system、method-card、reference-set、tool-run |

新门 `verify_object_model_backing.py`(已挂进 `verify_design_lab.py`)把这三桶钉住:桶成员必须逐条
在册,每条非 PRODUCT 记录必须写明"今天到底是什么在实现它"(门的长度下限 + 测试要求它点名一个路径
或明确说"无"),计数写死,所以"债还上了却忘了删豁免行"和"某个对象从模型里悄悄消失"两种漂移都会红。

两条仪器错误都留在了测试里,不是留在道歉里:

1. 第一版按标识符做词边界搜索,于是 `design-system`、`artifact` 和 jury record 被判"未实现"——它们
   全都实现了,只是代码写的版本串是 `design-lab/assurance-jury-record/v2`,而对象模型给它起的 id 是
   `quality-report`。**一次假阴就能让人去重建已经在跑的东西**,所以规则退回到只做字面串匹配,门顶把
   这件事写成"为什么不写更聪明的扫描"。
2. 门把**自己的清单**扫进了语料:它的理由里写着 `schemas/bom.schema.json`、`artifact.schema.json`
   这些名字,于是第一次跑就报出 16 个 TOOLING_ONLY、7 个"未在册"。加了 corpus 自排除之后数字才落到
   5/9/7。这一条现在有专门测试:把自排除那两行从副本里删掉,同一棵真实树必须立刻不匹配钉住的计数
   ——**门的证据集合里不能有门自己**。

顺带把 #21 的说法升级了一次:MethodCard 不是"两个形状冲突、需要人裁定"这么轻——object-model 指向的
那个 `method-card.schema.json` **全仓库没有任何代码读它**,而真正被使用的
`visual-quality/master-method-card.schema.json` 走的是研究侧的验证脚本。两个形状、零生产者,这句话
现在由门钉着,不再靠记忆传递。

本轮数字:门自身 11 条测试 OK(含 6 种 scratch 树变异 + 2 种削弱副本);`DESIGN_KERNEL=PASS`;
`TEST_SELF_SUFFICIENCY=OK modules=208 executable=208`;`OBJECT_MODEL_BACKING=OK objects=21
product=5 tooling_only=9 unreferenced=7`。仍开放:16 条非 PRODUCT 记录的逐条裁定(接线、改名或退役)、
#19 的真实时长、E3/E4/E5、D-6、74 主体 rights 台账选择。
from pathlib import Path

DOC = Path(r"D:/All projects/DESIGN-LAB/docs/audits/DESIGNLAB-LAUNCH-REVIEW-PREFLIGHT-2026-10-08.md")

SECTION = """

## 26. 模板是可执行合同的一面：三份 template 全坏，加上 delivery-manifest 的第一次裁定

### 26.1 量出来的，不是推断的

`*.template.json` 这个文件名后缀在本仓库里的意思是"人复制它去填一份真记录"。全仓库一共三份，
2026-10-08 一次扫描量下来**三份都是坏的**，而门链里没有任何一条看得见：

| 文件 | 坏法 | 后果 |
|---|---|---|
| `design-lab/production/handoff/BOM.template.json` | 被自己声明的 `bom.schema.json` 拒绝三次：`$schema` 键落在 `additionalProperties: false` 之外；`items[0].kind` 填的是候选菜单串 `"editable-source \| export \| derived"`；`version` 写 `1.0.0` 而合同钉的是 const | 复制→填空→提交，交上去的一定是无效文档 |
| `packages/capabilities/quality/jury/JuryRecord.template.json` | `$schema` 指 `../../../schemas/jury-record.schema.json`，从 `packages/capabilities/quality/jury/` 解析出来是 `packages/schemas/`——**仓库里不存在这个路径** | 指针本身就是一句谎；顺带 axes 全填 0（合同 minimum 1）、verdict 填菜单串 |
| `design-lab/evals/templates/score-sheet.template.json` | 不声明 `$schema`，只声明 `rubric`；而 `rubric` 的值是**仓库根相对**路径 | 形状无人可验；按文件相对解析它也不存在 |

第四点不是缺陷而是约定：仓库里两种相对基准都在用（`$schema` 按文件、`rubric` 按根），而
已有多个 schema 显式在 `properties` 里声明 `"$schema": {"type": "string"}`——也就是说"实例可以指
回自己的合同"是被维护的惯例，`bom`/`jury-record` 两个 schema 只是漏了。所以这两处补的是 schema，
而不是把模板的 `$schema` 键删掉。

### 26.2 门：`design-lab/scripts/verify_template_contracts.py`

十条规则，全部判"现在为假的声明"，不判会漂移的数量：`TEMPLATE_NOT_JSON`、`TEMPLATE_NOT_OBJECT`、
`NO_CONTRACT_POINTER`、`POINTER_UNRESOLVED`、`POINTER_OUTSIDE_REPO`、`SCHEMA_UNLOADABLE`、
`TEMPLATE_INVALID`、`RUBRIC_AXES_MISMATCH`/`RUBRIC_HAS_NO_AXES`、`NOTHING_SCANNED`、
`INVENTORY_MOVED`（模板清单钉死，新增/删除都必须在这里做一次决定）。校验用**离线 registry**，
由 `design-lab/schemas` 里 116 个 `$id` 组成，因此跨 schema 的 `$ref` 从仓内解析，绝不联网。

写门的过程中被自己的推理抓到一次真缺陷：`schema_errors()` 在不传 registry 时会**去联网取 `$ref`**
（jsonschema 的 `_warn_for_remote_retrieve`），本机 DNS 直接失败后抛出的是
`InteropError`，而门只在 `load_schema` 外面包了 try——一个畸形的 `$ref` 会让门**崩**而不是判红，
跟"候选轴是字符串就 AttributeError"那一类一模一样。于是加了第 8 条 `SCHEMA_REF_UNRESOLVABLE`，
并有专门测试把 label 钉成 `https://nowhere.invalid/x`。第二条仪器不一致也在测试里露了出来：
`TEMPLATE_NOT_JSON` 行写成 `... (exc)` 而不是 `... : exc`，规则名解析不到——统一成冒号格式，
测试从"读到 0 条规则"变成读到正确的那一条。

26 条测试（`test_template_contracts_gate.py`）全部在 scratch 树上注入对应的谎：指向仓库外的
`../../..`、指向远端 URL、draft-07 的 schema、多余键、与 const 冲突的 version、菜单串占位、
少一个维度、rubric 无 axes、非 JSON、非对象、空扫描、双向的在册漂移，以及一条
"构建残留里的同名模板不算合同"（`node_modules` 必须被跳过——这条同时也钉住门不去扫自己的源码）。

### 26.3 占位符怎么裁定

要求"模板自己必须通过合同"就逼出一个必须写下来的决定：封闭 enum 里没有"replace-me"的位置，
任何合法值都是一个**看起来像结论**的值。规则定为**合法且不得声称好结果**：

- JuryRecord 的 `axes` 从 0 改成下限 1，`verdict`/`humanReview.verdict` 从菜单串改成 `REVISE`
  （既不宣称通过也不宣称终局拒绝），而 `deterministic.result` 从 `"OK"` 改成 `"FAIL"`——
  **一份预填"自动化检查已通过"的模板，就是递给复制者的一张假绿灯**，这条改动有专门测试钉住；
- BOM 的 `version` 改成合同 const，`kind` 改成不声称交付物的 `derived`；自由文本字段保留
  `replace-with-…` 措辞，未填状态仍然一眼可见（`humanReview.date` 从假日期 `2026-08-13`
  改回 `replace-with-YYYY-MM-DD`）。

顺带又被自己的仪器骗了一次：用 `grep -c $'\\r'` 判断行尾，四份文件全部报"整文件 CRLF"，而
按字节数出来的结果是**四份都是纯 LF**。这是第 N 次同一类错误，规则照旧：数 `b"\\r\\n"` 与 `b"\\n"`，
不要信 grep。

### 26.4 delivery-manifest：16 条非 PRODUCT 记录里的第一条裁定

`object-model.json` 把 `delivery-manifest` 指向 `bom.schema.json`，而产品里唯一叫 `bom` 的东西是
`production_preflight.py` 拼给链接检查用的 `{'items': [{'id','path','sha256'}]}` 片段——把它送进
自己声明的合同，三项必填、六个 item 字段、五个 provenance 字段全部缺失，**必拒**。这就是门从未
执行过的合同的典型形状。

裁定分三步，只做真的：

1. 片段**改名**，不再冒充清单：参数 `bom=` → `link_manifest=`，局部 `bom_items` → `link_items`，
   两条中文文案把"交付清单（BOM）"改成"链接清单"；四处测试调用点与两个测试函数名同步
   （`..._bill_of_materials` → `..._link_manifest`）。断言一条没删。
2. 新模块 `src/design_lab/assurance/delivery_bom.py` 把边界写进代码：`version` 从 schema 的 const
   **读出来**而不是在这里打一遍；`kind` 由 manifest 的 `role` 决定、`format` 由成员后缀决定、
   `license` 取交付时记录的 rights 状态（没有就 `NOT_REVIEWED`，绝不编一个 SPDX 串）；`source` 对
   input 取登记的资产 id、对渲染产物取 `native-attempt:<attempt>/<host>`，未登记的 input 明写
   `unregistered-input:<name>`。四个字段（`handoff`、`repo_tree_sha`、`tool_version`、
   `generated_at`）**今天没有任何存储记录能说清**，调用方不证明就返回
   `DELIVERY_BOM_INCOMPLETE` 并逐条给理由；给了值就进 schema 校验，不合格返回
   `DELIVERY_BOM_REJECTED`。
3. 让它在能力链上**被调用**：`preflight_archive()` 现在插入一条 `delivery-bom` finding，写不成时
   判 `NOT_MEASURED` 并把 `missing` 列表带在 `measured` 里。前端不需要改——
   `artifactPreflightPanel` 按 `data.findings.map` 全量渲染，而
   `test_artifact_preflight_ui_contract.py` 早就钉住"不许 filter findings"，所以这条 finding 自动
   进入页面并带上它自己的判据。

这里又抓到一条**既有**缺陷，而且是靠一条本来就在那儿的老测试：
`RegisteredArtifactScopeTests.test_bytes_registered_but_not_measured_are_reported_as_unmeasured`
断言 `NOT_MEASURED` 计数必须**随 finding 移动**。它红了，报 `6 != 5`——原因是
`preflight_archive()` 在 `_recount()` **之后**才插入 finding，所以 `archive-digest` 和我新加的
`delivery-bom` 都不在 `counts` 里；两处 `insert` 一直在让聚合数少报，只是原来插的是 `PASS`，
数字看上去刚好对得上。修法是插入之后再 `_recount(result)`，并加一条新测试逐个字比对
`counts` 与 findings 的 tally。**门看不见的那一类漂移，靠的是本来就坚持"聚合不许装饰化"的老断言。**

`verify_object_model_backing.py` 随后自动把 `delivery-manifest` 归入 PRODUCT（`src/` 里现在真的
按文件名加载这份 schema），钉住的成员表和计数一起改：`product=5/unreferenced=7` →
**`product=6 / tooling_only=9 / unreferenced=6`**，那条 UNREFERENCED 理由整行删除而不是改写；
顺手把门里两处"measured against HEAD 0a873fc1"更新为本次真正测量所依据的 `c0d44f00`。

### 26.5 #19：那个"挂死"的重建证据模块，实测 26 分 49 秒

单进程、逐方法、**不加任何 box** 跑完 37 个方法，全部 OK：`TOTAL seconds=1609.5 methods=37
errors=0 failures=0 skipped=0`，最慢一条 289.4s
（`test_structure_projection_and_provenance_mutations_fail_closed`），其次 113.2s、103.4s。
先前记录的"挂死 + 13 errors"因此**不是产品缺陷**：13 条 error 来自我自己让两个套件实例并发跑
同一棵 scratch 树，"挂死"是 `timeout 900` 把测量仪器自己杀了。结论一句话——这个模块本来就慢，
任何给它设的时限都必须以这组数为准，而不是以"我以为一个单测应该几秒"为准。

### 26.6 本轮数字与仍开放

`TEMPLATE_CONTRACTS=OK templates=3 clean=3 schemas_with_id=116`；
`OBJECT_MODEL_BACKING=OK objects=21 product=6 tooling_only=9 unreferenced=6`；
`ARTIFACT_PREFLIGHT_CONTRACT=PASS bindings=1 compared object locations=28`；
测试新增 43 条（模板门 26 + delivery_bom 17）另加 2 条预检接线断言，
`test_production_preflight=35 OK`、`test_object_model_backing_gate=11 OK`。
`verify_template_contracts.py` 已进 `verify_design_lab.py` 的 SCRIPTS，因此不再是一条没人调用的文档。

仍开放：#21 的两个 MethodCard 形状仍无生产者（`method-card.schema.json` 全仓无人读，用的是
`visual-quality/master-method-card.schema.json`）；15 条非 PRODUCT 记录待逐条裁定；
JuryRecord 模板教的是 `jury-record.schema.json` 的 v1 形状，而产品实际写的是
`assurance-jury-record/v2`——这两份 schema 的取舍是一次需要 owner 裁定的形状决定，本轮只修
指针与合法性，没有替它做决定；真实宿主 E3、真人 Jury E4、发布 E5、D-6 落地壳统一、
74 主体 rights 台账选择仍为 BLOCKED。

## 27. design-system 行：注册表必须指向被执行的合同，而不是被声明的合同

### 27.1 事实

`design-lab/config/object-model.json` 把 `design-system` 指向 `schemas/design-system.schema.json`。
全仓（`src/`、`packages/`、`apps/`、`design-lab/scripts`）**没有任何代码打开过这个文件**，而它自己也
装不下产品真正在服务的东西：

* 它要求 `tokens` 的每个值是**字符串**（`additionalProperties: {"type":"string"}`），而
  `/api/projects/<id>/design-system-tokens/<name>` 读写的是 W3C DTCG 文档——组是嵌套对象，token 是
  `{$type,$value,$description}`；
* 它另外声明的 `typography`、`grid`、`components`、`assetContracts` 四节，没有任何一条代码路径写过。

产品的真实能力在别处，而且是完整的：`design_layer.write_tokens()` 先按打包目录校验 design-system
名字（`UNKNOWN_DESIGN_SYSTEM`），再跑两层判据——结构层 `interop-dtcg-document.schema.json`
（由 `src/design_lab/interop/dtcg.py` 的 `SCHEMA_PATH` 从仓内加载，绝不取 `$id` URL），语义层
`dtcg.validate_document`（`$type` 继承、别名解析与成环拒绝、复合成员完整性、按类型的 `$value`
形状）；校验**在落库之前**，2025.10 之前的文档点名适配器后拒绝而不是悄悄转换；然后才走版本链
（`STALE_REVISION`）、单写者租约与幂等表。该路由在 `config/contract-bindings.json` 里也已经绑到由
`dtcg.py` 发出的 `2025.10` 合同。

所以这不是"缺能力"，是**注册表在指着一份想象里的合同**——和 26 节的 BOM 同一类，只是这一条的实现在
别处已经做对了。

### 27.2 裁定

1. `design-system` 行的 `schemaRef` 改指 `schemas/interop-dtcg-document.schema.json`，
   `description` 改写成产品真正持有的形状："按目录名登记的 DTCG token 文档（tokens 的结构+语义合同，
   版本链与 lineage 读回）"。
2. `design-system.schema.json` **留在原处不删**，但根上加 `description` 写明
   `SUPERSEDED 2026-10-08`、被谁替代、为什么（字符串 token 装不下 DTCG 组；另四节零生产者），以及
   重开的条件：**先给产品一个读它与写它的代码，才允许再被任何对象行指回去**。删文件会让理由消失，
   留文件并写清条件才能挡住下一个人把它当现成合同绑回去。
3. `verify_object_model_backing.py` 里那行 UNREFERENCED 成员**整行删除**（不是改写），钉住的计数
   `6/9/6 → 7/9/5`；`test_object_model_backing_gate.py` 的 `REAL_COUNTS` 同步；聚合脚本注释里那句
   "六个/六个"改成"七个/五个"。
4. 新增一条**比字面串匹配更强的**守卫：这一行既然为了满足门的匹配规则而被改写，就必须证明它指的是
   产品运行时真的打开的那个文件——测试直接比较 `object-model` 声明的路径与 `dtcg.SCHEMA_PATH`
   （`resolve()` 后相等），并断言退役 schema 不再被任何对象行提及。
   **已证伪**：把 `schemaRef` 改回退役文件后跑这条测试 → `FAILED (failures=1)`；还原后
   `digest_match=True` 且 `OK`。

### 27.3 顺带抓到 round-trip 仪器的一个盲区

`test_oda4_0204b_object_model_roundtrip.py` 用 `_build_minimal()` 从 schema 合成最小实例，逐对象验一遍。
它改指之后这条测试**红了**：`design-system: {} should be non-empty`。查下来不是产品的错，也不是裁定错：
合成器只走 schema 自身的 `required`/`properties`，**不看 `$ref`/`$defs`/`minProperties`**，而 DTCG
schema 的全部规则都在 `$defs/rootGroup` 里（`minProperties: 1` + `patternProperties: {"^[^$]": …}`），
于是它合成出 `{}`，被合同正确地拒绝了。

处理方式是不放宽判据、也不跳过这一行：给这一行**手写**一个最小实例
`{"brand": {"$type": "color", "$value": "#316CFF"}}`，仍放进同一个校验循环（结构与 `{"tokens": {}}`
那类合成实例一样必须通过 schema），并另加一条测试用**产品自己的语义校验器**跑它——
`report["token_count"]==1`、`canonical` 为真、`types=={"color": 1}`。语义层是结构 schema 做不到的
（`$type` 沿组继承，schema 无法解析），这一条因此比原来的合成回路更强。盲区本身写进注释，
下一个人看到就知道合成器不覆盖 `$ref` 根，而不是误以为这一行被豁免了。

本轮数字：`OBJECT_MODEL_BACKING=OK objects=21 product=7 tooling_only=9 unreferenced=5`；
`DESIGN_KERNEL=PASS`；`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=5 failures=0`；
`test_oda4_0204_object_model=8 OK`、`test_oda4_0204b_object_model_roundtrip=5 OK`、
`test_design_system_tokens=15 OK`、`test_design_system_tokens_http=12 OK`、
`test_interop_dtcg=36 OK`、`test_design_system_token_form_contract=9 OK`、
`test_object_model_backing_gate=12 OK`。
UNREFERENCED 对象行剩 5 条：`artifact`、`tool-run`、`reference-set`、`candidate-knowledge`、
`method-card`（其中 `method-card` 仍是 #21 的形状裁定）。

## 28. 简报读回终于有了自己的合同：一条 SCHEMA_LESS 债被还上

### 28.1 测出来的两条不相干的事

`GET /api/projects/<id>/briefs` 返回的分页信封在 `config/contract-bindings.json` 里记的是
`SCHEMA_LESS`："a paging list of brief rows ... which declares no schemaVersion. Recorded debt."
而 `object-model.json` 给 brief 指的 `schemas/design-brief.schema.json` 要求
`discipline / objective / audience / deliverables / constraints`——**产品从来没存过这些字段**。
真实被写、被读、被页面渲染的是另一套东西（`design_layer.py`）：
`title` + `goals[]`（非空）+ `constraints?` + `reference_asset_ids[]`（去重、≤32、每个必须是本项目
真实 asset）+ `spec_sha256` + `version` + `superseded_by` + `created_at`。

也就是说：一个正在被使用的载荷无人校验，而一份校验存在却无人执行。这两件事挨在一起放了一个多月。

### 28.2 还债的方式（以及为什么不复用那份 schema）

新增 `design-lab/schemas/brief-readback.schema.json`：信封
`required[schemaVersion, briefs, next_cursor]` 且 `additionalProperties:false`，`briefs` 上限 100
（与 `LIMIT 101` 分页一致），记录用 `$defs/brief` 闭合九字段——`brief_id/superseded_by/next_cursor`
钉 `^brief-[0-9a-f]{32}$`，`spec_sha256` 钉 `^sha256:[0-9a-f]{64}$`，`goals` `minItems:1`，
`version` `minimum:1`，`brief_id/superseded_by/next_cursor`
钉 `^brief-[0-9a-f]{32}$`——`maxItems/minItems/minLength` 全部与写入端已经强制的上限对齐，不新增宽恕。
但参考 asset id **有意没有**钉成写入端的 `img-[0-9a-f]{64}`：如果存在 P0-05 规则之前写下的行，加了
pattern 就把一次读变成 500，而本仓库里没有任何证据能说那种行不存在。所以这条收紧留作点名的下一步，
不是被忽略，也不是被悄悄做掉。
`design_layer._check_brief_readback()` 在 **list / get / lineage 三条读路径上**执行，
不匹配就 `500 BRIEF_CONTRACT_VIOLATION` 并带上字段路径；路由因此不可能把一个"缺列"的简报发给页面，
让人读成"这个项目没有简报"。

**没有把 brief 行改指到这份新 schema**，这是本轮与 27 节的关键差别：27 节里
`design-system.schema.json` 与实现描述的是同一个东西（token 文档）而形状写错，所以指过去是纠错；
这里 `design-brief.schema.json` 描述的是**另一种野心**（专业简报内容模型），把它删掉等于用一次注册表
编辑替 owner 决定"DESIGN-LAB 不再拥有简报内容模型"。因此两条声明并存，差异写进 ledger 的
`reason` 里作为未决决定，`brief` 行仍是 TOOLING_ONLY、计数不动（`7/9/5`）。

### 28.3 谁在真实字节上校验它

`design-lab/scripts/verify_route_payload_contracts.py` 增加一条 binding，并在同一个 harness 里
**用写路由造数据**：POST 一份简报、再 POST 一个 revision（两个版本、一条活链），
参考 asset 是先 INSERT 的真实 asset 行（`img-` + 64 hex，正是写入端要求的形状）。
比对的两个载荷都是路由自己写出的字节，包括"本项目一份简报都没有"的空信封分支——空列表必须能被
读成空项目而不是错误。`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=6`（5→6），
brief-readback 两条 case 比较 4 个对象位置（两个信封 + 两条记录；`$ref` 会被跟进去，
所以九字段是真的在比，不是只比外壳）。`contract-bindings.json` 该行由 `SCHEMA_LESS` 变
`BOUND_SCHEMA`，聚合数从 `bound=14/schema_less=39` 变 `bound=15/schema_less=38`。

### 28.4 顺带：我自己写坏两次，两次都不是编译器抓住的

第一次：我想给 `design_layer.py` 插入常量，把 Edit 的 `new_string` 写成与 `old_string` 几乎相同的
内容，结果吞掉一个换行，`def _brief(row) -> dict:` 与 `return {` 被并成一行。**这次没有改变行为**——
Python 允许 def 行上跟单语句套件，我把这个形状单独拿出来编译过（`broken_rc=0`），所以它只是一处
错误的字节，不是一个故障。真正的问题是：编译器不能当这个编辑的检验器，我不写"它差点没编译过"这种
没测过的话。

第二次是真坏：我把 `_seed_briefs()` 插进了 `__enter__` 的尾部，`__enter__` 从此没有
`return self`，`with Harness() as harness` 会拿到 `None`。`py_compile` 同样过了——因为
`return brief_id` 后面那个孤立的 `return self` 在语法上完全合法，只是永远不会执行。
**发现它靠的是把方法边界重读一遍**：第一次跑那条门报的是
`RuntimeError: BRIEF_WRITE_REFUSED 400 INVALID_REFERENCE_ASSET_ID`（参考 id 形状问题），我去读
`__enter__` 附近 36 行想确认 seed 的调用位置，才看见 `return self` 掉到了我新方法的后面。
也就是说：一次运行只暴露了它前面那个错误，第二个错误是我在复读结构时抓到的——
"能编译"不是证据，跑它、并把改动附近读一遍才是。

同一轮里还有一个正向例子：参考 asset id 我用了 `'a1'`，被写入端
`INVALID_REFERENCE_ASSET_ID` 拒绝。这条拒绝正是那条校验存在的意义，所以我没有放宽校验，而是按
`_ASSET_ID_SHAPE`（`img-` + 64 hex）先 INSERT 一行真 asset 再引用它。

防复发的断言也加了一条：`test_the_three_brief_reads_all_run_the_guard` 断言
list / get / lineage 三条读路径源码里都仍在调用校验函数——"某一条读路径悄悄不再判"就是这类合同最
常见的死法。

第三次是我自己造的一次真实污染，而且是本轮最贵的一次：bound run 报
`tests=191 failures=47 errors=1 skipped=14`，失败集中在 `test_design_layer_http`
（15 例）和 `verify_route_payload_contracts` 的 `setUpClass`，而我单独跑每一个模块都是绿的。
读真实异常才看清：我的变异测试写的是
`original = DesignLayer._brief` → 拿到的是**普通函数**（staticmethod 的描述器已经被解包），
`finally` 里把它赋回类，于是类属性不再是 staticmethod；之后 `self._brief(row)` 会把 `self`
当第一个参数传进去 → `TypeError: takes 1 positional argument but 2 were given` →
HTTP 层统一吞成 `{'error': 'INTERNAL'}`。这个污染活在同一个进程的类对象上，
所以它把后面三个模块全打红了，而它自己那个模块 19 条全绿。
修法是从 `__dict__` 取还原（`holder = DesignLayer.__dict__['_brief']`，还原后断言
`isinstance(DesignLayer.__dict__['_brief'], staticmethod)`），并且这条教训落在测试自己的
docstring 里：**类属性猴子补丁要按描述器取回，否则一次"复原"就是一次永久破坏**。
同一轮里 `verify_route_payload_contracts` 的 seed 也顺带被这条污染误导过一次——它的
`BRIEF_WRITE_REFUSED 500` 其实不是简报合同在判，而是上面那个 TypeError。

### 28.5 本轮数字

`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS bindings=6 failures=0`；`VERIFY_CONTRACT_BINDINGS=PASS
schemas=32 binding=2 inert=30 routes=53 dispatched=53 bound=15 schema_less=38`；
`DESIGN_KERNEL=PASS`；`OBJECT_MODEL_BACKING=OK product=7 tooling_only=9 unreferenced=5`（未动）；
新模块 `test_brief_readback_contract.py=19 OK`，`test_design_layer_http=20 OK`、
`test_design_layer_revision=14 OK`、`test_route_payload_contracts=20 OK`、
`test_evidence_artifact_presence=4 OK`、`test_gate_reachability=4 OK`、
`test_test_selfsufficiency_gate=13 OK`。
四条 `design_layer.py` 行号指针全部按实际行重新核对：`:63`（版本常量，新增）、`:166`
（EVENT_KINDS，被我的插入从 128 推到 166）、`:291`（validate_token_document，从 253 推到 291）、
`:799`（hash_document，仍在原位）。

待 owner 裁定：brief 的两份形状——要么把内容模型（discipline/objective/audience/deliverables/
success_metrics/brand_assets）做进产品，要么正式退役 `design-brief.schema.json`。本轮只还了读回合同
这条债，没有替它选。

### 28.6 对本门自己的更正：把注释当引用，门就会自己造出 PRODUCT

写完 28.2 那条注释（解释 `design-brief.schema.json` 的形状无人实现）之后，
`verify_object_model_backing.py` 报了一条我没预料到的红：
`brief: pinned as TOOLING_ONLY but it is now PRODUCT`。

查下来不是我接了什么校验，而是**门把散文当成了引用**：它的语料是文件原始文本，
`classify()` 只做子串匹配，所以 `src/` 里一句注释写着某个 schema 的文件名，就能把那个对象从
TOOLING_ONLY 抬成 PRODUCT。这等于门自己造绿灯——只要有人**谈到**一份合同，合同就被算成在被执行。

修法在门上而不是在我的注释里：语料改为"可执行文本"。Python 走 `tokenize`，删掉 COMMENT token，
并删掉"独立成语句的字符串"（模块/类/函数 docstring），而赋值右侧、调用参数里的字符串保留——
真实加载器写路径的两种方式（`SCHEMA_PATH = PROJECT_ROOT / "…/x.schema.json"`、
`load_schema('…x.json')`）都因此仍然算数；TS/mjs 删整行 `//` 与 `/* … */`；无法 tokenize 的文件
退回"只删整行注释"，不假装散文是代码。

**更正后的实测**（`git grep` 逐条核对过，不是听门的）：

| 对象 | 之前 | 现在 | 依据 |
|---|---|---|---|
| `delivery-manifest` | PRODUCT | PRODUCT | `delivery_bom.py:36` 赋值 |
| `design-system` | PRODUCT | PRODUCT | `interop/dtcg.py:80` 赋值 |
| `domain-pack` | PRODUCT | PRODUCT | `domain_packs.py:44` 赋值 |
| `research-finding` | PRODUCT | PRODUCT | `research_store.py:86` 赋值 |
| `quality-report` | PRODUCT | 先降为 UNREFERENCED，再改指 V2 → PRODUCT | V1 只出现在 `human_jury.py` 的 docstring；V2 是 `human_jury.py:51` 的赋值并在 `:182` 被读 |
| `preflight-report` | PRODUCT | TOOLING_ONLY | `preflight.schema.json` 在 `src/` 里只有 docstring 提到；产品真正绑的是 `artifact-preflight.schema.json` |
| `handoff-package` | PRODUCT | UNREFERENCED（理由重写） | `handoff_readiness.py` 只在 docstring 里提名，且它自己发的 `design-lab/handoff-readiness/v1` 无任何 schema 绑定 |

于是钉住的计数从 `7/9/5` 更正为 **`5/10/6`**，两条新入册理由（`preflight-report`、
`handoff-package`）各写明"今天是靠什么实现的"，`brief` 回到 TOOLING_ONLY。
**本节之前所有 product 计数——25 节的 `product=5`、26 节的 `6/9/6`、27 节的 `7/9/5`、以及
28.5 自己写的 `7/9/5`——都出自这台把散文当引用的仪器，以本节表格为准。**
历史行没有被改写，只在这里声明其无效；受影响的具体断言是"某对象的 schema 被产品代码加载"这半句，
其余（门的规则、测试结果、路由绑定、计数以外的数字）不受影响。

`quality-report` 这一行我没有停在"降级"，而是按 27 节同一判据改指产品真正加载的
`assurance-jury-record-v2.schema.json`（V1/V2 是同一个对象的两个版本，V2 才是被执行的）。
改指之后新增的守卫也一并扩到两行：`test_both_repointed_rows_name_the_file_the_product_opens`
直接比较 `object-model` 声明的路径与 `dtcg.SCHEMA_PATH` / `human_jury.SCHEMA_PATH`。
遗留：`JuryRecord.template.json` 仍教 V1 形状（它按 26 节要求必须通过 V1 合同），
V1 模板与 V2 实现之间的取舍仍是要 owner 拍的形状决定，本轮不替它选。

新测试 `ProseIsNotAReferenceTests` 六条把这条规矩钉住：整行注释、行尾注释、模块 docstring、
函数 docstring **都不能**抬 PRODUCT；赋值右侧与调用参数里的路径**必须**抬。
另外两次我自己的仪器错也记在这：bound run 里 47 条跨模块失败其实来自我一处 `finally` 复原
把 `staticmethod` 降成了普通函数（类属性被污染，后续模块的 `self._brief(row)` 收到
`TypeError`，HTTP 层统一吞成 `{'error':'INTERNAL'}`）；以及"能编译"两次都不是证据——
`py_compile` 对被我并行的 `def` 行与被拆开的 `__enter__` 都返回 0。

## 29. 30 份 INERT 合同：把"没人实现"从一句话变成一条被复测的断言

### 29.1 为什么动这一片

`design-lab/schemas/contracts/` 里 32 份 schema，`VERIFY_CONTRACT_BINDINGS` 报
`schemas=32 binding=2 inert=30`。这是合同层最大的一片"声明看起来像能力"的地带：30 份被标为
INERT，每份配一段理由。理由里绝大多数是**否定断言**——"plan_id/jobs appear nowhere in src/"、
"nothing implements this"。否定断言是散文里最贵的一类：它不会随代码变化而报错，只会悄悄变成谎话。
本轮不实现这 30 份（那是内核架构决定，要 owner 拍），做的是让"没人实现"这句话**每次运行都被复测**。

### 29.2 我先把测量做错了（这条比结果重要）

第一版我按 schema 的 `required`/属性名去 `src/`、`packages/`、`apps/` 里搜，结果 27/30 都"在产品里
出现"——于是看起来 27 份 INERT 是谎。那是**我的判据错**，不是账本错：`action`、`at`、`note`、`result`、
`state`、`decision`、`changes` 这些词在任何代码里满地都是，一个字段名出现在产品里不等于那个形状被实现。
"名字搜索要按块归属、要处理别名"这条老教训又应验一次。

正确的问法和 25 节给对象模型定下的是同一个：**谁指名这份文件**。按字面文件名在
`src/`、`packages/`、`apps/`、`integrations/` 的 204 个产品文件里搜，结果是 **0**——
30 份 INERT 断言全部成立，连"散文里提一句"都没有。

### 29.3 门里新增的规则，和它当场抓到的一处

`verify_contract_bindings.py` 加了两类规则：

- **引用必须是路径**（第 8 条）：`instances` / `tests` / `fixtures` 每一项必须以仓库内路径开头，
  带 `:行号` 的必须落在文件行数内。当场抓到一处真缺陷：
  `planar-decomposition` 的 fixtures 写的是
  `generated at run time by design-lab/tests/host_fixtures/qualify_ocr_object_plan.py:45`——
  一句散文塞在专门用来被复测的字段里，等于那行"有证据"其实无人可查。改成只留路径（该行确实是
  实例被组装并 `jsonschema.validate` 的地方），"运行时生成"这句挪进 reason；
  顺带发现 scratch 树的构造器只复制 `instances`/`tests` 而不复制 `fixtures`，补齐，否则门的
  fixtures 检查在副本里无法工作。
- **INERT 是对源码的断言**（第 9 条）：INERT 行若被任何产品文件指名，判
  `INERT_BUT_NAMED_BY_PRODUCT`。搜索用**原始文本**（含注释），故意取严的一侧：今天它一条都不报，
  所以代价是零；而将来有人在 `src/` 里注释了一句这份 schema，也被要求出来说清楚——这比让一份
  已接线的 schema 继续躲在 INERT 后面好。

### 29.4 一个规则被自己的外科性测试挡回来

新加的"文件不存在"检查最初对三组字段一律生效，于是 `tests` 里一个消失的文件同时被
`TEST_ROW_STALE`（原有规则）和我的 `CITATION_STALE` 各判一次——测试
`assert_red_for(..., 1)` 立刻红了，报的不是我的规则而是"一个缺陷两行红"。这正是仓库里
"exactly N reds"存在的意义。改法是按组分工：**形状**三组都查；**行号**在文件存在时查；
**文件缺失**只由 `fixtures` 走新规则，`instances`/`tests` 继续归 `BINDING_ROTTEN` /
`INERT_ROW_HAS_INSTANCE` / `TEST_ROW_STALE`。另两条测试也因此换到树内真实存在的路径上，
否则它们验的是"文件不存在"而不是"行号漂移"。

### 29.5 本轮数字

`VERIFY_CONTRACT_BINDINGS=PASS schemas=32 binding=2 inert=30 routes=53 dispatched=53
bound=15 schema_less=38`；`test_contract_bindings.py` 32 条 OK（含 4 条新规则的注入测试 +
一条"字符串与注释都不许躲在 INERT 后面"的双面测试）。
仍待 owner：这 30 份 INERT 里要不要接线、接哪几份（`run-event`/`job-spec`/`job-attempt`/
`operation-intent`/`operation-receipt`/`host-session`/`document-session` 这一组明显对着
native_* 表，是同一内核决定的不同侧面）；本轮只把它们的"没人实现"变成可复测的事实。

## 30. 证据链的最后一环自己撒了谎：73 条收据全部"未核验"，而这是规则缺陷不是事实

### 30.1 为什么做这一片

能力链的最后一环是"证据"。账本把每条观察绑到一个提交上：`binding: COMMIT` 声明"这些字节来自那个
提交"；同一 enum 的另一个取值 `WORKTREE_FILES` 在 schema 里带着注释"字节来自脏工作树，永远不得冒充
提交"（`design-lab/schemas/task-ledger-r5-v1.schema.json:316-317`）。投影
`src/design_lab/governance/reporting.py::project_ledger()` 负责回答"这条收据还成立吗"。

它从来没读过 `binding`。它对每条收据都做两件事：把收据里的摘要和**当前工作树**的字节比对；并要求
收据的 `subject_sha` 等于**投影生成时所在的提交**。第二条在实践中不可达：投影只能记录一个已存在的
提交，而账本行必然落在那个提交之后的提交里，所以等式对任何一行都不成立。第一条对任何被 git 属性
正常化的文件也不成立（见 30.3 的 CRLF）。

2026-10-08 在 `e1ca2902` 实测：73 条收据，`verified` 为真 **0** 条。后果不是"显示不好看"，而是
`reporting.py:226` 的轴降级规则——轴声明为 `PASS`/`IMPLEMENTED_LOCAL` 时，必须有一条 `verified`
且属于本任务、kind 匹配的证据，否则降为 `UNVERIFIED`。既然 0 条通过，**任何轴的晋级在结构上不可
能**，而这个标志本身携带的信息量为零。没人发现，是因为 28 个任务的声明状态本来就都是 `PARTIAL`，
一片"未核验"看起来像正常衰减。

### 30.2 先把仪器测准：同一片里我自己错了两次

第一次是判据。我用"这个路径今天是否被 git 跟踪"区分"提交内字节"与"机器本地字节"，得到"仅 5 条路径
不在其绑定提交里"。这个数太小了：未被跟踪不等于机器绑定，它同样可能是**任何提交都不曾持有的派生
字节**。按声明的绑定重测，这类引用是 **63 条**，覆盖 14 行 `r5-*-static-unit-20260928`：57 个
`__pycache__/*.pyc` 字节码缓存，6 个 `fixtures/domains/game-visual/android-minigame/` 下的 wav——
该目录被同目录 `.gitignore` 第 12 行排除。把 `*.pyc` 写成 `binding: COMMIT` 的工件，等于声称一段
任何提交都不曾持有的字节是提交内容。

第二次更要紧，因为它是我写进草稿的一条不实指控。第一版测量对**所有**行都按"取绑定提交 blob 比对"
判定，于是报出 3 条"摘要在任何提交都复现不出来"，我把它当作伪造证据的实证写了进去。实际上这 3 条
全在**一共只有 3 行的 `WORKTREE_FILES`** 里（`r5-comfy-structural-rejection-20260909` 等，2026-09-09，
outcome 均为 `PARTIAL`）。这三行从未声明自己是提交观察，是我拿提交语义去审判它们才审判出莫须有。
与 29.2 同一类错误（问错问题），这次问的是自己的仪器；指控已删除，按声明的绑定重新分类。

第三次是工具的分歧，发生在我的回归测试上。我按"`git status --porcelain` 为空"刻画"CRLF 工作树 +
LF blob 且 git 认为干净"的条件，测试直接红：`git status` 报 `M src/logic.py`，而
`git diff --name-only <subject>` 报空。用探针（`.project-local/tmp/probe_crlf_status.py`，三种属性
组合加真仓实况）确认后，时效规则改为基于 `diff`——它按属性正常化后再比较，正是这里要的语义；真仓
`design-lab/config/contract-bindings.json` 磁盘 CRLF、blob LF，`status` 与 `diff` 都给空。

### 30.3 现在的规则：把"记录完好"和"仍适用于今天"拆成两个字段

一条收据要回答两个不同问题，混在一起就必然要么永远红、要么掩盖真相：

- **完整性 `verified`**——收据哈希的字节还在它自己声称的地方吗。`COMMIT` →
  `git show <subject_sha>:<path>` 取 blob 比对；`WORKTREE_FILES` → 只能用这块磁盘；
  `.project-local/task-artifacts/**` → 声明为运行期工件，同样落回本机。新理由逐个点名路径：
  `DIGEST_NOT_REPRODUCIBLE_AT_BOUND_COMMIT`、`PATH_NOT_IN_BOUND_COMMIT`、
  `ARTIFACT_IS_NOT_VERSIONED`、`DIGEST_CONFLICT_FOR_SAME_PATH`（同一路径被同一行以两个不同摘要
  声明）、`RUNTIME_ARTIFACT_ABSENT_ON_THIS_MACHINE`、`SUBJECT_COMMIT_ABSENT`。
- **时效性 `current`**——这条收据还在描述投影此刻要为其发言的字节吗。`MOVED_SINCE_BOUND_COMMIT`、
  `LOCALLY_MODIFIED_SINCE_SUBJECT`，而 `STALE_SUBJECT_SHA` 保留给 `WORKTREE_FILES`，那个字段本来
  就是给"脏树上取的观察"用的。

轴降级同时要求两者，所以这次改动**没有放松任何门槛**：
`test_source_mutation_invalidates_prior_pass`、`test_missing_artifact_does_not_reuse_declared_pass`、
`test_wrong_subject_commit_is_stale` 原样通过；改的只是把"永远不可满足"换成"按各自语义可满足"。
同一文件被 `subject_files` 与 `artifacts` 双重点名时现在只判一次，不再对同一事实发两行红——这是
29.4 的"一个缺陷一行红"在同一条链上的应用。

### 30.4 被点名的真实缺陷，不掩盖

- **63 条未版本化工件引用**，14 行（30.2）。历史行不重写：它们仍是当时的观察，只是从今往后被点名。
- **1 条运行期工件本机已不存在**：`r5-comfy-http-model-free-live-20260909` 引用的
  `.project-local/task-artifacts/comfy-http-live-…/result.json`。这是"多数账本工件只活在某台机器"
  那笔债的具名一处。
- **`COMMIT` 声明里没有任何一条摘要在自己绑定的提交上复现失败**：被版本化的 406 条全部对上。缺陷
  集中在"引用了根本不在版本控制里的东西"，不在"哈希写错"。这一点值得如实说，因为它意味着账本的
  提交绑定本身是可信的。
- **`verified` 此前没有仓外消费者**：除 `reporting.py:226` 之外，前端与 `design-lab/scripts/verify_*.py`
  都不读这个字段，所以这个缺陷可以长期存在而不被任何门拒绝——一个没人调用的断言就是文档。

### 30.5 数字（在 `763bcf47` 重跑，不继承）

`COMMIT` 声明共 502 条：406 条 blob 在其绑定提交复现，63 条引用未被版本控制的字节，33 条是运行期
工件声明。`WORKTREE_FILES` 声明共 9 条，按磁盘判定，其中 2 条路径的磁盘字节已不等于当年取的树——
它们本来就承认自己是脏树观察。73 条收据：**36 条完整**，**2 条仍适用于今天的字节**
（`r5-010-template-contracts-and-delivery-bom-20261008`、
`r5-001-inert-contract-claims-re-measured-and-citations-made-paths-20261008`）。
理由分布：`OUTCOME_NOT_PASS` 37、`ARTIFACT_IS_NOT_VERSIONED` 63、
`RUNTIME_ARTIFACT_ABSENT_ON_THIS_MACHINE` 1、`EVIDENCE_DIGEST_DIFFERS` 2；时效侧
`MOVED_SINCE_BOUND_COMMIT` 149、`STALE_SUBJECT_SHA` 8、`LOCALLY_MODIFIED_SINCE_SUBJECT` 1
（最后这条正指 `test_current_reporting.py` 本身——生成时它已被本次修改，规则抓得对）。

投影任务计数不变：`{'PARTIAL': 28}`——这次改动**没有点亮任何绿灯**，这正是重点：同一个字段现在
既能因真理由红，也能因真理由绿。`test_current_reporting.py` 43 例 OK（新增 10 例覆盖新语义），
`test_r5_migration.py` 10 例 OK，bound run `tests=387 failures=0 errors=0 skipped=0 order=forward
clean=True subject=763bcf471067`，聚合 `VERIFY_DESIGN_LAB=OK total=68 failed=0`，
`CURRENT_REPORTS=PASS mode=generate`。

只到 E1/E2：这是一条**投影规则**与其受控测试，未涉及宿主；E3/E4/E5 不因本片改变。

需要 owner 判断、这里不自作主张的：那 63 条未版本化引用要不要由 `verify_ledger_subject_binding.py`
升成硬门。升门会让 14 行历史收据在 CI 上一直红，除非同时给它们一份具名豁免清单；不升则只由投影
报告。两种都比"永远全红"诚实，代价不同，而且这是治理选择不是技术必然。

### 30.6 对本节的修正：那 63 条不是我发现的缺陷，而是一个已存在的门早就知道、而投影不知道

写完 30.4/30.5 之后去核 `design-lab/scripts/verify_ledger_subject_binding.py`，结论要改。该门
`verify_ledger_subject_binding.py:12-14` 说明它**已经**用 `git show <subject_sha>:<path>` 取对象库
字节来复算 `subject_files` 声明的摘要，并且带一份 `KNOWN` 豁免表：67 条目、17 行
（57 `.pyc` + 6 `.wav` + 4 `.py`），每条注明"摘要与那些字节相符，但 .pyc 不被跟踪，任何提交都无法
复现"。它还是双向的（`partition()`）：既拒绝未登记的缺陷，也拒绝"已变得可核验却仍赖在豁免表里"的
条目——所以这张表不能烂成永久借口。该门今天 `LEDGER_SUBJECT_BINDING=OK`，在 68 门聚合里通过。

因此本节的两处措辞是错的，按事实改写：

- 30.4 说"`verified` 没有消费者，所以缺陷可以长期存在而不被任何门拒绝"——前半句仍然成立（除
  `reporting.py:351` 外无人读该字段），但"不被任何门拒绝"不对：**账本本身是被拒过的**，而且是以
  正确基准被检查的。缺的是投影与那份检查对齐，不是检查本身。
- 30.5 与文末"需要 owner 判断"的那条把 63 条未版本化引用写成了待决策的新缺陷——决策其实早已做出，
  并且是做对了的那一侧：豁免表注明理由、带日期、双向腐烂保护。真正的缺口是投影无法区分
  "已被具名豁免的不可复现"与"新出现的不可复现"，两者都只报成 `ARTIFACT_IS_NOT_VERSIONED`。
- 30.4 里"0 条 COMMIT 摘要复现失败"仍然成立，且与该门一致：该门的 `unsanctioned` 为空，
  即所有能复现的都复现了，剩下的 67 条全在具名清单里。

不改变本片实现的严格性：投影**不**导入那张豁免表，被豁免的行仍然不 `verified`，也就仍然不能晋级
任何轴。理由是那张表的语义是"已知不可核验、已记录、不得以此冒充"，不是"这些可以当证据"；如果投影
照单放行，就会把治理上承认的缺陷洗成绿灯。下一步的正确做法是**基准对齐而非放宽**：让投影读取同一
`KNOWN`，把两种情形分开报成 `ARTIFACT_IS_NOT_VERSIONED_KNOWN` 与
`ARTIFACT_IS_NOT_VERSIONED_UNSANCTIONED`，两者都红，只有后者值得 owner 再看一眼。这一条留作待办，
因为它要求投影与门共享一个模块边界，属于另一个改动单元。

修正的教训与 30.2 同一类：我把手里仪器的第一次读数当成了事实本身，而没有先问"仓里是否已经有人在
用正确的基准看同一件事"。本节保留原文并追加修正，不改写已提交的段落。

## 31. 同一个声明不能有两套读法：把"哪些字节算声明"收成一个所有者

### 31.1 为什么做这一片

30.6 留下的不是"投影改好了"，而是一个更硬的事实：仓里有两个组件各自重算收据的字节声明，各自保
存了一份"哪些路径算声明"的规则。`design-lab/scripts/verify_ledger_subject_binding.py` 用
`git show <subject_sha>:<path>` 复算 `subject_files`；`src/design_lab/governance/reporting.py` 的
投影判定 `subject_files` + `artifacts`。两份规则字面不同，判定结果就必然漂移——30 片里投影那条
永远全红的规则正是这种漂移的一端。把缺陷修好而把根因留着，下一片还会从同一个缝里长出来。

### 31.2 门自己也有一处基准错用，并且把它记成了别人的证据债

门的 `classify()` 完全不读 `binding`。于是它对 `WORKTREE_FILES` 的行也按对象库复算——而 schema
给这个取值的注释是"字节来自脏工作树，永远不得冒充提交"
（`design-lab/schemas/task-ledger-r5-v1.schema.json:316-317`）。按被否定的基准审判，必然产出"缺陷"，
而这 4 条结果被写进了 `KNOWN` 豁免表，理由一字不差是"this entry does not equal the bytes at that
commit -- the subject was read from the working tree"。也就是说：门知道这些是工作树读数，却把
**自己的基准错用**记成了记录的证据债。

这不是把那 4 行记录改好，也不是给它们开后门：`WORKTREE_FILES` 的字节本来就只在当时那块磁盘上，
任何提交都无法复现它们。做法是让门不再用记录自己否定的基准审判它们，并把这类声明**计数并打印**
（`worktree_claims=8`），而不是当作已豁免的缺陷。豁免表因此从 67 条减到 63 条，全部是真正的
"提交无法持有的字节"（57 个 `.pyc` + 6 个 `.gitignore` 排除的 wav）。双向腐烂保护不动：
新出现的未登记缺陷仍红，已变得可核验却仍赖在表里的也仍红。

### 31.3 规则：一个所有者，两个消费者，各自的结论

`design_lab.governance.reporting` 现在拥有 `Claims` / `basis()` / `claims()`：
`subject_files` 与 `artifacts` 都算字节声明；同一路径只判一次；同一路径被同一行以两个不同摘要
声明即为自相矛盾（`DIGEST_CONFLICT_FOR_SAME_PATH`）；`.project-local/task-artifacts/**` 落在任何
提交基准之外，**计数而不丢弃**（`runtime=34`）；缺 `binding` 的行按更严的 `COMMIT` 读。

门 import 这个所有者，只保留自己的结论：`checked=472`（旧口径只看 `subject_files` 是 450，
其中还包含 4 条不该按提交判的），`worktree_claims=8`、`runtime=34`、`known_unverifiable=63`、
`records=74`。投影保留自己的两个字段（完整性 / 时效性），但用的是同一份声明枚举，不再自带一套
路径判定。方向是脚本依赖产品模块，不是反过来。

### 31.4 数字与验证（在 `9e7db8a4` 重跑）

`LEDGER_SUBJECT_BINDING=OK checked=472 subject_files=450 runtime=34 worktree_claims=8
known_unverifiable=63 records=74`；`test_ledger_subject_binding.py` 19 例 OK（原 11 例，新增 8 例
分别钉住：artefact 声明按提交判、可复现的 artefact 声明是旧门没有的覆盖、`WORKTREE_FILES` 不被对象
库审判、runtime 声明被计数不被跳过、同路径双摘要、缺 `binding` 默认更严基准、提交不可解析时两份
清单都要付出代价、豁免表里不再有非提交基准的条目）；`test_current_reporting.py` 43 例 OK；
聚合 `VERIFY_DESIGN_LAB=OK total=68 failed=0`；投影在该提交上：74 条收据 **37 条完整**、
**2 条仍适用于今天的字节**，理由分布 `OUTCOME_NOT_PASS` 37、`ARTIFACT_IS_NOT_VERSIONED` 63、
`RUNTIME_ARTIFACT_ABSENT_ON_THIS_MACHINE` 1、`EVIDENCE_DIGEST_DIFFERS` 2，时效侧
`MOVED_SINCE_BOUND_COMMIT` 153、`STALE_SUBJECT_SHA` 8；任务计数仍 `{'PARTIAL': 28}`，
没有任何轴因本片被点亮。30 片那条 `LOCALLY_MODIFIED_SINCE_SUBJECT` 已随提交消失——规则抓的是
"生成时该文件仍未提交"，正是它该有的行为。

### 31.5 仍未决（不替 owner 决定）

- 那 63 条"提交永远无法持有"的声明要不要进一步要求 owner 判断：现在它们被具名豁免且双向防腐，
  但记录本身仍是 `binding: COMMIT` 引用非提交字节。把 `binding` 改为 `WORKTREE_FILES` 才是语义正确
  的写法，而那等于承认这些行从来不是提交观察——是否允许这样修订历史行，是治理问题。
- 21 号任务（MethodCard 两种形状、零生产者）与 30 片前述 brief 内容模型、jury 模板 V1/产品 V2、
  30 条 INERT 合同的接线或退役，都仍等 owner 选择；可审查产物已在仓内，入口分别是
  `design-lab/schemas/method-card.schema.json` 与 `design-lab/schemas/visual-quality/
  master-method-card.schema.json`、`config/contract-bindings.json`。

## 32. 证据链终于有人能问：一条路由、一张卡片，以及一处把"慢"当成不可用的修复

### 32.1 为什么做这一片

30 与 31 把投影修成了会说真话的东西，但它仍然只有一处消费者：`reporting.py` 里那条轴降级规则。
也就是说，"这些证据到底站不站得住"这一问，在仓里没有任何人能问——没有路由、没有界面、没有门读它。
一条只有写它的那段代码读得到的结论，等于没有结论。这一片补的是能力链的最后一格（前端→读回→证据）。

### 32.2 契约与后端：拒绝比空列表更诚实

新合同 `design-lab/schemas/evidence-projection.schema.json`（`design-lab/evidence-projection/v1`）
闭合并界定了这份读回：`subjectSha / ledger / totals / reasonCounts / receipts / taskCounts`，
每条收据只有 11 个字段——账本行里的 note、software、逐文件摘要一律不带出去。理由词汇表是两个
**闭合枚举**（完整性 10 个词、时效性 4 个词，都允许 `:路径` 后缀），所以在代码里新增一个理由而不
在合同里登记它，会直接被判违规，而不是悄悄多出一个没人解释过的状态词。

发射器 `src/design_lab/governance/evidence_readback.py` 对**当前检出**重算 `project_ledger`：读账本
+ 对象库，绝不读 `reports/current/`（生成物绑定它写下时所在的提交，把它当作"你正在跑的这份代码的
状态"来供，正是本片在修的那种偷换）。它自检后才应答，失败一律具名：无账本 / 无 git 主题 →
`EVIDENCE_LEDGER_ABSENT`、`EVIDENCE_SUBJECT_UNRESOLVABLE`（503），合同分歧、账本拒投影、超过上限
→ `EVIDENCE_CONTRACT_VIOLATION` 等（500）。没有一种失败会退化成"0 条收据"。
`http_service.EVIDENCE_READBACK_STATUS` 与发射器 AST 里真正抛出的码双向对齐：新增拒绝码不给状态
是红的，留着没人抛的状态映射也是红的。

路由 `GET /api/evidence-projection` 记为 `BOUND_SCHEMA`（routes 53→54、bound 15→16、dispatched
同步跟上，否则门口就红），`scripts/verify_route_payload_contracts.py` 用真实 socket 两次调用它，
比对 **156 个对象位置**（bindings 6→7，`VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS failures=0`）。

### 32.3 一处把 10 秒当成"不可用"的修复

第一次量测：这条读回 cold 10.0s / warm 10.3s——因为 `_CommitReader` 每条声明起一个
`git show`（502 条声明 502 个进程）。这不是"页面慢一点"，这是没人会去问的问题；把按钮藏得深一点
也不解决它。改为**每个提交一次 `git cat-file --batch`**、一次 `ls-files -z`、一次 `diff`：
现在 1.0s（21 batch + 21 存在性探测 + 2，0 个 `git show`），且判定结果与逐条读法逐字节一致——
新测试把两条读法逐项对比（含"提交里没有这个路径"这一分支），因为一个改变结论的加速不是优化，
是另一个程序。成本用进程数量的**结构**断言钉住，不用计时器：计时断言在忙的 runner 上会假红、
在闲的 runner 上会假绿，而真正的退化（回到每条一个进程）两种情况下都看不见。

顺带清掉一处自己制造的技术债：两连补丁在 `reporting.py` 里留下两份
`RUNTIME_ARTIFACT_ROOT` 声明。第一次切片修复时把中间整段（含 `class Claims`）误删了——它被
脚本自己的守卫拦下、从 HEAD 复原、换位置锚点重做。这个教训是具体的：**切片替换的守卫必须断言
"被替换的区间里不该有什么"**，而不只是断言"我要找的东西在里面"。

### 32.4 界面：三个词必须是三个词

`证据系统` 页新增 `证据链完整性` 面板（`GET /api/evidence-projection`，点按钮才读，理由与交付收据
一样：它要对整个检出复算，没人选过就出一个结论等于猜）。判定词由两个布尔量派生，绝不手抄服务端的
枚举词：`VERIFIED CURRENT` / `VERIFIED NOT CURRENT` / `NOT VERIFIED`，并全部带 `lang="en"`。
缺 `totals` 或缺 `receipts` 时不画任何数字，只说未读回并点名缺什么；带拒绝码的响应把码原样显示，
绝不显示成"账本是空的"。列表展开上限 12 条，超出必须写明"其余 N 条未逐条列出"，因为把 12 读成
全部是另一类假绿。

面板挂在 `projectPickerPanel` 新增的 `preamble` 槽里，而不是项目正文里：这条判定说的是检出，不是
某个项目；挂在选完项目之后，在一个没有项目的合成台账上它就根本问不出来。

### 32.5 门与反证（在 `34d2515b` 重跑）

浏览器溢出/裁剪门新增 `INTERACTIONS` 表：点完按钮之后的那张卡片也被量一次
（`1440/1280/1920` 三档 clipped=0 stray=0 tiny=0 docX=0），且 settled 状态随测量一起写进报告
（`read` 还是 `refused`），Python 侧要求至少一档真的读回了东西——一张永远显示错误的卡片几何上可
以是完美的。**先证伪再相信**：把选择器指向一个不存在的 id，门退出 2 并报
`OV_INTERACTION_UNMEASURED`；控制组退出 0。

`test_evidence_readback_contract.py` 17 例 OK（含拒绝路径、成本结构、批读与逐条读等价）；
`test_current_reporting` 43、`test_ledger_subject_binding` 19、appshell/unit/shape-notice 三套 UI
测试 OK；投影在本次主题提交上：75 条收据、38 条完整、1 条仍适用于当前检出
（`MOVED_SINCE_BOUND_COMMIT` 163，随本波移动的文件继续增长），任务计数仍 `{'PARTIAL': 28}`——
这一片没有点亮任何绿灯。bound run `tests=398 failures=0 errors=0 skipped=0 clean=True
subject=34d2515b9f34`，聚合 `VERIFY_DESIGN_LAB=OK total=68 failed=0`。

### 32.6 一条流程自纠

第一次 bound run 报 `FAILED(1)`，红的是漂移清单（本波改了 4 个被更早记录哈希过的文件）；重测得
47→51 对 / 20 个具名工件，按日期写明理由后更新钉值，而不是放宽断言。此外我自己犯过一次更低的错误：
把 `git commit -F - <<'MSG'` 和后续命令接在同一行，heredoc 结束符因此不被识别，提交为空而 bound run
跑在了脏树上（`clean=False`）——该跑的收据作废，改用 `-F <文件>` 重提再重跑。钉住这条不是因为少见，
而是因为脏树 receipt 看起来和干净的一模一样。

## 33. 把 30 条 INERT 从"没有实现"变成可拍板的表

### 33.1 为什么还要做这一片

29 片让"nothing implements this"变成可复测的断言，31 片让声明与字节的对应关系只有一个所有者。
但 owner 决策仍卡着，而且卡的原因不是问题难，是**事实没铺开**：30 条各自一句 prose，没人知道哪条
其实已经有表在承载同一个活动、哪条真的什么都不对应、退役会牵动什么。缺的是可审查产物，不是勇气。

### 33.2 普查怎么算（可反对，但必须显式反对）

`design-lab/scripts/inert_contract_survey.py` 只算不猜：取 schema 自己声明的顶层属性名 → 在
`design-lab/schemas/state/*.sql` 解析出的 37 张表里找列名重合最高者 → 报告重合比例与命中字段名 →
在产品源码里找对该表的 `INSERT/UPDATE/DELETE`（写）与 `FROM/JOIN`（读），只看非注释行 →
再检查路由清单与账本里有没有别处引用这条 schema，得出"退役是否无连带"。

门槛是显式规则：重合 ≥ 1/3 才算"同一件事被声明两次"。文档写明这是判断门槛、不是产品测量值，
且每行带自己的 `overlap` 与 `matched_fields`；对 ≤3 属性而只有 1 列重合的行打 `（thin）` 标记，
因为两字段 schema 用一列就能迈过 1/3——这条性质由测试钉住，而不是藏在分类词后面。

产物落在 `docs/audits/INERT-CONTRACT-SURVEY-2026-10-08.md`，内含可校验 JSON 块，
`--check` 重算并逐字节比较：改了代码不重跑就是红的；文档因此不是手抄表格。

### 33.3 测出来什么（`45acfe67`）

30 条里：`TABLE_WRITES_THIS_ACTIVITY` 8、`TABLE_EXISTS_UNWRITTEN` 3、`ADJACENT_TABLE_WRITTEN` 2、
`NO_STATE_COUNTERPART` 17。最刺眼的一行是 `operation-intent.schema.json`：与真实表
`operation_intent` 重合 **1.00**，且 `store.py`、`job_store.py` 都在写它——同一事物的两种形状，一种被实现、
一种被声明为合同并标 INERT。`job-spec`(0.67)、`job-attempt`(0.62)、`run-event`(0.50，写方
`decision_ledger.py`) 同理。另有 3 条形状对得上但没人写表（含 `operation-receipt` 重合 1.00），
也就是说"接线"对它意味着先有写方，而不是先有 schema。

30 条今天都"可无连带退役"（路由清单与账本没有别处引用）——这只说明选项存在，不是建议。

### 33.4 这一片自己被证伪过什么

- 普查工具在第一版**会崩**：账本声明的 schema 文件不在盘上时直接 `FileNotFoundError`。现在报
  `SCHEMA_FILE_ABSENT`，既不 crash 也不把它算成可退役。
- `retire_coherent` 不是恒真装饰：把一条路由指向某个 INERT schema，标记翻成 `False`；把同一条合同
  在账本里声明两次，也翻成 `False`。两个方向都进测试。
- 重合算术逐行重算：`overlap` 必须等于 `matched_fields / fields`，`matched_fields` 里每个名字必须
  真的是那张表的列，报告出来的写方文件必须真含该表的写语句（至少 6 条被逐条核对）。
- 分类由证据决定：把写方清空，同一行从 `TABLE_WRITES_THIS_ACTIVITY` 掉到 `TABLE_EXISTS_UNWRITTEN`。
- `--check` 的失效控制：把文档 JSON 里一个 17 改成 16，就被判陈旧。

`test_inert_contract_survey.py` 18 例 OK，聚合 `VERIFY_DESIGN_LAB=OK total=68 failed=0`。

### 33.5 顺带修的一处界面自相矛盾

`证据系统` 页与项目阶段导航都写着"E0–E5 证据记录无服务路由"，而 32 片刚在同一页放了个正在读路由的
卡片。边界保留了（E0–E5 **逐条**记录仍无路由），措辞改为同时说明证据链完整性可读回并点名路由；
appshell ⑦b 钉住两面：必须出现 `/api/evidence-projection`、必须继续说逐条记录没有路由、不得复活旧的
无条件断言（已验证：退回旧文案会红）。提交 `78abda27`。

### 33.6 交给 owner 的具体选择

每条 INERT 的选项、代价与入口都在普查页里（`retire_targets` 给出要动的文件与账本行）：
- 8 条重叠且已被实现的：要么把 schema 定义改成对齐真实表并升级为 BINDING（需要 emitter 真的产出它），
  要么退役 schema、保留表作为唯一形状；
- 3 条形状对得上但没人写：需要产品决定这张表是否要被写，schema 不是缺的部分；
- 17 条无对应：退役即删文件 + 删行，`retire_coherent` 已确认无连带。

不自作主张执行任何一条：升级合同是宣布"边界已受保护"，退役是销毁一个声明，两者都是产品判断。

## 34. 界面换上自己的标志：一张黑白稿怎么穿过被 CSP 锁死的界面

### 34.1 为什么这算能力链上的一环，不是美工活

侧栏品牌砖和旧版页头一直写着 `DL` / `D/L` 两个字母。owner 交了正式黑白稿，要求"匹配界面尺寸比例、
自行抠出来使用、可以加光效"。难点不在抠图，在服务边界：`src/design_lab/workbench.py` 只服务三条
固定路径（index.html / main.js / style.css），文件头写着"never serve arbitrary paths or project
assets"，CSP 是 `img-src data:`。于是"加一张 logo"只有两条路：扩白名单并放宽 CSP（一次安全面变化，
还要动 wheel 打包与 packaging 校验），或者把资产内联进那条已经被服务的样式表。选了后者，并且把这个
理由写成断言——`test_workbench_brand_asset.py` 钉住 `img-src data:` 仍在、`ROUTES` 仍是三条；哪天真
加了资产路由，测试会要求改动者同时交代 CSP，而不是让 data URI 作为孤儿继续躺在样式表里。

### 34.2 抠的过程（可复算，不是手调参数）

源图 1344×1384、mode L。按行墨迹投影得到三条带：681×662、1088×117、758×135。选字标带用的是
"最接近正方"，不是"第一条带"——第一条带这个假设一旦上游把图裁掉顶部就会静默选中字标。
alpha 斜坡取 `clip((L-64)/128)`：源图是双峰的（85.2% 低于 32、12.5% 高于 224、中间只有 2.3%），
所以斜坡几乎不吃掉任何真实边缘。结果 17.93% 不透明 / 76.46% 全透 / 5.61% 过渡，不透明处 RGB 恒为
255，图形离画布边 10–12px。输出 144×144 透明画布、字形占 86%，PNG 4,953 字节、内联后 6,626 字符。

48px 的槽位放不下 1088×117 的字标带，所以只用图形标；`DESIGN-LAB` 仍是文本，这也正是品牌砖可以
`aria-hidden` 的前提——名字由文字给出，图像没有可播报的内容。旧写法把 `DL` 放在砖里，读屏会把项目名
念两遍。光效用 `::after` 承载，因为 `filter` 加在砖上会去给圆角方形的边描光，而不是给字形。

### 34.3 "logo 显示了吗"只能在真浏览器里回答

我一开始把断言写进 `apps/workbench/tests/appshell.mjs`，给 mock 的 `MockElement` 补了
`querySelector`。结果 `navigator is not defined`：`mountB10Shell` 第一行是能力探测
`if (typeof probe.querySelector !== 'function') return null;`，注释写明"the vm unit smoke has no
real querySelectorAll, so this never runs there"。也就是说那个 mock 缺 `querySelector` 是故意的，
补上它等于改了产品在该壳下的行为——它真的挂载了 B10 侧栏，然后撞上 mock 里没有的 `navigator`。
已回退，断言改到溢出门里。

样式表文本同样回答不了这个问题：URI 写坏了，声明仍然在。所以门里量的是渲染结果——砖 48×48、
无文字、`aria-hidden=true`、`::after` 的 filter 生效，以及浏览器自己报出这条 data URI 解码成
144×144。三个宽度各测一次。

### 34.4 这一片自己被证伪过什么

- 植入故障一：把内联 base64 换成合法但非 PNG 的串 → `OV_BRAND_BROKEN 1440: the mark decoded as
  decode-failed, not 144x144`。
- 植入故障二：把 `background:var(--brand-mark) center/76% no-repeat` 换成 `background:none` →
  `no-data-uri`。
- 两次都红，恢复后控制绿，且样式表字节与实验前一致（脚本比较 sha256 后才退出）。
- 单测侧同样可扰：payload 互换、digest 互换、资产缺失三种情况都要求 `--check` 返回 1；
  砖不消费 token、区域跑到 `:root` 外面、图形贴到画布边（即黑底没抠掉）都会红。
- `12` 例单测 OK，聚合 `VERIFY_DESIGN_LAB=OK total=68 failed=0`。

### 34.5 顺带纠正的一处旧账

给样式表加东西时撞上了 `test_workbench_css_single_definition.py` 的列表容器精确清单：树里是 41，
pin 还写着 39，差的两条正是 a0d001a8 加的 `projectionReasonList()` 与 `projectionReceiptRows()`。
增长是合法的，不合法的是这个 pin 四个提交之前就被打破而没人知道。之所以漏掉：那次报"398 全绿"的运行是
`--modules` 子集，而这个文件不在子集里。**子集不是全套**，把子集当全套汇报，正是精确清单型 pin 能
在被打破之后继续活下来的方式。本次之后每片收尾都跑 `--order forward` 全套。

### 34.5b 全套跑出来的另外两处（都是我自己前几片留下的）

同一轮全套还抓到两个子集永远看不见的红：

- `test_oda4_0204b_object_model_roundtrip.py` 的最小实例合成器不解析 `$ref`。`juror` 在
  `#/$defs/juror` 里是一个对象，合成器因为拿不到 `type` 就回落成字符串 `"test-value"`，于是
  round-trip 判的是探测器的盲区，不是 schema 的问题。这条从 463416fa 把 quality-report 一行
  重指到 `assurance-jury-record-v2.schema.json` 起就是红的——那一行的 required 字段全是 `$ref`。
  修的时候又连着掉出两个同类盲区：digest 的 pattern（schema 故意拒绝全零摘要，所以值改由字段名
  派生），和 rfc3339 的 pattern（装的 jsonschema 不校验 `format`，schema 只能用正则守时间戳）。
  schema 三次都对，错的一直是探针；现在解析不了的 `$ref` 会大声失败，不再悄悄塞字符串。
- 新增一个被跟踪的二进制，在这个仓里不是免费的：`verify_license_coverage.py` 要 SPDX 头与
  sidecar，`verify_asset_governance.py`（DL-AST-001）要 sha256 对得上、权利字段是布尔、
  并且没有 sourceId 就必须有人批的例外与到期日。sidecar 按事实写：作者与批准人是 owner
  本人（DTALEX66），依据就是本次"抠出来使用"的指示；`commercialUse` 真（它进产品界面）、
  `modelInputAllowed` 真（owner 把文件交给了做抽取的会话）、`redistributable` 假——
  没有任何一句话说过这个标志可以带到项目之外，品牌怎么授权是 owner 的决定，不是我替他写的。
  这三项里若有不对，改的就是这个 sidecar。

两处都不是"新发现的缺陷"，是"我前几片没跑全套所以没看见的缺陷"。差别很重要：前者说明门有用，
后者说明我汇报绿的方式有问题。

### 34.6 交给 owner 的选项

- 完整 lockup（图形标 + `DESIGN-LAB` 字标 + 中文副标）已能量出来并内联，但当前界面没有需要宽版品牌位
  的版面（没有 splash / 关于视图）。要用的话，入口是 `index.html` 的 legacy header，或者新增一个关于
  视图——这是版面决定，不是技术缺位。
- 若希望 logo 作为文件被服务（便于外部宿主或导出物复用），需要同时改 `workbench.ROUTES` 与 CSP
  `img-src`；`test_workbench_brand_asset.py` 会拦住并要求写明理由。
- 桌面窗口图标（原生宿主标题栏 / 任务栏）还没用这张稿，那是原生侧的资产通道，不在这条 Web 边界里。

## 35. 开源吸收池的账与货对不上（实测，含一处我自己的探针错误）

### 35.1 先说清楚：字段名猜错那一次

第一版新鲜度探针按猜测的字段名（`observedAt`/`id`/`sha256` 平铺）去读，结果是 980 条候选
全部"从未观测"、覆盖度全 0。**一批本该互不相同的样本读出全 0，是探针没动，不是池子全过期。**
换成记录里真实存在的字段（`adoption.observedAt`、`pinnedCommitSHA`、`source.acquiredAt`、
`integration.target`）之后，数字才分开。这条写进仓，是因为这类"全 0/全同"的读数最容易被人当成
结论念出去。

### 35.2 池子的真实状态（`CANDIDATE-TAXONOMY.json`，980 条，generatedAt 2026-10-06）

- 观测新鲜度：979 条的 `adoption.observedAt` 距今 ≤7 天（实测 2 天），**唯一没被重观测的是
  `tool-control`**，它同时也是唯一没有 `pinnedCommitSHA` 的一条；另有 7 条缺 `discoveredAt`。
- **吸收并没有发生**：980 条 `evidenceLevel` 全是 `E0`，`tier` 全为 `None`，
  `reviewedBy` **0/980**；disposition 只有 943 DISCOVERED + 37 CONDITIONAL_POC。
- 类型分布里确实有可复用的料：`component-library` 125、`design-system` 178（合计 303），
  其中按 `rights.license` 统计 MIT 194 / Apache-2.0 39 / NOASSERTION 31 / 无 23 / CC0 6 / ISC 2。

所以"开源池完成吸收了吗"的答案是：**调研完成、入库未开始**，而且已入库的那一小撮现在对不上账（下节）。

### 35.3 账与货零重叠

- `SOURCE_REGISTRY.json` 6 条，每条 `integration.target` 指向 `design-lab/knowledge/sources/<id>`；
  **这 6 个 target 现在一个都不存在**。`git log --diff-filter=D` 指到 `c9cde8a5`
  （2026-09-04，DL-DIR-MIG-R1 目录迁移），`git ls-files` 里已无任何 pixelmatch / ckw-design 路径。
  也就是说这份"人已审、字节在握"的记录已经悬空 34 天。
- `.project-local/cache/vendor/` 下实际有 **37 个** vendored 根（baoyu-design、tool-control、
  ui-ux-pro-max、visual-quality__* 等，合计约 30 MiB），**37 条一条都不在 SOURCE_REGISTRY 里**。
- `QUARANTINE_REGISTRY.json` 162 条，`contentHash` 0/162、`reviewedBy` 0/162，文档仍停在 2026-08-16。

### 35.4 已有守卫为什么没响

`design-lab/scripts/verify_source_registry.py:143` 确实会报
"integration.status=active but target is missing"。这 6 条的状态是 `review-required`，
不在该分支的覆盖范围内——所以这不是"没有门"，是**门的谓词只保护已激活的行，而字节被删掉的
待审行可以无限期保留"人已审"的样子**。修法应当是：任何带 `target` 的行，若 target 不存在，
就必须显式声明缺失状态（含缺失起始提交），不能让"删除"伪装成"待审"。本轮记录事实，改门与改状态
作为下一步，且注册 37 个 vendored 根需要 owner 人审——`verify_candidate_taxonomy.py` 明令
"代理不得自签 reviewedBy"，我不会替自己签。

### 35.5 关于"缺依赖就跑不了"的追正

上一轮我说 design-review 插件的 `audit-design-debt.mjs` 因缺 `fast-glob` 跑不了，并把这当成
环境限制。两条都不成立：(1) 我把"没装"当成"不能做"，而仓库自己的令牌门 + 直接扫描能回答同一问题，
我也确实拿到了数字（1238 条非令牌声明里 18 处字面色值、360 处字面 px、9 条无令牌阴影、12 条 z-index）；
(2) 本机对 `api.github.com` 与 `registry.npmjs.org` 的实测都是 200，"GitHub 连不上"这条旧记忆是错的。

## 36. 界面设计标准这一问：门本来有，但没问对问题

### 36.1 已有的门覆盖到哪

`design-lab/tests/e2e/audit_workbench_ui.mjs` 是量化 UI 门（对比度、键盘可达、alt、降级态措辞、
控制台噪声），`audit_workbench_contrast.mjs` 专管 WCAG AA 对比度，溢出门管裁切与不可达文本，
`test_design_system_tokens.py` / `test_interop_dtcg.py` / `test_workbench_css_single_definition.py`
管令牌与样式表单定义。本轮实测：UI 门 26 项度量 **0 违规**，令牌三门 **68 例 OK**。

但这些门问的都是"宽度"。`AUDIT_WIDTHS` 默认 1280/1920/2560，配 900px 以上的高度——**在这套门
跑到的任何一处，侧栏导航都不会溢出**。

### 36.2 实测出来的两个真缺陷（都已修）

1. **矮窗口下侧栏静默吞掉菜单项。** 11 个目的地要 587px；窗口高度 ≤720 时列表开始被裁，
   实测隐藏量 68px(720) / 177px(620) / 237px(560) / 297px(500) / 317px(480)，屏幕上没有任何
   "下面还有"的信号。`overflow:auto` 不是可供性：不知道能滚的人不会滚，而被裁掉的恰好是
   预检/QA、交付中心、证据系统、协作、设置。
   修法复用旧版底部导航**已有**的同一谓词 `.has-scroll-more` + 粘性 `::after`（那里的注释记录了
   "绝对定位的伪元素会随条目一起滑走"的踩坑），做成竖向变体，滚到底自动消失；不新造第二套机制。
2. **窄屏抽屉 Escape 无效。** `setNavOpen()` 打开时把焦点移进抽屉，键盘用户 Enter 打开后
   没有 Escape 可退。现在 Escape 关闭并复用 setNavOpen 里既有的"焦点还给触发器"分支。

### 36.3 两条断言都做了故障植入

- 把 cue 的 `content` 改成 `none` → 门报 `nav-overflow: cue claims true but paints content=none`。
- 只把抽屉那一句 Escape 条件改坏（不动命令面板里另一处同名比较）→ 门报
  `nav-drawer: narrow: Escape left the drawer at aria-expanded=true`。
  第一次植入我用全局字符串替换，把两处 Escape 一起改了，门因为别的原因红，**证明不了新断言**；
  重做时按整句条件定位，并要求控制态 0 违规。
- 恢复：样式表与 bundle 均比对 sha256 后逐字节还原；bundle 另用 vite 重建确认与源码一致。

顺带确认的两个事实（不是缺陷）：`B10_NAV` 11 条 vs `ROUTE_VIEWS` 12 条，差的那条是 `workbench`
根路由，不需要导航项；抽屉关闭态实测 11/11 目的地不可达，靠的是 `inert`，这是正确行为。

### 36.4 设计债实测（去掉 `:root` 令牌块后的 style.css）

1238 条声明里：字面色值 18 处（`#fff` 若干、`#1D4FC4`、`linear-gradient(135deg,#1D4FC4,#2A63D8)`——
后两个是绕过 `--color-primary` 的"差不多蓝"）、字面 px 360 处、未走令牌的阴影 9 条、z-index 12 条无层级表。

### 36.5 还缺的那一半：没有机器可读的设计契约

Design QA 要求"源真值 + 渲染实现"两侧都能打开。渲染侧现在能（真实 Chromium + 多视口截图 +
几何/命中断言）；**源真值侧在仓内不存在**：没有 `DESIGN.md` / `SCREEN_SPEC.md` / `design.qa.yaml`，
权威设计源是 `D:\All projects\UI套件` 里的 B04/L4/B07 展板（PNG）。因此"界面是否符合设计标准"
目前只能回答到"符合仓内已编码的令牌/对比度/可达性/响应规则"，**不能**回答"符合设计展板"——
任何逐像素一致性结论都会是假的。补一个把 UI套件 令牌落成仓内文本的 `DESIGN.md` 是这一步的前提。
