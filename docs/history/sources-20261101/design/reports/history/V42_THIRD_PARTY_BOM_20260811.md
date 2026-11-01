# V4.2 第三方物料清单（Third-Party BOM）— 2026-08-11

> Phase 11 许可合规 Gate 一部分。登记本项目使用的所有第三方依赖及其许可，
> 确保可审计、可合规。

## 第三方依赖清单

### Python（仅 1 项）
| 依赖 | 版本 | 许可 | 用途 |
|---|---|---|---|
| `jsonschema` | `>=4.18,<5`（实测 4.26.0） | MIT | 结构化校验（verify_evidence_cards / domain-pack / object-model 等） |

- 其余 Python 脚本**仅用标准库**（`json`/`pathlib`/`subprocess`/`argparse`/`unittest` 等），无第三方运行依赖。
- `requirements.txt` 已固定：`jsonschema>=4.18,<5`。

### Node / JavaScript（0 项）
- `fixtures/domains/game-visual/package.json`：`dependencies: {}`、`devDependencies: {}`——**无第三方 Node 依赖**。
- 浏览器无障碍扫描使用 `axe-core 4.9.1`，但**未 vendored**（仅作为外部工具运行，证据已存 `domain-packs/uiux-design/evidence/axe-scan-20260811.json`）。

### 资产
- 全部视觉/音频资产为项目原创，许可 **MIT**（`Copyright (c) 2026 DTALEX66 and contributors`）。

## 二进制资产 sidecar（3 项）
| 资产 | sidecar |
|---|---|
| `exports/minigame-mobile-controls/assets/cctv-elevator-corridor-clear.png` | `.png.license` (MIT) |
| `exports/minigame-mobile-controls/assets/cctv-elevator-corridor-figure.png` | `.png.license` (MIT) |
| `exports/minigame-mobile-controls/assets/cctv-elevator-corridor-warp.png` | `.png.license` (MIT) |

## 许可合规结论
- **LICENSE_COVERAGE=OK**（`verify_license_coverage.py`）：26 个源文件 SPDX 头补齐 + 3 个二进制 sidecar 就绪，0 缺口。
- **SPDX SBOM**：`config/sbom-v42.spdx.json`（SPDX-2.3，登记 3 二进制资产 + jsonschema 依赖）。
- 项目根许可：`LICENSE`（MIT）+ `LICENSES/MIT.txt`（REUSE 镜像）。

## 边界
- 未读取任何凭据；未扫描 `E:\`；未改动 Open Design 私有配置。
- MiniGame 生成产物已从源文件 SPDX 范围排除（产品树已切割）。
