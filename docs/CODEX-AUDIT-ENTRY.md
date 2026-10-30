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
migration/            work-gap-disposition.csv（198 条逐条去向）
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
- 计数（837 映射行、13 领域包、89 兼容路由、50 设计任务、198 缺口、2638/4049 来源文件）是**线索**，
  不是功能通过率；通过率只认逐项实测结果。
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
  `migration/source-coverage-design.csv`（4,049 个文件 → 4,469 行；同一来源被复制到多个目标时逐目标判定）。
  类别之和必须等于行数，由 `tests/unified/test_v14_registers.py` 现算校验，不靠人报数。
* 非 `.py` 的 7 条登记缺口现在会说明"目标仓同路径是否已有该文件"，并把摘要写进依据：
  两条 WORK 注册表文件其实已在目标 `config/` 下且逐字节相同，其余为治理文档与前端文件。
  "没进复制清单"与"缺失"是两句话，之前的关账把前者说成了后者。
* `migration/work-gap-disposition.csv` 的 198 条与覆盖登记中的 REGISTERED_GAP 集合必须完全相同（测试断言）。

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
