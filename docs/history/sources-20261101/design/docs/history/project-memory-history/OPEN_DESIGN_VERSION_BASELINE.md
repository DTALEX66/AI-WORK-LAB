# Open Design Version Baseline（ODA4-0301）— UPDATED

- 最近更新：2026-08-07（0.13.0 → 0.18.1，含应用内自动补丁）
- 来源：官方安装包 + 应用内自动更新；版本经应用 Settings→About 界面确认
- 证据：E1（界面截图 + `open-design-config.json` 读回）

## 实测基线（当前权威）

| 项 | 值 | 来源 |
|---|---|---|
| **运行版本（界面）** | **`0.18.1`** | Settings→About（"您已经是最新版本"） |
| 主版本号（config） | `0.18.0` | `open-design-config.json` `appVersion` |
| 渠道 | `stable` | About 界面 |
| 运行时 | `已打包应用`（packaged） | About 界面 |
| 平台 / 架构 | `win32` / `x64` | About 界面 |
| 自动更新 | 允许应用内自动更新（已勾选） | About 界面 |
| namespace | `release-stable-win` | config |

## 版本演进事实

`0.18.0` 是官方主安装包（NSIS），安装后应用内自动更新机制**自动拉取并安装了 `0.18.1` 补丁**。因此：
- **config `appVersion: 0.18.0`** = 主版本号（安装包版本）
- **界面运行版本 `0.18.1`** = 实际运行补丁版（权威，用户可见）

后续所有 E3 运行时对齐以 **0.18.1** 为准。

## 版本档位（最终）

- **minimum**: `0.18.1`（当前已测基线；0.13.0 仅为历史记录，不作为支持基线）
- **tested**: `0.18.1`（当前运行，界面确认）
- **latest**: `0.18.1`（界面"您已经是最新版本"）
- **历史**: `0.13.0`（2026-08-07 就地升级前观测，见 upgrade_history）

## 记录位置
- 本文件：`docs/OPEN_DESIGN_VERSION_BASELINE.md`
- 机器可读：`design-lab/config/compatibility-baseline.json`
