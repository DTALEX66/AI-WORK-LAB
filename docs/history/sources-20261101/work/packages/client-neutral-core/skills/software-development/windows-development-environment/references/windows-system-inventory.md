# Windows 硬件/系统配置采集

## 触发场景与术语澄清

用户说「检查我的本机配置 / 检查电脑配置 / 查下这台机器的配置」时，指的是**硬件 + 操作系统配置**（CPU / 内存 / 显卡 / 磁盘 / 主板 / BIOS），**不是** Hermes 运行时配置。

不要一看到「检查配置」就先去加载 `hermes-runtime-auditing` / `runtime-baseline-audit` 做软件运行时审计——那是用户说「检查 Hermes / 模型 / provider / 运行时配置」才用的。

判据：
- 「电脑 / 本机 / 机器 / 硬件配置」= 硬件 + 系统。
- 「Hermes / 模型 / provider / 运行时 / 入口 / 满血配置」= 软件运行时。

## 采集方法（guard wrapper 下的可靠配方）

terminal guard 强制 wrapper 形式；`systeminfo` / `wmic` 输出 GBK，会在 wrapper 的 UTF-8 解码线程里触发 `UnicodeDecodeError`（命令 exit 0、输出全丢）。可靠做法：写一个**纯 ASCII 的 .ps1 脚本**（避免 PS 5.1 中文乱码，无需 BOM），开头强制 UTF-8 输出，用 `Get-CimInstance` 采集，再经 wrapper 用 `powershell -NoProfile -ExecutionPolicy Bypass -File` 执行（单命令、无 chaining、无内联 `$`）。

脚本写到项目 `.hermes/task-runtime/sysinfo.ps1`（write_file 无 BOM 即可，纯 ASCII 无乱码问题），然后：

```bash
python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- \
  powershell -NoProfile -ExecutionPolicy Bypass -File .hermes/task-runtime/sysinfo.ps1
```

采集字段映射（脚本模板骨架，ASCII-only）：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'SilentlyContinue'

$os   = Get-CimInstance Win32_OperatingSystem   # Caption+Version+OSArchitecture, BuildNumber
$cpu  = Get-CimInstance Win32_Processor          # Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed
$cs   = Get-CimInstance Win32_ComputerSystem     # Name(hostname), Manufacturer, Model, TotalPhysicalMemory
$mem  = Get-CimInstance Win32_PhysicalMemory     # Capacity, Speed, Manufacturer, PartNumber, DeviceLocator
$gpu  = Get-CimInstance Win32_VideoController    # Name, DriverVersion, AdapterRAM, VideoModeDescription
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"   # DeviceID, Size, FreeSpace, FileSystem
$bb   = Get-CimInstance Win32_BaseBoard          # Manufacturer, Product, Version
$bios = Get-CimInstance Win32_BIOS               # Manufacturer, SMBIOSBIOSVersion, ReleaseDate
```

换算：`$cs.TotalPhysicalMemory/1GB`（总内存）、`$os.FreePhysicalMemory/1MB`（空闲内存）、磁盘 `Size/1GB`。

## Pitfalls

1. **GPU 显存 `AdapterRAM` 32 位截断**：`Win32_VideoController.AdapterRAM` 是 32 位 DWORD，上限约 4GB（4294967295 字节）。≥4GB 显存的卡（RTX 5060 8GB、RTX 3060 12GB 等）都会被截断显示成 ~4GB。**判断真实显存查官方规格，不要信 AdapterRAM**；报告时必须标注「字段截断」而不是照抄 4GB。
2. **内存混插识别**：`Win32_PhysicalMemory.PartNumber` 能看出条子的标称频率（如 Corsair `CM4X16GD3200...` 是 3200 条），与运行频率 `Speed` 对比即可识别超频混插；前缀 `CM`(Corsair) / `VAM`(Asgard) 等可识别品牌。
3. **KF/-F 后缀无核显**：Intel `-KF` / `-F` 后缀 CPU 无核显，必须有独显；`MaxClockSpeed` 是**基础频率**不是睿频（如 i5-14600KF 基础 3.5GHz、睿频 5.3GHz）。
4. **主板具体型号看 `Win32_BaseBoard.Product`**：`Win32_ComputerSystem.Model` 返回 `MS-7D99` 这类内部板号，`BaseBoard.Product` 才返回可读型号（如 `PRO B760M-A WIFI DDR4 II (MS-7D99)`）。
