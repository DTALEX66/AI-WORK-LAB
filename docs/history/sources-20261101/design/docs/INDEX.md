# 仓库目录分类与归档索引（REPO INDEX）

生成方式：目录事实来自 `scripts/classify_repo.py`（由 `git ls-files` / `git ls-tree` 派生，
不是手抄），产物为 `reports/current/REPO-CLASSIFICATION.json`。
本文件解释**分类规则与放置约定**；数字以 JSON 为准。

```
python scripts/classify_repo.py          # 再生
python scripts/classify_repo.py --check  # 只读校验：派生事实与已提交件是否漂移
```

观测 commit 与体量（由上表再生时的真实测量）：
**跟踪文件 3724 个 · 工作区 69.68 MiB · pack 241.69 MiB**（`observedCommit bdd890fb`，
再生于 2026-10-19T09:59Z）。工作区体积此前被低估：`blob_sizes()` 用 `git ls-tree HEAD` 按行读，
非 ASCII 路径被转义后查不到键（11 个文件记成 0 字节），未提交的新文件更整体记成 0——
同一棵树先后测出 52.28 与 60.22 MiB 而文件数不变。现改从 index + 对象库取，且 blob 读不到即 fail-closed。
**2026-10-19 修掉的第三个读数缺陷**：分类原先按 bundle 汇总，而 `bundle_key()` 把一个顶层目录收成
一个 bundle，于是 `docs/` 里第一个文件的类别给整个目录贴了标签——`planning` 因此从投影里整体消失
（24 个任务包 + 6 个当前面文件 + 账本 = 0）。现改为**逐文件计数**，各类别之和 = 跟踪文件数（3801 = 3801），
这一等式本身写进了再生后的核对里。

---

## 1. 权威脊线（读取顺序，唯一）

| 层 | 路径 | 类别 |
|---|---|---|
| 顶层权威 | `AUTHORITY.md`（`DL-AUTHORITY-2026-09-18-R2`） | authority |
| 权威索引 | `.project/governance/authority-index.json` | authority |
| 根执行规则 | `AGENTS.md` | authority |
| 当前任务包 | `docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`（`DL-TP-20261019-DIRECTION-R1`） | planning |
| 唯一可变账本 | `design-lab/config/task-ledger-r3.json` | planning |
| 任务文档定态登记 | `design-lab/config/task-document-states.json` | authority |
| 归档波次清单 | `docs/history/archive-2026-10-19/MANIFEST.json` | history |
| 外部卷导入台账 | `docs/history/record-imports-2026-10-08/RECORD-IMPORT-MANIFEST.md` | history |
| 当前投影 | `reports/current/`（生成器产物，非真值来源） | generated |
| 本机外置根 | `.project/paths.json` · `docs/LOCAL_ENVIRONMENT.md` | authority |

`scripts/verify_path_refs.py` 会 fail-closed 检查 `AUTHORITY.md` / `AGENTS.md` 里每一条路径
引用在盘上真实存在。**因此任何目录搬迁都必须同步改这两份权威文件，否则门红。**

定态登记由 `design-lab/scripts/verify_task_document_states.py` 把关（已入聚合链）：
它从属于 `authority-index`，与其不一致即红，且要求规划/历史面上**每个 tracked 任务文档都有声明**、
派工入口恰好一个、导入件不得自称 CURRENT、被 SHA-256 钉死的每一件必须登记为 frozen。

## 2. 分类规则（`classify_repo.py` 里的有序前缀表）

| 类别 | 含义 | 现量（`bdd890fb` 实测，逐文件计数） |
|---|---|---|
| `authority` | 顶层权威、治理索引、决策与架构政策 | 70 files / 0.31 MiB / 4 bundles |
| `planning` | 任务包、当前定义面与任务账本 | 21 files / 0.89 MiB |
| `evidence` | 审计包、黄金用例、域 fixture、评估语料、设计项目产物 | 1159 files / 22.17 MiB / 5 bundles |
| `history` | 冻结历史、归档区、Record 导入件 | 732 files / 27.26 MiB / 3 bundles |
| `generated` | 当前状态投影、提交的构建产物 | 67 files / 1.29 MiB / 4 bundles |
| `source` | 产品源码、能力包、集成层、门脚本、测试、CI | 1637 files / 13.22 MiB / 8 bundles |
| `documentation` | 其余文档 | 13 files / 4.31 MiB / 2 bundles |
| `repo-meta` | 根级运维/政策文档 | 24 files / 0.25 MiB |
| `other` | 未落入任何规则的件 | 1 file |

九类相加 = 3724 = 跟踪文件总数；这个数字对不上就说明规则漏了或重复了，再生时必须核对。

