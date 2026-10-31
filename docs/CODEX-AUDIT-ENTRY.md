# AI-WORK-LAB 本地后端融合 — Codex 独立审计入口

版本：2026-10-30 R2（QODER 审计返工轮）
状态：**上一候选经 Codex 独立审计判 FAIL；本轮为修复后的新候选，QODER 修复自测完成，待 Codex 独立复审。**

> 本文件取代 R1 版本的入口作用。**R1 的「P0/P1 完成，无必做阻塞」结论已被独立审计否定，停止引用。**
> 旧候选的证据、审计报告与原任务包一律未改动，仍可用于对照。

## 1. 位置与状态

| 项 | 值 |
|---|---|
| 目标仓 | `D:\All projects\AI-WORK-LAB` |
| 工作分支 | `integration/local-fusion-20261029`。返工测量时 HEAD 为 unborn（候选全是未跟踪文件，`git diff` 为空不代表没有改动）；2026-10-31 owner 放行首次上传后，本分支已有提交并被推到 owner 自有的空远程仓。**当前提交一律用 `git rev-parse HEAD` 现读，本文不抄写任何 SHA 数字。** |
| 候选绑定 | 路径→SHA-256 清单（见证据目录 `snapshot-before.json` / `snapshot-after.json` / `target-*.json`），口径见 §6；上传前后的差值另见 `.project-local\push-20261031\candidate-*.json` |
| 来源仓（只读） | `D:\All projects\WORK-LAB` @ a8cc2fb + 既存未提交增量；`D:\All projects\DESIGN-LAB` @ c4359bb（锚点 + 23 提交）。**本轮结束时两仓摘要与开始完全一致**（`snapshot-after.json`） |
| 执行策略 | `INTEGRATION_POLICY.md`。§6（2026-10-31）定点放行「首次 commit + 首推到 owner 自有空远程仓 + 更新仓库描述」；其余远程动作、PR、Release、云 CI、改历史继续禁止。pre-push hook 未删除、未用 `--no-verify` 绕过，推送后逐字节复位 |
| 上一候选审计证据（未改动） | `.project-local\audit\20261030-codex-independent\`（`audit-report.md`、`audit-verdict.json`、原始探针与夹具） |
| 上一执行轮证据（未改动） | `.project-local\audit\20261029-local-fusion-p0p1\` |
| **本轮返工证据（新）** | `.project-local\audit\20261030-qoder-ed9037\`（含 `REWORK-DELIVERY.md`） |

## 2. 上一候选被审计否定的结论与本轮对应关系

| 审计发现 | 上一候选的结论 | 本轮处置 | 机器可读证据 |
|---|---|---|---|
| F01 P1 来源映射未落实 | 198 条登记为 `MAPPED_P0` 指向不存在的规划目录 | 13 个真实断链模块迁入并接通统一入口；198 条逐条给去向；迁移脚本改为不再删候选树 | `f01-disposition.json`、`migration\work-gap-disposition.csv`、`.project-local\runs\f01-migration\F01-MIGRATION-REGISTER.json` |
| F02 设计结果导入无绑定校验 | 错项目/错任务/错尝试/旧版/零摘要/`../../…ps1` 均 201 入库 | 两域共用一份版本化绑定合同，入库前拒绝且不留残条 | `tests\unified\test_v11_audit_rework.py`、`a01-a10-results.json` 的 `A04` |
| F03 技术核验摘要口径不一致仍 PASS | 两支都 PASS，读的是最新修订却宣称修订 1 通过 | 按固定修订自身的存储行读回并比同一口径摘要；新增 `LATEST_AT_PACK` / `IMMUTABLE_PIN` 两种合同 | 同上 `A03` |
| F04 验收门接受伪 PASS | 伪绑定+空证据+错指纹 → BACKED/exit 0；后写 FAIL 不影响旧 PASS 支撑就绪 | 门重算关系、摘要、证据可读性、时序与当前有效性；COMPLETED 在存储层需要当前支撑；核验按 `rowid` 定序 | `acceptance-gate-evidence.json`、`tests\unified\test_v10_gate.py` |
| F05 统一搜索丢 WORK 维护方案 | 调用不存在的 `solution_library.search` 并回报 unavailable | 按真实 `store_view(store, query=…)` 接通，返回类型化状态 | `a01-a10-results.json` 的 `A05` |
| F06 无法离线隔离安装 | 根无包定义，pip 实际 not installable | 补 `pyproject.toml` 与资源收录；wheel 建成并安装到隔离目录，安装态 `__file__` 全部指向安装树 | `.project-local\build\20261030-qoder-ed9037\verify-report.json`、`a08-verify.log` |
| F07 test/demo 被写成 live | 默认值把合成证据升为真实来源 | 来源沿 project→task→attempt→result→verification 继承，拒绝向上提升；旧库行读作 UNENFORCED_LEGACY | `test_v11_audit_rework.py` 的 F07 段 |
| F08 Agent 引用冒充真人验收 | `verifier_ref` 非空即可 COMPLETED | 真人验收只解析本地 Human Gate 账本；合成批准只产生 test 记录；身份仍声明为自证非核实 | 同上 F08 段、`scripts\human_approval.py` |
| F09 Observer 独立入口靠偶然导入顺序 | 干净进程 import 失败；统一服务未挂任何 WORK 消费面 | 包内相对导入修好；Observer/Control 经同一内核挂载且复用同一 CanonicalStore（不建第二账本） | `GET /api/work/surface-map`、同上 F09 段 |
| F10 资格由常量/文件存在派生 | 纯函数即 VERIFIED；`authorization=REQUIRED` 仍 can_invoke=true | 资格只由绑定当前候选版本、操作与范围的探测记录派生，未知即 fail closed | `GET /api/v1/qualification-evidence`、同上 F10 段 |
| A06/V07 只验证源码复制 | 业务数据迁移未验证却填 PASS | 源码复制与受控业务数据迁移分成两条，各自有夹具与失败恢复验证 | `scripts\migrate_business_data.py`、`tests\unified\test_v12_data_migration.py` |

## 3. 结构速览（新增/变动部分）

```
backend/core/         origins.py 引用与来源格 · binding.py 结果绑定合同 · refs.py 引用范围
                      qualifications.py 探测资格账本 · probes.py 受控本地探测
                      human_gate.py 真人验收账本 · work_surfaces.py WORK 消费面挂载
domains/work/orchestration/   F01 迁入的 13 个运行模块 + resources.py + probe.py（默认关闭的授权门）
config/               software-registry / adapter-registry / project-platform-map 等 5 个注册表（迁入）
migration/            work-gap-disposition.csv（197 条逐条去向）
scripts/              build_f01_disposition.py · migrate_work_modules.py · human_approval.py
                      migrate_business_data.py（受控业务数据迁移）· build_offline_install.py
                      verify_isolated_install.py（安装态验收）
tests/unified/        test_v11_audit_rework.py（F01–F10 反例）· test_v12_data_migration.py
                      test_v07_migration.py（隔离复演契约）· test_v10_gate.py（门与恢复）
```

## 4. Codex 复跑步骤（全部本地，不联网；本轮已可**原地全量**执行）

```bat
cd "D:\All projects\AI-WORK-LAB"
set PY=D:\All projects\AI-WORK-LAB\.venv\Scripts\python.exe

