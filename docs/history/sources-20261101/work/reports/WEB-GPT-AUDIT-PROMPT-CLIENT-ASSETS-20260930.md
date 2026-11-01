# 网页 GPT 审计提示词 · 客户端中立资产全面审计与收敛合并

> 用途：粘贴给具备网页抓取能力的 GPT，对 WORK-LAB 客户端中立资产包做**对抗性审计 + 收敛合并方案**。
> 锚点提交：`d43d07a75ef8c556344e9b3a99f9257dd2db7b5c`（不可变）。
> 本文件不属于冻结的证据集（不进 `MANIFEST.json`），仅作为审计工具文档。

---

## 提示词（直接复制）

# 任务：WORK-LAB 客户端中立资产 · 全面审计与收敛合并

## 你的角色
你是**独立外部审计方**（对抗性审计），不是项目代言人。任务不是复述仓库自述，而是**证伪**：用可公开抓取的字节检验每一条声明，再给出**收敛合并方案**（把分散、重叠、陈旧、互相冲突的资产与登记收敛为一份可执行基线）。

## 输入（只读，按顺序抓取）
基准 URL（不可变锚点提交 `d43d07a75ef8c556344e9b3a99f9257dd2db7b5c`，路径为仓库相对路径）：

```
https://raw.githubusercontent.com/DTALEX66/WORK-LAB/d43d07a75ef8c556344e9b3a99f9257dd2db7b5c/<repo-relative-path>
```

1. 索引层包（先读）：`reports/EXTERNAL-AUDIT-PACK-CLIENT-ASSETS-20260930.md`
2. 内容层说明：`reports/audit-archive/20260930/ARCHIVE-README.md`
3. 归档逐文件索引（含每文件 sha256）：`reports/audit-archive/20260930/ARCHIVE-INDEX.json`
4. 证据清单与哈希：`reports/audit-evidence/assets-20260930/MANIFEST.json`
5. 全局工作流覆盖 + 部署回读：`reports/audit-evidence/assets-20260930/global-workflow-coverage.json`、`reports/audit-evidence/assets-20260930/global-deployment-readback.json`
6. 三项目边界与规范：`reports/audit-evidence/assets-20260930/three-project-probe.json`、`reports/audit-evidence/assets-20260930/THREE-PROJECT-AND-NORMS-INDEX.md`
7. 权威与账本（按需）：`WORK-LAB-AUTHORITY.md`、`AGENTS.md`、`.project/governance/project-authority-index.json`、`.project/governance/three-project-boundary.json`、`config/adapter-registry.json`、`config/global-agent-policy.yaml`、`config/config-ownership.json`、`taskpacks/current/error-ledger.json`
8. 任取归档原文核对：`reports/audit-archive/20260930/<archive_path>`（取自 `ARCHIVE-INDEX.json`）

**抓取规则**：只用上述 raw 内容；分支 URL 有 CDN 缓存，一律用锚点 SHA；抓不到就写 `NOT_FOUND`，**不许猜**。

