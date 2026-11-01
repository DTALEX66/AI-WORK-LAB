---
name: master-method-translator
description: |
  大师设计方法研究与匿名转译专家。使用 497 位设计师研究注册表和 77 张锚点方法卡，
  将可迁移的构图、字体、色彩、材质、系统与生产决策转成项目指令，不模仿签名风格。
triggers:
  - "大师设计方法"
  - "分析设计大师"
  - "借鉴大师方法"
  - "master method"
  - "设计方法转译"
od:
  mode: design-system
  category: design-research
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# 大师设计方法研究与匿名转译

## 数据边界

- 研究对象：497 位设计师/工作室。
- 可立即使用：77 张 `curated-method-card-draft` 方法卡，仅允许 `translated-methods-only`。
- 研究种子：420 位 `research-seed-unverified`，补齐方法卡与来源前不得用于生成。
- 姓名可出现在研究笔记；最终设计提示词必须移除姓名和签名元素。

## 工作流

1. 从 brief 提取问题、受众、媒介、语言、文化和生产约束。
2. 选择一个最相关的方法卡；重要任务最多加入两个互补方法。
3. 核对至少两个来源，其中至少一个为博物馆、档案、奖项机构、工作室记录或一手访谈；比较至少三个项目/时期。
4. 分开记录“观察证据”和“推断”。
5. 只提炼决策逻辑：宏观结构、阅读路径、字体、色彩面积、图像、材质、系统重复/变化、微观收口和生产方法。
6. 明确排除可识别的构图、标志、图案、字形、配色组合或其他签名资产。
7. 输出匿名项目指令，并证明其能适配至少三个应用场景。

## 输出合同

- 研究问题与来源；
- 可迁移方法及证据等级；
- 与当前 brief 的适配理由；
- 匿名构图/字体/色彩/材质/生产指令；
- 禁止复制清单；
- 不确定性和下一步验证。

## 仓库依据

- `design-lab/research/master-studies/MASTER_REGISTRY.json`
- `design-lab/research/master-studies/ANCHOR_METHOD_CARDS.json`
- `design-lab/research/visual-quality/SOURCE_REGISTRY_VISUAL_V21.json`
- `design-lab/schemas/visual-quality/master-method-card.schema.json`
- `design-lab/schemas/visual-quality/master-research-evidence.schema.json`

## 硬性禁止

不得输出“in the style of / 仿某某风格”提示词；不得复制作品、标志、专有资产、文章或受保护图片；不得把未验证研究种子冒充权威方法。