REM 1) 全量回归。审计当时 2 项会 rmtree 候选而无法原地跑；V07 契约已改为隔离复演，
REM    默认 migrate_sources.py 只读，因此现在可以不带 --ignore 直接全量执行。
%PY% -B -m pytest tests\unified tests\legacy -q -p no:cacheprovider --basetemp .project-local\runs\codex-regression

REM 2) 真实启动（token 走 stdin，只绑 127.0.0.1，端口 0）
echo <64位hex> | %PY% -B -X utf8 -m backend --workspace .project-local\runs\codex-boot --port 0

REM 3) 验收门（只读审计被检库，绝不写它；0=当前有支撑 1=拒绝 2=不可读）
%PY% -B scripts\acceptance_gate.py .project-local\runs\codex-boot\.project-local\ai-work-lab\unified.sqlite3 ^
  --work-store .project-local\runs\codex-boot\.project-local\ai-work-lab\work-store.sqlite3

REM 4) 离线构建 + 隔离安装 + 安装态验证（全程 --no-index，不联网、不改环境）
%PY% -B -X utf8 scripts\build_offline_install.py --run-id 20261030-qoder-ed9037
%PY% -B -X utf8 scripts\verify_isolated_install.py --run-dir .project-local\build\20261030-qoder-ed9037

REM 5) F01 台账重算与登记校验（只读）
%PY% -B -X utf8 scripts\migrate_work_modules.py
%PY% -B -X utf8 scripts\build_f01_disposition.py --json-out .project-local\runs\codex-f01.json

REM 6) 受控业务数据迁移（只用合成夹具；对真实用户库与生产路径 fail closed）
%PY% -B -X utf8 scripts\migrate_business_data.py --describe
```

**危险命令提示（不要照抄旧入口）：** `migrate_sources.py --apply` 会写目标树，需要
`--confirm REBUILD-MIGRATION`，且遇到候选内已有返工时**拒绝**而非覆盖——**切勿对开发候选执行**。
旧审计脚本 `independent_probes.py` / `additional_probes.py` / `restart_readback.py` 含固定绝对路径、
旧 API 与破坏性前置，只作审计原始留档，**不是可复跑入口**；等价问题已由
`tests/unified/test_v11_audit_rework.py` 稳定复现。

## 5. 本轮未关闭的项（不得当作通过）

- **BLOCKED（仅剩一项）**：`regression-path-loading-test` —— `tests/legacy/work/test_repair_pack_projection.py`
  按仓库路径 exec 源码，安装态天然不满足，属测试自身作用域限制，已如实登记。
- **已关闭（曾是 BLOCKED）**：PyYAML 用本机离线缓存完成项目本地环境的必要依赖调整（未联网、未升级其他包；
  记录见 `.project-local\audit\20261030-qoder-ed9037\local-dependency-step.json`，回滚脚本
  `rollback-local-dependency-step.ps1` 同目录；缓存里 cp312 的 `_yaml` 扩展被有意排除，
  本 venv 是 3.13，PyYAML 走自身纯 Python 回退，这一点在登记里写明而不是隐藏）；
  宿主桥接脚本已放到适配层实际探测的包内路径，并与真值逐字节一致，漂移由守卫测试拦截。
- 真实 Photoshop/Illustrator 保存-重开-读回（需 Human Gate）仍 BLOCKED。
- **NOT_RUN**：真实用户数据迁移（未获精确路径与授权）；外部执行器真实资格；模型推理；
  STITCH 前端；真人专业验收签字（留给 owner，不由 QODER 代签）。
- **DEFERRED**：多 Agent/BOT、跨机执行、完整自改写激活与恢复（按 P3 分期）。
- **未声明**：系统级出站隔离未被证明；本文不声称绝无外传，也不把提示词或 pre-push hook 当作隔离证据。

## 6. 口径与红线

- 候选摘要口径：Git cached + 非忽略 untracked 的「路径→文件 SHA-256」，排除 `.mimosa`、`__pycache__`、
  `.pytest_cache`，映射按路径排序后取 `json.dumps(mapping, sort_keys=True)` 的 UTF-8 字节再算 SHA-256。
  不要混用「仅 tracked」与「含未跟踪」两种口径。
- 源码摘要与证据摘要互相独立，不循环绑定。
- 计数是**线索**，不是功能通过率；通过率只认逐项实测结果。括号里是 Codex 审计时点的读数
  （837 映射行、13 个断链模块、89 兼容路由、50 设计任务、198 缺口、2638/4049 来源文件）：
  本轮实测 837 / 89 / 50 / 2,638 / 4,049 仍成立，缺口随真实迁入变成 197、DESIGN 覆盖行变成 4,470，
  所以按数字的断言一律由生成器与 `tests/unified/test_v14_registers.py` 现算，不引用本文档的数。
- **Codex 复审本身不构成推送授权**：授权只来自 owner 的明确指令。2026-10-31 owner 已就
  「首次上传 + 更新仓库描述」下令我方执行（`INTEGRATION_POLICY.md` §6），该放行**不含**
  合并 main、PR、Release、云 CI、force-push 与改写历史；pre-push hook 在推送后逐字节复位，
  继续阻断后续未经授权的推送。
- 两个来源仓保持只读；本轮由 `snapshot-before/after.json` 与
  `test_sources_are_byte_identical_before_and_after_a_rerun` 断言其逐文件摘要未动。
  （R1 版本文提到的 `test_source_repos_stay_untouched` 已被该更强断言取代。）
- `.project-local\audit\` 下的既有审计库是反例证据，不是工作区生产库，不得据其伪造记录判断产品资格。

## 7. SSE 与旧消费面的剩余边界

`/api/work/observer/events` 现在提供 SSE 帧：帧格式由迁入的 `sse_hub.render_sse_frames` 生成，
事件号取自 store 自身修订，每帧现读现发，且 `continuous_stream=false` 写在帧内；流是**有界**的
（`?frames=`，上限 5），持续推送的 watcher 仍属独立 sidecar，本批未接入，也不谎称等价。
该路径同样拒绝写请求并落拒绝记录。

## 8. 本轮新增的两本账

* `migration/source-coverage-work.csv`（2,638 行 = 2,638 个非忽略文件）与
  `migration/source-coverage-design.csv`（4,049 个文件 → 4,470 行；同一来源被复制到多个目标时逐目标判定）。
  类别之和必须等于行数，由 `tests/unified/test_v14_registers.py` 现算校验，不靠人报数。
* 非 `.py` 的 7 条登记缺口现在会说明"目标仓同路径是否已有该文件"，并把摘要写进依据：
  两条 WORK 注册表文件其实已在目标 `config/` 下且逐字节相同，其余为治理文档与前端文件。
  "没进复制清单"与"缺失"是两句话，之前的关账把前者说成了后者。
* `migration/work-gap-disposition.csv` 的行集与覆盖登记中 `REGISTERED_GAP` 类的 `.py` 子集必须完全相同
  （`test_v14_registers.py::test_coverage_gap_rows_match_the_f01_register` 断言）。行数不写死在这份文档里：
  审计时是 198，本轮关掉一条真实缺口后是 197，测试改为要求两个生成器、登记文件与类别之和是同一个 population。

## 9. 首次上传（2026-10-31 owner 授权）与回读方式

owner 指令「完成后上传到仓库 更新描述」→ 定点放行三个动作，登记在 `INTEGRATION_POLICY.md` §6：
首次 commit、首推到 owner 自有且当时为空的远程仓 `DTALEX66/AI-WORK-LAB`（PUBLIC）、更新该仓描述。
其余远程动作（合并 main、PR、Release、云 CI、force-push、改写历史、fetch/pull）不在放行范围内。

- 推送对象是当前工作分支，不是 `main`；远程在推送前没有分支、没有提交、没有内容
  （回读命令见下），所以不存在被覆盖的历史。
- 上传的是**受测候选本身**：先改文档、再跑全量回归、再提交，使「测过的树」与「推上去的树」
  是同一份。`.project-local/`、`workspace/`、`.venv/`、`node_modules/`、`__pycache__/` 由
  `.gitignore` 排除——数据库、令牌、日志、审计证据和任务包都不在上传面内。
- pre-push hook 不删除、不用 `--no-verify` 绕过：按 SHA-256 登记后临时移出 `.git\hooks\`，
  授权推送完成后逐字节复位并复核摘要。
- 推送前的逐文件审读（数字只写在 JSON 里）：`prepush-hazard-scan.json` 扫凭证形态，
  `public-exposure-scan.json` + `personal-identifier-detail.json` 扫个人标识与真实邮箱。

Codex 复审时请现读，不要抄本文任何数字：

```bat
cd "D:\All projects\AI-WORK-LAB"
git rev-parse HEAD & git rev-list --count HEAD & git ls-tree -r --name-only HEAD | find /c /v ""
git ls-remote --heads origin & git config --get core.hooksPath & dir .git\hooks\pre-push
gh repo view DTALEX66/AI-WORK-LAB --json description,defaultBranchRef,visibility,pushedAt
```

若上述回读与本文陈述不一致，以回读为准，并把差异登记到 `.project-local\push-20261031\` 后再继续。

三条实测事实（推送当轮现读，数字只写在证据 JSON 里）：

- 上传面与候选面一致：远程树实测为 1,226 个 blob，数据库、日志、`__pycache__`、`.venv`、
  `workspace`、`.project-local` 成员数为 0——被 `.gitignore` 排除的运行库与审计证据没有因为
  这次上传离开本机；远程 ref 与本地 HEAD 同一个提交。
- 新克隆可复现逐字节断言：根 `.gitattributes` 关闭 Git 文本转换。本机 `core.autocrlf=true`
  原本会在 add/checkout 时改写换行，而 `migration/copies.json` 与覆盖登记按 SHA-256 断言
  目标文件与来源一致，归一化后的克隆会让这些断言凭空失败。 staged blob 与工作文件被逐个
  比对过，差异为 0。
- 重跑不再移动候选摘要：`scripts/build_migration_map.py` 只在实质内容变化时才刷新
  `generated_at` / `reviewed_at`（此前每次重跑都会重写这两份产物的时间戳，使提交后的树
  看起来发生漂移）；`tests/unified/test_v07_migration.py` 现在逐文件断言两次重跑后
  `migration/` 全部产物**字节**不变，而不只是去掉时间戳后相等。提交之后又跑了一遍全量套件，
  `git status` 与 `git diff HEAD` 均为空。

## 11. 2026-10-31 全量闭环轮（按 acceptance 条款逐条实测）

本轮的口径换了：不再按「任务」报完成，而是把 `09_任务分期与验收.json` 的 **19 项任务、48 条
acceptance 子句**逐条判定（子句原文从任务包转录，不由本文改写），每条必须指向一个**现在就会
执行的断言**——测试函数、实时路由、可复跑脚本或跟踪登记；`CONFIRMED` 的行在测试里被重新解析一次，
解析不到就自动降级。登记：`migration/task-acceptance.csv`（48 行）+
`config/blocker-register.json`（由条款登记派生，不手抄）。

| 实测项 | 读数（§10 时点：那张表测的是当时的候选；后续读数在 §12–§14，勿把本表当当前值） |
|---|---|
| 全量回归 | `340 passed, 3 subtests passed`，0 failed / 0 errors，exit 0 |
| acceptance 条款 | 48 条：39 CONFIRMED / 4 PARTIAL / 2 BLOCKED_BY_BOUNDARY / 3 DEFERRED_P3；必做阶段（P0/P1）无 GAP |
| 必做阶段开放项 | 2 条：`L10#0`（32 行来源待 owner 判定）、`L15#1`（migrate_sources 无进程级 kill 复演） |
| 验收门 | `--blockers config/blocker-register.json` → **REFUSED / exit 1 / batch_ready=false**，点名 L10#0、L15#1 |
| 端点面 | 164 条逐路由实测：97 成功 / 66 具名领域拒绝 / 1 缺陷；兼容面 49 条 GET 全表 × 无令牌/错 Host = 401×49、403×49 |
| 启动探针 | `scripts/boot_probe.py` exit 0、verdict OK、8 项全 as_declared（新增的两项就是兼容面 401/403，此前 docstring 声称而代码未做） |
| 迁移计划 | identical 1369 / EOL_ONLY 2 / MODIFIED 10，其中**已声明且摘要相符 10、未声明 0**；unmanaged 0 |
| 来源仓 | WORK 2,638 文件 `f1032967…`、DESIGN 4,049 文件 `c3c1bfe3…`，与本轮开始时逐字节一致 |

