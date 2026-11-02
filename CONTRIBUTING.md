# 怎么在本仓干活（入口，不是第二套权威）

规矩本身只写在两个地方：**`AGENTS.md`（读序与更新责任）** 和
**`PROJECT_CURRENT.md`（当前状态）**。这份文件只讲"提交前跑什么、什么不能做"，
不复述状态、不登记能力，免得出现第二份会腐烂的口径。

## 分支模型

| 分支 | 用途 |
|---|---|
| `main` | 稳定主干。日常不直接推；由 `integration/*` 通过快进合并进来 |
| `integration/<主题>-YYYYMMDD` | 融合与批次工作分支的命名约定；当前仓库已收敛到单一主线，
  批次分支完成后并入 `main` 并退掉（`integration/local-fusion-20261029` 于 2026-11-02 这样退掉） |

- 不重写已推送的历史：`--force` / `--force-with-lease` / `commit --amend` 已推送的提交都是禁止动作。
- 打标签只用带注标签，且必须指向一次全量收据对应的提交。

## 提交前必跑（按改动面选，别一律全量）

| 改了什么 | 必跑 |
|---|---|
| 任何代码/文档 | `scripts/check_project_current.py --check`（顶层入口与寄存器现算相等） |
| 寄存器/生成器 | 对应 `scripts/build_*.py --check`（比较模式，只写不比对的那台除外） |
| 测试文件（增删改） | `scripts/build_test_census.py --check` —— **减少节点必须显式 `--allow`** |
| 迁移与台账 | `scripts/migrate_sources.py --plan`（`unmanaged` 必须为 0） |
| 后端行为 | 对应的 `tests/unified/` 里那一版 `test_v` 文件 + `scripts/boot_probe.py` |
| 交付级结论 | 全量 `tests/unified tests/legacy`，然后重取收据并改绑登记表 |

串行跑重量级套件：并发的全量运行会因为 CPU、端口与 IO 争用造出**假红**，
不能拿它判定任何东西。

## 提交信息

一次提交只做一件逻辑上的事，第一行说"为什么"，中文书写。
数字必须由生成器/寄存器现算——**不手抄**；手抄的数字会在下一轮悄悄变错，
这件事本轮已实测抓到过一次（`6687` 与并集 `6676` 的差）。

## 硬性禁止

- 删测试、放宽断言、用 `skip` 换绿；绕过 pre-push hook（`--no-verify`）。
- 把运行产物、数据库、日志、夹具提交进 Git：只准落 `.project-local/`（已被忽略）。
- 打印或提交凭证明文、真实客户素材、真实个人信息。
- 未授权执行：提交、推送、合并、发布、远程 CI、上传数据各需 owner 分别授权，一次授权不延伸。

## 行尾与字节保真（本仓特有）

`.gitattributes` 是 `* -text`：Git 不做行尾转换。仓里有一批**纯 CRLF 的跟踪文件**
（含 `backend/v1.py`、若干 `design-lab/schemas/*.json`）与更多 LF 文件，
这个混合状态是**迁移血统**，不是随手写出来的：`migration/copies.json` 按字节记过这些文件的摘要，
`tests/unified/test_v07_migration.py` 会复验。**因此禁止"顺手统一行尾"**——
那会让已认证的复制摘要与磁盘不符。

现算的这个数不写死在本文件里：它就是顶层入口的数字段键 `crlf_tracked_files`
（口径：排除 `docs/history/`、`docs/authority-202610/`、随包资源与 `vendor/`），
由 `scripts/check_project_current.py --check` 每次重算。新写的文件一律 LF；
**CRLF 文件数只许变少、不许变多**——变多说明有新文件写在了这条边界的错误一侧。
