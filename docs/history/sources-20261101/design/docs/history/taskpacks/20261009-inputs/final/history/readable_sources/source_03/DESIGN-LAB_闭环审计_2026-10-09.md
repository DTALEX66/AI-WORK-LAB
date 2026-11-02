# DESIGN-LAB 闭环审计

审计日期：2026-10-09  
唯一审计对象：DTALEX66/DESIGN-LAB  
远端 main：`fc03a3033e900a8066d863a223636cc68804c4fa`  
已核验 CI：Canonical Verify，run `37602613560`，11 个 job 结论均为 success。Open Design 的条件式独立结构检查存在 skipped 步骤，不能把 job success 解读成真实宿主执行。  
审计模式：远端文件与实现抽查、实时 CI jobs/artifacts 回读、一个抽取函数的独立合成测试。没有修改用户仓库，没有控制 Windows/Adobe，没有重跑全仓测试。branch-protection 查询返回 403，未验证当前保护规则。

## 结论

DESIGN-LAB 已有可运行工作台、设计流程前半段、原生任务接口和受控测试基础。不能再按“没有前端、没有安装验证、没有产物证据”判断。

尚未获得完整产品闭环的证据：**设计决策 → 原生可编辑工程 → 局部修改 → 保存重开 → 人工评审 → 权利与生产预检 → 合格交付 → 独立安装环境复现与恢复**。

剩余工作不全是“等用户批准”。人工评审路由缺失、能力库资源打包和分类信息投影缺口，都是明确的工程工作。真实审美认可、权利裁决、宿主副作用许可与发布决定，才需要用户作出真实决定。

不以文档数量、候选数量、commit 数、测试数或旧报告百分比估算完成度。证据缺失也不等于相关代码不存在。

## 已经具备的基础

- Workbench：strict TypeScript、Vite build、构建产物一致性、真实浏览器受控运行测试。
- Project → Brief → Reference → Direction → DesignSystem：实际 API、持久化、修订、选择与绑定读回；测试明确不声称 E3/E4。
- 原生任务：HTTP 已有 native-plans、run、patch、cancel、bundle 和下载入口，不应误报为“原生功能全无”。
- 安装基础：CI 在干净环境安装 wheel，验证工作台静态资源、健康检查、项目重启读回。
- CI 产物基础：查询到 2 个未过期 artifact；浏览器 E2 artifact 绑定当前 main SHA。CI artifact proof job 成功。本次没有自行下载二进制 artifact 并重新散列。

## 发现与整改

### DL-AUDIT-01｜设计系统到原生生产的产品级接续仍需闭合

证据：`AUTHORITY.md` 第 15 节把 DesignSystem → DesignIR → Photoshop/Illustrator 列为原生生产剩余项。`http_service.py` 中，方向绑定接收 `design_system_name`，原生计划入口接收 `host/rir/text_styles/idempotency_key`；现有两类入口不能单独证明用户已能从设计决策一路完成原生生产。

裁决：原生任务接口存在；本次未确认“所选设计系统驱动原生对象计划”的完整用户链路，不把接口存在等同闭环。

完成标准：从 UI 中当前选择的方向与设计系统生成受控对象计划，保留 brief/direction/binding/version 到任务及产物的引用；支持不确定项修正；无需用户手写原始 RIR/JSON 来接通断点。

### DL-AUDIT-02｜E3 真实宿主往返不能由结构测试替代

证据：README 能力矩阵将 Adobe Adapter 限于 E1；现有权威要求真实 Brief、原生工程、两次局部修改、保存关闭重开读回、失败恢复与回滚。

完成标准：固定一个已安装宿主版本，用用户自有/许可明确的视觉项目，检查文字、形状、图层/对象等真实编辑性；两次局部 patch 不重建无关对象；中断后对账，不重复创建，不关闭用户无关文档。证据绑定源码 SHA、宿主和适配器版本、输入/产物哈希与回滚记录。

先跑通单宿主可作为阶段检查点；不擅自把当前任务包里的 Photoshop 和 Illustrator 双宿主验收删掉，也不绕过原有依赖关系宣布全部 M1 完成。

