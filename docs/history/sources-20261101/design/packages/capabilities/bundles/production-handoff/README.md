# Production Handoff（生产交付入口）

DESIGN-LAB 的**第三个公开入口**（与 `commercial-design-core`、`visual-quality-core` 并列）。

## 职责

把经过质量门禁的设计结果转化为：
- 可编辑源文件与结构化资产；
- 数字/印刷/包装/空间/动效/3D 生产预检；
- 有来源、权利、版本、评分、预检和回滚证据的交付包。

## 输入
- 已审定的 DESIGN.md / DTCG Tokens / 组件 / 资产清单；
- 生产目标（数字/印刷/包装/施工/视频/音频/3D）。

## 输出
- Preflight 报告（尺寸、出血、色彩、字体、BOM、无障碍）；
- Handoff 包（可编辑源、预览、资产清单、Provenance）；
- 版本与回滚记录。

## 原子能力
`commercial-preflight`、`delivery-packager`、`micro-detail-finisher`、`cross-format-coherence-critic`。

## 证据
- `schemas/preflight.schema.json`、`schemas/design-handoff.schema.json`、`schemas/provenance.schema.json`、`schemas/release-evidence.schema.json`。

## 边界
- 不替代 Open Design 的导出/Artifact 系统；
- 交付声明必须绑定 evidence level，无 E3/E4/E5 不夸大。
