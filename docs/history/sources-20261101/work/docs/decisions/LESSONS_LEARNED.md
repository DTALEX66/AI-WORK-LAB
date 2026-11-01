# 经验教训固化（2026-08-23 治理体系构建全过程）

> 从今天完整对话提炼的经验，固化为本项目治理纪律，防止未来 agent 重犯（防止胡乱漂移）。

## 一、核心教训（跨会话铁律）

### 1. 核实优先 > 凭记忆假设
- 任何结论（版本/状态/文件内容/路径）必须读文件核实，禁止凭记忆/印象下结论
- 今天所有误判的根源都是我以为而非我查了
- 错误示例：language 空（查错字段）、648 是副本（没看路径）、HEAD 是 tag（没 describe）

### 2. 治理最小化（治理必须比执行轻）
- 治理是最小护栏，不是每步设卡；检查只在落地前一次
- 建议性检查 fail-open（失败不阻塞执行，只报告），禁止元治理循环；安全/权限检查 fail-closed（失败即阻断）
- 工具按需用（可选），不强制；加机制前先问更快还是更慢
- 做减法优先，不为完美堆机制

### 3. 三层结构（清晰定位，不混淆）
- 全局层：跨软件跨项目的通用规则（安全边界/数据边界/官方更新/五维基线）
- 项目层：各项目内部自己的规则/技能/插件
- 软件层：各软件自身配置（Hermes SOUL/Codex AGENTS/DSH 工作区）
- 全局不等于某个软件（Hermes）单独；全局=一套规则适配所有软件+项目

### 4. 官方优先（软件更新铁律）
- 更新以官方发布为准（官方 tag/release/安装包），禁止私自本地打包构建
- 唯一入口 = 官方标准格式（vendor 发布什么就是什么），不自定义 launcher
- 官方命令（如 hermes update）不等于官方发布标准（update 默认 main，发布=tag）

### 5. WORK-LAB 定位 = 治理控制面（非 runtime）
- 职责：全局规则定义+部署、软件入口标准、执行规范、并行协作、技能调用、防漂移
- 不承担 runtime（Observer 只读）；这些是本职，不是额外工作

## 二、具体误判清单（防止重犯）

| 误判 | 真相 | 教训 |
|---|---|---|
| DESIGN-LAB 648 skills 是运行时副本 | 项目源设计能力库 | 看路径再定性 |
| WORK-LAB 138 scripts 偏多闲置 | 治理工具链核心（仅1个0引用）| 查引用再判断 |
| 用户配置 = language 字段 | provider/model/auth/desktop | 读定义 |
| 质量门/CI 全量一刀切 | 已有 --changed + gate-plan | 核实机制 |
| Hermes HEAD 应=tag | hermes update 默认 main | 区分命令vs标准 |
| 唯一入口需 vbs launcher | 官方标准格式 | 官方发布为准 |

## 三、执行纪律（防漂移）

- 读文件核实 > 凭记忆（下结论前先 read/grep/Test-Path）
- 做减法 > 做加法（治理最小化）
- 必须 > 可选（可选不列待办，不制造虚假剩余）
- 每步核实 > 连续带病推进（不停下来确认会错误累积）
- 区分命令 vs 标准（官方命令的输出不等于官方发布标准）

## 四、今天已固化的机制（治理控制面资产）

- 全局标准：00-governance/global-execution-standard.md（生命周期+最小化原则）
- 规则同步：deploy_global_rules.py（单一来源到各软件）
- 强制拦截：e_drive_guard.py + terminal guard
- 技能调用：skill_call_index.py（索引+失效重建）+ SOUL/AGENTS 纪律
- 并行框架：agent_claims + worktree_manager + merge_queue
- 防漂移：project_drift_check.py（基线+检测+收敛）
- 模型路由：model_router.py

---

## 五、2026-09-03 补充：循环幻觉 / 任务漂移 / 批量替换教训（WL-DIR-MIG-R1 收尾实战）

> 用户连续质疑「汇报进度？」「是不是循环幻觉了？」「为什么老出模型错误？」后，以 git 证据复盘（error-ledger ERR-084..086 已固化）。

### 1. 批量路径替换铁律（ERR-084）
- 迁移后全仓库路径引用改写是**高错误率场景**（parents[N] 深度、ROOT 语义、模块位置全变），对任何模型都不例外
- 批量替换前必须先 `git grep` 计数命中；替换后**每个被改 Python 文件立即 py_compile + 单文件测试**
- 含复杂语法的代码块用 patch 而非 `str.replace`——本次 `str.replace` 直接把 test 的 load() 替换成语法错误（`'(' was never closed`），一次引入 40+ CI 失败
- 换行/路径写入 Windows 字符串时注意 `\r` 转义（曾出现 `DSH\r\nesources` CRLF 嵌入损坏）

### 2. 修复循环止损纪律（ERR-085）
- **同一目标修 2 轮不收敛 = 停下重新评估问题性质**，不是继续加码。13 个 fix commit 在同一套件打转是本次最大错误
- 动手修一个失败套件前必须先回答：**baseline 绿不绿？义务载体现在在哪？**
  - 本次铁证：`setup.sh/setup.ps1` 从未被 git tracked 却被测试断言读取 → 该套件 baseline 可能从未全绿，修复前提错误
  - 正确动作是重新定位问题性质（测试义务漂移 vs 迁移回归），不是逐条修断言
