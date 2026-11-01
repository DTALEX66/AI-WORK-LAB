# WORK-LAB DSH 更新与维护 RUNBOOK（2026-09-20）

日期：2026-09-20 · 项目：`D:/All projects/WORK-LAB`（客户端中立控制面）· 受管客户端：DSH（DeepSeek Harness，桌面 + 社区版）
性质：SOP 固化文件（tracked，防复发）。与 `WORK-LAB-PARALLEL-DISPATCH-HANDOFF-2026-09-20.md` 同目录同惯例；不进 CURRENT_STATE digest 区。
§40 铁律：全程不引入任何 C 盘持久写入、不引入第二套 updater / runtime；官方 NSIS 装到 LOCALAPPDATA 只是**瞬态 staging**，步骤 5 必须删净，步骤 5 postflight residue 扫描必须全 absent。

---

## 1. Purpose & scope

- DSH 是 WORK-LAB 受管客户端之一；本 RUNBOOK 覆盖 **官方更新（update）+ 例行维护（maintenance）+ 三大复发陷阱预防**，是 2026-09-20 实证收敛后的唯一 SOP。
- 红线（用户原文，逐字锁死）：
  > “D:\All projects\DSH 这个路径绝对锁死，所有 DSH 的本体和社区桌面版的配置等官方标准都在这个路径下完成，不要标准路径下又链接部署其他路径指向”
- 适用：任何 DSH 官方版本升级、NSIS 重装、`resources\app` 代码树恢复、数据根迁移复核、月度健康巡检。
- 不适用：DSH 功能开发（见各 taskpack / 交接文档）；WORK-LAB 自身 CI（见 `exact-sha-ci-delivery` 系列 skill）。

## 2. Golden identity（DSH canonical，2026-09-20 实证基线）

| 项 | 值（canonical） |
|---|---|
| install_root | `D:\All projects\DSH` |
| exe | `D:\All projects\DSH\DSH Desktop.exe` |
| data_root | `D:\All projects\DSH\.dsh`（实证：sessions=114，settings.yaml 61987B，全量在 D） |
| user-data | `D:\All projects\DSH\desktop-user-data` |
| 快捷方式 | 桌面 + 开始菜单 `.lnk` → `D:\All projects\DSH\DSH Desktop.exe --user-data-dir=D:\All projects\DSH\desktop-user-data` |
| 端口 | `43120`（LISTENING = 健康） |
| 注册表 | `DSH_HOME` [HKCU] = `D:\All projects\DSH\.dsh` |
| 本体 | 2.0.13 官方：`resources\app` unpacked 22101 文件、无 asar、官方卸载器在 D 根 |
| C 盘 | 零 DSH 活体：6 项已迁入 `D:\All projects\DSH\.migration\20260920\c-drive-dsh-archived\`（日志 `c-dsh-migration.log`） |
| junction | 671 条全在 D 盘内；asar 时代 120 条悬空链接已清（回滚记录 `dangling-junctions-fixed-20260920.tsv`） |

任何检查都以本表为 expected；偏离即告警。

## 3. Pre-update gate（P0-07 preflight，PASS / PENDING 才可动手）

P0-07 双契约：`workflow/software-installation-identity/v1` + `workflow/software-update-preflight/v1`
（脚本 `packages/client-neutral-core/scripts/software_installation_identity.py`，下称 `sii`；
负控 `tests/workflow-assistance/` 内 `nf_dsh_installation_location` 14 项锁住 DSH 位置语义）。

调用要点（纯函数，先分类再判定，fail-closed）：

```python
import sys; sys.path.append(r"D:/All projects/WORK-LAB/packages/client-neutral-core/scripts")
import software_installation_identity as sii

# ① 观测态分类（expected = D 路径，user_declared = 用户红线值）
cls = sii.classify_installation(
    observed_existing=[r"D:\All projects\DSH"],
    registered_existing=[r"D:\All projects\DSH"],
    expected_existing=[r"D:\All projects\DSH"],
    user_declared=r"D:\All projects\DSH",
    verified=True)

# ② preflight 判定
rec = sii.build_update_preflight(
    software_id="dsh-desktop",
    location_status=cls["location_status"],
    install_root=r"D:\All projects\DSH",
    proposed_install_root=r"D:\All projects\DSH",   # 更新必须 in-place；改 root = RELOCATION
    verified=True,
    user_declared=r"D:\All projects\DSH")
