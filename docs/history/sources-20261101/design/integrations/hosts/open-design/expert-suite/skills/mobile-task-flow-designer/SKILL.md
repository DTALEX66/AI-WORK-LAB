---
name: mobile-task-flow-designer
description: |
  移动端任务流 UI 设计专家（DESIGN-LAB 个人专家套件）。
  基于五黄金案例，当前为 E1 结构验证；E3 需真实 Host 浏览器运行与 Axe 读回。
triggers:
  - "移动端任务流"
  - "预约小程序 UI"
  - "订单追踪界面"
  - "mobile task flow"
  - "任务型小程序"
  - "预约流程设计"
od:
  mode: design-system
  category: ui-ux
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# 移动端任务流 UI 设计专家

> 个人专家技能（源自 DESIGN-LAB 历史能力版本；当前 SSOT 以本仓库产品定义与边界合同为准）。

## 核心方法

1. **状态即导航**：订单状态时间线是主视觉锚点，用户永远知道"现在在哪一步"。
2. **短任务路径**：核心操作（联系客服/查看详情）≤3 步可达。
3. **键盘完整**：所有交互可 Tab 到达，Enter 触发，焦点可见（:focus-visible）。
4. **无障碍**：WCAG AA；语义结构 banner/main/region/log/form；Axe critical/serious = 0。
5. **动效克制**：尊重 prefers-reduced-motion。

## Token（uiux-commercial-light 子集）

- 背景 `#0E1116`，表面 `#171C24`，主色 `#4F8CFF`（低对比度场景用 `#3D7EFF`）
- 成功 `#34C77B`；徽标用纯色背景 + 深色文字（对比度 ≥4.5）
- 间距 4/8/12/16/24；圆角 8/12/16；字号 12/14/16/20/24

## 交付合同

- baseline + enhanced 两个可编辑 HTML；三视口（360/390/430）响应式
- 键盘路径文档；Axe 扫描报告（0 critical/serious）
- 完整参考：`D:\All projects\DESIGN-LAB\design-lab\domain-packs\uiux-design\benchmarks\mobile-task-flow-golden\`

## 参考实现（已通过 Axe 验证）

`...\benchmarks\mobile-task-flow-golden\implementations\enhanced.html`（23 pass / 0 violations）