- 义务仍在的测试改指向新位置（README→docs/current/workflow-assistance-README.md 存档、setup→scripts/setup-workflow.* 迁移改名），义务随文档重写消失的更新断言

### 3. 任务范围 + 汇报纪律（ERR-086）
- **主任务完成 = 检查点**：任何超出主任务的延伸（CI 长尾、额外清理）必须先汇报并取得同意
- **每次状态变更（commit/push/清理）后汇报**——不等用户质疑。本次交接/上传/清理（18f0dff）完成后又自主延伸 5 个 fix commit 未汇报
- 用户质疑时用 git/文件证据直接回答（`git log` 循环证据、`git ls-files` 从未 tracked 证据），不用口头保证

### 4. "老出模型错误"的真实归因（答复用户）
- 主因是执行方式（批量替换不验证 + 循环无止损 + 不汇报），不是模型随机抽风
- 客观因素：大型目录迁移（28 commits、数百文件）本身对路径语义是毁灭性改动
- 次要因素：会话内模型多次切换（mimo-v2.5 → deepseek-v4-pro → deepseek-v4-flash），flash 级模型在精确长尾修复上更易上下文丢失/批量出错——但同样的坏习惯换更强模型仍会犯错

---

## 六、2026-09-29 补充：三项目 GitHub 交付链与本机身份（ERR-090..091）

本节记录本次已验证的事件，不替代当前 Authority、GitHub 规则或实时身份检查。WORK-LAB PR [#159](https://github.com/DTALEX66/WORK-LAB/pull/159)、ArcheAxis-Knowledge-OS PR [#154](https://github.com/DTALEX66/ArcheAxis-Knowledge-OS/pull/154)、DESIGN-LAB PR [#207](https://github.com/DTALEX66/DESIGN-LAB/pull/207) 已合并；main 回读分别为 `d424236ea5dabc135775c444014263adf60cc160`、`df1a0d59961d0ced18c99dc3e31a5c5bee4a4eac`、`7a00b8bc8d9688ff387b3a5984d91b3ee90027b7`。三个合并提交的主线门禁已通过；DESIGN-LAB 的 H001 main-run 上传证明也通过。这是当时的 exact-SHA 证据，不保证未来运行状态。

### 1. 身份与权限必须分层诊断（ERR-090）

- 网页 GitHub 连接、`gh` CLI、Git SSH/HTTPS 与 Codex 沙箱是不同身份和运行层。网页连接返回仓库写权限，不能推出本机 `gh` 或 Git 已可用；`gh` 登录也不能推出 Git 实际传输身份。`user.name`/`user.email` 只是提交署名。
- 本机 `gh auth status` 以退出码 1 报告进程继承的 `GH_TOKEN` 无效；忽略该覆盖后，已有 keyring 登录识别为 DTALEX66，三个仓库的 API `pull/push/admin` 均为 true。用户级 `GH_TOKEN` 已在用户明确授权后删除，Windows 环境变更通知已发送；**已运行的 Agent 软件和终端仍可能继承旧值，必须重启并重新验证**。未读取、记录或上传令牌值。
- 三仓库 Git 实际 SSH 读取与 PR 分支推送成功；AAOS 的 HTTPS 配置经 Git URL 重写后实际走 SSH。一次 WORK-LAB SSH `publickey` 拒绝在两次复测后消失，不能据此宣称永久故障或永久无故障。Codex 沙箱账户访问用户 `known_hosts` 受限也不能归因为凭据失效。链路正常时不为统一而切换 HTTPS + GCM。

### 2. 交付脚本必须先确认写边界

- PR #159 修复了硬编码项目路径、隐式 `git add -A`、可能写 main、`--create-pr` 静默成功、干净工作区漏报未推送提交、Git 失败被当成 CLEAN、错误质量门禁路径以及仅凭 PASS 文本/空检查列表批准审核等缺陷。修复后以项目注册表和 Git root/remote 身份定位仓库，写操作前检查分支、upstream、显式任务文件与已有暂存；检查 PR head SHA、必需检查和分页，失败/未知即拒绝批准。
- 16 项针对性回归测试及 WORK-LAB 本地质量门禁通过，PR head 与合并后 main 的 `aggregate` 均通过。AAOS 与 DESIGN-LAB 文档改用当前入口，WORK-LAB 保持可选协调工具，不成为其独立运行的强制依赖。模拟 PR 创建测试不能冒充真实凭据或所有 Agent 软件的桌面验收。

### 3. 分支规则检查要跟随变化的 main（ERR-091）

- PR head 上已有绿色检查时，WORK-LAB 和 DESIGN-LAB 的 main 又前进；GitHub 合并接口返回 405，要求在更新后的合并基线上重新取得必需检查。绿色的旧 head 检查不代表最新合并候选满足规则。
- 在隔离分支中合入最新 main，确认 PR 自身文件范围未扩大，推送普通分支并等待新 exact-SHA CI；随后合并、回读 main SHA 和合并后 CI。不得用 `--admin`、强推或修改 ruleset 绕过检查，也不得在合并确认前删除 PR 分支。一次被拒绝的合并是 BLOCKED，不是成功。
