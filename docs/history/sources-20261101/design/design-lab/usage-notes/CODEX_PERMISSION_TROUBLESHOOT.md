# Codex 执行策略修复（Open Design 非交互会话写删权限）

## 现象

Open Design 内调用 Codex 执行任务时，写入或删除文件报错：

```text
approval required by policy, but AskForApproval is set to Never
```

路径存在、writable_roots 已配置、Node spawn 可直接执行 Codex，但所有 shell 命令（PowerShell、Python、cmd）和删除类操作（Remove-Item、rm）都被拦截。

## 根因

Codex 本机 exec policy 规则文件：

```text
%USERPROFILE%\.codex\rules\default.rules
```

里面有许多**仅按命令名匹配**的泛化 `prompt` 规则，例如：

```text
powershell.exe -> prompt
Set-Content -> prompt
Remove-Item -> prompt
python -> prompt
node -> prompt
```

Open Design 调 Codex 时使用非交互模式：

```text
AskForApproval = Never
```

因此在 Open Design → Codex 链路上，这些 `prompt` 规则无法弹出确认框，直接失败为：

```text
approval required by policy, but AskForApproval is set to Never
```

## 修复方式

### 方式 A：注释泛化规则（已执行）

编辑 `%USERPROFILE%\.codex\rules\default.rules`，注释以下**不依赖 E 盘路径**的泛化 prompt 规则：

```text
powershell
powershell.exe
pwsh / pwsh.exe
cmd / cmd.exe
python / py / node
Set-Content / Add-Content / Out-File / New-Item
Get-Content / Get-ChildItem / Get-Item / Test-Path / Resolve-Path / Select-String
Copy-Item / Move-Item / Rename-Item
Remove-Item / rm / del / rmdir / rd
Invoke-Item / Start-Process / Compress-Archive / Expand-Archive / tar / 7z
wsl / bash / robocopy / xcopy / copy / move / ren / rename
compass / cipher / fsutil / subst / mklink
attrib / icacls / takeown
reg / winget / scoop / choco / npm / pip
```

保留以下规则不变：

```text
format / diskpart / bcdedit / shutdown（真正破坏性操作）
git push / git commit / git clean / git reset（需谨慎的 git 操作）
Set-ExecutionPolicy（系统级策略修改）
```

备份来自动创建：

```text
%USERPROFILE%\.codex\rules\default.rules.bak-open-design-policy-<timestamp>
```

### 方式 B：使用 --ignore-rules（可选）

Open Design 的 Codex 适配器打包在：

```text
%APPDATA%\Open Design\launcher\channels\stable\namespaces\release-stable-win\versions\<version>\payload\resources\app\prebundled\daemon\chunks\chunk-VPEQFAVI.mjs
```

可通过环境变量 `OD_CODEX_IGNORE_RULES=1` 使适配器自动追加 `--ignore-rules` 参数。启动器中已配置：

```bat
set "OD_CODEX_IGNORE_RULES=1"
```

如果 Open Design 后续自动更新覆盖了此补丁，重新在启动器 bat 中设置此环境变量，然后解压/重新打补丁即可。

## 验证

### 探针测试

```bash
cd D:\All projects\DESIGN-LAB\1d864770-e234-43fe-8994-27bf9350690a
printf '%s\n' '创建并删除 permission-probe.tmp，成功后只回复 PROBE_OK。' \
  | CODEX_HOME=C:/Users/admin/.codex codex exec \
    --json --skip-git-repo-check \
    --sandbox workspace-write \
    -c sandbox_workspace_write.network_access=true
```

预期结果：

```text
PROBE_OK
probe_exists_after False
```

即通过 PowerShell 在当前工作区创建、写入、删除临时文件且无残留。

### Open Design 内验证

在 Open Design 中对该项目重新执行文件写入/删除任务即可。

## 常见的误报排查

| 检查项 | 说明 |
|---|---|
| `writable_roots` | Codex config.toml 是否包含 `D:\All projects`？ |
| `.codex/rules/` | 是否有规则把命令名设为 `prompt`？ |
| Open Design daemon | 是否重启后生效？进程列表里还有旧 Codex 进程吗？ |
| `AskForApproval` | Codex doctor 显示 `approval OnRequest` 还是其他？ |

## 关键文件

```text
%USERPROFILE%\.codex\config.toml                      # writable_roots + trusted projects
%USERPROFILE%\.codex\rules\default.rules               # exec policy 规则（已修复）
%USERPROFILE%\.codex\auth.json                         # OAuth 凭据
%APPDATA%\Open Design\namespaces\release-stable-win\data\app-config.json  # Open Design 配置
D:\Programs\Open Design\Open Design - GPT Codex Proxy.bat  # 启动器
```
