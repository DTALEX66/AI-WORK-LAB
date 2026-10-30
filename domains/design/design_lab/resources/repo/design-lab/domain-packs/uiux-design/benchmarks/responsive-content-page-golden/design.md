# 响应式内容页面黄金案例 — 长文内容页 — DESIGN.md

- 案例：`responsive-content-page-golden`｜方向：direction-b｜版本：0.1.0

## 设计原则
1. 信息层级清晰，任务 ≤3 步可达。
2. 三视口（320/768/1280）优雅重排，无横向溢出。
3. 键盘路径完整，WCAG AA，reduced-motion 支持。
4. 基线 vs 增强对比明确，偏好率 ≥70%。

## 视觉系统
| Token | 值 |
|---|---|
| bg | #FFFFFF |
| accent | #0F6BFF |
| text | #111827 |
| text-dim | #4B5563 |
| surface | #F9FAFB |
| success | #15803D |

## 组件
1. `article-header`
2. `toc-nav`
3. `prose-body`
4. `code-block`
5. `data-table`
6. `related-articles`

## 键盘路径
Tab 遍历 / Enter 激活 / Esc 返回（完整路径见 handoff.md）

## 无障碍
- [x] 语义化结构 [x] 可见焦点 [x] WCAG AA 对比度 [x] reduced-motion [x] aria-label
- [ ] Axe 实跑（V42-0410 冻结）
