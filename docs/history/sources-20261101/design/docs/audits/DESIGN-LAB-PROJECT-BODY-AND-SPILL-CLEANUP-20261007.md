# DESIGN-LAB 项目本体与外溢数据清理记录 · 2026-10-07

**观测 exact SHA**：本轮起点 `main` = `b7f82ac0`；书写时 `origin/main` = `f36ba6ec`（#242 已并入）
**观察窗口**：2026-10-06T22:04Z–22:24Z，全部为本机直测
**本轮唯一删除动作**：ComfyUI 工具根里的 8 个 nebula PNG（6,924,967 B），
逐字节证明与仓内 committed blob 相同后才删，仓内证据**一个未动**。

---

## 一、已执行：外溢清理（可恢复已先证明）

`AGENTS.md 执行规范`写明「设计产物留在本项目内，不外溢到其他项目/共享库」。
唯一被证实的真实外溢是 2026-08-28 一次 ComfyUI 生成把 8 张 PNG 留在了工具根的
`…/ComfyUI_windows_portable/ComfyUI/output/` 下。

流程（`scripts/clean_nebula_spill.py`，默认 DRY，需 `--apply`；清单同时提交在
`docs/audits/DESIGN-LAB-PROJECT-BODY-AND-SPILL-CLEANUP-20261007/evidence/nebula-comfyui-output.json`，
运行时写回的副本在 `.project-local/task-artifacts/spill-cleanup-20261007/`）：

1. 逐张 `sha256` 比对工具根文件与 `docs/projects/nebula-tech-culture-wall/assets/` 的同名件
   （名字规则差异按 `_00001_` 后缀对齐后**仍以内容哈希判定**，不按名字判定）；
2. 每张必须同时存在 `.license` sidecar，否则整批拒绝；
3. 清单先落盘：`.project-local/task-artifacts/spill-cleanup-20261007/nebula-comfyui-output.json`
   ——含 spill 绝对路径、size、sha256、`gitBlob`、`licenseSidecar` 与可直接粘贴的 `restore` 命令；
4. 删除前对每个目标**再哈希一次**（verify→delete 之间变过就中止），只删这 8 条确切路径，
   不删目录、不用通配。

结果：`verified identical pairs: 8/8`、`DELETED=8 remaining_nebula_in_tool_root=0`、
`mirror untouched: 16 files still present, hashes match manifest: True`。
复跑（已是清理后状态）不再拒绝，而是转成校验器：
`SPILL_CLEAN_VERIFIED=8 bytes_reclaimed=6,924,967 committed_copies_intact=True`。
恢复 = `git show main:docs/projects/nebula-tech-culture-wall/assets/<file>`，
因为幸存副本是 committed content，不是本机自产拷贝。

## 二、被推翻的三条既有前提（含我自己记忆里的两条）

| 前提 | 实测 | 结论 |
|---|---|---|
| 「182 MiB minigame-runtime 只由 archive-evidence 标签持有」 | `git rev-list --objects refs/heads/main \| grep " minigame-runtime"` = **182.19 MiB / 487 blob**；`--all --not refs/heads/main` 同路径 = **0.00 MiB** | **错**。这些字节就在 main 自己的历史里。删掉全部 12 个标签只释放约 2.64 MiB（还是别的东西），**对体积无收益却销毁证据** |
| 「`.hermes/` 为空」（`reports/…/12_SPILL_AND_SIZE_AUDIT.md`） | 目录存在且非空：`skill-call-index.json`(13,638 B, 08-24) + `task-artifacts/` + `task-runtime/`，共 20 KiB | **错**。且已写进仓内审计报告，属需解释后再处置的偏差 |
| 「tmp 有 2026-10-05 之前的陈旧文件」 | `-newermt 2026-10-05` = 289 个，`!-newermt` = **0** 个；`*.log > 1M` = **0** 个（最大 43,968 B） | **错**。没有陈旧可清 |

另记一次**我自己的测量缺陷**：第一次统计用
`git rev-list --objects --since=2026-10-06 main`，得到「78 MB 新字节 / docs 41 MB」。
这条命令列的是**近期提交可达的全部对象**（含祖先 blob），不是新写入的字节。
换成 `--objects refs/heads/main --not cdf9bddb`（2026-10-05 边界提交）后为
**815 个新 blob / 41,709,332 B**。数字差一倍，结论形状也不同。

## 三、体积实况（本轮唯一能动的杠杆是"别再重复提交同一批二进制"）

```
git ls-tree -r -l main      → 2970 tracked files / 51,925,654 B  (working_tree_budget_mib=64)
  docs     25,701,384   fixtures 8,452,041   design-lab 6,219,807
  research  4,409,819   reports  3,179,306   src        911,150
gh api repos/DTALEX66/DESIGN-LAB → git_size_kib=242088 = 236.4 MiB
verify_asset_governance.py → ASSET_GOVERNANCE=OK
  pack_mib=237.7 hard_budget_mib=256 warn_mib=220  → WARN（已越 220 警告线，距 256 硬线 18.3 MiB）
  LARGE_ASSETS declared_bundles=5 large_mib=11.89 quarantine_bytes=0.6MiB
```