### DL-AUDIT-03｜人工 Jury 缺可操作的产品入口

证据：2026-10-07 实施报告明确记录 Human Jury 合同存在但无路由/UI；本次抽查完整 `http_service.py` 的 GET/POST 分发，未见 Jury 提交与审查路由。

裁决：不是“只剩用户点击”。工程需先接通显示评审对象、意见、Accept/Reject/Request changes、修订比较与回执。

完成标准：真人可对确切产物版本作决定；Agent 可准备界面、自动检查和候选意见，不得冒填真实人工审核人/时间/结果。修改产物后不得沿用旧版本的合格状态。

### DL-AUDIT-04｜测试导出与合格交付尚未同义

证据：`native_delivery.py` 的导出授权 scope 是 `project-native-test`，回执显式写明不代表 rights/quality acceptance。预检浏览器用例主要覆盖工具可用/缺失/恢复及零交付包显示，不能代表真实设计品的权利与生产规格已验收。

完成标准：区分测试导出/草稿与正式交付；对原生工程、预览、依赖素材、字体信息、尺寸色彩、链接、可编辑性、rights、Jury、BOM、版本与哈希形成一次有真实文件的预检。缺任一必需证明时可以保留草稿，但不能签发可正式交付结论。

交付包要在离开开发目录后解包、重开和核对，不只证明“ZIP 能下载”。

### DL-AUDIT-05｜审美资料库尚未成为可调用、可评估、可撤销的能力库

证据：10 月 7 日实施记录区分了 60 个展示记录（46 来源 + 14 模型）与 980 个候选；候选中的多个分类/审美/审核轴为空，证据级别为 E0。该统计是该记录的观察，不是本次重跑整个候选集所得。

本次直接检查 `analysis/capability_library.py` 得到两项实现事实：

1. `_taxonomy_axes()` 返回来源、权利、热度和 `unclassifiedAxes`，没有返回 7 个分类轴的实际值。对抽取函数输入 7 轴均非空的合成候选，输出 `unclassifiedAxes=[]`，但 7 轴本身仍全不在输出中。见同包 probe/result；不是全仓或浏览器复测。
2. 来源和模型的 `qualified` 固定为 `None`，`qualificationEvidence` 也为 `None`。这忠实表达当前投影没有资格化证据，但不能替代未来从真实资格化结果读回的实现。

因此不是只给源表补标签就完工。需要：真实分类值透传到 API/UI；从现有证据记录接入资格化状态；对选定来源做 source/revision/license/用途/映射/落点/测试/回滚闭合。

现有 `SOURCE_REGISTRY.json` 的 6 个 integration.status 均为 `review-required`，不能把已有来源许可记录误算成整合已完成，也不能误报“没有任何历史来源人工审核”。

最小推进建议：选择服务于当前黄金工作流的少量来源，先完成分类候选、来源引用、合法性核对、独立适配和真实案例对比。不要求 980 条全部吸收，也不把热度当审美质量。机器可整理有出处的描述性标签；人工签名与质量认可保持真人操作。

### DL-AUDIT-06｜wheel 的能力库资源存在高置信静态部署缺陷

证据链：

- `analysis/capability_library.py` 默认根为 `Path(__file__).resolve().parents[3]`。
- 随后读取 `vendor/sources.lock.json`、`vendor/sources.revisions.json`、`design-lab/readiness/model-radar.json`；分类还依赖 `research/candidates/CANDIDATE-TAXONOMY.json`。
- `pyproject.toml` 的 wheel 包含 `src/design_lab` 与明确 force-include，未包含上述库输入。
- `test_workbench_launch.py` 即使在安装模式仍以 `cwd=REPO` 启动进程；验证静态 UI、health、projects 与重启，不访问 `/api/capabilities`。

裁决：干净 wheel 的启动基础测试是有效的，但并未证明能力库脱离源码可用。按所查代码推演，标准安装布局中所需文件缺失时，`/api/capabilities` 将进入文件缺失异常路径。此项为高置信静态发现，未在用户 Windows 上动态复现。

