# WORK-LAB 移交文档 — 独立审计对账 + 待决问题（2026-10-01）

> **用途**：一份**自包含**的移交文档。读者无需任何本次会话的上下文即可判断。
> **面向**：交给外部模型（GPT）评审，重点是**第五节待决问题**与**第六节我的错误**。
> **证据等级**：本文所有"通过"均指**本地 canonical 门**或**已列出的 exact-SHA CI 结果**；未运行项一律写 `NOT_RUN` / `BLOCKED` / `UNKNOWN`。

---

## 一、当前机器状态（可直接核对）

| 项 | 值 |
|---|---|
| 仓库 | `D:\All projects\WORK-LAB` |
| 分支 | `task-decomposition/atlas-gap-archive-20261001` |
| `HEAD` | `ea780b6` |
| 远端 | **只有一个** `origin` = `git@github.com:DTALEX66/WORK-LAB.git` |
| 远端分支 | `ea780b6`（与本地**一致**） |
| `origin/main` | `cd4daa8`（**未被本次会话修改**） |
| 领先/落后 main | **83 / 0**（fast-forward，**未改写历史**） |
| PR | **#162**，`state=OPEN`，`mergeStateStatus=**CLEAN**`，`mergeable=MERGEABLE` |
| 必需检查 `aggregate` | **pass**（exact-SHA CI） |
| canonical 门数 | **48**（本次会话前为 41） |

---

## 二、本次会话的任务

用户提供 `D:\All projects\Record\WORK-LAB_审计裁决_2026-10-01.json` —— 一份**独立收敛审计**：

| 项 | 值 |
|---|---|
| schema | `worklab-independent-convergence-audit/v1` |
| anchor_sha | `d43d07a75ef8c556344e9b3a99f9257dd2db7b5c`（**已核实不是 `main` 的祖先**） |
| overall_verdict | **`NOT_READY_FOR_REINSTALL_OR_DEPLOYMENT_ACCEPTANCE`** |
| 规模 | 47 裁决 / **23 发现（2 blocker / 9 high / 12 medium）** / 17 收敛项 / 10 unverifiable / 13 清理决策 / **7 合并门** / 3 风险 |
| 其中 | **18 项标 `needs_local=true`** |

**任务**：把这 23 项发现**逐项拿到当前树上对账**，不采信任何一方的叙述。

---

## 三、对账结果（全 23 项，脚本校验计数平衡）

| 结论 | 数量 | 条目 |
|---|---|---|
| **已修复** | **16** | F01、F02、F04、F05、F06、F07、F08、F09、F12、F13、F14、F15、F16、F18、F19、F21 |
| **已确认、仅报告** | **7** | F03、F10、F11、F17、F20、F22、F23 |
| 另 | +1 | 裁决 **Q5**（FAIL，指出共同根因） |
| **未对账** | **0** | — |

### 3.1 四项审计说法被**当前证据推翻或判定为夸大**

| 项 | 审计说法 | 实测 |
|---|---|---|
| **F03** | 探针读 `CODEX_HOME/skills`、源码写 `~/.agents/skills` → 会误判缺失/重复部署 | **探针根本不查技能**（只查 `codex` 可执行文件）。其机制不成立；但更窄的缺口存在：**Codex 技能部署从未被任何探针验证** |
| **F11** | "494 个 references 原文缺失" | 494 是**配额丢弃的文件数**（`ARCHIVE-INDEX.json` 的 `hermes.excluded_cap=494`），**不是 494 个按名缺失的引用**。有效残余：被丢弃文件**未按路径枚举**，依赖它们的结论无法溯源 |
| **F14** | 用户状态被混入清理候选 | **内容本非破坏性** —— `CC-4` 原文写"用官方 prune、**禁止删除**活动库"，`HH-1` 写"改设置、**只 OBSERVE 绝不删除**"。**缺陷在容器**：安全的话放进"清理候选"清单 |
| **F01** | 归档不是"三仓云端全树"，也不是"全部 GPT 历史" | 检查 `ARCHIVE-INDEX.json`、`ARCHIVE-README.md` 与审计包本身：**三者都没有这两种声称**。且今日脏项为 **5**，不是 111 |