本轮新立的登记（全部由脚本生成，行数由测试现算校验）：
`migration/task-acceptance.csv`（48）、`migration/route-surface.csv`（164）、
`migration/ui-entry-disposition.csv`（56 个原界面入口）、
`migration/capability-family-register.csv`（30 个能力族）、
`migration/requirement-traceability.csv`（25 条需求）、
`migration/api-contract-check.json`（15 条前后端 API 提案）、
`migration/deferral-register.json`（9 个延期能力 + 5 个 P2/P3 任务的接缝/依赖/验收）、
`config/blocker-register.json`、`config/environment-baseline.json`、`docs/AUDIT-STATE.json`。

**本轮找到的四个后端真缺陷（不是测试缺口）**，都已修且有能红的断言：

1. `backend/core/unified_store.py` 的 `update_attempt` 只在 Python 里比 revision，然后发
   **无条件 UPDATE**——两个写者同一 revision 有 30/30 都落地（丢更新），共享连接时还会抛
   未typed 的 `sqlite3.InterfaceError` 而两支都没写进去。现改为 `WHERE revision=?` 条件更新
   + `rowcount` 复核 + `busy_timeout` + 进程内写锁；模块 docstring 早就写着「每个写都是
   compare-and-swap」，那句在本轮之前是不成立的。
2. `GET /api/v1/tools` 与 `GET /api/v1/connections` 的状态是**写死常量**，`CONNECTED_LOCAL`
   没有任何探测产生它——正是 F10 关掉的形状在工具面复发。现由探测账本派生（同一本账，不起
   第二账本），加一条记录会改变状态、撤掉或过期就回到 `NOT_PROBED` 并带具名原因。
