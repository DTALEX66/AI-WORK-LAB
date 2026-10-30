# MINIGAME Design Domain Pack

这是 Open Design 的设计领域包，不是小游戏产品平台。

## 包含

- 竖屏移动端布局、Safe Area 和触控热区；
- CCTV 主视觉、工业控制台材质和 HUD 信息层级；
- 正常、异常、危险状态；
- 低文本密度、图标优先和响应式规则；
- 视觉 QA、交互 QA、Runtime Fixture Smoke 和实现交接。

## 排除

本包不提供广告、收入、平台发布、AppID、玩家运营、产品 Analytics、多游戏合集或商业 Release Pipeline。

## 核心循环

```text
读取规则 → 观察 CCTV → 对比楼层/人数/门状态
→ 必要时调查 → 放行或封锁 → 承担后果 → 因果复盘
```

MINIGAME 产品源码仍保留在历史路径，不由本 Domain Pack 自动复制、移动或删除。

事实源边界见 [`SOURCE_OF_TRUTH.md`](SOURCE_OF_TRUTH.md)：领域合同以
`manifest.json` 为准，运行验证只使用仓内 `fixtures/domains/game-visual/` fixture；外部历史
目录不是第二个 live source。