### 3.2 六项最值得注意的修复

1. **F21 — 证据包里的可证伪假断言。** `global-workflow-coverage.json` 断言 `per_software.codex.has_worklab_managed_marker: true`，而 live 与归档两份 `CODEX_HOME/AGENTS.md` **都是 16,805 B / 691 行、都不含渲染器标记**。改为 `false` + 可复核更正块；MANIFEST 摘要同步。
2. **F08/F09 — `live_sha256` 从未被比对过。** `check_skill_provenance` 的 live 检查被 `if live_root is not None` 包住，而 canonical 门**不传 `--live-root`** → 门输出 `live_checked=False`。`model-switch` 因此长期带陈旧值。
3. **F07 — revision 正确、字节不对。** `chrome-profiles` 声明 `revision 5b9c3257`（`git rev-parse HEAD` **一致**），但工作树**被本地改过**：`__init__.py` 已装 **24,433 B** vs 该 revision 的 **23,764 B**。**只记 revision 等于给错的字节发认证。**
4. **F05 — 归档"完整性"是假的。** README 称"所有技能主文件均已完整复制"，实际**5 个根级技能从未归档**，含**受管技能 `model-switch`**（枚举只下潜进分类目录）。
5. **F19 — 一条被声明、却从未被检查的规则。** 边界验证器**从不扫任何调用者**；而 SSOT 的 `MEMORY_BACKEND` seam 写着 **"no new callers allowed"**，扫描显示**代码调用者为 0**。**既无人执行、又碰巧满足**。
6. **F18 — 归档的 `AGENTS.md` 被当作指令注入会话。** `ArcheAxis-Knowledge-OS/AGENTS.md` 归档进本仓库后，因**文件名是 `AGENTS.md`**，工具链**自动加载为治理指引**并注入本次会话（**实测发生**）。已加解除指令横幅。

---

## 四、本次会话新增的门与结构修复（41 → 48）

| 门/检查 | 作用 |
|---|---|
| **`evidence-tiering`** | 证据包的行为声明必须标等级（DECLARED/OBSERVED/VERIFIED）；**低于 VERIFIED 却不写"不能证明什么"→ 拒绝** |
| **`plugin-inventory-honesty`** | 插件记录不得超出证据；**revision 字符串不能证明字节匹配**；bundled 组件不得按"安装"语义评估 |
| **`root-governance-suite`** | 跑根 `tests/ci/` 套件（**此前 canonical 门完全不跑它**），`glob` 发现，新检查自动生效 |
| seam-caller 基线 | 声明"禁止新增调用者"的 seam，**增长即失败**（注入调用者已验证会失败） |
| 归档深度覆盖 | 只枚举深层、浅层为空 → 拒绝，除非显式记录缺口 |
| 归档指令文件 | 归档中可自动加载的治理文件名**必须带解除指令标记** |

**负向对照**：nf23 9 / nf27 43 / nf28 13 / nf29 22 / nf30 11，全部验证过"能失败"。

---

## 五、待决问题（**这是本文档的重点**）

### Q1 —— ⚠️ 启动器归属：`codex.cmd` 被部署进 Hermes 家目录

**用户提出的原则**：
> 各软件目录应该保持自己的内容；本项目只推送相关的；**如果是统一入口，应该放到用户目录下**。

**事实**（已核实）：

