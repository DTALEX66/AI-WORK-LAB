# design-lab-core 插件

> DESIGN-LAB 核心插件，用于 Open Design 主宿主集成。

## 功能

- Brief 输入与解析
- Direction 锁定
- Design IR 读取/写入
- Human Gate（Direction/Quality/Rights/Production/Release）
- Jury 评审
- Rights 检查
- Preflight 验证
- Delivery Receipt

## 安装

```bash
# 通过 Open Design CLI 安装
od plugin install ./design-lab-core
```

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
const direction = await designLab.lockDirection(brief, {
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

## 目录结构

```
design-lab-core/
├── manifest.json          # 插件清单
├── src/
│   ├── index.js           # 入口
│   ├── brief.js           # Brief 处理
│   ├── direction.js       # Direction 处理
│   ├── design-ir.js       # Design IR 读写
│   ├── human-gate.js      # Human Gate 状态机
│   ├── jury.js            # Jury 评审
│   ├── rights.js          # Rights 检查
│   ├── preflight.js       # Preflight 验证
│   └── receipt.js         # Delivery Receipt
├── schemas/
│   ├── brief.schema.json
│   ├── direction.schema.json
│   └── gate.schema.json
└── tests/
    └── test-core.js
```

## 状态

- 当前版本：0.1.0
- 状态：declared（未启动）
- 证据等级：E0

## 下一步

1. 实现 Brief 输入/解析
2. 实现 Direction 锁定
3. 实现 Human Gate 状态机
4. 集成 Design IR v2
5. 测试真实 brief 流程