2026-10-05 边界以来的新 blob 面积分布（raw bytes）：

```
docs/UI-CONVERGENCE-20260930  24,595,306   ← 81 个截图路径的**新版本堆积**，当前树里该目录只有 5,190,459 B
apps                           5,361,294   ← 含 apps/workbench/build/main.js 2,460,711（committed artifact，每次 UI 改动一份）
research/candidates            4,418,058
reports/current                4,190,717   ← TASK_PROGRESS.json 单路径 3,079,153，每次合并重生成一份
design-lab/config              1,540,899
```

要点：**工作树只用了预算的 81%，pack 已越过警告线**。差额不是垃圾，而是同一批
路径的版本堆积——截图（2560px 单张 1.8 MB）、`build/main.js`、以及九条兄弟 PR 串行合并
时每轮重生成的 `reports/current/**`。今天一天 pack 从 223.82 → 237.7 MiB。
因此：
- **历史重写（filter-repo + force push）不在选项内**（销毁证据、破坏所有人 clone、本轮不发布）；
- **删标签无收益**（见第二节）；
- 唯一还能动的杠杆是**减少重复提交的二进制与投影版本数**：截图按 1280/1920 提交、
  原图留在 `.project-local/task-artifacts`（已声明的证据根，gitignored），
  只把文档真正链接的那几张进 Git；`reports/current` 的重生成只在真正改动了
  tracked input 时提交。以上属政策改动，**未在本轮擅自执行**。

## 四、本机体积（不动 pack，只占盘）

```
.project-local/task-runtime/fresh-clone  305,803 KiB  ← verify_fresh_clone.py 每轮自建，可重建
.project-local/projects/d2981992a4fa…    289,210 KiB  ← 未做账本核对，禁止当作垃圾
.project-local/projects/828ccec779ac…     50,308 KiB
.project-local/task-artifacts/zero-spill 104,648 KiB  ← 门快照配对，声明保留
```
本轮**未删除任何一项**：`fresh-clone` 虽可由脚本重建，但删除只省本机磁盘、不改 pack、
且 `classify_repo.py` 尚未对它出结论；`projects/d298…` 在未核对账本前按"可能是用户作品"处置。

## 五、DO-NOT-TOUCH（有主或有账的）

- `.project-local/tmp/**` —— 已被 `.project-local/PRESERVATION-MANIFEST.json`
  （schema `design-lab/evidence-preservation/v1`）逐条带 sha256 登记 53 个文件 / 2,752,936 B，
  含 `tmp/overflow-*.json`、`gate-{red,green,final}.json`、`workbench-shots/*.png` + `.license`，
  且该清单记录的是一次从 WorkBuddy worktree 迁入本仓 `.project-local` 的 copy（`mismatched: 0`）。
  它是声明的证据副本根，不是 scratch；
- `.project-local/task-artifacts/zero-spill`、`authority-gates/latest.json`、`test-run/` ——
  门绑定工件，再删只会加深断链；
- 27 条 `qoder/designlab-*-20261007` + 7 条 `tmp-rebase-*` 分支、12 个证据标签 ——
  同日在飞的 PR 序列与证据保留点；
- `Design Projects/`、`UI套件/`、`Record/` 里按名字命中的 `design-lab-*` ——
  **名字巧合**：仓内 12_SPILL_AND_SIZE_AUDIT 记录近三天 DESIGN-LAB 写入这三处为 0，
  且两处无 `.git` 无法证明归属，按他人作品处置，不碰；
- `E:` 盘 —— 受保护，本轮未访问（`checked_cache_root` 本身就拒绝 E 盘作为探测根）。

## 六、留给 owner 的处置项（按收益排序，均含前置证明）

1. **截图/投影提交政策**（第三节）：唯一能阻止 pack 继续逼近 256 硬线的动作，需政策裁决；
2. `projects/d2981992a4fa…` 289 MB：先 `scripts/classify_repo.py` 出分类，再决定处置；
3. `fresh-clone` 305 MB：确认可弃后删除（仅本机磁盘，脚本会自建）；
4. **4 条无据可查的 LOCK_REFERENCE**（`anydesign`/`motion-engine`/`shipit-ui`/
   `web-content-designer`）——见 PR #252，路径为何消失需裁决，本轮只列出不改写；
5. `ai-product-os-frontend`：`ABSORB_MINIMAL` 且字节在仓内但**无 revision**，
   属 AUTHORITY §9 缺口，需上游查证或人工门裁决；
6. `.hermes/` 与 12_SPILL_AND_SIZE_AUDIT 的矛盾：先解释，再谈清理。

本轮不做：历史重写、force push、删证据、删标签换体积、发布。
