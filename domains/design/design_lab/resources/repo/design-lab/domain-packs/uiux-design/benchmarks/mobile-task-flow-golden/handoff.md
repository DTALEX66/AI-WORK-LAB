# Mobile Task Flow — Handoff

- 案例：`mobile-task-flow-golden`｜版本：0.1.0｜状态：READY_FOR_REVIEW

## 交付物

| 文件 | 格式 | 可编辑 |
|---|---|---|
| `implementations/enhanced.html` | HTML（含 CSS 内联） | ✅ |
| `implementations/baseline.html` | HTML | ✅ |
| `tokens.json` | DTCG JSON | ✅ |
| `design.md` | Markdown | ✅ |
| `case.json` | JSON（方向/组件/验收） | ✅ |

## 组件清单

1. `app-header` — sticky 顶部栏（返回/标题/头像）
2. `status-timeline` — 垂直状态时间线（done/current/warn/upcoming）
3. `order-card` — 订单摘要卡 + 状态徽章
4. `chat-bubble` — 客服/用户消息气泡（role=log aria-live）
5. `quick-reply-bar` — 常驻快捷回复（label + input + submit）

## 键盘路径

```
Tab: 返回 → 状态时间线(当前项) → 订单卡 → 回复输入 → 发送
Enter: 激活焦点操作
Esc: （聊天）返回订单详情
```

## 无障碍清单

- [x] 语义化（header/main/section/article/ol/form/label）
- [x] 可见焦点（:focus-visible 2px accent）
- [x] WCAG AA 对比度（深色方案正文 ≥7:1）
- [x] reduced-motion 支持
- [x] aria-label 补全（图标按钮/隐藏标题）
- [ ] Axe 实跑（待 V42-0410 浏览器验证）

## Provenance

- 生成：Hermes（DESIGN-LAB），Open Design 0.18.x 运行时
- 参考：项目内部 minigame-mobile-controls（owned）、WCAG 2.2（reference-only）
- 证据卡：`../evidence/mobile-task-flow-golden.json`（E1 结构）
