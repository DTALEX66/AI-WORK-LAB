# production — Handoff / Preflight V1

DL-PRD-001：商业生产闭环——颜色/字体/尺寸/格式/源文件/许可证/BOM/回滚完备。

## 结构

```text
production/
├─ preflight/        # 生产预检（颜色/字体/尺寸/格式/源文件/许可证）
├─ handoff/          # 可编辑交付（源文件 + 导出 + 规范）
├─ provenance/       # 溯源（boundTreeSha、输入 hash、工具版本）
└─ rollback/         # 回滚包（版本化、可恢复）
```

## Preflight V1（DL-PRD-001 核心）

交付前逐项检查：

| 项 | 检查 | 缺失后果 |
|---|---|---|
| 颜色 | 色值规范（hex/oklch）、色彩空间声明、对比度 | 跨端色差 |
| 字体 | 字体文件许可、字形覆盖、回退栈 | 渲染替换 |
| 尺寸 | 目标尺寸、出血/安全区、多端断点 | 裁切错位 |
| 格式 | 输出格式（可编辑源 + 导出）、版本兼容 | 无法编辑/无法复用 |
| 源文件 | 可编辑源（PSD/AI/INDD/Figma/Blender）随交付 | 无源=不可编辑 |
| 许可证 | 字体/素材/模型权重许可声明（SPDX） | 法律风险 |
| BOM | 资产清单（文件、hash、来源） | 供应链不可追踪 |

## Handoff V1

- **可编辑源**：交付 PSD/AI/INDD/BLEND/Figma 等源文件（Adobe PS 适配器链）
- **导出**：目标格式导出（web/print/motion/3D）
- **规范**：tokens/type scale/grid/component 规范文档
- **BOM**：`production/handoff/BOM.json`（每文件 hash + 来源 + 许可）

## Provenance

- 每产物记录：boundTreeSha、生成时间、执行环境、工具版本、输入 hash
- 与 `schemas/provenance.schema.json` 对齐

## Rollback

- 每次交付生成回滚包（上一版完整状态）
- 版本化：`handoff/v1/`、`handoff/v2/`…保留历史
- 回滚不破坏证据链（EVIDENCE_POLICY）

## 证据等级

- 合同/E0：adapter.manifest.json
- E1：预检脚本输出
- E3：真实运行时读回（PS 打开/编辑/导出真实文件）

## 关联

- `schemas/preflight.schema.json` / `provenance.schema.json` / `design-handoff.schema.json`
- Adobe PS 适配器（DL-ADB-PS-001）：可逆可编辑文档操作
- 生产交付用例：`scenarios/` 商业设计场景
