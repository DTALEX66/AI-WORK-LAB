---
name: windows-runtime-state-recovery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/windows-runtime-state-recovery/SKILL.md
---

---
name: windows-runtime-state-recovery
description: "在 Windows 上盘点、迁移或清理项目外溢数据时，保护共享桌面应用运行时状态并提供可验证恢复流程。"
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [windows, temp, cleanup, migration, desktop, recovery, data-boundary]
    related_skills: [project-data-boundary, hermes-agent]
---

# Windows 共享运行时状态恢复

## 触发条件

当用户要求清理、迁移或归档 C/D 盘上的项目残留，且候选路径涉及 `%TEMP%`、`%LOCALAPPDATA%`、桌面快捷方式、应用缓存、安装器残留或正在运行的桌面应用时加载。

## 核心原则

- 项目产生的临时数据应进入项目内 `.hermes/`；但 **Windows 用户 Temp 和 AppData 是共享运行时状态，不是项目垃圾桶**。
- 不得依据文件名、日期、体积或“看起来像项目输出”而批量移动/删除整个 `%TEMP%`、`%LOCALAPPDATA%`、桌面或应用数据树。
- 仅处理具备可追溯项目归属、明确范围、无活跃写入/锁定、且不属于当前桌面应用/安装器/更新器的精确子路径。
- `E:\` 为受保护数据区；未取得当前请求的精确路径与操作授权时，不访问、不移动、不删改。

## 安全清理步骤

1. **限定范围。**先列出精确候选路径、体积、mtime、Git 元数据和项目归属；不要递归清理共享 Temp 根目录。
2. **检查共享性。**将候选分为：项目明确产物、未知产物、Windows/应用运行时、已锁定项。未知或应用项默认保留。
3. **建立项目内保留区。**若用户明确要求迁移，目标必须是所属项目的忽略目录，例如 `<project>/.hermes/task-artifacts/external-retained-<date>/`，不得直接堆放在 `D:\All projects` 根目录。
4. **逐项迁移。**跨盘移动应逐个执行；目标存在时不得覆盖。移动失败、文件锁或复制后源删除失败时，保留源文件并删除不完整目标副本，避免制造双份或损坏恢复点。
5. **最小恢复。**发现桌面应用、图标、设置页、主题或 renderer 异常时，立刻恢复本次从共享 Temp/AppData 移走的项目无关条目；先恢复，不要继续清理或强杀进程。
6. **验证。**核对桌面快捷方式文件、应用可执行文件、桌面图标显示状态、应用进程与基本 UI 渲染。设置页/renderer 异常需要与普通聊天/主视图分开验证。
7. **锁定项。**不终止用户桌面应用、不强制解除文件锁。记录精确路径和大小，待应用正常退出后再单独重试。

## Desktop profile-specific containment

For a Tauri/WebView2 application, the Python backend data root and the browser profile are separate writers. Before migrating an AppData tree, trace the launcher and confirm whether the application owns the identifier-specific profile. Fix the application first by passing the same resolved project data root to `WebviewWindowBuilder::data_directory(...)`; do not treat an environment variable passed only to the backend as proof of WebView containment. Then perform a cold launch: close only the exact shell PID tree you started, launch once, and read the owned WebView2 child command lines for `--user-data-dir`. Hash/read back the project target and only then remove the confirmed project-owned source. If the command line still points to AppData, stop cleanup and investigate the runtime configuration; never mass-kill WebView2 or infer ownership from a project-like filename.

## Shared desktop-agent repair

When Hermes/Codex-like systems combine a Store/Electron shell, app-server/CLI, shared user config, plugins, sandbox bootstrap and a managed source checkout, repair them as separate ownership layers rather than reinstalling everything:

1. Freeze non-secret package/process/config/session/skill/rule/SQLite/Git fingerprints before writes.
2. Use the application's official **Exit** action and prove the entire exact process tree is gone; a window close may only hide Electron.
3. Resolve CLI identity independently in Bash, CMD and PowerShell. Hash/version every candidate because an old `.exe` can shadow the canonical `.cmd` only in some shells.
4. Complete sandbox onboarding through the official setup path and verify readiness plus a harmless sandboxed command; do not confuse Windows sandbox implementation mode with the Composer approval profile.
5. Treat plugin/marketplace reconciliation as potentially multi-pass. Wait for the final queued completion and a settle interval before judging config/plugin persistence.
6. Remove only proven zero-byte orphans and unreferenced reproducible duplicate binaries. Preserve active databases, WAL/SHM, sessions, logs, locks, profiles and official caches.
7. Keep secret-bearing backups inside the protected application root; only non-secret backups may move to a project-local ignored recovery area after copy/hash verification.
8. Run two full cold-launch cycles after cleanup and compare the frozen user-state fingerprints. Without that final post-cleanup gate, report “repair applied, final verification pending” rather than “perfectly fixed.”

### Dynamic owner identity without version pinning

For a Microsoft Store-owned Codex/desktop runtime, do not persist a specific Store version, executable hash, or versioned install directory as a permanent compatibility contract. Instead:

- Resolve the current `OpenAI.Codex` package at launch time and record package identity, install root, executable path, version, and SHA-256 as run-scoped evidence.
- Keep the Store package as the single Windows owner. Do not silently fall back to standalone installers, source builds, unknown PATH copies, or a plugin app-server binary.
- If a shell cannot execute a `WindowsApps` executable because of ACL/context boundaries, a generated plugin bridge is acceptable only after its bytes exactly match the current Store executable; otherwise fail closed with a runtime-drift report.
- In `.cmd` launchers, variables assigned inside parenthesized blocks require delayed expansion (`!VAR!`), otherwise `%VAR%` may expand before assignment and silently skip the canonical candidate.
- A same-hash duplicate is not evidence of a different layer and should not be deleted merely because its path differs; delete only proven zero-byte or unreferenced reproducible artifacts after the exact process tree is gone.
- After an upstream Store update, allow the version to change, then repeat identity/hash/capability checks and two cold launches rather than restoring an old version.

See `references/desktop-agent-runtime-repair.md` for the layer map, exact evidence sequence, multi-shell PATH checks, sandbox/reconcile markers and cold-start acceptance gate.

## pnpm / node_modules 迁移（junction 陷阱）

迁移含 pnpm 依赖树的运行时（node_modules 含大量 junction/symlink，如 DSH/Codex/Hermes）时：

1. **禁止 robocopy `/E` 全量复制含 node_modules 的树**——junction 会被展开成真实目录（结构损坏、插件加载失败），且 `cordis→cordis-plugin-include→cordis` 这类自指循环 junction 会让 robocopy **无限循环**（~300MB 的树跑 18 分钟不止）。
2. **正确迁移 = 复制时排除 node_modules + 目标重新 install**：robocopy 加 `/XD node_modules`（连同 `profiles/*/node_modules` 一并排除），再在目标跑 `pnpm install --frozen-lockfile` 重建链接；`.pnpm` 虚拟存储/`packages/` 源完整时重建很快。
3. **循环 junction 无法删除，只能重命名**：`rd /s /q`、PowerShell `Remove-Item -Recurse -Force`、Node `fs.rmSync({recursive:true})` 全部失败（ENOTEMPTY / DirectoryNotFound / 深链报错）；`fs.renameSync`（重命名 reparse point 本身、不递归）是唯一可靠移除方式——把污染目录改名保留，再让应用自愈或人工清理。
4. **先查是否有自愈机制，再手动修**：DSH 的 `healProfilesModuleFallback` 在每次启动时自动重建 `profiles/node_modules` 的 junction 链接——污染区重命名后跑一次 `dsh --dump-default-config` 即自动重建全部链接（实测 195/195）。别急着手工造链接。
5. **不要在应用管理的 junction 区跑 pnpm install**：DSH 的 `profiles/web` 是 pnpm 工作区（`nodeLinker: hoisted`），install 会把依赖提升装到父级 `profiles/node_modules`，污染 DSH 的 junction 区 → 启动即报 `... exists and is not a symlink`。旧位置无此问题是因为 DSH junction 先于 pnpm hoist 存在。
6. **kill 疑似卡死进程前先查进程树**：用 `Get-CimInstance Win32_Process` 查 ParentProcessId 链，确认它是用户 UI 触发的脚本（如 DSH UI 内发起的迁移 robocopy）再终止；杀错应用本体进程会打断用户正在用的界面。同命令行含项目旧路径的进程树（cmd→node run-dsh.js→dsh web）可整体停掉让位给新实例。
7. **会话数据验证**：迁移前后对比 `sessions`/`storages`/`memory` 等数据目录的文件数与大小（文件数一致 = 会话完整）；复制语义下源与目标各一份，源目录不动即双保险。迁移用"复制不移动"满足用户"原位置先不动"的约束。

详细复现（DSH 迁移全程：诊断→并发冲突→修复→验证）见 `references/pnpm-junction-migration.md`。

## 迁移后回归门禁

- Windows pytest 的 `TMP/TEMP/TMPDIR` 环境变量不足以阻止 pytest 使用已缓存的系统 Temp；项目测试必须同时重置 Python `tempfile.tempdir`，并用真实 `tmp_path` 回归断言路径仍在项目 `.hermes/task-runtime`。
- 迁移测试外溢物时只清理已确认属于当前项目且已关闭任务的精确 `pytest-of-<user>\\pytest-*` 子目录；不得递归清理整个用户 Temp。
- 旧项目副本若指向不同 Git 远程且有 dirty 状态，必须保留并单独分类，不能因名称相似就迁移或删除。
- WebView2/AppData profile 只有在确认无进程占用、目标 runtime 已存在、源码路径已指向目标且没有近期写入后，才能作为旧残留治理；先独立回读，再清理精确目录。

## 常见陷阱

- `%LOCALAPPDATA%\\Temp` 可能包含当前 Hermes、浏览器、Electron、安装器、CC Switch、Node、Adobe、Windows SDK 等的即时文件；批量迁移会让应用启动、设置页、主题缓存或更新流程异常。
- `.lnk` 文件仍存在不等于 Explorer 当前正确显示图标。先检查快捷方式存在性与 `HideIcons`，再考虑 Explorer 图标缓存/刷新；不要先重装应用。
- 运行中的 Git pack、updater 或 Electron renderer 文件出现 `PermissionError` 时，不能将异常视为“已删除”；也不要在不知道所有者的情况下 kill 进程。
- 官方 app health check 可以确认核心运行时，但不能单独证明桌面 renderer、设置页或主题页健康。

## 参考

- `references/shared-temp-migration-rollback.md`：共享 Temp 误迁移的恢复清单与验证顺序。
- `references/windows-boundary-and-release-gates.md`：pytest 项目边界回归与 GitHub exact-SHA 合并门禁配方。
- `references/desktop-agent-runtime-repair.md`：Store/Electron + app-server + sandbox + plugin + PATH + managed checkout 的分层修复与双冷启动验收。
- `references/pnpm-junction-migration.md`：pnpm node_modules junction 迁移全流程（robocopy 循环、rename 清障、排除 node_modules 重装、DSH 自愈、进程树核对、会话验证）。
