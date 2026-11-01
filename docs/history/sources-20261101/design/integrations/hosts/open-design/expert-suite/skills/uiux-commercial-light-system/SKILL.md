---
name: uiux-commercial-light-system
description: |
  UIUX Commercial Light 设计系统（DESIGN-LAB 个人专家套件）。
  基于五黄金案例，当前为 E1 结构验证；E3 需真实 Host 浏览器运行与 Axe 读回。
triggers:
  - "uiux-commercial-light"
  - "商业 UI 设计系统"
  - "商用浅色主题"
  - "UI 组件库"
  - "design tokens"
od:
  mode: design-system
  category: design-systems
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# UIUX Commercial Light 设计系统

> 个人专家技能（源自 DESIGN-LAB 历史能力版本；当前 SSOT 以本仓库产品定义与边界合同为准）。

## 设计系统：UIUX Commercial Light

跨案例统一视觉合同（V42-0402..0406 五黄金案例共享）。

## Token（29 个 DTCG）

- 主色 `#2563EB`；成功 `#16A34A`；危险 `#DC2626`；警告 `#D97706`
- 背景 `#F4F6F8`；表面 `#FFFFFF`；边框 `#E2E8F0`；文字 `#0F172A` / 次级 `#475569`
- 间距 4/8/12/16/24；圆角 4/8/12/16；字号 12/14/16/20/24/32
- 完整：`D:\All projects\DESIGN-LAB\design-lab\design-systems\uiux-commercial-light\design-tokens.json`

## 组件（19 个）

app-header / side-nav / breadcrumb / tabs / table / data-table-row / search-box /
status-badge / kpi-card / action-button / form-field / select / checkbox / radio-group /
toast / modal / bulk-action-bar / pagination / footer

- 完整：`...\design-systems\uiux-commercial-light\components.manifest.json`

## 使用规则

- 用 Token 不用裸色值；对比度 ≥4.5（WCAG AA）
- 状态徽标用纯色背景 + 深色文字
- 参考 DESIGN.md：`...\design-systems\uiux-commercial-light\DESIGN.md`