## 3. 规划件的当前/历史判定

2026-10-19 归档波次后，`docs/taskpacks/` 只剩 **14 个跟踪文件**：4 个包体（当前 DIRECTION 包 +
被钉的三份血统包 UI-FIRST / FINAL-AUTHORITY / DEEPSEEK）与两个来源目录
（`20261009-ui-first/`、`20261019-direction/`）。**只有 1 个是当前派工入口**（§1 所列），
其余 19 个旧包体已整体搬入 `docs/history/archive-2026-10-19/taskpacks/`。
逐文件的定态（CURRENT / SUPERSEDED / HISTORICAL / NON_AUTHORITATIVE / REFERENCE /
REQUESTED / FROZEN，外加依据与取代对象）不再靠猜：登记在
`design-lab/config/task-document-states.json`，由 `design-lab/scripts/verify_task_document_states.py`
检查"每个跟踪任务文档都有声明"。旧任务 ID 必须先经 `authority-index` / crosswalk 映射才可执行。

已受理但**尚未采纳为 Authority** 的 REQUESTED 面随本轮归档
（当前入口是 §1 的 2026-10-19 包）：
`docs/history/archive-2026-10-19/taskpacks/DESIGN-LAB-GLOBAL-DESIGN-CAPABILITY-INTELLIGENCE-TASKPACK-2026-10-06.md` 与
2026-10-06 权威修复对（`docs/history/archive-2026-10-19/taskpacks/03_DESIGN-LAB_权威修复_双端描述同步_可审计执行提示词_20261006.txt`
+ 其输入 `docs/history/archive-2026-10-19/taskpacks/03_DESIGN-LAB_完整项目描述与未来蓝图_20261006.docx`）。
待 owner 裁决的项在登记表里逐条写明 `ownerActionPending`；归档改变位置，不改变"未裁决"这一事实。

外部 Record 卷的 DESIGN-LAB 任务文档与包已于 2026-10-08 归档进
`docs/history/record-imports-2026-10-08/`（259 个文件 / 7,735,797 字节；R4.1、REAUDIT-09-14、
R2 发布包原件、CODEX-09-22、2026-09-29 MASTER ATLAS 汇总包、UI-FRONTEND-09-30、
研究生态汇总包的 DESIGN-LAB 子包、B00/B07/B08/B09/B10 批次）。
逐条源路径/字节/sha256/crc32/目标/定态见同目录 `RECORD-IMPORT-MANIFEST.md`（同名 `.json` 为机器面）；
复跑 `scripts/record_import_apply.py` 得同一张表（对 HEAD 幂等），
复验 `scripts/record_import_verify.py --head` 做 源字节↔工作区↔已提交 blob 三方比对。
2026-09-08 R5 包与 2026-09-28 能力闭环包的成员经 CRC32 证明早已逐字节在仓内，因此**只登记映射不重复写字节**；
B01–B06 图片包 44,183,932 字节受本仓体积门约束留在源卷，逐成员哈希登记为 EXTERNAL-ONLY。

`docs/current/`（6 个）是产品与路线图定义；`reports/current/` 是**机器投影**，
两者不可混用：投影可被再生，定义需人裁决。本轮把 4 份按日期堆积在 `docs/current/` 的旧记录
（ARCHIVE-KEY-INFORMATION / HANDOFF-2026-10-13-COMPLETE / TASKPACK-ADOPTION-VERIFICATION /
UI-DESKTOP-RECONCILIATION）搬入 `docs/history/archive-2026-10-19/current-records/`；
当前入口只剩就地更新的 `docs/current/NEXT-AGENT-PROMPT.md`，不再按日期铸新文件。

`REQUESTED` 面对应的机器可读骨架在
`design-lab/schemas/candidate-taxonomy.schema.json` + `research/candidates/CANDIDATE-TAXONOMY.json`，
并由 `design-lab/scripts/verify_candidate_taxonomy.py` 把「未测轴必须为 null、评分必须有
evidenceRef、parentRepoStars 不得冒充自身、无许可不得越过 QUARANTINE、代理不得自签 reviewedBy」
变成 CI 门——导入件的二进制 sidecar 同样把 `reviewedBy` 留空待 owner 签（见 §6）。

第三方候选的登记位置是 `research/candidates/`（CONDITIONAL_POC 索引区，源码只在
`.project-local/cache/vendor/<id>`，不进 Git）；已人工复核的源在
`design-lab/research/global-absorption/SOURCE_REGISTRY.json`（v3，`reviewedBy` 为人工责任字段）。

## 4. 证据区（禁止「整理式删除」）

