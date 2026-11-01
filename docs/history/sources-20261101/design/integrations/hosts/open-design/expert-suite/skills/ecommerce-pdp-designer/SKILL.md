---
name: ecommerce-pdp-designer
description: |
  电商 PDP/结算设计专家（DESIGN-LAB 个人专家套件）。
  基于五黄金案例，当前为 E1 结构验证；E3 需真实 Host 浏览器运行与 Axe 读回。
triggers:
  - "电商 PDP"
  - "商品详情页"
  - "结算流程"
  - "checkout flow"
  - "ecommerce product page"
  - "购物车"
od:
  mode: design-system
  category: ui-ux
  upstream: "https://github.com/DTALEX66/DESIGN-LAB"
---

# 电商 PDP/结算设计专家

> 个人专家技能（源自 DESIGN-LAB 历史能力版本；当前 SSOT 以本仓库产品定义与边界合同为准）。

## 核心方法

1. 信息层级清晰，任务 ≤3 步可达（选规格 → 加购 → 结算）。
2. 三视口（320/768/1280）优雅重排，无横向溢出。
3. 键盘路径完整，WCAG AA，reduced-motion 支持。

## 关键模式

- 商品图 + 标题 + 价格 + 规格选择（radiogroup + aria-checked）+ 促销徽标 + 加购/结算
- 结算步骤条 + 表单校验错误关联（aria-describedby）
- 促销徽标：对比度 ≥4.5（如 `#A8271F` 文字 + 深色背景）

## 交付合同

- baseline + enhanced HTML；三视口；键盘路径；Axe 0 violations
- 参考：`D:\All projects\DESIGN-LAB\design-lab\domain-packs\uiux-design\benchmarks\ecommerce-pdp-checkout-golden\`
- 参考实现：`...\benchmarks\ecommerce-pdp-checkout-golden\implementations\enhanced.html`（22 pass / 0 violations）
