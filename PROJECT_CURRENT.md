# AIWORKLAB / AI-WORK-LAB — 当前状态（唯一顶层入口）

**WORK-LAB + DESIGN-LAB 已合并为 AIWORKLAB / AI-WORK-LAB。旧名称只用于历史追溯与迁移兼容，
不再是两个并行维护的产品，也不再各自持有生产权威。**

本文件是薄入口：只给结论、关键未完成项与可到达的链接。数字一律指向下方"唯一维护位置"里的
登记表，不在这里复制维护；本文件的每个数字都由 `scripts/check_project_current.py` 与寄存器
现值比对，对不上即为红。

- 最近核验：2026-11-01（本地，不联网）
- 依托提交：`2312963`（分支 `integration/local-fusion-20261029`，工作树含本轮未提交的顶层入口新增）
- 远程：`DTALEX66/AI-WORK-LAB`，分支 `integration/local-fusion-20261029` 已推至 `a490f7c`
- 入口三件套：本文件 + `README.md` + `AGENTS.md`（同在本仓根目录，读序见 `AGENTS.md` §1）

<!-- entry-figures:start -->
acceptance_blocked_by_boundary = 2
acceptance_confirmed = 41
acceptance_deferred_p3 = 3
acceptance_partial = 2
archive_objects = 1212
archive_only_objects = 1131
archive_registered_not_migrated = 80
archive_source_hints = 1212
archive_unclassified_residue = 1
blocker_items = 7
byte_copy_rows = 1132
capability_families = 30
capability_implemented_verified = 18
capability_partial = 12
distinct_paths_design = 4049
distinct_paths_union = 6676
distinct_paths_work = 2638
route_endpoints = 164
source_rows_design = 4470
source_rows_total = 7108
source_rows_work = 2638
task_acceptance_clauses = 48
unsettled_files = 237
<!-- entry-figures:end -->

上面这段不是手抄的：它由 `.venv/Scripts/python.exe -B -X utf8 scripts/check_project_current.py --print-block`
从寄存器现算生成，`--check` 逐条比对；对不上就是红，不做"大致没错"。

## 一、现在成立什么

- 单一融合后端：统一信封、统一存储、只读验收门；两套旧生产权威已不是并行入口。
- 历史资产去向已逐条登记：来源仓逐仓去重 `2638`（WORK）+ `4049`（DESIGN）条不同路径，
  跨仓并集 `6676` 条（有 11 条路径两边都出现，所以并集小于两数之和），共 `7108` 行去向，
  与登记枚举差集为 0；本项目按字节持有其中 `1132` 行对应的副本。
- 统一归档（`D:\All projects\Project Archiving`，只读）与本仓已逐摘要对账：`1212` 个唯一对象中
  `1131` 个**只在归档里有一份副本**（约 `1.06 GB`），`80` 个已登记但未迁入，`1` 个停在未归类；
  本仓 `migration/copies.json` 的 `962` 个来源摘要与归档对象摘要**交集为 0**——两边的字节不是同一批。
  逐条见 `migration/archive-object-reconciliation-20261101.csv`。
- 机器可核证的验收与追溯：`migration/task-acceptance.csv`（48 条验收子句）、
  `migration/capability-family-register.csv`（30 个能力族）、
  `migration/audit-item-closure.csv`（A/F 审计项闭环）、
  `docs/CODEX-AUDIT-ENTRY.md`（含逐轮实测与收回记录）、`docs/AUDIT-STATE.json`。

## 二、尚未成立（不要当成已完成）

| 类别 | 现状 | 权威位置 |
|---|---|---|
| 能力验证状态 | `IMPLEMENTED_VERIFIED` 与 `PARTIAL` 并存，PARTIAL 每条都写明缺什么 | `migration/capability-family-register.csv` |
| 验收子句 | `CONFIRMED / PARTIAL / BLOCKED_BY_BOUNDARY / DEFERRED_P3` 分列，不合并计成"通过" | `migration/task-acceptance.csv` |
| 待裁决来源 | `237` 个文件停在 `REGISTERED_GAP` / `OWNER_DECISION_PENDING` | `migration/source-unsettled-groups-20261101.md` |
| 阻断项 | 验收门 `REFUSED`，blocking `L10#0`（owner 决定队列） | `config/blocker-register.json`、`docs/AUDIT-STATE.json` |
| 界面（STITCH 前端） | 未做：本批只做本地后端 | `migration/ui-entry-disposition.csv` |
| 真实宿主写入 / 模型推理 / 真实私有数据迁移 / 真人专业验收 | `NOT_RUN`，按边界如实记录 | `docs/CODEX-AUDIT-ENTRY.md` §5、`migration/deferral-register.json` |
| 系统级出站隔离 | 未证明（无防火墙/沙箱配置；云端会话模型上下文可离开本机这一限制仍成立） | `INTEGRATION_POLICY.md` §2 |
| workbench bundle | 无法重建（缺 `picomatch`，需网络安装，未授权），两个读 bundle 的 JS 闸门仍校验旧字节 | `docs/CODEX-AUDIT-ENTRY.md` §15.22 |
| 顶层入口自身 | 本文件与 `README.md`、`AGENTS.md` 是本轮新建；`HEAD 2312963` 那 `2 failed` 已全部定位并各自修好（`test_v16…does_not_relamp_them`：寄存器里一个行号指针随 `migrate_sources.py` 漂移，重发布；`test_v23…machine_independent_part`：台账查键只按本机绝对根剥前缀，克隆里剥不出来，改为按路径结尾取且要求唯一）。**收据仍记 `2 failed`**：重取需要干净跟踪树，也就是需要一次提交授权 | `.project-local/audit/20261031-fullclosure/CLOSURE-STATE.json`、`docs/CODEX-AUDIT-ENTRY.md` §15.23 |
| 归档原件的唯一副本 | `1131` 个对象（约 `1.06 GB`）目前只在统一归档里有；归档自己的 `完整性校验报告.json` 仍写 `source_file_set_unchanged: true`，而它点名的 `2031` 条来源路径现在**一个都不存在**（`D:\All projects\Record` 已消失，`xiangmuguidang` 是空目录）——那句话对今天的磁盘已不成立，归档不可再被当作可清理的副本 | `migration/archive-object-reconciliation-20261101.csv`、`_归档管理\完整性校验报告.json` |
| 删掉两个来源仓之后本仓还能不能独立跑 | 见 §五 最后一条：正在用"把来源路径改指到不存在的位置"的副本实测，不靠推断 | `.project-local/runs/independence-simulation-20261101.json` |

