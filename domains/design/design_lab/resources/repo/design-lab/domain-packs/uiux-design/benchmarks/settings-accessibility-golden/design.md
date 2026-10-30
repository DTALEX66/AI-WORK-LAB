# 设置/无障碍黄金案例 — 系统设置与无障碍中心 — DESIGN.md

- 案例：`settings-accessibility-golden`｜方向：direction-b｜版本：0.1.0

## 设计原则
1. 信息层级清晰，任务 ≤3 步可达。
2. 三视口（320/768/1280）优雅重排，无横向溢出。
3. 键盘路径完整，WCAG AA，reduced-motion 支持。
4. 基线 vs 增强对比明确，偏好率 ≥70%。

## 视觉系统
| Token | 值 |
|---|---|
| bg | #F5F6F8 |
| accent | #2B6CB0 |
| text | #1F2933 |
| text-dim | #6B7280 |
| surface | #FFFFFF |
| success | #237A57 |

## 组件
1. `settings-nav`
2. `setting-row`
3. `toggle-switch`
4. `slider-control`
5. `a11y-preview-panel`

## 键盘路径
Tab 遍历 / Enter 激活 / Esc 返回（完整路径见 handoff.md）

## 无障碍
- [x] 语义化结构 [x] 可见焦点 [x] WCAG AA 对比度 [x] reduced-motion [x] aria-label
- [ ] Axe 实跑（V42-0410 冻结）