完成标准：把必要的、脱敏的最小只读目录作为安装资源，或通过明确可配置的数据提供者加载；不把整个外部资料/模型库打进 wheel。测试需真正离开源码 CWD、禁用源码路径兜底并检查 `/api/capabilities` 及所声明的核心业务链。

### DL-AUDIT-07｜可重复交付、资产恢复与 E5 尚需验收

证据：本次可见 Releases 集合为空；当前 README 明确 E5 尚未达到。10 月 7 日记录说明真实作品和交付包存在于 `.project-local/projects` 下的本机工作区，不能把这些当缓存随手清理。

完成标准：从固定提交得到可验证安装包，在标准 Windows 配置下执行真实工作流与重启恢复；备份资产后做实际恢复与哈希校验；保留已知限制和回滚方式。源码仓库无须塞入全部大型作品或客户内容。公开发布仍需用户明确授权；不能擅自创建 Release。

## 排序与完成定义

| 顺序 | 工作包 | 交付/验收 |
|---|---|---|
| 1 | 修复能力库资源装载与测试边界 | 独立 wheel 环境核心路由可用 |
| 2 | 补齐分类值/资格化证据投影，接通 Jury API/UI | 不只展示观察记录；真人有实际审查入口 |
| 3 | 打通 DesignSystem → 原生计划 → 执行 | 真实方向/设计系统与原生产物有可核对的关联 |
| 4 | Adobe E3 往返与异常恢复 | 原生编辑、两次修改、关闭重开、失败对账/回滚 |
| 5 | rights + Jury + preflight + 可重开交付 | 正式交付与测试导出严格分开 |
| 6 | 黄金工作流与资产恢复 | GOLDEN-001/002 按既有任务包保留并验收，结果可再使用 |
| 7 | 固定版本与重复验收 | 当前 SHA、安装包、运行证据、回滚和限制一致 |

其中 1–3 有明确可执行的工程部分，不能笼统推给 owner；4–5 的真实宿主操作与人审需实际环境和真实决定；6–7 不得由一次 CI 成功代替。

项目可独立闭环：不等待 WORK-LAB、ArcheAxis、所有 Agent、所有本地模型或所有开源候选。前述跨项目集成是可选后续，不是这次 DESIGN-LAB 验收前置。新增框架、第二画布、第二账本、全仓重写不在本审计建议内。

## 证据使用限制

`reports/current/PROJECT_STATUS.md` 自述观察提交为 `63b12e96...`、`test_run_id=None`、worktree subject，不能直接当作当前 main 的验收凭证。旧 SHA 不自动证明报告损坏：仓库有 input/tree-digest 与 STALE 语义。这里不据其全 PARTIAL 状态推导“代码全部没完成”，也不据其数字算百分比。

## 精确源码入口

以下均按 `fc03a3033e900a8066d863a223636cc68804c4fa` 读取：

- AUTHORITY.md
- .project/governance/authority-index.json
- AGENTS.md
- README.md
- docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md
- docs/audits/DESIGNLAB-UI-IMPLEMENTATION-REPORT-2026-10-07B.md
- src/design_lab/http_service.py
- src/design_lab/native_delivery.py
- src/design_lab/analysis/capability_library.py
- pyproject.toml
- .github/workflows/canonical-verify.yml
- design-lab/tests/test_workbench_launch.py
- design-lab/tests/test_design_layer_http.py
- design-lab/research/global-absorption/SOURCE_REGISTRY.json
- reports/current/PROJECT_STATUS.md
- design-lab/config/task-ledger-r3.json（仅入口/前继结构抽查，不声称全文逐项完成审计）

GitHub 源码 URL 结构：
`https://github.com/DTALEX66/DESIGN-LAB/blob/fc03a3033e900a8066d863a223636cc68804c4fa/<相对路径>`

CI：`https://github.com/DTALEX66/DESIGN-LAB/actions/runs/37602613560`

本报告是本次审计结果与整改建议，不替换项目 AUTHORITY、唯一机器账本，不授权改动其他项目或用户资产。
