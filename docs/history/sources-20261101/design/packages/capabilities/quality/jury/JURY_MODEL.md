# Visual Quality Jury V1 — 评分模型

DL-QLT-001。六轴评分 + 人审门。**不用单张 AI 图作为通过证据。**

## 评分流程

1. **确定性检查**（自动）：token 锁定、无硬编码色值、响应式断点、无 AI 默认模式
2. **六轴评分**（1-5，每轴独立）：反 AI 味 / 布局 / 材质 / 可读性 / 商业适配
3. **人审**（人工）：至少一位人工评审，按 Rubric 逐项确认
4. **裁决**：每轴 ≥3 + 人审 pass → PASS；任一轴 <3 → REVISION

## 反 AI 味轴（anti-slop）

吸收 hallmark `slop-test.md` 的核心信号：

| 信号 | 判定 |
|---|---|
| 结构多样性 | 不同 brief 不得共享 hero→3-feature→CTA→footer 节奏 |
| 无 AI 默认 | 禁：紫渐变、居中 hero 深色网格、三等卡、全玻璃拟态、无限循环微动效、Inter+slate-900 |
| 锁定令牌 | 每处颜色/font-family 引用命名 token，禁止中途中发明值 |
| 诚实文案 | 禁止虚构指标/证言/案例数（"+47% conversion" = slop） |
| 无重绘 chrome | 禁手绘假浏览器栏/假手机框/假代码窗 |
| 排版纯度 | 标题不用斜体；强调靠字重/强调色/下划线 |
| 移动响应 | 320/375/414/768 全宽度无横向滚动 |

## 布局轴

- 宏结构选择（吸收 hallmark `macrostructures.md`：21 种结构）
- 节奏与留白（`layout-and-space.md`）
- 层级明确（视觉重量排序）

## 材质轴

- 光影方向一致、物理合理（`knowledge/visual-quality/COLOR_MATERIAL_LIGHT.md`）
- 纹理不过度、不脏

## 可读性轴

- 对比度（WCAG AA）、字号、行高
- 标题/正文层级、断行控制（`typography.md`）
- 响应式无横向滚动、无两行可点击文本

## 商业适配轴

- 品牌一致性、目标受众匹配
- 文案诚实（真实指标占位而非虚构）
- 商业意图清晰（CTA 层级）

## 人审轴

- 至少 1 位人工评审（设计方向或用户）
- 记录：评审人、日期、boundTreeSha、环境、结论
- 人审不通过 = 整体不通过（即使自动检查全绿）

## 输出

每次评审生成 `JuryRecord`：
```json
{
  "jury_id": "...",
  "boundTreeSha": "...",
  "axes": {"antiSlop": 4, "layout": 3, "material": 4, "readability": 5, "commercial": 4},
  "humanReview": {"reviewer": "...", "date": "...", "verdict": "PASS"},
  "evidence": [{"level": "E3", "artifact": "..."}],
  "verdict": "PASS"
}
```
