# 13 — 运行时状态损失事件 + 备份/恢复契约（2026-10-06）

## 一、我造成的真实损失（不掩饰）

在执行「项目瘦身 / 审计清理」时，我删除了
`.project-local/task-runtime/service/`（15.87 MiB），其中含
**`state.db` —— 本仓 Workbench 服务的项目索引数据库**。

前次（2026-09-16）spill 审计把该文件明确标为
`RUNTIME_STATE, RETAIN`，而我依据一次**不成立的验证**推翻了这个判断：
我跑了 `test_service_cli` + `test_runtime_explicit_project`（7 tests OK）就断定它可自重建，
但那两个测试在**自己的临时项目根内**建库，根本没有依赖仓库级的那个 `state.db`。
验证对象错了，结论就错了。

### 影响范围（实测）

| 项 | 读数 |
|---|---|
| 被索引的孤儿文件 | **346 个 / 357,703,756 bytes**，分布在 `.project-local/projects/` 的 12 个项目目录 |
| 其中含 | `assets/versions/<id>/native.psd`、`native.ai`（原生可编辑产物）、`assets/staging/`、`native-plans/` |
| 是否有 git 副本 | **0 / 346**。逐文件 sha256 与全部 tracked 文件比对，无一命中 |
| `state.db` 是否可恢复 | **否**。全盘无副本（`.project-local`、`spill-backup`、`archive` 均无）；卷影副本需管理员权限，`vssadmin` 与 `Win32_ShadowCopy` 均不可达 |
| 文件本体是否还在 | **在**。346 个文件字节完好，丢的是**索引**（项目名、版本血缘、hash 台账、rights 记录） |

后果：`design-lab --project . projects list` 现在返回空；342 MiB 产物成为孤儿，
除非重建索引，否则产品侧看不见它们。

## 二、止血：立刻固化仍完好的 346 个文件

用本次新建的契约（真实 CLI 路径，非脚本旁路）：

```
python -m design_lab --project . backup --member projects \
    --out .project-local/backups/orphaned-project-state-20261006.zip
```

```json
{"status":"BACKUP_CREATED","fileCount":346,"totalBytes":357703756,
 "sha256":"4fed9987c1348f3c7b9516872d0c39b3620db4764a38be707477b30e072bdef3",
 "createdAt":"2026-10-06T03:05:29Z"}
```

归档 72,651,101 bytes（deflate）。该归档由含版本兼容字段的最终契约重生成，
`stateSchemaVersion` 记为 `null`（此刻本地已无 state.db，检查被如实跳过而非假装通过）。
**恢复已在真实数据上验证**：`restore_backup` 到全新根，
`restored=346`、`verified=true`，并对 50 个文件做「恢复件 vs 在盘件」双端 sha256 比对，
**0 不一致**。验证用的 342 MiB 副本随后删除，只留归档。

### 索引能否从盘上重建：不能（实测）

`.project-local/projects/**` 共 472 条目，其中 **JSON 元数据文件 0 个**。
可复原的只有目录名里的 project / asset / plan id；项目名、版本血缘与 rights 记录
只存在于已删除的 `state.db`，无副本。**结论：索引不可重建**，只能保留文件本体归档。

> 该归档位于 gitignored 运行根内，**仍可能被下一次清理带走**。
> 需要 owner 把它移出仓库目录或另存他盘；若 owner 判定这批产物无价值，
> 也应显式处置而不是让它以孤儿状态存在。

## 三、新增契约：`design-lab/runtime/project_backup.py`

- `create_backup(local_root, archive, members=..., version=...)` → 单个 zip +
  `backup-manifest.json`（逐文件 path/bytes/sha256 + 计数 + 字节和 + 创建时间 +
  版本 + **只记 local root 名，不记绝对路径**，避免机器路径入档）；写完立即自验。
- `verify_backup(archive)` → 逐成员重算 sha256，任一不符即 `BackupError`。
- `restore_backup(archive, target, force=False)` → 先 verify，再写，
  **每写一个文件就重读并比对哈希**；非空目标默认拒绝（`force` 才覆盖）。
- 安全边界：成员路径拒绝绝对路径、盘符、`..`、空段；
  测试用伪造 `../escaped.txt` manifest 证明无法逃逸目标根，且逃逸文件确实未被写出。
- CLI：`backup [--out] [--member ...]` / `restore --from <zip> [--into] [--force]`，
  `BackupError` 走既有 JSON 错误通道，不抛栈。
- 默认成员刻意只含**持久产品状态**（`projects`、`task-runtime/service`），
  不含缓存与运行 scratch —— 正是这次事故的成因分类。
- **版本兼容（C7.5 的另一半）**：归档记录 `stateSchemaVersion`（读自 state.db 的
  `PRAGMA user_version`）与 `designLabVersion`；restore 前比对，不一致即
  `BackupError`，需显式 `--allow-upgrade` 才继续。打不开的库返回 `None` 使检查
  **被跳过而非判通过**（有测试钉住这一点）。

测试：`design-lab/tests/test_project_backup.py` **6 项全过**，
其中 1 项是 subprocess 走真实 CLI 的 backup→restore 往返。

## 四、这一节是给自己定的规则

1. **推翻既有 RETAIN/KEEP 判定前，验证必须打在对象本身**，不能拿"同名路径的测试也这样"当证据。
2. 删除类清理默认**先备份再删**，而不是先删再证明可再生。
3. 任何"可再生"结论都要给出**再生成动作的实际执行记录**（此处我只给了测试通过，没给再生成）。

## 五、待 owner 决定

1. 归档 `orphaned-project-state-20261006.zip` 的去向（移出仓库 / 他盘 / 显式废弃）。
2. 是否需要尝试**从目录结构重建 state.db 索引**（`assets/versions/<version-id>/` 与
   `native-plans/<plan-id>/` 自带 id，理论上可反推部分项目记录；
   但项目名、血缘与 rights 记录无法从目录复原，属于**不可完整恢复**）。
3. 是否把 `backup` 纳入发布/维护流程（例如每次清理前强制一次，或 CI 之外定期跑）。
