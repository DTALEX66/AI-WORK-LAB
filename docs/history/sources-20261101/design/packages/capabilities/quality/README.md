# quality — Visual Quality Jury

DL-QLT-001：Visual Quality Jury V1。质量门基于**可执行评分 + 人审**，不用单张 AI 图作为通过证据（任务包 K 节 Quality gate）。

## 结构

```text
quality/
├─ jury/              # Jury 评分体系（6 轴 × 1-5 分）
│  ├─ JURY_MODEL.md   # 评分模型与阈值
│  ├─ axes/           # 每轴细则
│  ├─ anti-slop.md    # 反 AI 味（吸收 hallmark slop-test）
│  ├─ layout.md       # 布局与节奏
│  ├─ material.md     # 材质与光影
│  ├─ readability.md  # 可读性与排版
│  ├─ commercial.md   # 商业适配与品牌
│  └─ human.md        # 人审流程（Rubric + 人审，非单张 AI 图）
├─ regression/        # 视觉回归（跨端读回）
└─ fixtures/          # 评分 fixture 与 benchmark cases
```

## Jury 六轴（V1）

| 轴 | 内容 | 评分 |
|---|---|---|
| 反 AI 味 | 结构多样性、无模板味、无 AI 默认（紫渐变/居中 hero/三卡/Inter+slate） | 1-5 |
| 布局 | 节奏、层级、留白、宏结构选择 | 1-5 |
| 材质 | 光影、纹理、物理合理性 | 1-5 |
| 可读性 | 排版、对比度、无障碍、响应式 | 1-5 |
| 商业适配 | 品牌一致性、目标受众、商业意图 | 1-5 |
| 人审 | 人工评审记录（非 AI 自评） | pass/fail |

**通过标准**：每轴 ≥3 分 + 人审 pass + 确定性检查通过。任何轴 <3 触发修订。

## 证据纪律

- 静态文件只证明 E1；视觉验收需要**真实渲染读回**（官方模拟器/实机截图）为 E3
- 不把"AI 生成图"当通过证据（任务包 Quality gate）
- 每次评审记录：boundTreeSha、时间、环境、工具版本、输入 hash、评审人

## 关联

- 反 AI 味细则吸收自 `knowledge/visual-quality/hallmark/references/slop-test.md`
- 布局/排版细则参考 `knowledge/visual-quality/hallmark/references/structure.md`、`layout-and-space.md`
- 商业适配参考 `knowledge/visual-quality/hallmark/references/copy.md`
