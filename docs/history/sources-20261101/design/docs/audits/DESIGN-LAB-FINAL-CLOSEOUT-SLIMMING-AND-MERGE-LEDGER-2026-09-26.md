# DESIGN-LAB — FINAL CLOSE-OUT · SLIMMING · BRANCH MERGE LEDGER — 2026-09-26

> 本账本是 09-26「全收口指令」(全部上传 / 总结摘要 / 错误记录 / 分支审计合并 / 瘦身清理) 的
> 终端记录，落仓后成为可回读证据。前序 `FULL-SWEEP-CLOSE-OUT-LEDGER-2026-09-26`(#166) 记录
> 非操作结构层 3 gap 收口；本账本记录其后**分支合并收口 + 瘦身 + stash 清理 + 全量错误记录**。
> 层级：本账本 = 事实证据/投影层，不高于 AUTHORITY.md(#R2)，只作 read-back receipt。

## §A 执行指令与边界
- 用户指令：「全部上传，总结摘要，错误记录，分支审计合并，瘦身清理（全部授权，严格审计后
  自行清理迁移合并）」。
- 边界：全部 zero-tracked 的 `.project-local` 运行数据可清（manifest 落仓可回溯）；分支合并、
  stash 备份+drop、投影 rebind、本账本上传 = 结构层，agent 自主闭环；E3/E4/G-9/G-10/core/
  H003 lane 晋升 = 实操面 owner-gated，**不执行**（本指令未解锁，保留文档）。

## §B 分支审计与合并（决定性 9/9 required 核读后执行）
| PR | 内容 | head | required 门 | 结果 |
|---|---|---|---|---|
| #165 | Lane C workbench 模块化拆分（保 build-truth 四道门） | `aba634e`（update-branch 并入 main `b7fa8f9` 后） | 9/9 SUCCESS（H001 advisory by-design FAILURE，非 required） | **squash 合入 main → `d8edddc`**，`feat/workbench-module-split-c` 远端分支已删 |

- `gh pr merge 165 --squash --delete-branch` rc=0；readback `state=MERGED`, `mergedAt=2026-09-26T14:24:01Z`,
  mergeCommit `d8edddc38d…`, by DTALEX66。
- 本地 main + origin/main 同步至 `d8edddc`；远端分支现仅剩 `origin/main`（open PR = 0）。
- **合并前的 exact-SHA 纪律**：`verify-merge-165.py` 原始 `gh pr checks --json name,state,event`
  确认 head `aba634e` 上 `event=pull_request` 的 9 道 required gate 全 SUCCESS；`mergeStateStatus=UNSTABLE`
  仅由 H001 advisory（main-only、PR-run 上按设计 fail）造成，与 #166 合并时情形一致，by-design，非 blocker。

## §C 瘦身清理（`.project-local` 1418.8 MB → 533.7 MB，释放 ~885 MB）
全部 zero-tracked（git ls-files 0 文件），manifest 落仓 `prune-manifest-2026-09-26.json` 可回溯：
- **task-artifacts ≥2d 陈旧会话层**：67 子目录 / 631.9 MB（`ocr-qualification` 281M、
  `real-poster-ps` 103M 等 09-22~09-25 旧会话证据，tracked 文件已背书）→ 清；`<2d` 会话数据(1.2MB) → 保留。
- **archive/hermes-legacy/runtime/dl-ad-pkg-ci**：253.3 MB（09-22 旧会话 CI 构建产物，
  重跑 CI 即复现，纯可再生）→ 清。
- **空占位目录** `worktrees`（零文件子树）→ 清。
- **保留**：`projects/`(09-25 账本判为权威 state)、`cache/vendor`(35M 技能缓存，清了要重下)、
  `runs/`(顶层账本 JSON)、`task-artifacts/<2d 会话数据>`。

## §D stash 清理（字节级验证 main 超集/identical 后，先备份成远端 tag 再 drop）
- 严格审计发现 2 个旧 stash 均为 #148/#149/#150/#156 squash 合并后的本地工作树残留：
  - `stash@{0}` `verify_design_lab.py`：main 侧 +15 行超集（#151 union-resolve 后的聚合器已 PASS）
  - `stash@{1}` `canonical-verify.yml`(main +60 行超集) + `sbom.json`/`sbom-verifier.mjs`(identical)
- **drop 不丢 main 没有的内容**。备份为远端 tag（可回滚）：
  - `stash-backup/2026-09-26/i0` (obj `ce24edad`) + `stash-backup/2026-09-26/sbom` (obj `b6aab3b0`)
  - 记录 `.project-local/stash-backup-2026-09-26.json`。
- 现 `git stash list` = 空。

## §E 工具层错误记录（全部已即时纠正，作为 09-26 全收口错误档案）
| # | 错误 | 纠正 |
|---|---|---|
| 1 | `git stash create` 备份的是**干净工作树**（非已有 stash） | 改 `git rev-parse "stash@{i}"` 拿真实 stash 对象再 tag |
| 2 | drop `stash@{0}` 后**索引位移**，循环再取 `stash@{1}` 不存在 | 改按 label/当前索引动态解析，逐 drop |
| 3 | `os.rmdir` 撞含空子目录的 `worktrees` 中断（WinError 145） | 改 `shutil.rmtree` 且先确认子树零文件 |
| 4 | 多次 `/dev/null`、外层 `&&` 链、缺 workdir、项目外绝对 POSIX 路径 → wrapper 零容忍 block | 一律脚本文件(`write_file`) + 单命令 + `workdir` 参数 + 无 `/dev/null`/无外层链 |
| 5 | 长内联 python 触发 "shell chaining/redirection forbidden" + 内核截断 | 逻辑全部落盘为脚本再 `python 脚本.py` |
| 6 | `gh` 本版本 `--json` 无 `conclusion`/`commit` 字段；`completedAt` 在 `run` 子对象 | 改用 `state`+`event`；`event=pull_request` 区分 PR head run 与 main `push` 历史 |
| 7 | 轮询器曾把 H001 FAILURE 计入 required 门 → 假 FAIL 早退 | 改为**精确匹配 9 道 required gate 名**，显式排除 H001 advisory；合并前再原始核读 |
| 8 | `process_manage kill` 报 "session_id is required" | 传 `session_id=proc_…`（非 process_id） |

## §F 最终状态（本账本上传后）
- open PR = 0；远端分支仅 `main`；main = `d8edddc`（#165 合入）。
- 非操作结构层（J/I/K/O-lane + #165 分支合并 + 瘦身 + stash）**全部闭环**。
- 保留 tag：`archive-evidence/*`(5) + `superseded-tip/*`(4) + `stash-backup/*`(2) = 回滚点。
- 剩余 owner-gated 实操面（未在本指令解锁，仅文档）：E3 真宿主 readback、E4 人工 Jury、
  G-7 download-leg 415→H003 lane 晋升、G-9/G-10 真宿主执行、`design-lab/core/` 迁移、
  L-lane P2 扩展。