## 三、证据分级（不拼接旧成绩）

| 级别 | 本次状态 |
|---|---|
| 文档 / 登记 | 已核：登记互相勾稽，7 台生成器 `--check` 全 rc=0 |
| 代码 | 已核：静态与反例断言在套件内 |
| 构建 | 部分：Python 侧可导入安装（离线隔离安装 PASS，见 `config/isolated-install-verdict.json`）；`apps/workbench` bundle 不可重建 |
| 运行 | 已核：164 端点逐路由实测（`migration/route-surface.csv`），loopback HTTP |
| 外部 Agent / 宿主真实往返 | 未做：`NOT_RUN`，不拿合成回执冒充 |
| 迁移恢复 | 已核（合成夹具与副本）：崩溃注入下旧字节不被半写；真实私有数据迁移仍 `NOT_RUN` |
| 安装态 | 已核：wheel 安装后读回通过，含随包发布的领域包校验器可载入 |
| 用户验收 | 未做：真人专业签字是 Human Gate，不由 Agent 代签 |

## 四、唯一维护位置（防止出现第二套当前权威）

| 内容 | 唯一位置 | 其他文件只做 |
|---|---|---|
| 项目身份与当前结论 | 本文件 | 引用，不改写口径 |
| 能力族与验证状态 | `migration/capability-family-register.csv` | 链接 |
| 验收子句逐条状态 | `migration/task-acceptance.csv` | 链接 |
| 来源文件去向（含未迁原因） | `migration/source-coverage-work.csv`、`migration/source-coverage-design.csv`、`migration/copies.json`、`migration/archive-object-reconciliation-20261101.csv` | 链接 |
| 阻断与延期 | `config/blocker-register.json`、`migration/deferral-register.json` | 链接 |
| 端点面实测 | `migration/route-surface.csv` | 链接 |
| 审计项闭环与逐轮实测 | `docs/CODEX-AUDIT-ENTRY.md` | 追加小节，不改写历史 |
| 执行边界与授权沿革 | `INTEGRATION_POLICY.md` | 定点放行，不整份重写 |
| 统一归档原件 | `D:\All projects\Project Archiving`（**只读**） | 只引摘要，不整包复制、不反向清理 |

## 五、下一步

1. ~~定位并修掉 `2312963` 上那 `2` 个失败~~ 已定位、已各自修好并在本机复验；剩「重取全量收据 +
   改绑登记表」这一步物理上需要一次提交（生产器拒绝在脏跟踪树上测量），等 owner 授权。
2. owner 对 `237` 条待裁决来源做批量判定（含 32 条阻断 `L10#0` 的）。
3. ~~统一归档 `1212` 个对象与融合仓的逐摘要对账~~ 已建成 `1212` 行逐条登记；
   剩一个 owner 决定：那 `1131` 个只在归档里的对象要不要按摘要迁入本仓。
4. 界面与外部宿主往返仍需新的明确授权；在那之前保持 `NOT_RUN`。
5. **删除两个来源仓之前必须先回答的三件事**（本仓不替 owner 决定，也不会在未授权时动手）：
   - 来源仓的 `.git` 历史（含 `426` 个不可达提交）与 LFS 载荷，现在的镜射位置是
     `.project-local\source-mirror-20261101`、`.project-local\source-tar-20261101`、
     `.project-local\source-archive-20261101`——**这三处都不在 Git 里，也不随克隆走**；
     删除来源仓后它们是唯一副本，需要 owner 指定一个长期位置（归档目录对本轮是只读的）。
   - `237` 条待裁决来源与 `1131` 个归档唯一副本，删了就没有第二次机会；先判定再删。
   - 本仓的独立性以 §二 最后一行的实测结论为准；凡是依赖来源仓的测试都会显式点名前置，
     不会静默跳过或报错伪装成通过。