3. `domains/design/design_lab/governance/evidence_readback.py` 的仓库根用 `parents[3]`，在融合
   后的目录深度上落到 `<root>/domains`，于是投影永远在错误位置找 `design-lab/config/task-ledger-r3.json`。
   这是 F01 点名的同一类锚点缺陷（`composition_root` 的 `parents[2]`）在另两个模块上的复发；
   `illustrator_com.py` 同样中招。现按标记上溯求根，并在迁移的 `PATCHES` 里声明——否则下一次
   `--apply` 会把修复抹掉。修复后 `GET /api/evidence-projection` 仍是**具名拒绝**
   `EVIDENCE_LEDGER_ABSENT`：融合仓自己没有那份 ledger，按合同拒绝而不是回空清单。
   （本行写的状态当时是 503；§14 把这一类拒绝按部署事实改判为 409，拒绝本身与不回空清单的
   要求不变。）
4. Illustrator 宿主桥接脚本**从未被迁入**（包内路径只有 Photoshop 那一份，迁移规则里也没有它），
   所以 `ILLUSTRATOR_BRIDGE_MISSING` 是「资产缺失」而不是「未授权」。现按适配层实际探测的包内
   路径补入并登记为逐字节相同的复制（24,587 字节）。

两处**我自己说错并被本轮纠正**的话，留在这里而不是悄悄改掉：

- 我先前断言「Illustrator 桥接资产在来源仓也不存在」——错。那是一条 `ls … | head -4` 被截断的
  目录列表，来源仓其实跟踪着该文件；缺失只发生在目标仓。
- §5 的「BLOCKED（仅剩一项）`regression-path-loading-test`」是当时的读数，已被本轮实测取代：
  `tests/legacy/work/test_repair_pack_projection.py` 的按路径 exec 改为包内导入，
  `verify_isolated_install.py` 的 `legacy-regression` 从差分判据改为**对 `tests/legacy` 要求
  绝对 0 失败**，另配暂存源码对照；实测安装树 `170 passed`、exit 0，报告
  `overall PASS`、`blocked = []`（`.project-local/build/offline-20261031T000643Z/verify-report.json`）。
  撤掉这条 BLOCKED 没有删除或放宽任何断言。

另外两处「登记面」的收紧：源码覆盖里 226 行共用一句模板的 `SOURCE_UNREGISTERED` 被拆成
**已判定（逐行带 file:line 权威）**与 `OWNER_DECISION_PENDING`（32 行，逐行理由唯一，测试冻结
了这份名单）；F01 的「已接线」标签不再由文件存在证明，而由从 `backend/v1.py`、
`backend/core/work_surfaces.py`、`backend/app.py` 可达模块的 **AST 导入图**证明——
`git_collector.py` 因此被降级为 `MIGRATED_PRESENT_UNWIRED`（零消费者）。迁移侧 10 个
「按返工而非按复制」的文件此前在计划里是无差别的 MODIFIED；现在逐个声明并附摘要/字节数/差异行数，
`tests/unified/test_v07_migration.py` 摘要校验也从 25 文件抽样改为**全量扫描**（正是这次改全量
才发现其中 3 个是未声明的）。

Codex 复审的复跑命令在本轮有增补：

```bat
%PY% -B -m pytest tests\unified tests\legacy -q -p no:cacheprovider --basetemp .project-local\runs\codex-regression
%PY% -B -X utf8 scripts\build_task_acceptance_register.py
%PY% -B -X utf8 scripts\build_blocker_register.py
%PY% -B scripts\acceptance_gate.py <unified.sqlite3> --blockers config\blocker-register.json
%PY% -B -X utf8 scripts\boot_probe.py
%PY% -B -X utf8 scripts\candidate_snapshot.py
```

另有一处**先前就存在、本轮才现形**的登记面缺陷：`write_text(...)` 不传 `newline=""` 时，
Python 会把每个 `\n` 翻成 `\r\n`，而 csv.writer 的行尾本来就是 `\r\n` —— 于是 `migration/mapping.csv`
与 `migration/design-tasks.csv` 每一行后面都跟了一个幻影空行（838 与 51 处）。`DictReader`
静默跳过空行，所以行数、状态直方图与所有下游测试一直是绿的，只有按字节比对才看得见。
现在两个写入点都显式 `newline=""`，并由
`tests/unified/test_v14_registers.py::test_no_register_carries_a_doubled_line_ending`
按原始字节扫全部登记（读文本的检查看不到这个问题）。同一条纪律也用于本轮新出的登记表：
校验一律 `--check`，不写跟踪文件。

仍开放的必做条款有两条，其中**阻断本批的只剩一条**（口径要分清，两个数字都来自同一次实测）：
**L00#2**（可证明的隔离范围）按 owner 明确移出义务登记为 `disclosed`，仍写 BLOCKED 不写通过；
**L10#0** 的 32 行
`OWNER_DECISION_PENDING`（WORK 18 / DESIGN 14，逐行理由唯一、名单在覆盖登记里冻结）。
这些是"要不要作为能力迁入"的判断，不是可以由代理解释的技术问题——任务包的延期规则写着
「不可借延期删除行为」，所以既不能默默丢弃，也不能由代理擅自接线。

### 从克隆复跑时被实测出来的三处新问题（本轮内已修）

「Codex 克隆后按 §4 复跑」这句话本身此前从未被执行验证过。真的克隆一次之后：

- `tests/legacy/design/{test_assistance_plan,test_knowledge_library,test_target_profile}.py`
  把 `REPO/.project-local/task-runtime` 作为 `mkdtemp` 的**父目录**使用，而 `.project-local/`
  被 `.gitignore` 排除——克隆里没有这个父目录，`mkdtemp` 直接 `FileNotFoundError`，81 项在
  克隆里根本跑不起来。现在由 `tests/conftest.py` 的会话级 autouse 夹具创建
  `.project-local/{task-runtime,runs,build}`（只建目录，不建文件）。
- `GET /api/health`（兼容面）读取**已构建**的 workbench bundle；没构建过的检出里读操作抛
  `FileNotFoundError`，被分发层折叠成 `503 PROJECT_STORE_UNAVAILABLE`——把运维指向数据库，
  而真实事实只是"这里没构建 UI"。现在该路由恒答 200，`bundleSha256: null` +
  `bundleOrigin: "not-built"` 把缺失写在字段里，由 `tests/unified/test_v24_health_bundle.py`
  三个用例双向钉住（未构建时不得报 store 故障；真构建时不得谎报 not-built）。该修复同时写进
  迁移 `PATCHES`，否则下一次 `--apply` 会把它抹掉（计划现读：10/10 已声明且摘要相符，0 未声明）。
- L15#1「失败恢复」补上进程级复演：`migrate_sources.py --fail-after N` 在写完临时件、
  `os.replace` 之前 `os._exit(9)`（注入异常会跑完清理，杀进程不会）。实测断言：崩溃点最多留下
  一个 `.migrating`、没有任何目标被截断为零字节，续跑后与一次干净运行逐文件摘要相同。

`tests/unified/test_v23_clone_repro.py` 把这件事变成常驻守卫：它在临时短路径里 `git clone`
本仓，在克隆内跑完"不依赖 .venv、不依赖两个只读来源仓、不依赖 .project-local/build 收据"的
那一半套件（分类由扫描每个测试文件的源码得到，不写死名单），并要求 machine-bound 那一半被
点名而不是被忽略。

