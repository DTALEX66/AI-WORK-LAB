---
name: style-lineage-composer
description: |
  设计风格谱系分析与组合专家。基于 47 条谱系和 47 张分析卡，将历史/地域设计语法
  转成匿名、项目特定的构图、字体、色彩、材质和空间规则，避免表面化复古与大师模仿。
triggers:
  - "风格谱系"
  - "设计风格分析"
  - "视觉方向组合"
  - "style lineage"
  - "风格 DNA"
od:
  mode: design-system
  category: art-direction
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# 风格谱系分析与组合

## 选择规则

1. 先匹配 brief 的问题与媒介，不按流行标签选风格。
2. 只选一个主谱系；最多两个辅助谱系。
3. 单个辅助谱系只允许改变一个主要工艺层；任一历史谱系影响上限 30%。
4. 表达性体系必须搭配可读性/生产约束；理性体系必须加入项目特定的情感或文化反重力。
5. 最终提示词删除谱系名和设计师名，只保留匿名工艺指令。

## 分析维度

- 核心问题与历史媒介；
- 构图与阅读路径；
- 字体和多语言关系；
- 色彩面积比例；
- 图像、摄影、插画和材质；
- 间距、重复、节奏与例外；
- 动效/时间与空间行为；
- 商业应用、质量信号和失败模式。

## 输出合同

- 主谱系与辅助谱系的选择理由；
- 冲突与层级；
- 匿名 craft grammar；
- 项目化 token/组件/版式建议；
- 禁止使用的表面符号和签名元素；
- 三个应用场景的一致性检查。

## 仓库依据

- `design-lab/research/style-lineages/STYLE_LINEAGES.json`
- `design-lab/research/style-lineages/STYLE_ANALYSIS_CARDS.json`
- `design-lab/schemas/visual-quality/style-lineage.schema.json`
- `packages/capabilities/atoms/style-lineage-mapper/SKILL.md`
- `packages/capabilities/atoms/style-vector-builder/SKILL.md`
