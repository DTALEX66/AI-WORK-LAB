# DL-KNW-007 — 外置资料 AI 可复用知识转化管线

> 硬边界（DL-KNW-005/006/007）：外置资料库 `D:\All projects\Design assets` 不整体复制、不建 submodule/symlink、不扫描根目录、不改动原件；只允许按人工选择的 Collection Manifest 做受控摄取。

## 管线

```text
External Source Candidate
→ Collection Manifest（人工创建，DL-KNW-006）
→ Manifest 校验（fail-closed；根扫描 ** 拒绝）
→ Hash Readback（sha256 回读，root 不可用时 reference-only）
→ SourceRecord（隔离草稿；权利/审核事实绝不伪造）
→ Rights Gate（rightsReviewRequired=true 为硬闸）
→ Safe Extraction（复制禁止清单校验）
→ ResearchFinding / MethodCard / ReferenceSet / Rubric / Benchmark
→ Human Review
→ Capability Index
```

## 只允许把以下派生结果放入 Git

设计规律、构图方法、排版规则、色彩关系、材质与光影方法、质量 Rubric、
匿名化 Reference DNA、Benchmark 描述、生产检查规则。

## 禁止复制进 Git

完整原图、完整视频/音频、模型权重、字体、PSD/AI/FIG 原件、
受保护 Logo、大师标志性构图复刻、第三方完整前端。

## 去重键（每条派生产物必须携带）

- content SHA-256（原始获取内容的 `sha256:<64hex>`）
- perceptual hash（图像可选）
- sourceId
- derivedArtifactId

## 工具

`design-lab/scripts/external_asset_intake.py`：

```bash
python design-lab/scripts/external_asset_intake.py \
  --manifest design-lab/config/collection-manifests/example.collection.json \
  --root "<外置库根路径（仅本地，来自 local-profile）>" [--dry-run]
```

- 校验 Manifest（Draft 2020-12 schema）；根扫描 / `**` 通配 → 非零失败。
- `--root` 提供时执行 Hash Readback；缺失时仅 reference-only（不伪造哈希）。
- `rightsReviewRequired=true` → Safe Extraction BLOCKED（人工权利复核是硬闸）。
- 复制禁止类型（图片/音视频/权重/字体/PSD/AI/FIG 等）被选中用于抽取 → BLOCKED。
- 运行状态只写 `.hermes/task-runtime/intake/`（gitignored），不污染 Git 树。

## 本地 Profile（DL-KNW-005）

- 示例：`design-lab/config/local-profile.example.json`
- 真实文件：`design-lab/config/local-profile.json`（已 Git ignore；禁止提交 Windows 绝对路径）

## Collection Manifest（DL-KNW-006）

- Schema：`design-lab/schemas/collection-manifest.schema.json`
- 示例：`design-lab/config/collection-manifests/example.collection.json`
- 字段：collectionId / displayName / selectedPaths（显式相对路径）/ intendedUse /
  rightsReviewRequired / outputTargets / createdBy / createdAt
- 禁止默认扫描：`D:\All projects\Design assets\**`