- **真源在本仓库**：`packages/client-neutral-core/bin/{codex, codex.cmd, hermes-npx, hermes-npx.cmd, hermes-project-data.py, hermes-project-terminal-guard.py}`，**均被 git 跟踪**。
- **部署产物**：`%LOCALAPPDATA%\hermes\bin\` 下同名 6 个文件。已比对 `codex.cmd`：**两边 SHA-256 完全一致**（`02a8ce078564626c`，1619 B）。
- **部署理由（我的推断）**：`%LOCALAPPDATA%\hermes\bin` **已在用户 PATH 上**（已从用户级注册表读出）。放这里可全局可用，**且不必改用户 PATH** —— 符合"治理最小化"。
- **`hermes/bin` 里另有 13 个不是我们推的**：`hermes.exe`、`hermes.cmd`、`hermes-acp.exe`、`uv.exe`、`browser.exe`… 这些**是 Hermes 自己的内容**。

**问题**：`codex` 是 **Codex 的入口**，却住在 **Hermes 的家目录**。这**违反"各软件目录保持自己的内容"**；同时也**不满足"统一入口放用户目录"**（它放进了某个软件目录）。`hermes-npx` / `hermes-project-data.py` / `hermes-project-terminal-guard.py` 那 4 个**不违反** —— 它们本来就是 Hermes 的工具。

**已提议但未执行**：把 `codex` + `codex.cmd` 移到中立用户级目录（如 `%LOCALAPPDATA%\Programs\work-lab\bin`），并**追加**一条用户 PATH。**未执行原因**：修改用户 PATH 是全局配置变更，按项目规则需明确授权。

**请评审**：这个搬迁是否合理？有没有比"新增 PATH 目录"更好的方案？

### Q2 —— Hermes / Codex 的删除与重装范围

用户表示**要自行删除 Hermes 与 Codex 后重装**，然后由 WORK-LAB 部署。但**删除范围尚未确定**：

- 方案 A：**只清家目录**（`%LOCALAPPDATA%\hermes` 26.22 GB + `%USERPROFILE%\.codex` 7.90 GB），程序本体保留
- 方案 B：**连程序一起卸载**（Codex 是 **Windows Store 包 `OpenAI.Codex`**，其包数据**不在这两个目录里**）

**关键安全发现（已完成只读核实）**：

- 两个目录内**无符号链接/junction** → 删除**不会**波及用户项目
- 用户项目独立存在于磁盘（WORK-LAB 38 项、ArcheAxis 76、DESIGN-LAB 45、Obsidian-Assistance 14、Record 57、资料库 4）
- `~/.codex` 数据库里的 `D:\All projects\...` 是**历史路径字符串**（会话记录里的引用），**不是项目数据**
- **凭证（`auth.json`、`.env`）一律未读取、未复制** → 重装后需重新登录

**已归档**（`reports` 外的本地归档）：`.project-local/artifacts/pre-reinstall-archive-20261001/`，**130 项、130/130 摘要校验通过**，含 `BOUNDARY-AND-RECOVERY-REPORT.json`。

**刻意不归档**（按项目规则）：Codex 会话正文（~4.3 GB，对话日志是禁止类别）、thread/logs（~1.6 GB）、Hermes `state.db`（4.32 GB）、凭证。

### Q3 —— 部署内容保全（F04）：已 land，但需在重装后验证

`windows-development-environment/SKILL.md` 的**实机版本比仓库多 2 条经验 + 1 个 reference**：

- **经验 30**：`.cmd` 包装器不能经 `node <path>.cmd` 执行（抛 `SyntaxError`），须直接传入或走 `cmd.exe /d /s /c`
- **经验 31**：`pnpm`/`cargo` 缺失必须**如实报 BLOCKED**，不得编造 PASS；Vite 检查仍可独立成立
- **`references/frontend-baseline-contract.md`**（仓库原无）

**已 land 进仓库源码**（144 行，1.3.0 → 1.4.0），并把 live 中指向**不存在**文件的悬空引用换成真实路径。**重装后需经 sync 部署 + 原生回读验证**（`NOT_RUN`）。

### Q4 —— codex 受管块缺失（ERR-095）与部署通道

- 状态文件（`~/.codex/.workflow-assistance-state.json`，v3）记录 `AGENTS.md` 受管块哈希 `365659e0…`，而实机**没有该块** → `sync` **故意 fail-closed**：`{"status":"BLOCKED","error":"managed guidance block changed after apply"}`
- hermes sync 的 **dry-run**（只读）结果：**21 步，20 步已收敛，仅 1 步受阻**（`windows-development-environment`，`guard_verdict=UNKNOWN_LIVE_CHANGE`），脚本拒绝发布并要求 `--adopt-baseline` 或 `--suspend`
- **未执行任何 apply**（只跑了只读 `plan`）

### Q5 —— 字段语义拆分（审计 F10/F23 与裁决 Q5 的共同根因）

审计指出：registry 把**"结构就绪度"**与**"部署观测"**写进了同一批字段，导致 `READBACK_VERIFIED` 与"AGENTS 缺块"并存。

**已做**：按 ERR-095 的台账指令把 codex 的 `maturity` 由 `READBACK_VERIFIED` 降为 `APPLY_SUPPORTED`，并新增 `deployment_observation` 块（**F10 拆分的第一具体形式**）。

**未做**：完整的字段拆分是**清单 schema 变更**，需要决策。

### Q6 —— 其余未决项

| 项 | 状态 |
|---|---|
| **AG-15 可写控制面** | 需决策：授权 loopback 零鉴权端点，或暂缓 |
| **AG-17 网页 GPT 传输** | 需决策：结构化人工移交 vs 官方 Remote MCP |
| **DSH_HOME 数据根迁移** | 需决策（`DSH_HOME` 用户环境变量仍指向 `D:\All projects\DSH\.dsh`） |
| **AG-09/10/11 真实执行闭环** | **BLOCKED**：需用户指定"一个项目 + 两个执行器" |
| **Rust/Tauri U19** | **BLOCKED**：Rust **MSVC 工具链无 `rustc.exe`**、无 Visual Studio/VC 工具。**先前发现 GNU 构建的 Tauri 二进制运行时缺 `WebView2Loader`** → **很可能仍需 MSVC**（即"授权抓依赖"可能解决不了） |
| **F01 的两个外项目 commit/tree 绑定** | **UNKNOWN**：需访问 `ArcheAxis-Knowledge-OS` / `DESIGN-LAB` 仓库的授权 |
| **DSH 是否一并重装** | 未答 |

---

## 六、本次会话我自己的错误（14 项，均已撤销并留痕）

| # | 错误 | 处置 |
|---|---|---|
| **E1** | 报告 `security-guidance`/`web-ddgs` 存在"声明 vs 观测不一致" | **假发现** —— 两者 `type/upstream/spdx` 均写明 **`bundled`**，实为随 Hermes 应用发布的组件（`hermes-agent/plugins/security-guidance`、`hermes-agent/plugins/web/ddgs`）；**不在用户安装目录是正确状态**。**已撤销**，新增门规则禁止再犯 |
| **E2** | 误把 `skills-inventory.json` 路径按 `packages/client-neutral-core/skills` 解析，一度认为"技能名字全错" | 已更正：其 `sources` 是 `integrations/executors/codex/skills`，14 条路径**全部可解析** |
| **E3** | 把 13 个受管技能**重复归档**一遍 | **重复劳动**（用户指出）；核实后 **11/13 哈希与既有 `reports/audit-archive/20260930` 完全一致**，重复部分**已删除** |
| **E4** | 对账计数（tally）**三次算错**（均加不到 23） | 第 25 轮起改为**由列表长度计算并打印校验** |
| **E5** | 手工数 `"x/skills/n/SKILL.md".count("/")` 数错，并写出 `3 if False else 2` 这种自相矛盾断言 | **删掉硬编码断言，改为断言语义** |
| **E6** | 证据分级校验器写成 `if not findings:` 串联，**一个检查可短路另一个** | 改为**两个检查都跑** |
| **E7** | `report_registry_closure` 的 `last_verified` 分支**从不查 reason** | 修正：有理由即标 `EXPLICITLY_OPEN` |
| **E8** | 编辑 `run_quality_gate.py` 误删 docstring 开引号；另一次误删 `if` 行 | 均由 `py_compile` **当场抓住**并恢复 |
| **E9** | `git show ... > file` 产生 UTF-16 + null 字节 → `SyntaxError` | 改用 Python 写 UTF-8 |
| **E10** | PowerShell 多行 `git commit -m` 被拆分 → `pathspec 'Every' did not match` | 改为始终 `-F <file>` |
| **E11** | 安全门把注释里的字面词 `token` 判为"可能的硬编码密钥" | 内部命名 `token` → `marker`（**改名字而不是加豁免**） |
| **E12** | **三次**把正当的 U+2014/U+2192 误判为"编码损坏"（控制台渲染问题） | 记录为环境陷阱；**注意本行前几版把替换字形当字面内容写进文件，才真产生 2 处 U+FFFD**，已在提交前改为描述 |
| **E13** | 断言用固定切片检查横幅，但文案在短语中间换行 → 失败 | **让断言折叠空白**，而不是为迁就测试改写文案 |
| **E14** | 误以为 `E:\` 命中是新暴露 | 核实**大部分是"禁止访问 E:\"政策文本本身**；且 `origin/main` 与分支**同为 86 个文件**含同类路径 → **不引入新暴露** |

### 6.1 CI 抓到的 3 个真实缺陷（**本地门全绿却失败**）

| 缺陷 | CI 报错 | 根因 |
|---|---|---|
| **A** | `ERROR_LEDGER_FAIL ERR-097 invalid phase` + `original failure exit_code cannot be zero` | 我给共享台账写了非法 `phase` 枚举值，且 `exit_code` 写了修复后的 0（该字段要**原始失败**的退出码）。**canonical 门跑 43 个 `tests/workflow-assistance/` 模块、`tests/ci/` 的 22 个一个都不跑** |
| **B** | `AssertionError: None != '/tmp/tmptbeohd9m'` | `_probe_install` 用 `os.path.expandvars`，它**只在 Windows 认 `%VAR%`**；本清单根路径**就是 Windows 形态** → Linux runner 上变量保持字面、探针报"无安装根"。**修的是代码，不是测试** |
| **C** | `CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch` | 我改了 `skill-provenance.yaml` 与 `SKILL.md`，而 `CURRENT_STATE` 的 source digest 覆盖它们 → 已提交生成物过期。本地**同样复现**（是过期，非平台差异） |

**缺陷 A 引出的结构性修复**：新增门 **`root-governance-suite`**，`glob` `tests/ci/test_*.py` 使**新检查自动生效**；只排除 1 个（`test_exact_tree_review.py` 断言 `HEAD == origin/main`，是**合并后复核**，在 PR 分支必然失败，**且它也不在 CI 门里**）；排除项**过期即报错**。

---

## 七、本文档撰写时的诚实边界

**已发生**：83 提交已推送；PR #162 已开且 `aggregate`（必需检查）**pass**、`mergeStateStatus=CLEAN`；双端一致；本地 48 门 PASS。

**未发生（一律 `NOT_RUN` / `BLOCKED`）**：

- **未合并 PR**（`main` 仍是 `cd4daa8`）
- **未执行任何删除**（Hermes / Codex 均**原封未动**）
- **未运行 sync 的 `apply`**（只跑了只读 `plan`）
- **未修改任何 live 客户端文件**（只读）
- **未读取或复制任何凭证**
- **未访问 `E:\` / `F:\`**
- **未安装、未联网抓取依赖**
- **原生运行验收 / 用户验收 / Release 全部 `NOT_RUN`**

**push 前的安全检查结果**：凭证模式（AWS / GitHub PAT / OpenAI / Anthropic / Slack / 私钥 / JWT / URL 内嵌认证 / Azure SAS）**0 命中**；私密会话正文 **0 命中**。

---

## 八、给评审者的具体提问

1. **Q1 的启动器归属**：把 `codex`/`codex.cmd` 搬到中立用户级目录 + 追加一条用户 PATH，是否是正确的解法？有没有更好的（例如不新增 PATH 而用别的方式提供全局入口）？
2. **Q2 的删除范围**：只清家目录 vs 连 Store 包一起卸载 —— 对"重装后由 WORK-LAB 部署"这个目标，哪种更干净？有无我未考虑的残留（如 `%LOCALAPPDATA%\Packages\`、注册表项、Node 运行时依赖）？
3. **Q5 的字段拆分**：把"结构就绪度"与"部署观测"彻底拆成两个字段，是否会破坏既有消费者？有无更低风险的过渡方案？
4. **Q4 的 fail-closed**：`sync` 因受管块消失而拒绝执行 —— 这是正确的保守行为，还是应当提供一条"明确审阅后重渲染"的受控通道？
5. **我对 4 项审计说法的推翻（F03/F11/F14/F01）是否成立**？如果成立，是否意味着该审计的其余部分也需重新评估可信度？
6. **E 系列 14 项错误**中，哪些反映的是**流程缺陷**（而非一次性疏忽）？我已把其中最典型的（A）做成门，还有哪些值得制度化？