| 位置 | 文件数 | 说明 |
|---|---|---|
| `docs/audits/` | 840 | 其中 784 个属于 `DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/` 一个包 |
| `docs/history/record-imports-2026-10-08/` | 259 | Record 卷导入的冻结任务包与批次材料（11,196,550 B 含同目录其余历史件） |
| `docs/history/archive-2026-10-19/UI-CONVERGENCE-20260930/` | 93 | UI 收口：40 张截图 + 40 个 `.license` sidecar + manifest + 审计前后报告（2026-10-19 自 `docs/UI-CONVERGENCE-20260930/` 整体搬入，字节未变） |
| `fixtures/` | 226 | 域 fixture（`game-visual` 被 clean-tree 门钉住） |
| `docs/projects/` | 19 | 真实设计项目产物（6.66 MiB，本仓最大单目录产物面） |
| `docs/golden-cases/` | 11 | 黄金用例 |
| `reports/history/` | 90 | 冻结历史账本；2026-10-19 先收进 5 份按日期的 reports 交接摘要，随后按 owner 删除指令移出 10 份 loose 交接件（汇总面与恢复句柄见归档区） |

## 5. 体积：能减的和不能减的（实测归因）

```
pack 242.0 MiB  −  工作区 60.38 MiB  ≈  181.6 MiB 全部是历史对象
```

按路径前缀对**全体历史 blob** 归因（下表为 2026-10-06 那次全历史归因，本轮未重算；
本轮可测增量为 pack +1.76 MiB、工作区 +7.94 MiB，全部来自 §3 的 Record 导入；
2026-10-09 的外部审计轮再加 5 个文件、工作区 +0.08 MiB，见 `docs/audits/DESIGNLAB-EXTERNAL-DESIGN-REVIEW-2026-10-09.md`）：

| 前缀 | 历史字节 |
|---|---|
| `minigame-runtime/`（**当前树里已不存在**） | **182.1 MiB / 326 blobs** |
| `docs/` | 32.7 MiB |
| `research/` | 31.9 MiB |
| `design-lab/` | 27.9 MiB |
| `reports/` | 17.3 MiB |
| `fixtures/` · `apps/` | 7.7 · 5.8 MiB |

那 182 MiB 是 8–12 MiB 的 CCTV 场景 GIF 等，**只经 `archive-evidence/2026-09-25/*` 与
`superseded-tip/*` 这些 tag 可达**——即它们是**被刻意保留的证据归档**，不是垃圾。

由此得出三条硬结论：

1. **目录规范化不会缩小 pack。** Git 的 blob 按内容寻址，`git mv` 只新增极小的 tree 对象；
   历史体积与目录形状无关。
2. **不动历史就没有 179 MiB 的回收空间。** 要回收必须删 tag + `git filter-repo` 重写 + 强推，
   这会破坏 `archive-evidence` 证据并影响所有克隆。本轮**未做**，且按现行规则（禁止删证据、
   禁止 force push）也不应由代理执行。
3. **能立刻做的是止血**：`verify_asset_governance.py` 已在 220 MiB 告警 / 256 MiB 硬预算
   （当前 242.0 MiB → WARN，余量 14.0 MiB）。重复提交大二进制的面是截图与 fixture；sidecar 与 manifest
   已绑定 exact commit，重拍一轮就会新增 40 个 blob。**新增大文件前先看它属于哪一类，
   并能被清单绑定证据链，否则进 `.project-local/`（gitignored）而不是进仓。**
   任务 #29 就是这么处置的：Record 卷里 44,183,932 字节的 B01–B06 图片包**没有**进仓
   （容器超单文件 5 MiB 上限，且解出面会顶穿 256 MiB 硬预算），改为逐成员登记
   名称+大小+CRC32+sha256 的外链行；同理 ≥256 KiB 的二进制必须先有
   `design-lab/config/large-assets.json` 里带理由的 bundle 声明，`docs/audits/` 那一格
   预算只有 2.0 MiB，塞不进就按上面这条走 gitignored 证据根，而不是抬高阈值。

`git gc` / repack 只整理本地对象（当前 loose 395 个 / 5.93 MiB），对远端体积无影响。

## 6. 放置约定（今后新增东西去哪）