门的新语义（复审时请按这个读）：`--blockers` 缺席时 `batch_readiness.scope` 标为
`IN_STORE_CLAIMS_ONLY` 并给 warning，不再沉默；必做阶段的非通过条款一律阻断；P2/P3 与 owner
明确移出义务的条款进 `disclosed` 列表并带出处，不阻断也不消失。**因此本轮的门输出是
REFUSED/exit 1——这就是「本批不能宣称 P0/P1 全部通过」的机器表达**，不是脚本坏了。

仍未关闭（不得当作通过）：真实宿主保存-重开-读回与外部执行器真实资格（授权边界，BLOCKED）、
模型推理、真实私有用户数据迁移（NOT_RUN）、STITCH 前端（NOT_RUN）、真人专业验收签字（留给
owner）；系统级出站隔离未被证明。结论口径仍是**「QODER 全量闭环自测完成，仍有 2 条必做条款
开放，待 Codex 独立复审」**。



## 12. 2026-10-31 收尾：交接文档要求的追踪表进仓，外加四处我自己写的假绿

交接 §七 要求「一份新的 F01–F10 与 A01–A10/V01–V10 追踪表」，§八.2 要求「F01–F10 逐项闭环表
和 A01–A10/V01–V10 机器可读结果」。这张表此前只存在于 `.project-local/`——也就是克隆看不到，
连「F04 是什么」都无法在仓内回答。本轮把它搬进来，并按同一纪律处理它的两个配套：

- `migration/audit-item-closure.csv`：20 行（F01…F10 + A01…A10），列即 §七 点名的字段——
  适用要求、定义出处与**定义文件摘要**、根因/待核假设、实际修改文件与调用入口、当前结果
  （只允许 PASS/FAIL/BLOCKED/NOT_RUN/DEFERRED）、**证据种类单列**（禁止把测试/合成/真实来源
  混成一个完成率）、未验证子项、独立复审（20 行全部 `NOT_RUN`：本候选没有被独立复审过）、
  独立命令与 cwd/解释器、真实 exit code、测量时刻、日志/产物路径、受测候选摘要、机验结果、
  限制与下一步。由 `scripts/build_audit_item_closure.py` 生成，要求原文从定义文件**解析**而来
  不是转写；本机没有运行收据时相关列写「未在本机测量」，不留一个无法溯源的数字。
- `docs/CODEX_REWORK_ITEMS_F01-F10.md`：F 项定义的逐字摘录（文件头登记来源文件 SHA-256、
  字节数与行区间 112–182）。交接原件按边界继续留在 `.project-local/`，不改原件、不把它的
  提示词语句升格为根指令。
- `config/isolated-install-verdict.json`：`scripts/build_isolated_install_verdict.py` 从
  `.project-local/build/offline-20261031T044636Z/verify-report.json` 现读生成，绑定该报告的
  SHA-256；`overall PASS`、`blocked = []`、16 项检查逐条带 verdict，路径前缀折叠成
  `<REPO>`/`<HOME>`，用户主目录不进 Git。没有报告时脚本**拒绝生成**并给出重建命令，而不是
  输出一份空记录。
- V01–V10 **不进这张表**：它的归属是 `tests/unified/test_v01_v10_register.py`（用 importlib
  解析到真实可调用的测试函数）。同一件事不留两个门管同一批字节；新表只引用它，不重述它。

四处**我自己写的假绿**，是被上述纪律当场抓出来的：

1. 共享解析器 `_resolve` 有一条 `symbol in text` 兜底，于是 L11#0 引用的
   `tests/conftest.py::build_server` 只命中了一个**调用点**（`build_server` 的定义其实在
   `backend/app.py:69`）。现在 `.py` 目标必须落在定义点（`def`/`class`/赋值），非 `.py` 仍允许
   字面标记。改正后总数仍是 40 CONFIRMED，但 L11#0 的证据换成
   `test_v17_process_restart.py::test_backend_boots_twice_and_recovers_the_orphan`——它真的用子
   进程起 `python -m backend` 并断言 `host == 127.0.0.1`，条款「真实 loopback HTTP」由执行它的
   测试证明，而不是由一个 helper 的名字证明。
2. 复制引擎按目录走，逐文件登记按 `git ls-files` 口径走，两个读数相差 254 个**来源仓自己
   `.gitignore` 的文件**：253 个 `apps/workbench/node_modules/**` 与 1 个
   `design-lab/config/.verify-chain-ok`。后者的全部内容是一行 `ok <DESIGN-LAB 的提交号>`，
   它被复制进了跟踪树——放在本项目里会被读成「某条验证链通过了」，而那条链不是这里跑的。
   已加入 `SOURCE_IGNORED_NAMES` 排除（`--plan` 不再意图它），删除该文件并同步去掉复制清单里
   的记录：§13 时点读数 `identical 1115 + EOL_ONLY 2 + MODIFIED 10`、`unmanaged 0`
   （§15.4 现读为 `identical 1116`；这 +1 具体是哪一条本轮没有去追，两个数分属两次实测，
   不合并成一句"现读"）。node_modules 的
   253 条记录按历史事实保留（它们的去向在本机存在、且被本仓 `.gitignore` 排除，克隆里没有）。

覆盖登记的**行键**第一次被钉住（`test_v14_registers.py::test_coverage_row_identity_is_the_pair_and_the_extra_rows_are_the_fan_out`）：`(来源, 去向)` 必须唯一；DESIGN 现为 4,470 行 = 4,049 个来源路径 + 421 行一对多扇出，多出来的行数
必须等于「每个来源的去向数 − 1」之和；不得出现复制清单里没有的去向。登记注记原先写
「DESIGN 4,049 每行有类别与依据」，把路径数当成了行数，已改成两个数都写清。本节写下时 DESIGN 是
4,469 行 = 4,049 + 420，L21 关账给 `adapter_conformance.py` 多登记了一个去向，现算为 4,470 = 4,049 + 421；
这类差一行只会让抄数字的人出错，所以 L10#0 注记里的数字已改为生成器现算（§15）。

第三处假绿在我自己新写的守卫里：它用 `str(Path.home())`（反斜杠形式）检查安装判定记录有没有泄漏用户主目录，而报告里的 argv 是**正斜杠**形式的整条命令行，于是 6 处临时目录路径全部漏检、守卫仍然绿。折叠改成对两种写法做子串替换，守卫同时断言两种写法与用户名本身都不在跟踪文件里（`test_v25_...::test_the_isolated_install_record_is_tracked_and_self_describing`）。顺带清理：本机发现两个 20:53 起就没退的 `-m backend` 测试子进程（`--port 0`，指向临时 workspace），已终止并删除其临时根——这是上一轮安装验收留下的孤儿，不是产品进程。

第四处是这张新表自己带出来的，而且是被**克隆复跑守卫**抓的（这正是留它的意义）：
`build_audit_item_closure.py --check` 在克隆里必然报 drift——因为它把「真实 exit code / 测量时刻 /
受测候选摘要」三列也逐字节比，而这三列的值只能来自本机 `.project-local` 里的运行收据。修法不是把
检查放宽，而是把检查的**射程写清楚**：本机有收据时三列照样全比；没有收据时其余 17 列照样全比，
并由 `receipt_columns_exempted` 明说免检了哪三列。`test_v25` 因此双向断言（有收据→免检表必须为空；
无收据→必须恰好是这三列），另加一条反例：改动落在免检列之外时 drift 必须仍为真。
登记的数字仍然是本机测的，登记**说了**这一点——克隆不需要假装验证过它没见过的东西。

