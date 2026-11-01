---
name: b2b-backoffice-designer
description: |
  B2B 后台工作台设计专家（DESIGN-LAB 个人专家套件）。
  基于五黄金案例，当前为 E1 结构验证；E3 需真实 Host 浏览器运行与 Axe 读回。
triggers:
  - "B2B 后台"
  - "运营工作台"
  - "管理后台 UI"
  - "b2b dashboard"
  - "admin console"
  - "工单系统"
od:
  mode: design-system
  category: ui-ux
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# B2B 后台工作台设计专家

> 个人专家技能（源自 DESIGN-LAB 历史能力版本；当前 SSOT 以本仓库产品定义与边界合同为准）。

## 核心方法

1. 高频任务 ≤3 步：导航 → 列表 → 批量条。
2. 总览 KPI 一眼可读（数字优先，趋势为辅）。
3. 批量操作有确认与回退（bulk-bar 模式）。
4. 表格：状态徽标对比度 ≥4.5；行操作可见；全选/批量条键盘可达。

## 关键模式

- 侧栏导航 + 顶栏 + KPI 卡片区 + 表格主区
- 状态徽标：纯色背景 + 深色文字（如 open `#1D4ED8`、done `#047857`、waiting `#475569`）
- 工具栏：状态筛选 combobox + 搜索框 + 批量操作条

## 交付合同

- baseline + enhanced HTML；三视口；键盘路径；Axe 0 violations
- 参考：`D:\All projects\DESIGN-LAB\design-lab\domain-packs\uiux-design\benchmarks\b2b-backoffice-golden\`
- 参考实现：`...\benchmarks\b2b-backoffice-golden\implementations\enhanced.html`（19 pass / 0 violations）
