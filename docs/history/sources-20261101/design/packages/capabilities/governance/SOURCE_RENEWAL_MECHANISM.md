# Source Renewal & Invalidation Mechanism（ODA4-0807）

- **任务**：ODA4-0807（建立来源定期复核与失效机制）
- **状态**：**COMPLETE**（机制建立 + 校验入口就绪）
- **日期**：2026-08-14（boundTree=`cbae9fa`）
- **关联**：`OPEN_SOURCE_ABSORPTION_POLICY.md`（许可/晋级政策）、`SOURCE_REGISTRY.json`（162 条登记）

## 1. 机制总览

```text
周期复核（人工触发或 cron）
   │
   ├─ 1. 静态检查（离线）：registry schema 校验 + 记录一致性
   ├─ 2. 网络探针（可选，容错）：来源 URL/commit 可达性 + 许可页变化
   ├─ 3. 失效判定：许可变更 / 来源下线 / commit 消失 / 政策变更
   └─ 4. 处置：变更记录 + registry 状态更新（不自动进 runtime）
```

**核心原则**：
- **来源变更不自动进入 runtime**——任何复核结果只写 registry 状态，不改变能力加载
- **失效/许可变化触发 reverify**——状态从 `adopt-now/reference-now` 降级为 `review-required`，由人工批准后恢复
- **网络失败不破坏主 CI**——网络探针独立于 canonical CI（见下）

## 2. 三态状态机

| 状态 | 含义 | 处置 |
|---|---|---|
| `adopt-now` / `reference-now` | 许可已验证 + 已吸收 | 正常使用 |
| `review-required` | 许可变化/来源下线/待复核 | **不参与能力加载**，触发人工 reverify |
| `quarantine` | 隔离（未验证/争议） | 不参与索引/检索/构建/提示词 |

## 3. 复核触发条件

1. **周期复核**：每季度（或人工触发 `verify_source_registry.py --renewal`）
2. **事件触发**：上游 commit 变化 / 许可文件变更 / 来源 404 / SBOM 更新
3. **政策变更**：KNOWLEDGE_ASSET_POLICY / 许可政策修订后全量 reverify

## 4. 网络探针（容错设计）

- 独立脚本 `scripts/source_renewal_probe.py`（可选运行，不进 canonical CI）
- 失败语义：
  - **网络不可达** → `PROBE_SKIPPED`（不失败，不降级——避免误杀）
  - **URL 404** → 标记 `review-required`（来源下线）
  - **commit SHA 不存在** → 标记 `review-required`（上游改写）
  - **许可页变化** → 标记 `review-required`（需人工比对）
- 主 CI 只跑**离线**静态校验（`verify_source_registry.py`，DL-KNW-004）——网络失败绝不破坏 CI

## 5. 已落地的离线校验（现有，无需新代码）

| 校验 | 脚本 | 覆盖 |
|---|---|---|
| registry schema | `verify_source_registry.py` | v3 SourceRecord 全量 schema；162 条遗留登记已隔离至 QUARANTINE_REGISTRY（DL-KNW-003） |
| 许可覆盖 | `verify_license_coverage.py` | 新增文件 SPDX/.license 侧车 |
| 资产治理 | `verify_asset_governance.py` | 二进制大小/来源/哈希 |
| SBOM | `verify_sbom.py` | vendored 覆盖 |

## 6. 处置流程（人工批准为硬前置）

```text
发现失效 → registry 状态 → review-required → 人工审查（reviewedBy/reviewedAt）
  ├─ 确认失效 → 降级 reference-only / quarantine / 移除
  └─ 确认误报 → 恢复原状态 + 记录
```

## 7. 合规确认

- ✅ 来源变更不自动进入 runtime（状态机隔离）
- ✅ 失效/许可变化触发 reverify（review-required 降级路径）
- ✅ 网络失败不破坏主 CI（探针独立 + SKIPPED 语义）
