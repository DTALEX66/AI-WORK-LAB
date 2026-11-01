# V4 Security Remediation Report（安全整改报告）

- 任务：`ODA4-0101`（P0，risk=critical）
- 日期：2026-08-07
- 证据等级：`E2`（隔离 dry-run + 安全回归测试通过）
- 目标脚本：`design-lab/scripts/configure_open_design_windows.py`、`doctor_open_design_windows.py`

## 移除的危险行为

| 原行为 | 处置 | 说明 |
|---|---|---|
| 读取 `CODEX_HOME/auth.json` 内容 | ✅ 移除 | 改为存在性检查 `codex_auth_present()`，绝不读内容 |
| 修改 `CODEX_HOME/config.toml` 授予宽根 writable/trusted | ✅ 移除 | `update_codex_permissions`/`add_trusted_project` 全部删除 |
| `permission_root.rglob(".od-skills")` 宽根扫描 | ✅ 移除 | 删除 `discover_od_skill_roots` 及 PowerShell 读取 |
| 默认写入 Open Design 私有 `app-config.json` | ✅ 收紧 | 默认 `dry-run`，仅 `--apply` 且精确项目根才写，写前备份 |
| 默认信任 `D:\All projects` 宽根 | ✅ 移除 | 新增 `SECURITY_BLOCK` 宽根拒绝 |

## 新增的安全边界（SECURITY_BLOCK）

`configure` 脚本现在拒绝以下作为项目目标：
- 精确宽根：`D:\All projects`、盘符根（`C:\`、`D:\`、`E:\`、`F:\`）
- `E:` 盘任意路径（铁律禁止）
- 用户 home（`C:\Users\<user>`）

放行：`D:\All projects\DESIGN-LAB` 这类精确深层项目路径。

## 验证结果

**CLI 行为测试（5 场景）**：
| 场景 | 结果 |
|---|---|
| 精确项目根 `D:\All projects\DESIGN-LAB` | ✅ 放行（dry-run，`CONFIG_OK`） |
| 宽根 `D:\All projects` | ✅ `SECURITY_BLOCK` |
| 盘符根 `D:\` / `C:\` / `E:\` | ✅ `SECURITY_BLOCK` |
| `E:\x` | ✅ `SECURITY_BLOCK`（forbidden root） |
| 用户 home `C:\Users\ALEX` | ✅ `SECURITY_BLOCK`（forbidden root） |

**安全回归测试**：`tests/test_oda4_0101_security.py` — **9/9 通过**
- 代码路径扫描：无 auth 内容读取、无 config.toml 写入、无 .od-skills 宽扫描
- 两个脚本均无危险函数残留

**静态扫描**：两脚本均无 `auth.json read_text` / `rglob(.od-skills)` / `writable_roots` / `config.toml write_text`。

## 边界确认

- 本次整改**未访问 E:\**、未读取任何凭据内容、未修改任何私有配置、未授予宽根权限。
- 所有验证均在 `--dry-run` / 只读模式下进行，未对用户系统做任何写入。
- `doctor` 脚本保持只读，不再报告宽根 writable/trusted 期望。

## 遗留（非本任务范围）

- `doctor` 报告的 `Codex CLI runs` FAIL（`codex.exe` 探测路径问题）属环境探测，非安全缺陷，由 ODA4-0303（Windows 原生安装验证）处理。
- 根 LICENSE / SPDX 决策由 ODA4-0102 处理（当前保持 `NO_PUBLIC_COMMERCIAL_RELEASE`）。
