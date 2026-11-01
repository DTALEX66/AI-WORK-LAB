# Source License & Promotion Audit（ODA4-0803）

- **任务**：ODA4-0803（完成来源许可、集成模式和供应链晋级）
- **状态**：**PASS**（审计通过，无违规晋级）
- **日期**：2026-08-14（boundTree=`02dd38b`）
- **范围**：SOURCE_REGISTRY.json（162 条）许可 × 晋级状态 × 集成模式交叉审计

## 1. 审计方法

对全部 162 条，检查 `license` × `status` × `integration_mode` 三字段一致性：

| 检查项 | 标准 | 结果 |
|---|---|---|
| GPL/AGPL 进入商业核心 | 禁止（必须 adapter + review-required）| ✅ 0 违规 |
| 非商业许可（CC-BY-NC）捆绑 | 必须限制 + derive/隔离 | ✅ 已限制 |
| 大型工具默认 adapter | 不得 vendor-adapt 到核心 | ✅ 合规 |
| 每次晋级有审批和证据 | reviewedBy/reviewedAt 齐全 | ✅ 162 条齐全 |

## 2. 高风险许可条目明细

| id | license | status | mode | 判定 |
|---|---|---|---|---|
| blender | GPL-3.0-or-later | review-required | adapter | ✅ 正确隔离 |
| ghostscript | AGPL-3.0 / commercial | review-required | adapter | ✅ 正确隔离 |
| freecad | LGPL-2.1-or-later | review-required | adapter | ✅ 正确隔离 |
| openskill-eval | Apache-2.0 code; CC-BY-NC-4.0 data | adopt-now | derive | ✅ 代码可吸收，数据已标非商业限制（`restrictions: do not bundle in commercial distribution`）|
| chromatic | PROPRIETARY-SERVICE | reference-now | reference | ✅ 正确引用级 |

## 3. 结论

- ✅ **GPL/AGPL/非商业/未知权利不进入商业核心**：0 违规
- ✅ **大型工具默认 adapter**：blender/ghostscript/freecad 全部 adapter 模式
- ✅ **每次晋级有审批和证据**：162 条全部含 reviewedBy/reviewedAt
- **无需修改**——registry 状态与许可政策一致

## 4. 关联

- 支撑 ODA4-0801（registry 完整性）与 ODA4-0807（来源复核机制）
- 晋级审核（candidate→quarantined→…）记录在 `capability-status.json`（promotion levels 政策见 OPEN_SOURCE_ABSORPTION_POLICY.md §Promotion levels）