| 你要放的是 | 放这里 | 不要放 |
|---|---|---|
| 权威裁决、政策、ADR | `AUTHORITY.md` 索引所指 · `docs/decisions/` · `docs/architecture/` | 根级散落新 .md |
| 派工入口 | `docs/taskpacks/`（且**只能有一个 current**）+ 账本 `design-lab/config/task-ledger-r3.json` | 第二套 ledger / 会话内台账 |
| 审计/验收证据 | `docs/audits/<包名-日期>/`，二进制必须配 `.license` sidecar 与 manifest | `reports/`、`docs/current/` |
| 状态投影 | `reports/current/`，且必须由生成器写出、可 `--check` | 手写「当前状态」 |
| 冻结历史 | `docs/history/` 或 `reports/history/`，逐字节冻结、不改写 | 原地更新历史文件 |
| 过期但仍可读的整目录（旧任务包 / 按日期的 handoff / 一次性计划与研究 / 旧当前面记录） | `docs/history/archive-<日期>/<原相对路径>`，逐文件 `原路径→新路径→blob→字节` 登记在 `docs/history/archive-<日期>/MANIFEST.json`，并同步改：登记表前缀、`.gitattributes` 的 `-text` 规则、指引面引用、被钉文件的哈希（走 `AUTHORITY-PIN-CHANGE.json` 留痕）；`git mv` 只搬路径，字节必须复验一致 | 明面保留第二份"看起来像当前入口"的副本；只搬文件不登记；只搬一半留下混合形状；用旧路径继续派工 |
| 外部卷导入的冻结原件 | `docs/history/record-imports-<日期>/<包名>/`；逐成员清单（源路径/字节/sha256/crc32/目标/定态）随件入库；二进制配 `design-lab/asset-sidecar/v1` 且 `reviewedBy` 留空待 owner 签；`.gitattributes` 对该子树 `-text`，禁止行尾改写 | 抬高体积阈值 / 为过门而重命名或重排原件 |
| 装不下的原件（超单文件 5 MiB 或会顶穿 pack 256 MiB 硬预算） | 留在源卷，逐成员登记 名称+大小+CRC32+sha256 的外链行；运行期副本进 `.project-local/` | 为「全部归档」写进仓里把门做红 |
| 运行期/缓存/大中间件 | `.project-local/`（PROJECT_LOCAL_ROOT） | 仓内任何目录 |
| 构建产物 | `apps/workbench/build/`（受 Build Output Truth 门钉） | 仓外未提交副本 |
| 设计契约的存量数字 | `DESIGN.md` §4 的文本必须逐字等于 `scripts/design_debt_baseline.py` 量出来的那句（`design-lab/tests/test_design_debt_baseline.py` 在 CI 看守）；逐站点色值登记在 `design-lab/config/ui-off-palette-colours.json`，其 `adjudication` 只允许人填，脚本重写必须保留 | 手点的「大概多少处」；代理替 owner 填裁决 |
| 外部审查工具的入仓面 | 配置 `design.qa.yaml` + 驱动 `scripts/run_design_review_plugin.py`（插件在 `~/.qoder-cn/plugins`，仓内不复制它） | 把第三方插件源码 vendored 进仓 |
| 外部审查工具的产物 | `.project-local/runs/design-review/`（原始 JSON）与 `.project-local/task-artifacts/design-review/plugin-run.json`（运行台账：commit/版本/端口）；结论写进 `docs/audits/` | 把每次跑出的 JSON 提交进仓（体积与噪声） |

## 7. 结构债与本轮处置

- **2026-10-19：本节原先写的"批量归档被三件事卡住"已由 owner 明确指令解除，本轮执行了物理归档。**
  Owner 要求旧件离开明面、并防止下一轮再索引旧路径（原话：「任何旧的过时的冗余的陈旧的，不要再明面上，
  全部归档到该去汇总的地方，包括仓库目录文件夹整体搬走…按照规范化处理」）。三条阻塞各自的处置：
  1. **SHA-256 钉死**：搬迁必然改动 `AUTHORITY.md`、`.project/governance/authority-index.json`、
     `docs/current/HISTORY-FREEZE-RULES.md` 里的路径字符串，因此本轮按规程**重钉并留痕**，
     逐次改动（from/to 摘要 + 理由 + 跑了哪些门）登记在
     `docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json`，不是悄悄改哈希；
  2. **被钉索引的活指针**：`authority-index` 与账本仍引用四份包体
     （DIRECTION-2026-10-19、UI-FIRST-2026-10-09、FINAL-AUTHORITY-2026-09-18、DEEPSEEK-2026-09-14），
     这四件**留在 `docs/taskpacks/` 原位**——「link update 无法完成」这一条对它们依然成立，
     所以没有搬；其余 19 个旧包体全部归档；
  3. **"只搬一部分会拆散家族"**：定态已由 `task-document-states.json` 逐文件表达，
     不再依赖目录形状，混合形状不再损害可读性。
