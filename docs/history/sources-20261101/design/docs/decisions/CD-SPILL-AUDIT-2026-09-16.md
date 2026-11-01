# CD-SPILL-AUDIT-2026-09-16 — C/D 双盘 DESIGN-LAB 外溢严格审计

日期：2026-09-16。授权：用户当前请求「追踪数据外溢，有用的迁移回本项目内，没用的删除掉；
C 盘 D 盘都要追踪；严格审计，确保属于本项目才执行删除」。E 盘未触碰。

## 判定原则（本轮执行口径）

- 删除前要求 **两个独立归属信号**（内容溯源 + 生成命令/git/任务引用），冲突即保留；
- 有用项先 **SHA-256 校验迁移** 进 `.project-local/`，原件保留（不删 Hermes 全局态）；
- 全局工作流状态（Hermes home 附件、session 库等）不迁移进项目、不删除；
- 非本项目外溢（其他项目/他人仓库）只报告，不删。

## 逐对象定性

| 对象 | 体积 | 归属证据 | 判定 |
|---|---|---|---|
| `D:\All` + `All-shm` + `All-wal` + `All.writer.lock` | ~136 KB | 库表集（13 表：knowledge/learning_events/jobs/job_outputs/workspace_meta…）与 **ArcheAxis-Knowledge-OS 的 `v3-thirteen-tables` fixture 精确吻合**；与 DESIGN-LAB state 表（asset/artifact/asset_writer_lock）**零重叠**；DESIGN-LAB 代码无外部 `<db>.writer.lock` 惯例 | **保留（非本项目）** |
| `D:\All projects\.project-local`（父级孤儿骨架） | 0 文件 | 项目数据 wrapper 在父级 cwd 误触发的 `.project-local/task-runtime` 空树；审计时实测 0 文件、0 junction、0 reparse | 审计时已消失（外部回收，0 数据丢失；删除断言先行中止，未执行 rmtree） |
| `D:\tmp\oh\` + blog.txt + mm-*.html | 1.19 MiB | git remote = `KunalSin9h/openai-harness`（他人浅克隆）；mm html = MiniMax 站点内容 | **保留（非本项目）** |
| C 盘全盘（盘根/用户根/桌面/文档/下载/AppData 二级/TEMP） | — | 0 个 DESIGN-LAB 命名产物 | **干净** |
| `C:\Windows\TEMP` | — | 系统 ACL 受限 | 不触碰 |
| Hermes 全局附件 5 个 DESIGN-LAB taskpack | ~118 KB | 内容溯源 = 本项目任务包；所在目录为全局工作流状态 | **copy 迁入项目，原件保留** |

## 有用项迁移（copy + SHA-256 回读，5/5 通过）

落位 `.project-local/task-artifacts/external-recovery-20260916-hermes-taskpacks/`：

| 文件 | 与库内 `docs/taskpacks/` 的关系 |
|---|---|
| `DESIGN-LAB-DIRECTORY-MIGRATION-CLEANUP-TASKPACK-2026-09-01.md`（17504 B） | 库内缺；-2/-3 为同内容冗余副本（sha256 一致，且 -2/-3 已在库为不同文件） |
| `DESIGN-LAB-DIRECTORY-MIGRATION-CLEANUP-TASKPACK-2026-09-01-2.md` | 与库内同名文件 **内容不同**（库内为另一修订；原件保留在 .project-local 恢复区） |
| `DESIGN-LAB-DIRECTORY-MIGRATION-CLEANUP-TASKPACK-2026-09-01-3.md` | 同上（内容不同） |
| `DESIGN-LAB-FINAL-TASKPACK-2026-08-25.md`（30290 B，`DLR-FINAL-20260826-R2-OSS-FAST-TRACK`） | 库内缺，历史任务包 |
| `DESIGN-LAB-FINAL-TASKPACK-2026-08-25-2.md`（26916 B，`DLR-FINAL-20260825-R1`） | 库内缺，前序历史任务包 |

## 删除结果

**本轮删除集为空**：唯一「属于本项目且无用」的候选（父级空骨架）在删除校验时已自行消失
（0 文件，零数据丢失）；其余候选全部因归属非本项目或属全局工作流状态而保留。
符合「确保属于本项目才执行删除」的铁律。

## 双端复核（DESIGN-LAB）

- HEAD = `9cc8f2aaaa8232ceabb14f1d1d2031bcce7bee86`
  （= origin/codex/deepseek-authority-r1，behind=0，工作区 0 漂移）
- `DESIGN-LAB/.project-local` 真实根完好（41112 文件 / ~3.4 GB，上轮瘦身后状态）

## 遗留（需另行授权）

1. `D:\All*`（~136 KB，ArcheAxis 13 表型）→ 归口 ArcheAxis 项目处理；
2. `D:\tmp\oh`（他人浅克隆）→ 是否清理由用户定；
3. Hermes 全局附件原件 → 默认保留（全局态），是否删除需明确授权「删除全局态」。