assert rec["overall"] in ("PASS", "PENDING"), rec   # BLOCKED(FAIL) 一律禁止动
```

三大 BLOCKED 场景（出现任一 = 停手，先解决）：

1. **updater 想写 C**：NSIS 默认目标 `C:\Users\ALEX\AppData\Local\DSH Desktop` ≠ 当前 root `D:\All projects\DSH` → root change，无 approved relocation → `BLOCKED`（`INSTALL_ROOT_CHANGE_REQUIRES_EXPLICIT_RELOCATION` / `RELOCATION_NOT_APPROVED`）。对策：按 §4 流程 staging 到 LOCAL 后 `/MIR` 回 D 并删 LOCAL 体，**不**留 C 活体。
2. **双安装（DUAL_INSTALLATION）**：C staging 残留 + D 本体同时存在 → `DUAL_INSTALLATION_UPDATE_BLOCKED`。对策：删净 C 侧（§4 步骤 5）后再跑 preflight。
3. **期望缺失（MISSING_EXPECTED_INSTALL）**：`D:\All projects\DSH` 不存在 → `MISSING_EXPECTED_INSTALL_NO_VENDOR_FALLBACK`（不回退 C 盘 vendor default）。对策：走官方安装包重提取到 D（§8），不得装到 C。

（另有 `LOCATION_DRIFT` 用户声明 vs 观测冲突、`SINGLE_UNVERIFIED` 先验身份——同样 BLOCKED，须先验证。）

## 4. Update procedure（官方 NSIS，7 步，命令可直接复制）

PowerShell 执行；每步把实测值（文件数/字节数/exit）记入 `D:\All projects\DSH\.migration\YYYYMMDD\upgrade-log.md`（§8）。

**① 停 DSH，确认 43120 DOWN + 0 进程**

```powershell
Get-Process | Where-Object {$_.Path -like "D:\All projects\DSH\*"} | Stop-Process -Force -ErrorAction SilentlyContinue
(Test-NetConnection -ComputerName 127.0.0.1 -Port 43120 -InformationLevel Quiet)            # 期望 False（DOWN）
(Get-Process | Where-Object {$_.Path -like "D:\All projects\DSH\*"}).Count                  # 期望 0
```

**② robocopy 备份 `.dsh`（`/XJ` 排除 junction；实文件数/字节数 = 回滚基线）**

```powershell
$ts = "YYYYMMDD"   # 当天日期
robocopy "D:\All projects\DSH\.dsh" "D:\All projects\DSH\.dsh-backup-$ts" /E /XJ /MT:8 /R:1 /W:1
# 读 robocopy 输出 C:35（Files / Bytes 行），把实文件数与字节数写进 upgrade-log = 回滚基线
# 注：/XJ 必须带——.dsh 内 junction（671 条全 D 内）不跟随，防外渗/双写
```

**③ 下载官方 NSIS 安装包（记录精确字节数）**

```powershell
$installer = "$env:TEMP\dsh-official-SETUP.exe"
Invoke-WebRequest -Uri "<当次官方 release URL>" -OutFile $installer
(Get-Item $installer).Length   # 精确字节数 → upgrade-log
```

**④ 静默装到 LOCALAPPDATA（瞬态 staging，不是最终位置）**

```powershell
& $installer /S /D="$env:LOCALAPPDATA\DSH Desktop"   # NSIS /D= 必须最后、等号后无空格；exit 0 仅代表装完，不代表成功（§3 判读）
```

**⑤ robocopy `/MIR` resources LOCAL→D，然后删 LOCAL 体（C 盘必须回到零活体）**

```powershell
robocopy "$env:LOCALAPPDATA\DSH Desktop\resources" "D:\All projects\DSH\resources" /MIR /MT:8
# 记录 resources\app 实文件数（= 当次官方提取实数，供 §5 expected_code_tree_files_min）
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\DSH Desktop"
Test-Path "$env:LOCALAPPDATA\DSH Desktop"   # 期望 False（C 盘零 DSH 活体）
```

**⑥ 重钉桌面 + 开始菜单 `.lnk` 回 D 盘（NSIS 会重置成 LOCAL = 死链，必须 Test-Path 验证）**

```powershell
$wsh = New-Object -ComObject WScript.Shell
$targets = @(
  "$env:USERPROFILE\Desktop\DSH Desktop.lnk",
  "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\DSH Desktop.lnk"   # 目录名跟官方实际，先 ls 确认
)
foreach ($p in $targets) {
  $lnk = $wsh.CreateShortcut($p)
  $lnk.TargetPath      = "D:\All projects\DSH\DSH Desktop.exe"
  $lnk.Arguments       = '--user-data-dir="D:\All projects\DSH\desktop-user-data"'
  $lnk.WorkingDirectory = "D:\All projects\DSH"
  $lnk.Save()
}
# 验证：TargetPath 必须 = D 路径且文件存在；若仍指 LOCAL = 死链，重钉一次
foreach ($p in $targets) {
  $t = $wsh.CreateShortcut($p).TargetPath
  [pscustomobject]@{lnk=$p; target=$t; ok=($t -eq "D:\All projects\DSH\DSH Desktop.exe" -and (Test-Path $t))}
}
```

**⑦ 带 DSH_HOME 显式注入启动，43120 须 5s 内 LISTENING**

```powershell
$env:DSH_HOME = "D:\All projects\DSH\.dsh"     # 显式注入，防会话冻结回退 C（§6b）
Start-Process "D:\All projects\DSH\DSH Desktop.exe" -ArgumentList '--user-data-dir="D:\All projects\DSH\desktop-user-data"' -WorkingDirectory "D:\All projects\DSH"
$ok = $false
$deadline = (Get-Date).AddSeconds(5)
while ($ok -eq $false -and (Get-Date) -lt $deadline) {
  $ok = (Test-NetConnection -ComputerName 127.0.0.1 -Port 43120 -InformationLevel Quiet)
  if (-not $ok) { Start-Sleep -Milliseconds 500 }
}
$ok   # 期望 True（5s 内 LISTENING）；False → 查 §6b / §8
```

## 5. Post-update gate（software-update-postflight，overall=PASS 才宣告更新完成）

本次新固化的纯函数门禁（与 §3 preflight 对偶）：
`packages/client-neutral-core/scripts/software_update_postflight.py` · 契约 `workflow/software-update-postflight/v1`（contract-catalog 37 号位）· §4.1：全动态引用，不写死测试计数。

```python
from software_update_postflight import run_postflight_checks
res = run_postflight_checks(
    expected_install_root=r"D:\All projects\DSH",
    expected_data_root=r"D:\All projects\DSH\.dsh",
    residue_watchlist=[
        r"C:\Users\ALEX\.dsh",
        r"C:\Users\ALEX\AppData\Roaming\DSH Desktop",
        r"C:\Users\ALEX\AppData\Local\DSH Desktop",
        r"C:\Users\ALEX\AppData\Local\dsh-plugin-desktop-updater",
    ],
    expected_code_tree_files_min=<当次官方提取 resources\app 实数>   # 例：2.0.13 基线 = 22101（unpacked，无 asar）；每次取步骤 ⑤ 实测
    ,
    asar_expected=False,          # canonical 形态 = unpacked 代码树，出现 asar 即形态漂移
    uninstaller_expected=True,   # 官方卸载器必须在 D 根
    target_version="2.0.13",     # 本次官方目标版本
)
assert res["overall"] == "PASS"   # 任何一项 FAIL → 禁止宣告更新完成，走 §6/§8
```

逐项 checks 含义（任一 FAIL → overall=FAIL，fail-closed）：

| check | 判据 |
|---|---|
| location | install_root / exe realpath == expected D 路径（防 NSIS 把活体留在 LOCAL） |
| version | 实读版本 == target_version |
| body_integrity | `resources\app` 实文件数 ≥ expected_code_tree_files_min 且无 asar（捕获 §6c 清空事故） |
| residue | residue_watchlist 4 项全部 absent（C 盘零 DSH 活体；捕获 §6b C fallback 重建） |
| data_root | expected_data_root 存在、与 HKCU `DSH_HOME` 一致、且 mtime 在更新后前进（数据未回退/未双根） |
| uninstaller | 官方卸载器在 D 根存在 |
| overall | 全部 PASS 才允许宣告更新完成并归档 upgrade-log |

## 6. 三大复发陷阱（2026-09-20 实测）

**(a) NSIS 重置 `.lnk` 回 LOCAL（死链）**
- 症状：官方安装/更新后，桌面+开始菜单快捷方式 TargetPath 指向 `C:\Users\ALEX\AppData\Local\DSH Desktop`，C 体已删 → 点了没反应 / 误装回 C。
- 根因：NSIS 安装器按自身参数重写快捷方式，把 golden .lnk 冲掉。
- 检测：§4⑥ 的 TargetPath 读回 + `Test-Path`；月度巡检一并做。
- 修复：§4⑥ 重钉回 D。**每次官方安装后必做**，不可省略。

**(b) Windows 用户 env 会话冻结 → DSH_HOME 缺失 → C fallback 双根**
- 症状：数据看似「消失」（sessions/配置读不到），实为进程读到了 `C:\Users\ALEX\.dsh` 新根——双根。
- 根因：`DSH_HOME` 写在 HKCU 注册表，但当前登录会话的环境块是登录时快照——新设的 HKCU 变量在会话内不可见，启动进程回退 C 盘默认根。
- 检测：对比 D 数据根 `.dsh` mtime 是否前进 + C 侧 `C:\Users\ALEX\.dsh`（residue_watchlist 第 1 项）是否被重建/有新 mtime。
- 缓解（每次都做）：§4⑦ 启动时显式注入 `$env:DSH_HOME`。
- 根治：注销或重启一次，让新 HKCU 环境块进入会话。

**(c) 更新循环清空 `resources\app` 官方代码树**
- 症状：2026-09-20 20:33 实测 45k 文件 → 0；DSH 功能全失效但 exe 还在。
- 根因：更新循环（LOCAL staging → D 的同步步骤）在官方提取未完成/路径漂移时把 D 侧代码树 MIR 成空。
- 检测：§5 postflight `body_integrity`（文件数 < expected_code_tree_files_min 即 FAIL）。
- 恢复：官方安装包重提取 resources → D + `robocopy /MIR`（本次已实操验证可行；随后跑 §5 全 gate）。

## 7. Maintenance cadence

| 触发 | 动作 |
|---|---|
| 每次官方安装/更新后 | 必跑 §5 postflight（overall=PASS 才归档）；必做 §4⑥ .lnk 重钉 + §4⑦ DSH_HOME 注入启动 |
| 每月一次 | junction 健康（external=0 / dangling=0）+ C 盘残留复扫（residue_watchlist 4 项全 absent） |
| 每次维护/更新 | 数据备份基线落 `D:\All projects\DSH\.migration\YYYYMMDD\`（含 upgrade-log） |

月度 junction 健康 + 残留复扫（PowerShell）：

```powershell
# junction 健康：external=0（目标全在 D 盘内）、dangling=0（目标存在）
$js = Get-ChildItem "D:\All projects\DSH" -Recurse -Force -Directory |
      Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }
$external = @($js | Where-Object { $t=(Get-Item $_.FullName).Target; $t -and -not ($t -like "D:\*") }).Count
$dangling = @($js | Where-Object { $t=(Get-Item $_.FullName).Target; -not $t -or -not (Test-Path $t) }).Count
[pscustomobject]@{total=$js.Count; external=$external; dangling=$dangling}   # 期望 external=0, dangling=0

# C 盘残留复扫：4 项必须全部 absent（False）
@("C:\Users\ALEX\.dsh","C:\Users\ALEX\AppData\Roaming\DSH Desktop",
  "C:\Users\ALEX\AppData\Local\DSH Desktop","C:\Users\ALEX\AppData\Local\dsh-plugin-desktop-updater") |
  ForEach-Object { [pscustomobject]@{path=$_; exists=(Test-Path $_)} }
```

## 8. Rollback（顺序固定，逐条记录到 `.migration\YYYYMMDD\upgrade-log.md`）

1. 停 DSH（§4① 命令），43120 DOWN + 0 进程。
2. **恢复数据基线**：`robocopy "D:\All projects\DSH\.dsh-backup-YYYYMMDD" "D:\All projects\DSH\.dsh" /MIR /XJ /MT:8`（基线 = §4② 记录的实文件数/字节数；对账）。
3. **官方安装包重提取 + `/MIR`**（代码树恢复，同 §6c 恢复路径）：重跑 §4③④⑤（或直接用已存档 installer），记录新的 resources\app 实数。
4. **`.lnk` 重钉**：§4⑥ 全套 + Test-Path 验证。
5. **DSH_HOME 显式注入启动**：§4⑦，43120 5s 内 LISTENING。
6. 跑 §5 postflight（overall=PASS）→ 把本次升级日志（每步命令 + 实测值 + 失败点）归档 `D:\All projects\DSH\.migration\YYYYMMDD\`。

---

证据基线快照（2026-09-20）：官方 2.0.13 unpacked（22101 文件 / 无 asar / 卸载器在 D 根）；`.dsh` sessions=114、settings.yaml 61987B；C 盘 6 项 DSH 活体已归档 `D:\All projects\DSH\.migration\20260920\c-drive-dsh-archived\`（`c-dsh-migration.log`）；junction 671 全 D 内、120 条 asar 时代悬空已清（`dangling-junctions-fixed-20260920.tsv`）。
