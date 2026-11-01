# DL-MIG-002 — 术语 Allowlist / Denylist

- 任务：DL-MIG-002 Terminology allowlist/denylist
- 状态：✅ 完成（identity gate 强制）

## Denylist（活动路径禁止）

| 术语 | 允许出现位置 |
|---|---|
| `OPEN-DESIGN-Assistance` | history/、source/、host adapter、退出活动命名声明 |
| `opendesign-assistance` | 同上 |
| `Open Design Assistance` | 同上 |
| `Design Intelligence Layer` | 同上（历史名） |
| `Design Intelligence Capability Kit` | 同上（历史名） |

## Allowlist（活动命名）

- `DESIGN-LAB`（产品）/ `design-lab`（目录/namespace）
- `design-lab/product-manifest/v1`（schema namespace）
- `Agent-platform-neutral`（定位）
- `Game Visual Design Fixture`（MiniGame 角色）

## 强制机制

- `verify_identity_gate.py`：活动路径旧名命中即 fail
- 豁免：含"退出活动/历史归档/不再作为活动/仅允许出现在/retired"行
- host adapter 投影脚本文件级豁免（F1 允许）