复现路径也归位了：V07 的进程级崩溃复演把复演根放在系统临时目录（按 pid 命名、结束即清理），
因为它测的是「进程被杀之后字节收敛」，不该被 pytest `--basetemp` 的长度左右。我一度把同一文件里
4 个 `tmp_path` 用例报的 `ERROR` 当成同类缺陷——实际是我那条复现命令的 `--basetemp` 父目录根本
不存在（WinError 3），探针自己坏了；把父目录建出来之后 11 项全过，那 4 个用例并没有缺陷。

还有一处是**这套绑定机制本身**的循环，必须说清，否则复审者会以为登记数字可以被随意刷新：
`CLOSURE-STATE.json` 每次测量都就地重写，而登记表是被跟踪文件——「登记表对齐最新收据」这个要求
会让两者互相追着跑（重测使登记变陈旧，改登记又使候选摘要与刚测的那份不一致）。做法是给每份收据
按自己的候选摘要存档：`receipt-archive/CLOSURE-STATE-<digest16>.json`，登记表新增「运行收据」列
**点名它绑的是哪一份**，`test_v26` 读的就是那一份存档，之后的重测不再动摇已发布的登记。产生这份
干净收据的那次运行显式 `--deselect` 了两个节点（`test_v26_...::test_the_measured_figures_are_the_ones_the_named_receipt_carries`
与 `test_v23_clone_repro.py::test_a_clone_can_run_the_machine_independent_part_of_the_suite`——前者当时
拒绝绑定一份记录了失败的收据，后者的克隆来自尚未包含本次修复的提交），**节点 id 与数量都写进了收据
的 `deselected_nodes`**，不靠事后解释。随后包含全部守卫的完整复跑（见本节末尾的实测行）才是对最终
提交态的验证。

§4 的复跑命令再增补两条：

```bat
%PY% -B -X utf8 scripts\build_audit_item_closure.py
%PY% -B -X utf8 scripts\build_isolated_install_verdict.py --check
```

守卫分两半，按能否在克隆里跑分开：`test_v25_audit_item_closure.py` 查人口、词表、定义出处、
证据目标与「PASS 必须写明仍未验证的子项」；`test_v26_local_run_receipts.py` 查登记数字是否等于
本机运行收据与安装报告的现读值，并由 `test_v23_clone_repro.py` 点名归为 machine-bound，
而不是被静默跳过。

### §12 时点的实测（提交态，非计划；被 §13 末尾的读数取代）

- 全量回归：`360 passed, 3 subtests passed, 0 failed`（exit 0，8m20s，
  `--basetemp .project-local/runs/final-32c3d22`，解释器 `.venv/Scripts/python.exe` = CPython 3.13）。
  这一条包含 `test_v23_clone_repro` 的克隆复跑与 `test_v26` 的收据绑定守卫，
  所以「克隆里能跑」与「登记数字对得上存档收据」是在同一棵树上同时成立的。
- 验收门（消费必做阻塞登记）：`REFUSED / exit 1`，阻断项 1（`L10#0`），披露项 7
  （含按 owner 移出义务的 `L00#2`、真实宿主的 `L20#0`）。
- 任务包 48 条子句：CONFIRMED 40 / PARTIAL 3 / BLOCKED_BY_BOUNDARY 2 / DEFERRED_P3 3；
  必做阶段（P0+P1）37 条，其中 35 条 CONFIRMED。
- F/A 闭环表：20 行全 PASS 自测结论，`独立复审` 列 20 行全部 `NOT_RUN`；
  每行「未验证子项」写明该行边界内还没测的部分。绑定的测量收据：
  `receipt-archive/CLOSURE-STATE-c2d9dd68fa0f34e8.json`（358 passed / 0 failed / 2 deselected，
  节点 id 记录在收据内）。
- 来源两仓只读性：WORK 2,638 / DESIGN 4,049 个 git 口径文件的摘要在两次读数之间不变。
- 结论口径：**QODER 全量闭环自测完成，仍有 1 条必做条款阻断（L10#0 的 32 行待 owner 判定），
  待 Codex 独立复审**。不自称「Codex 已通过」，也不把本批说成产品就绪。

### 13. 2026-10-31 续：L21 的三方对账闭不上，是因为一条 PASS 没有可读依据

`L21#0「本地契约可先验证」` 上一轮写 PARTIAL，理由当时只有一句「三者一致性无对账」。
把这句话当真去查，查出的不是一个缺失的检查，而是**一条站不住的 PASS**：

- `config/capability-conformance.json` 对 `acp` 与 `skills` 两个协议写 `STATIC_PASS`，
  而它们**唯一**的条目分别声称依据 `integrations/executors/codex/acp_adapter.py` 与
  `config/skill-provenance.yaml`——两个文件都不在本候选里（来源仓 `.gitignore` 之外、
  按 F01 判定为未随迁）。投影把这两个状态逐字抄进每一张适配器卡片，
  于是「静态契约通过」这句话在这个仓库里没有任何可再读的依据。
- 协议契约本身在这个仓里也没有执行者：`adapter_conformance.py` 在映射里是 `RETAIN`。
  它现在按字节迁入 `domains/work/workflow_core/adapter_conformance.py`
  （摘要 `b4fb018e…`，逐字节等于来源），动词表
  `detect/capabilities/plan/apply/invoke/observe/rollback` 第一次有一个可执行的主人。

两条处理，方向都是将低而非拔高：

1. `acp`、`skills` 从 `STATIC_PASS` 改为 `STATIC_UNVERIFIED`，并把规则写进数据的
   `status_rule`（协议只有在其全部条目的来源都能在本候选读到时才可声明 PASS）。
   未随迁的来源不作为遗忘：判定文件把它们列进 `disclosed`，**降级不等于抹掉**。
2. `scripts/check_adapter_conformance.py` 做三方对账（登记 ↔ 枚举 ↔ 投影），
   判定写入跟踪文件 `config/adapter-conformance-verdict.json`；
   `tests/unified/test_v27_adapter_conformance.py` 现读复算，并带两条反例：
   把 `STATIC_PASS` 加回去必须变红（`UNSUPPORTED_PASS` + `SOURCE_ABSENT` 同时命中）、
   登记里凭空多一个动词必须变红。合成夹具跑通用的是 `ISOLATED_PASS`，
   判定里记为 `CONTRACT_ONLY`——它不授予任何真实资格（这条与 F10 同界）。

`L21#0` 因此改为 CONFIRMED（必做阶段不变，仍是 P2/条件项），全量 CONFIRMED 从 40 到 41；
阻塞项仍然只有 `L10#0`。这轮还被自己的钉子拦住两次，都是有效信号：

- `migrate_work_modules.py` 按哈希钉住它迁移的配置文件，我改完 `capability-conformance.json`
  就报 `CONFLICT`。正确做法不是改钉值，而是把这条改为**按必需内容钉**
  （`pinMode: content` + `requiredContent`），于是它校验的是「诚实降级还在」而不是
  「没人碰过这个文件」；把状态改回去会立刻 `REVERTED`。
- `test_v14` 的行键守卫拦住「覆盖登记出现了一个复制清单里没有的去向」——因为我刚给覆盖
  构造加了「按声明的复制表 + 现场重算字节」这一路。守卫改成同样独立地重算摘要，
  只对**字节确实相同**的声明复制放行；注册表不能自己定义什么叫「已复制」。