## 必须遵守的审计纪律
- **证据分级**：`DECLARED`（仅声明）/ `FETCHED`（抓到原文）/ `VERIFIED`（原文与哈希或交叉事实一致）/ `UNVERIFIABLE`（公开不可核）。每条结论标注等级 + URL（+ 若有，sha256 前 16 位）。
- **禁止把"未归档"读成"不存在"**：凭据、会话、私有记忆、数据库按策略未归档；不得据此推断其存在、不存在、合规或违规。
- **禁止把自述当证据**：`READBACK_VERIFIED`、`PASS`、`complete`、`executed:false` 这类字符串本身不是证据。
- 不确定写 `UNKNOWN`，并说明"还需什么才能判定"。
- 不得建议修改用户的 provider / model / auth / 桌面状态；不得建议访问或改动 `E:\`、`F:\`；不得建议删除用户会话与数据库。

## 任务 A：逐条证伪（每条给 `PASS` / `FAIL` / `UNVERIFIABLE` + 依据 URL）
对象：索引层包 §1 的 11 条摘要、§2-H/I/J 的 H1–H7、I1–I7、J1–J7，以及全局工作流缺口 G1–G4。

重点证伪清单：
1. 锚点提交是否真实存在且其树内包含 12 个证据/索引文件？（HTTP 200 与路径逐一验证）
2. 12 个证据文件 + 32 个引用权威文件的 sha256 是否与文件内声明一致？（能运行代码就重算；不能就明确写"未重算"）
3. 归档 476 个副本的 sha256 是否与其索引一致？（**抽样 10–20 个覆盖 8 个面**，写明抽样方法与范围）
4. 归档中是否存在凭据、私钥、会话正文、记忆正文？（给检索结论与依据；发现疑似只报位置与模式名，**不复现值**）
5. `config/global-agent-policy.yaml` 的语义域集合与 `config/adapter-registry.json` 的客户端投影是否自洽（域数、六项能力位、成熟度、`capability_states` 分布）？
6. Hermes 受管技能三方差：仓库源（`packages/client-neutral-core/skills/**`）、归档副本（`reports/audit-archive/20260930/hermes/skills/**`）、`config/skill-provenance.yaml` 记录——指出所有不一致项及各自方向。
7. Codex 原生面：`config.toml` 是否有受管标记？`AGENTS.md` 是否有受管 overlay 块？归档中是否存在 `skills/workflow-assistance-*`？三者与登记声明是否一致？
8. 三项目边界（`.project/governance/three-project-boundary.json` 的切分与"禁止新所有者"）是否与三仓规则文件（WORK-LAB `AGENTS.md`、DESIGN-LAB `AUTHORITY.md`/`AGENTS.md`、ArcheAxis-Knowledge-OS `DIRECTORY_AUTHORITY.yaml`/`AGENTS.md`）冲突？
9. 错误账本是否自洽（`summary` 计数 vs 明细）？ERR-093/094/095/096 的描述是否能被归档证据支持？
10. 是否存在"平行账本 / 第二权威"：同一事实存在两份互相冲突的登记？列具体文件与冲突字段。
11. 归档配额裁剪（494 个 `references/*.md` 未入档）是否影响任何一条结论的判定？逐条标注"受影响/不受影响"。

## 任务 B：矛盾与缺口台账
输出一张表：`id | 面 | 冲突或缺口 | 级别(阻断/高/中/低) | 支持证据 URL | 影响 | 建议动作 | 是否需本机验证`。
必须覆盖：登记 vs live 漂移（G1–G4）、记录陈旧（`skills-inventory.json` 6/14、`plugin-inventory.json` revision、`skill-provenance.yaml`）、配额裁剪造成的证据缺失、以及任务 A 中所有 `FAIL` / `UNVERIFIABLE`。

## 任务 C：收敛合并方案（核心交付）
目标：把当前分散/重叠/陈旧状态收敛为**一份可执行基线**，并给出合并到 main 的门禁与回滚。

1. **canonical 收敛表**：对每个客户端（hermes / codex / dsh / cc-switch / open-design / openhuman / github）与本项目，逐项标注
   `KEEP_AS_IS` / `MERGE` / `REBUILD_FROM_SOURCE` / `DEPRECATE` / `ARCHIVE_ONLY` / `NEEDS_USER_DECISION`
   并写理由（引用证据 URL）。其中两处必须明确**定性并给出判据**：
   - Codex 全局 `AGENTS.md`：应"重新渲染 overlay 并回读"，还是"下调登记成熟度、承认用户自有文件"？谁拥有该文件？
   - Hermes `windows-development-environment`：以**仓库源为准重部署**，还是以 **live 为源回收进仓库**？给出选择判据。
   - 登记类（`skills-inventory.json` / `plugin-inventory.json` / `skill-provenance.yaml`）：如何改为**由部署通道同批生成**，从机制上消除再次漂移（不要只给手工改值）。
2. **顺序与门禁**：合并到 main 前必须通过哪些检查（结构门禁、证据重算、零密钥扫描、边界扫描）？先修登记还是先修 native？每步的**失败判据**是什么？
3. **回滚**：每类动作的回滚手段（分支 / 标签 / 备份 / 重渲染命令），以及"回滚成功的判据"。
4. **清理候选裁决**：对 13 条清理候选逐条给 `APPROVE_LOW_RISK` / `APPROVE_WITH_BACKUP` / `REJECT` + 理由。注意 Codex 1.5 GiB 历史库与 Hermes `state.db` 4.2 GiB 属**用户状态**，只能 OBSERVE/归档，不得删除。
5. **风险与反例**：若按此方案合并，最可能出错的 3 件事 + 各自的早期信号（可观测指标）。

## 输出格式
1. 结论表（任务 A，逐条 PASS/FAIL/UNVERIFIABLE + 证据 URL）
2. 台账（任务 B）
3. 收敛合并方案（任务 C，含每项的回滚）
4. **不可验证清单**（公开不可核的事实 + 需要什么才能核）
5. 机器可读 JSON（便于本机消费）：

```json
{
  "verdicts": [{"claim_id": "", "level": "PASS|FAIL|UNVERIFIABLE", "evidence_url": "", "note": ""}],
  "findings": [{"id": "", "area": "", "severity": "blocker|high|medium|low", "evidence_urls": [], "action": "", "needs_local": true}],
  "convergence": [{"target": "", "action": "KEEP_AS_IS|MERGE|REBUILD_FROM_SOURCE|DEPRECATE|ARCHIVE_ONLY|NEEDS_USER_DECISION", "reason": "", "evidence_urls": [], "rollback": ""}],
  "unverifiable": [""]
}
```

## 硬约束
- **只读审计**：不要声称你已执行任何修改（你无法执行）。
- 每条结论必须可回溯到 URL；无 URL 的结论标为推测。
- 不要输出任何疑似凭据值；疑似只报位置与模式名。
- 结尾必须明确区分：**哪些结论可以直接据此合并**，**哪些必须等本机（Windows）实机验证**。

---

## 第二轮提示词（把收敛方案变成可执行补丁清单）

> 用法：把 GPT 第一轮的 JSON 结论贴回来，用下面这段做第二轮，产出本机可直接执行的补丁清单。

# 任务：把收敛方案转成可执行补丁清单（不改动任何源文件）

基于你上一轮的 `convergence` 与 `findings`，产出**可执行**清单，每条包含：

1. `id` 与目标（仓库相对路径或客户端原生路径；原生路径一律用 `%USERPROFILE%` / `%LOCALAPPDATA%` / `%APPDATA%` / `%PROJECTS_ROOT%` 令牌化）
2. 动作类型：`EDIT_REPO_FILE` / `GENERATE_SCRIPT` / `RE_RENDER_NATIVE` / `REBUILD_REGISTRY` / `ARCHIVE_ONLY` / `DELETE_CANDIDATE` / `NEEDS_USER_AUTHORIZATION`
3. 精确改动：给出**最小 diff 语义**（改哪个字段/哪一段），或给出**生成脚本的用途与输入输出**（不要写假定存在的工具）
4. 前置检查与失败判据
5. 验证命令（必须可复现；哈希一律按**仓库字节 LF** 计算）
6. 回滚步骤与回滚判据
7. 授权级别：`already_authorized` / `needs_explicit_user_authorization`（写明要授权什么）

约束：
- 不得提议修改用户的 provider/model/auth/桌面状态；不得提议访问 `E:\`、`F:\`。
- 不得提议删除会话、数据库、记忆；这些只允许 OBSERVE 或归档。
- 涉及 Codex / Hermes 全局原生文件的写入，一律标 `needs_explicit_user_authorization`。
- 输出顺序必须是**可串行执行**的拓扑序，并标注哪些步骤可并行。
- 最后给一张"**本机实机验证清单**"：哪些步骤必须在 Windows 本机执行、以什么证据判为通过。
