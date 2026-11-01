# Observer 信息架构（WLR-820/830/840）

> 正式页面（WLR-820）：Overview / Executions / Projects / Delivery / Trust

## 当前实现（React frontend 8 视图）与 IA 映射

| WLR-820 正式页面 | 当前视图 | 状态 |
|---|---|---|
| Overview（正在发生/阻塞/不可信数据）| 总览 | 已有（KPI+Agent+成本+资源）|
| Executions（trace/waterfall）| 执行 + 时间线 | 已有（timeline）|
| Projects（主体项目）| 项目平台 | 已有（snapshotToServices）|
| Delivery（Git/CI/exact-SHA）| 交付（待补）| IN_PROGRESS |
| Trust（freshness/provenance）| 监控/设置 | 部分（live/数据源）|

## 视觉系统（WLR-830）

- Dark/Light x Full/Compact：tailwind tokens 已有（bg 0d1117 / panel 161b22 / primary 00d4ff）
- 未知/离线/过期视觉可区分：UNKNOWN 文本 + 颜色（非唯一编码）

## 可访问性（WLR-840）

- WCAG 2.2 AA：aria-label/semantic table 已有部分
- 待补：axe 审计 + 键盘导航 + reduced motion（PENDING，需门禁）