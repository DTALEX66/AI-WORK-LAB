# Codex Desktop Windows 更新后状态调查摘要（2026-08-13）

> 状态：当前调查权威摘要 + 另一台电脑只读采样清单<br>
> 范围：登录、外观、项目索引、线程权限、`config.toml`、Windows MSIX/AppX、Codex CLI 与 CC Switch 路由<br>
> 历史来源：`taskpacks/history/CODEX-DESKTOP-STORE-UPDATE-BEHAVIOR-20260812.md` 仅作为 2026-08-12 的历史假设，不再作为当前事实依据。

## 一页结论

1. **不能把“重新登录、外观、项目列表、sandbox、`config.toml`”合并成一次整体重置。**它们至少分属认证缓存、Desktop UI/global state、项目索引、线程权限和用户配置等不同层。
2. **当前本机只确认发生过重新登录。**用户未观察到外观重置，也未观察到 sandbox 或 Codex 配置重置；受管字段和 14 个仓库托管 Codex Skills 的 overlay 验证通过。
3. **没有证据证明本机与历史 #72 是同一故障。**#72 归档缺少更新前后 diff、原始 AppX 事件、截图和完整机器采样；其中“Windows 只有 Store 渠道”“更新后重登属于固有特性”“#37927 是官方确认 bug”等表述已不再成立。
4. **普通 MSIX 包更新与应用启动后的状态写入必须分开归因。**Windows 包更新替换应用包，不等于 Codex Desktop 不会在随后启动时迁移、写回或重新序列化自己的用户状态。
5. **当前本机不需要修复。**不要为复现另一台电脑而执行 Reset、卸载重装、删除 `.codex`、删除认证文件、恢复未知 `.bak` 或整文件覆盖配置。
6. **若另一台电脑存在故障，先只读采样，再按层修复。**最低风险顺序是：版本/入口对齐 → 完整退出再启动 → overlay `plan/verify` → 仅受管字段漂移时 `apply` → 应用本体异常时考虑 Windows Repair → 有损 Reset/卸载仅作最后手段。

## 证据等级

| 等级 | 含义 | 本报告用法 |
|---|---|---|
| A | OpenAI / Microsoft 当前官方文档或本机命令直接回读 | 可作为事实陈述 |
| B | `openai/codex` 官方仓库中的公开 issue，但没有维护者确认 | 只能证明存在用户报告 |
| C | 用户直接观察或历史 PR/归档陈述 | 标明机器和时间，不外推根因 |
| D | 根据时间接近、文件名或键名作出的推断 | 不作为结论；需要额外证据 |

公开 issue 位于 OpenAI 官方仓库，不等于 OpenAI 维护者确认。2026-08-13 复核的 #37927、#27178、#37768、#26421、#38193、#35673、#36490、#30736、#24036 和 #36497 均为开放的用户报告；当时没有 assignee、milestone 或维护者评论。

## 两台电脑必须分栏

| 检查面 | #72（暂按另一台电脑） | 当前本机（2026-08-13） |
|---|---|---|
| 身份 | 待晚间现场确认 | 当前对话所在本机 |
| Desktop 包 | 历史归档未保留可审计完整采样 | `OpenAI.Codex 26.803.10989.0`，状态 `Ok` |
| Desktop 进程 | 待采样实际 `ExecutablePath` | `ChatGPT.exe` 从对应 WindowsApps 包启动；包内 `resources/codex.exe` 也在运行 |
| PATH CLI | 待采样 `where codex` 和版本 | `codex-cli 0.147.0-alpha.6.6` |
| 登录 | 历史归档称频繁重登，待现场确认时间和错误 | 用户确认本次被要求重新登录 |
| 外观 | 历史归档称重置，但无截图/明确偏好键 | 用户未观察到外观重置 |
| 项目索引 | 历史归档借用 #37927 推断，缺少本机前后证据 | 本轮未证明项目索引丢失 |
| sandbox / approval | 历史归档称重置，缺少字段级 diff | `approval_policy=on-request`；`sandbox_mode=workspace-write`；Windows sandbox 为 `elevated` |
| 项目文档上限 | 未知 | `project_doc_max_bytes=65536` |
| workspace 网络 | 未知 | `sandbox_workspace_write.network_access=false`；属于保留字段，不由 overlay 覆盖 |
| 模型/路由 | 未知 | Codex 配置模型为 `gpt-5.5`；API origin 为本地 `127.0.0.1:15721`；监听进程为 `cc-switch` |
| Overlay | 未知 | 调查开始时 `plan` 零写集、`verify` PASS；实际 14 个仓库托管 Codex Skills。提交摘要不把未来 live 漂移预测当作事实；任何新机器或画像变更都必须先重新执行 `plan/verify`，未经单独 live-apply 授权不自动部署 |
| 精确根因 | 未证实 | 未证实；现有证据只支持“认证层发生过重登，配置层仍正常” |