顺带把去向数从字面钉子改成推导关系：`198` 是审计时读数，本轮真的关掉一条
（`adapter_conformance.py`）后是 `197`；`test_v11`/`test_v14` 现在断言的是
「报告、登记文件、类别之和三者是同一个 population」加一个下限（190≤N≤198），
而不是要求关掉缺口的人先改四个数字。文档散文里留下的 `198` 也一并改为不带行数的表述。

### §13 的最终实测（提交态）

- 全量回归：**368 passed, 3 subtests passed, 0 failed**（exit 0，8m19s，无 deselect）。
  这一条包含 `test_v27`（三方对账与两条反例）、`test_v23_clone_repro`（克隆复跑）与
  `test_v26`（登记对命名收据的复算）。
- 闭环表绑定的测量收据：`receipt-archive/CLOSURE-STATE-cad6c549ca9371bb.json`
  （`head_commit` = `2f37901c0d04…`，即承载 L21 关闭的那一次提交；`suite.deselected = 0`）。
- 任务包 48 条子句：**CONFIRMED 41** / PARTIAL 2 / BLOCKED_BY_BOUNDARY 2 / DEFERRED_P3 3；
  必做阶段（P0+P1）37 条中 35 条 CONFIRMED，非通过 2 条为 `L00#2`（owner 移出义务，披露）
  与 `L10#0`（32 行待 owner 判定，唯一阻断项）。
- 门禁：`REFUSED / exit 1`，`blocking = [L10#0]`，`disclosed` 6 条。
- 结论口径不变：**QODER 全量闭环自测完成，仍有一条必做条款阻断（待 owner 判定），待 Codex 独立复审**。

### §13 补记：对已推送 HEAD 的复跑，以及登记里两处过期陈述

- 对推送后的提交态复跑全量两次，都是 **368 passed, 3 subtests passed, 0 failed**
  （exit 0，无 deselect；`7f025a4` 用 11m27s，最终 tip `6df3c5e…` 用 14m02s）。
  闭环表绑定的仍是收据 `cad6c549ca9371bb`（`2f37901c0d04`，同样 368/0/0）：跟踪文档不能
  命名承载它自己的提交，所以 `运行收据` 列说的是它点名的那份存档收据，不是「最新那一次运行」。
  按这个口径读它，别把它当成 tip 的指纹；tip 的测量就是上面这两次复跑，
  其原始输出在 `.project-local/runs/`（被 Git 排除，不进候选摘要）。
- 自查登记时抓到两条**过期陈述**（不是伪 PASS，是同一张表里自相矛盾）：`L30#0` 与
  `L32#0` 的注记仍写「接缝登记未独立成册 / 未独立登记」，而同一张表的 `L03#1` 已由
  `test_deferral_register_names_a_real_seam_for_every_deferred_item` 确认接缝册存在
  （14 条，缺接缝时生成器直接失败）。注记改为点名接缝册里的 `L30`/`L32` 条目，
  `L30#0` 的证据目标同时换成 `migration/deferral-register.json`——把声明指回真正
  支持它的文件。延期本身（P3 未做）没有改变，改变的只是描述延期理由的那句话。

## 14. 2026-10-31 再续：全表复测把最后一个 5xx 缺陷关掉了

上一节做登记面普查时发现，164 条端点里唯一被判 `缺陷` 的那条就是这个兼容面路由：

```
GET /api/evidence-projection  ->  503  EVIDENCE_LEDGER_ABSENT   判定=缺陷
```

它不是路由坏了，是**状态分类错了**。该路由重算「本检出的证据链状态」，而本检出没有
DESIGN-LAB 的任务账本（账本作为包内来源材料留在 `domains/design/design_lab/resources/repo/`
下）。它拒绝作答是对的——投影合同自己写着「`receipts` 为空从不等于「证据没问题」」，
所以补一个 200 空投影就是造一个假绿；但 503 说的是「服务暂不可用」，会把复审者支去查
一个好好的存储。按部署事实回答才是诚实的：

- `EVIDENCE_READBACK_STATUS['EVIDENCE_LEDGER_ABSENT']` 503 → **409**，并附 `meaning`
  一句话说明「没有账本可读，这不是通过，也不是存储故障」；
- 另外两类拒绝**保持原样**：契约文件不在/取不到提交号仍是 503（操作者可修），
  代码与契约分歧仍是 500（要人改代码）。`tests/unified/test_v28_evidence_refusal_status.py`
  把这三类分开钉住，并逐条植入拒绝验证状态没有被一刀切降格；
- 该修改是迁入文件的返工，因此按锚点声明进 `migrate_sources.PATCHES`：脚本先取引擎
  本会写出的字节、与树上字节做差异、再把自己产出的片段应用回去要求逐字节相同，
  最后重新导入断言「引擎打算写的字节 == 树上的字节」——不是把手改的内容抄进表里。

复测（`scripts/probe_full_surface.py --fresh`，从零工作区起，真实启服务逐路由打）：

```
enumerated=164  success=97  refusal=67  defect=0  fixture=0  unconstructed=0  variants=15
```

`migration/route-surface.csv` 已按这次实测重写：`缺陷` 归零，
`GET /api/evidence-projection` 记为 409 / 领域拒绝 / `EVIDENCE_LEDGER_ABSENT`，
响应键 `detail|error|meaning`。至此 164 个端点里没有一个 5xx。

同一次普查还确认：`migration/requirement-traceability.csv` 里剩下的 3 条 `GAP`（U09/P01/P05）
全部是 STITCH 前端交付物，按边界保持未运行；`ui-entry-disposition.csv` 的 29 PARTIAL / 7 GAP
同属前端面。后端侧在这两张表里没有可自主关掉的余项。

对当前树的完整测量（收据 `receipt-archive/CLOSURE-STATE-845082918268d073.json`，
HEAD `70d5faaa205f`）：**372 passed, 3 subtests passed, 0 failed**（exit 0，10m06s，无 deselect），
门禁 `REFUSED / exit 1`（阻断项仍是 `L10#0`），两来源仓 git 口径摘要不变。

## 15. 2026-10-31 再续：登记面自己引用的数字必须现算，阻断条款必须自带待办清单

这一轮没有新增功能，做的是两类"登记面自洽"：**(a) 文档与登记表引用的数字全部改成现算**，
**(b) 唯一阻断本批的必做条款（`L10#0`）把它等待的行逐行装进就绪门读取的那份文件里**。

### 15.1 第三处也是最后一处手抄数字

`migration/task-acceptance.csv` 的 `L10#0` 注记原先写死
「WORK 2,638 行 / DESIGN 4,469 行（4,049 个来源路径，200 个文件多去向）」，
而 §14 的 L21 关账给 `adapter_conformance.py` 多登记了一个去向，登记表现读是
**4,470 行 / 4,049 个路径 / 201 个文件多去向 / 多出 421 行**。也就是说登记表还在描述上一棵树。
现在这段文字由 `scripts/build_task_acceptance_register.py::_coverage_shape()` 现读两本登记表生成，
注记里没有任何可抄死的数字；同一轮把 §8、§13 与本文件计数条目里的
`4,469 / 420 / 198` 一并改为「现读值 + 审计时读数」双写（历史读数保留并注明是当时读数）。
`tests/unified/test_v14_registers.py` 里那条同样写死 `4,469 / 200` 的 docstring 也删掉了数字——
它的断言本来就是推导式的，绿着的同时把错数字留在文档字符串里。

