---
name: design-lab-core
description: DESIGN-LAB 核心插件：Brief、Direction、Design IR、Human Gate、Jury、Rights、Preflight、Delivery Receipt
version: 0.1.0
author: DTALEX66
license: MIT
---

# DESIGN-LAB Core Plugin

DESIGN-LAB 核心插件，用于 Open Design 主宿主集成。

## 功能

- **Brief 输入**：创建和管理设计需求
- **Direction 锁定**：定义设计方向和约束
- **Design IR 读写**：读取和写入 Design Intermediate Representation
- **Human Gate**：人工审批门（Direction/Quality/Rights/Production/Release）
- **Jury 评审**：专业评审和评分
- **Rights 检查**：权利和许可验证
- **Preflight 验证**：交付前检查
- **Delivery Receipt**：交付收据生成

## 使用

```javascript
// 在 Open Design 中使用
const designLab = await od.plugins.load('design-lab-core');

// 创建 Brief
const brief = await designLab.createBrief({
  title: '品牌系统设计',
  domain: 'brand-identity',
  references: [...],
  constraints: [...]
});

// 锁定 Direction
const direction = await designLab.lockDirection(brief.id, {
  target: '高端科技品牌',
  audience: 'B2B 企业客户',
  brandGuidelines: [...]
});

// 执行 Human Gate
const gateResult = await designLab.humanGate({
  type: 'direction',
  direction: direction,
  approval: 'required'
});
```

## 状态

- 当前版本：0.1.0
- 状态：declared（未启动）
- 证据等级：E0