> 当前聊天运行时是 `gpt-5.6-luna / openai-codex`；Codex Desktop/CLI 用户配置模型是 `gpt-5.5`。二者是不同执行面，不能混写；本报告不把 Hermes live 默认配置作为另一台电脑的事实。

## 官方文档能证明什么

### Windows 安装和更新

OpenAI 当前文档说明 Windows 应用是 Store-signed，但用户不必打开 Microsoft Store：可以使用 Web Installer、`winget`、Intune/MDM，或下载 x64/Arm64 Store-signed MSIX。因此“Windows 只有 Store UI 一个安装渠道、无直接 MSIX”是过时结论。

- [OpenAI：Deploy the Windows app](https://learn.chatgpt.com/docs/enterprise/windows-deployment)
- [OpenAI：Manage app updates](https://learn.chatgpt.com/docs/enterprise/manage-app-updates)

企业管理员可以关闭应用内 updater，再通过设备管理平台分阶段部署；该策略不阻止 Microsoft Store、Intune、MDM 或其他外部分发工具更新。个人环境不能据此假定已经关闭全部更新源。

### 认证

OpenAI 说明 Desktop、CLI 和 IDE extension 会缓存登录；ChatGPT 登录的 token 在使用中会自动刷新，活跃会话通常不需要再次浏览器登录。因此“每次更新后重登是固有正常行为”没有官方依据。一次重登也不能单独证明包更新、token 过期、代理、组织策略或客户端 bug 中的哪一个是根因。

- [OpenAI：Codex authentication](https://developers.openai.com/codex/auth)

`cli_auth_credentials_store` 只说明 CLI 可以选择凭据存储方式，不能据此断言 Desktop 登录缓存由同一键控制。认证文件只允许检查存在性、大小和修改时间；正文应视为密码，禁止读取、提交、复制或贴入 issue。

### 用户配置

OpenAI 定义用户配置位置和 `approval_policy`、`sandbox_mode` 等字段，但没有承诺 Desktop 永远不会写回 `config.toml`。公开 issue #27178、#37768 和 #26421 说明有人报告过重启写回、截断或异常关机损坏；这些是 B 级用户报告，不是统一根因或官方修复声明。

- [OpenAI：Codex basic configuration](https://developers.openai.com/codex/config-basic)
- [OpenAI：Codex configuration reference](https://developers.openai.com/codex/config-reference)
- [#27178](https://github.com/openai/codex/issues/27178)
- [#37768](https://github.com/openai/codex/issues/37768)

### Repair 与 Reset

Windows Repair 与 Reset 不是同一操作：Repair 是较低风险的应用修复候选；`Reset-AppxPackage` 会把应用恢复到初始配置，使它像新安装一样运行。Reset、卸载和删除状态都可能扩大数据损失，不能作为首步诊断。

- [Microsoft：Reset-AppxPackage](https://learn.microsoft.com/en-us/powershell/module/appx/reset-appxpackage?view=windowsserver2025-ps)

## 分层判断与恢复

| 层 | 常见可见现象 | 首选证据 | 最低风险动作 | 不应直接做 |
|---|---|---|---|---|
| 认证缓存 | 要求登录、token refresh 错误 | 准确错误、发生时间、CLI 与 Desktop 是否同时失败、状态页/代理 | 正常 UI 登录；临时隔离代理做 A/B | 删除或读取 `auth.json`、全盘清认证 |
| Desktop UI / global state | 主题、布局、引导状态变化 | 更新前后截图、明确偏好键、文件元数据 | UI 重新设置；完整退出再启动 | 仅凭 `onboarding-*` 键判定重置 |
| 项目索引 | 侧栏项目消失但线程可能仍在 | UI 搜索/Recent、更新前后索引证据 | 先确认线程仍存在，再重新打开/pin | 修改 SQLite、盲目恢复同步 `.bak` |
| 线程权限 | 重开线程后 Full access/Auto-review 回落 | UI 状态 + 一次低风险行为测试 | 每次重开后重新确认 | 用全局 config 推断当前线程权限 |
| 用户 config | 受管字段缺失或值变化 | TOML 字段级解析、overlay `plan/verify` | 完全退出 Desktop；仅漂移时 `apply`；再 `verify` | 删除 `.codex`、整文件覆盖、覆盖 OBSERVE 字段 |
| AppX 包 | 无法启动、包状态异常 | 包版本、Status、进程实际路径、事件日志 | 完整退出/重启；必要时 Windows Repair | 首步 Reset 或卸载重装 |
| provider / CC Switch | 请求、模型、服务端行为异常 | endpoint origin、监听进程、临时直连 A/B | 保留现有路由；用临时进程/隔离配置比较 | 为诊断永久改写 provider/base URL |

## Overlay 所有权边界

权威合同：`config/config-ownership.json` 与 `config/codex-enhancement-boundary.json`。

Overlay 只管理：

- `approval_policy`
- `sandbox_mode`
- `project_doc_max_bytes`
- 一个带标记的用户 `AGENTS.md` block
- 一个规则文件
- 14 个明确命名、仓库托管的 `workflow-assistance-*` Codex Skills

以下均保持 OBSERVE / PRESERVE 或 FORBIDDEN：模型、provider、base URL、reasoning、workspace 网络、MCP、plugin、认证、会话、memory、Desktop 私有状态以及未知字段。

恢复受管字段时，从模块目录执行：

```bash
python integrations/executors/codex/sync_codex_global_assets.py plan \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"

python integrations/executors/codex/sync_codex_global_assets.py verify \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"
```

只有 `plan` 明确显示本模块自己的受管字段或 Skills 漂移，且用户批准后，才执行：

```bash
python integrations/executors/codex/sync_codex_global_assets.py apply \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"

python integrations/executors/codex/sync_codex_global_assets.py verify \
  --codex-home "$HOME/.codex" --agent-home "$HOME/.agents"
```

`apply` 不应被当作登录、主题、项目索引或线程权限的修复器。

## 晚上在另一台电脑上的只读采样清单

### 0. 先记录可见状态

不要先修改配置。记录：

- 是否要求重新登录；错误类别/错误码（脱敏）和发生时间；不要复制完整错误正文；
- 主题/外观是否变化；
- 项目侧栏和历史线程是否可见；
- 当前线程显示的权限模式；
- 更新前是否有截图或版本记录；
- 是否使用 CC Switch、官方直连或其他代理，只记录非敏感 endpoint 类型。

### 1. AppX 包和真实进程

在 PowerShell 7 中运行：

```powershell
Get-AppxPackage -Name OpenAI.Codex |
  Select-Object Name, Version, PackageFullName, InstallLocation, Status

Get-CimInstance Win32_Process |
  Where-Object { $_.Name -in @('ChatGPT.exe', 'codex.exe') } |
  Select-Object Name, ProcessId, ExecutablePath
```

### 2. CLI 和入口

```powershell
# 不扫描 PATH，也不执行未知候选。只检查两个已知 Windows 用户入口。
$cliCandidates = @(
  "$env:LOCALAPPDATA\Microsoft\WindowsApps\codex.cmd",
  "$env:LOCALAPPDATA\OpenAI\Codex\bin\codex.exe"
)
$safeCli = $cliCandidates |
  Where-Object { Test-Path -LiteralPath $_ -PathType Leaf -and $_ -notlike 'E:\*' } |
  Select-Object -First 1
if ($null -ne $safeCli) {
  & $safeCli --version 2>&1 | Select-Object -First 1
} else {
  'CLI_VERSION_SKIPPED=NO_SAFE_NON_E_DRIVE_CANDIDATE'
}

Get-ChildItem "$env:USERPROFILE\Desktop" -Filter '*Codex*.lnk' -ErrorAction SilentlyContinue |
  Select-Object FullName
```

如果有快捷方式，只记录目标路径，不启动未知或过时的硬编码版本目录。

### 3. 认证只查元数据

```powershell
Get-Item "$env:USERPROFILE\.codex\auth.json" -ErrorAction SilentlyContinue |
  Select-Object Exists, Length, LastWriteTime
```

禁止使用 `Get-Content`、编辑器或脚本读取正文。

### 4. 配置和 overlay

从实际拉取的 WORK-LAB 仓库根定位模块后进入（不要假设盘符或目录）：

```powershell
$repo = Get-Location
while ($repo.Path -and -not (Test-Path (Join-Path $repo.Path '.git'))) {
  $repo = $repo.Parent
}
if (-not $repo.Path) { throw 'WORK-LAB Git root not found; stop without running overlay commands.' }
Set-Location (Join-Path $repo.Path '10-workflow\workflow-assistance')

python integrations/executors/codex/sync_codex_global_assets.py plan `
  --codex-home "$env:USERPROFILE\.codex" `
  --agent-home "$env:USERPROFILE\.agents"

python integrations/executors/codex/sync_codex_global_assets.py verify `
  --codex-home "$env:USERPROFILE\.codex" `
  --agent-home "$env:USERPROFILE\.agents"
```

先只运行 `plan` 和 `verify`，不要运行 `apply`。报告只需要：

- `write_set_count`
- `preserved_user_config_fields`
- `status`
- `issues`
- managed skill count

不要粘贴完整 `config.toml`。模型/provider/base URL 只记录脱敏后的字段名和 origin，不记录凭据、query、header 或 token。

### 5. 状态文件只查元数据

```powershell
Get-Item "$env:USERPROFILE\.codex\.codex-global-state.json", `
         "$env:USERPROFILE\.codex\.codex-global-state.json.bak" `
         -ErrorAction SilentlyContinue |
  Select-Object Name, Length, LastWriteTime
```

不要读取会话、项目列表或 private state 正文；不要仅凭 `onboarding-*` 键声称主题被重置。

### 6. 更新证据

```powershell
# Message 仅用于本地匹配，不打印、不保存、不复制其正文。
$events = Get-WinEvent -FilterHashtable @{
  LogName='Microsoft-Windows-AppXDeploymentServer/Operational'
  StartTime=(Get-Date).AddDays(-7)
} -ErrorAction SilentlyContinue |
  Where-Object { $_.Message -match 'OpenAI\.Codex' } |
  Select-Object TimeCreated, Id, LevelDisplayName
$events | ForEach-Object {
  [pscustomobject]@{
    TimeCreated = $_.TimeCreated
    Id = $_.Id
    Level = $_.LevelDisplayName
    MessageSummary = 'MATCH_OPENAI_CODEX'
  }
}
```

空结果只表示该日志中没有命中，不能证明没有发生 Store 或应用内更新。

### 7. 比较后再决定

两机至少比较：

1. 包版本；
2. 实际进程路径；
3. PATH CLI 候选和版本；
4. 登录现象和准确时间；
5. 外观/项目索引/线程权限；
6. 三个 MANAGE 字段；
7. overlay `plan/verify`；
8. CC Switch/代理类型；
9. AppX 事件或其他更新证据。

只有这些层相同且症状、时间线也一致，才可以把两台机器归入同一问题。

## 晚间结果填写模板

```text
机器：另一台电脑
采样时间：
Desktop Version / Status：
Desktop 实际进程路径：
安全 CLI 候选（未扫描 PATH）：
CLI 版本（仅安全候选；无候选则 SKIPPED）：
是否重登 + 错误/时间：
外观是否变化：
项目索引是否变化：
线程权限显示：
overlay plan write_set_count：
overlay verify status/issues：
managed skill count：
代理/CC Switch 类型（无凭据）：
AppX 更新证据：
与当前本机相同层：
与当前本机不同层：
结论：同一故障 / 不同故障 / 证据不足
```

## 经验总结

1. **先分存储层，再谈根因。**文件时间接近、更新后首次启动和一次重登都只构成线索。
2. **机器必须分栏。**当前机器的成功回读不能证明另一台机器正常；#72 的历史陈述也不能替代另一台机器今晚的现场采样。
3. **官方仓库 issue 不是官方确认。**必须检查作者关联、维护者评论、assignee、milestone、修复 PR 和 release note。
4. **handoff 是 claim，不是 truth。**先读当前 live 状态和权威合同，再修正文档；OBSERVE 字段与文档不同不等于配置 drift。
5. **备份与主文件相同不等于可恢复。**应用可能已把坏状态同步到 `.bak`；恢复前必须证明它是故障前、版本匹配的独立副本。
6. **Repair 与 Reset 分开。**Repair 是较低风险候选；Reset/卸载/删除状态是有损动作，必须单独说明损失并获授权。
7. **更新渠道和状态写入分开。**Web Installer、winget、MSIX、Store/MDM 可能进入同一 Store-signed 产品线；更换安装入口不自动修复应用状态逻辑。
8. **路由变量单独隔离。**CC Switch 可以影响 provider/模型/请求行为，不能解释本地 MSIX 数据迁移；A/B 应使用临时、可逆配置。
9. **字段级恢复优于整文件恢复。**只恢复合同 MANAGE 面，保留 provider、模型、网络和未知用户字段。
10. **验证要做两次。**Desktop 完全退出时 `plan/verify` 一次，重新启动后再 `verify`，才能发现启动过程是否重新引入漂移。

## 当前处理建议

- 当前本机：保持现状，不 Reset、不卸载、不删除状态、不 apply。
- 另一台电脑：先执行本页只读清单，把结果分栏；有证据后再选择恢复层。
- 仓库：以本报告替代 #72 的过度推断；#72 继续保留作历史记录。