顺带纠正一处会让人误读的汇总字段：`unresolved` 原先把 `kind=none` 的边界条款（它们本就不声称
任何证据）当成"证据目标解析失败"列出来，输出 `unresolved: [""]`。现在
`unresolved` 只列真正声称了证据却没解析成功的目标（本轮为空），另用
`no_evidence_clauses` 点名不声称证据的条款（`L00#2`、`L20#0`）。**这不是把阻断改成通过**，
是把"没有可读证据"和"证据不成立"分成两句话。

### 15.2 阻断条款现在自带 32 行待办

`L10#0` 等待的是 32 行只有 owner 能判定的来源文件。此前 `config/blocker-register.json` 只说
"32 行待判定"，owner 要自己去两本 CSV 里筛 `OWNER_DECISION_PENDING` 才知道被问的是什么。
就绪门读的就是这份 JSON，所以现在它把行本身带在身上：`L10#0.owner_queue` 逐行给
`repo / path / target / source_sha256 / reason`（32 行，WORK 18 + DESIGN 14），
`decision_options` 给可落到的类别，`decision_how` 给改完之后要重跑什么。不选就继续
`PARTIAL`，本批继续 `REFUSED`。类别不是新造的词：`test_the_owner_queue_offers_only_classes_the_ladder_can_emit`
用正则扫 `build_source_coverage.py` 里 `return ("<类别>",` 的返回形状，核对 offered 的类别确实会被
裁决梯子产出，并拒绝任何"选了等于没选"的类别（`OWNER_DECISION_PENDING`、`SOURCE_UNREGISTERED`、空串）。

四道新守卫在 `tests/unified/test_v21_task_acceptance.py`，其中
`test_the_queue_guard_can_actually_fail` 逐个植入拒绝：登记表文件被删 → `SystemExit`，
两行共用一句理由 → `SystemExit`，同一 `(repo,path)` 出现两次 → `SystemExit`；
`test_the_published_blocker_register_is_still_what_the_builder_produces` 第一次把
`config/blocker-register.json` 的"是否过期"变成断言——门读这份文件决定就绪，此前没有任何测试
看它是不是重新生成过的。

### 15.3 覆盖登记的 `file:line` 权威引用：本轮没坏，但过去靠的是位置巧合

覆盖登记里有 42 行的 `authority` 列指向 `docs/CODEX-AUDIT-ENTRY.md:行号`（`_line_of` 在构建时
按文本找行）。本轮实测这 42 行全部指向**同一行**（第 99 行，`§5 未关闭项` 的 `NOT_RUN` 那句），
而本轮所有文档改动要么在它下面，要么是等长改写（第 46 行是一行改一行），所以行号没位移、登记表没有过期——
`build_source_coverage.py --check` 现读两本登记表逐列比对，实测 `drifted: []`、4,470 + 2,638 行零差异。
**这是位置巧合，不是机制保证**：只要改动落在第 99 行之上，`authority` 就会指向无关文本，
而 `test_v14_registers.py` 只断"行号在文件行数范围内且文件存在"，位移后的引用照样绿。
这与 §12、§13 里那几处我自己写的假绿是同一类问题——检查在跑，但它读的已经不是被改动的那个对象。
处置办法与它们相同：给生成器加一个不写跟踪文件的 `--check`，再让测试断它必须为 0（新增
`tests/unified/test_v14_registers.py::test_the_tracked_coverage_registers_are_not_stale`）。
本轮按该顺序重跑，`audit-item-closure.csv` 的 `--check` 无漂移。

这条新守卫不是"写完就绿"的摆设：在本机把第 99 行上面临时插入一行 `<!-- drift rehearsal -->`，
该测试立刻 **rc=1 FAILED**（131.48s），随后按原字节还原，前后 SHA-256 同为
`be9760c14baa2fc2816de40d657b7faf51c2479a836f3e9cef7b78e04d2165bb`、逐字节相同。
植入的正是它要防的那件事。

### 15.4 本轮实测

- `tests/unified/test_v21_task_acceptance.py` + `test_v14_registers.py`：**26 passed**（0 failed，0 skipped）；
- `build_task_acceptance_register.py` 重跑：48 条款直方图不变
  （CONFIRMED 41 / PARTIAL 2 / BLOCKED_BY_BOUNDARY 2 / DEFERRED_P3 3），
  必做 37 条 = 35 CONFIRMED + `L10#0` PARTIAL + `L00#2` BLOCKED，`mandatory_hard_gaps=0`；
- `build_blocker_register.py`：7 项 = 1 blocking（`L10#0`）+ 6 disclosed，`owner_queue_rows=32`；
- 登记表现读：`source-coverage-work.csv` 2,638 行、`source-coverage-design.csv` 4,470 行、
  `work-gap-disposition.csv` 197 行、`route-surface.csv` 164 行（成功 97 / 领域拒绝 67 / 缺陷 0）、
  `audit-item-closure.csv` 20 行、`capability-family-register.csv` 30 行、
  `requirement-traceability.csv` 25 行、`ui-entry-disposition.csv` 56 行、`deferral-register.json` 9+5；
- 全量回归（收据 `receipt-archive/CLOSURE-STATE-0f3ee5187f919c94.json`，候选摘要
  `0f3ee5187f919c94…` @ `1f82dd36eb4e`、1,265 个候选文件）：
  **377 passed, 3 subtests passed, 0 failed, 0 errors**（exit 0，846.09s = 14m06s，无 deselect）；
  `boot_probe` `verdict: OK` 且输出纯 ASCII；验收门 `REFUSED / exit 1`，
  `blocking_ids=["L10#0"]`、`disclosed_ids=["A00#1","L00#2","L20#0"]`（门能读带 `owner_queue`
  的新版 JSON，未被多出的字段噎住）；迁移普查 `identical 1116 + EOL_ONLY 2 + MODIFIED 10`、
  `unmanaged 0`、10 个返工文件 10/10 有声明与摘要回执、`unattested: []`；
- `migration/audit-item-closure.csv` 的 20 行收据三列（`真实exit_code / 测量时刻UTC /
  受测候选摘要`）与 `运行收据` 一起改绑到这份新收据，`--check` 随后
  `register_drift: false`、`receipt_columns_exempted: []`、`pass_with_unresolved: []`、
  `results` 仍为 PASS 20 / FAIL 0 / BLOCKED 0 / NOT_RUN 0 / DEFERRED 0，`独立复审 NOT_RUN`；
  `test_v25_audit_item_closure.py` + `test_v26_local_run_receipts.py` 实测 **12 passed**；
- 本节新增的 5 个测试节点（`test_v21` 4 个 + `test_v14` 1 个）就是 372 → 377 的差额。

边界没有因为本轮改动而变化：真实宿主写入/读回（`L20#0`）、系统级出站隔离（`L00#2`）、
模型推理、真实私有数据迁移、STITCH 前端（`U09/P01/P05` 与 `ui-entry` 的 PARTIAL/GAP）、
真人专业验收签字、Codex 独立复审仍是 `BLOCKED/NOT_RUN`；`audit-item-closure.csv` 的
`独立复审` 列仍全为 `NOT_RUN`。
