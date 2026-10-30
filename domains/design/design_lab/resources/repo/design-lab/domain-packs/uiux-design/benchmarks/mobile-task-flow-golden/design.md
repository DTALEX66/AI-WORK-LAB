# Mobile Task Flow — DESIGN.md

- 案例：`mobile-task-flow-golden`｜方向：B（状态流主导）｜版本：0.1.0

## 设计原则

1. **状态即导航**：订单状态时间线是主视觉锚点，用户永远知道"现在在哪一步"。
2. **短任务路径**：核心操作（联系客服/查看详情）≤3 步可达。
3. **键盘完整**：所有交互可 Tab 到达，Enter 激活，Esc 返回。
4. **无障碍优先**：语义化 HTML、可见焦点、WCAG AA 对比度、reduced-motion 支持。

## 视觉系统

| 层 | 规格 |
|---|---|
| 背景 | `--bg: #0E1116`（深色，减少眩光） |
| 主色 | `--accent: #4F8CFF`（状态高亮） |
| 成功 | `--success: #34C77B` |
| 警告 | `--warning: #F5A623` |
| 危险 | `--danger: #E5484D` |
| 文本主 | `--text: #E8ECF1` |
| 文本次 | `--text-dim: #9AA5B1` |

## 布局

- 移动端单列：header（app-title + avatar）→ status-timeline → order-card → quick-reply-bar
- 断点：320 / 375 / 414 / 768（768 起双栏：左侧时间线，右侧详情）

## 组件

1. `app-header`：标题 + 返回 + 头像（sticky）
2. `status-timeline`：垂直时间线，已完成/当前/待办三态
3. `order-card`：订单摘要卡（id、金额、状态徽章）
4. `chat-bubble`：客服/用户消息气泡
5. `quick-reply-bar`：常驻快捷回复（键盘可达）

## 键盘路径

```
Tab: header → timeline(current) → order-card(actions) → quick-reply(edit)
Enter: 激活当前焦点操作
Esc: 聊天返回订单详情
```

## 无障碍

- 全部交互元素有可见 focus ring（2px accent + offset）
- 对比度 ≥ 4.5:1（正文）/ ≥ 3:1（大文本）
- `prefers-reduced-motion` 关闭过渡动画
- 表单控件均有 label 或 aria-label
