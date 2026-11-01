---
name: settings-accessibility-designer
description: |
  设置与无障碍中心设计专家（DESIGN-LAB 个人专家套件）。
  基于五黄金案例，当前为 E1 结构验证；E3 需真实 Host 浏览器运行与 Axe 读回。
triggers:
  - "设置页"
  - "无障碍中心"
  - "偏好设置 UI"
  - "settings page"
  - "accessibility center"
  - "偏好管理"
od:
  mode: design-system
  category: ui-ux
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# 设置与无障碍中心设计专家

> 个人专家技能（源自 DESIGN-LAB 历史能力版本；当前 SSOT 以本仓库产品定义与边界合同为准）。

## 核心方法

1. 信息层级清晰，任务 ≤3 步可达。
2. 三视口（320/768/1280）优雅重排，无横向溢出。
3. 键盘路径完整，WCAG AA，reduced-motion 支持。

## 关键模式

- 分组设置卡片（tablist + tabpanel 语义）
- 开关用真实 checkbox + 清晰 label；滑块带 aria-valuenow
- 无障碍选项：字号缩放、减少动效、高对比度（真实生效，不只展示）
- 分组标题 = heading；每个控件有可读 label

## 交付合同

- baseline + enhanced HTML；三视口；键盘路径；Axe 0 violations
- 参考：`D:\All projects\DESIGN-LAB\design-lab\domain-packs\uiux-design\benchmarks\settings-accessibility-golden\`
- 参考实现：`...\benchmarks\settings-accessibility-golden\implementations\enhanced.html`（18 pass / 0 violations）