- **分叉头已消失**（2026-10-19 实测）：`feat/ui-commercial-workbench-20260930` 经 PR #213 合入
  `main`（merge commit `fa3a7baa`，已核验为 main 的祖先），`qoder/designlab-m1-closeout-20261005`
  既不在本地分支也不在远端分支列表。原先"合并前全仓重命名会让两边冲突不可解"的前提不再成立。
- `WORK-LAB-DESIGN-MODULE-FINAL-HANDOFF-2026-08-07.md` 原先以"某条历史记录引用它在根级"为由留在根目录；
  本轮复核该行内容（`docs/history/project-memory-history/V4_MIGRATION_FINAL_STATE.md:41` 只按文件名评述
  其证据分级，不含目录断言），该理由不成立，已移入 `docs/history/archive-2026-10-19/`。
  冻结历史文件本身不改写，新旧路径对照只登记在 `MANIFEST.json`。
- `docs/superpowers/`、`docs/research/`、`docs/plans/` 与 `design-lab/research/` 的主题重叠已随本轮
  归档收口：前三者整体进 `docs/history/archive-2026-10-19/`，研究面统一留在
  `design-lab/research/` 与 `research/candidates/`。
- **本轮交付记录**：`docs/audits/DESIGN-LAB-ARCHIVE-AND-REMOVAL-2026-10-19.md`——基线读法、实测数字、命令与退出码、§6 六处与 §6.5 一处共七处被暴露并修掉的缺陷、回滚方法；§0 是结论与状态声明。方向批次那份 dated 报告的 §7 数字已被它取代（按规则不改写旧报告）。
- **2026-10-19 删除波（同一 owner 指令链的第二次重钉）**：83 份过期交接与按日期提示词副本在汇总后删除，跟踪文件从 3806 降到 3724（在删除提交 `e9ff0717` 上实测，83 个 D 行；此后本波次又落了登记件与脚本，写这一行时 `git ls-files | wc -l` 读到 3725，这不是漂移，别去改那两个历史读数）；`docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md` 承载逐份标题/自述/结论/独有事实，`REMOVALS.json` 承载逐份 blob/sha256/crc32/字节/restoreAt，`git show <restoreAt>:<path>` 实测可还原。五份记录自身的 canonical 路径、blob SHA-1、字节与 SHA-256 已登记在 `docs/RECORD-ARCHIVE-INDEX.md` 的 2026-10-19 一节。
  故意没删的三类写进 `README.md` 的目的地表：owner 随包提供的 deepseek-r3 审计输入 17 件、`PROMPT-LINEAGE.json`、按日期 bundle 目录内的成员。
  一处真门被这次删除救回来：`verify_top_level_authority.py` 的 `handoff-demoted` 仍按归档前的旧路径找文件，找不到就 PASS 成 "absent; nothing to demote"——文件一搬走这条降级检查就被静默关掉。现改走 `scripts/archive_records.py:read_record()`（工作区→归档移动→removal restoreAt 三层），并把 UCR 条目的 restoreAt 改成假 SHA 验证过它会 FAIL exit=1。
- **2026-10-08 记录（任务 DL-REC-29）**：该轮把外部 Record 卷的 DESIGN-LAB 任务包落到
  `docs/history/record-imports-2026-10-08/`，并指出该前缀在 `verify_asset_governance.py` 的
  `SKIPPED_PREFIXES` 里，是仓库自己定的"冻结历史面豁免"，不是为过门找的出口——导入件的 sidecar 照写，
  并且把"门若在此处审会报什么"原样登记在 `RECORD-IMPORT-MANIFEST.md`
  （`reviewedBy`/`approvedBy` 留空等 owner 签，代理不自签）。同一豁免同样覆盖本轮的
  `docs/history/archive-2026-10-19/**`（`docs/history/**` 家族），所以归档不新增体积门风险；
  新增的字节只有 `MANIFEST.json` 与本 `README.md`。
- **本轮修掉的两个 git porcelain 解析缺陷**（都不是断言问题，是读法问题）：
  `verify_asset_governance.py` 按行读 `git ls-files`，被转义的中文路径当成不存在（6 个真文件报
  "cannot stat"，且这些路径完全绕过体积核算）；`classify_repo.py` 的 `blob_sizes()` 从
  `git ls-tree HEAD` 取值，同一棵树先后测出 52.28 / 60.22 MiB——11 个非 ASCII 文件记成 0 字节，
  未提交的新文件整体记成 0。两处都改成 `-z`（唯一不加引号的 porcelain），后者并改为从 index +
  对象库取数且 blob 读不到即 fail-closed，与 `verify_asset_governance.tracked_blob_sizes()` 同法。
