# B2B 后台黄金案例 — DESIGN.md

- 案例：`b2b-backoffice-golden`｜方向：direction-b｜版本：0.1.0

## 设计原则
1. 高频任务 ≤3 步：导航 → 列表 → 批量条。
2. 总览 KPI 一眼可读（数字优先，趋势为辅）。
3. 批量操作有确认与回退。
4. 键盘全程可达，WCAG AA。

## 视觉系统
| Token | 值 |
|---|---|
| bg | #F4F6F9 |
| accent | #2563EB |
| text | #0F172A |
| text-dim | #64748B |
| surface | #FFFFFF |
| success | #059669 |
| danger | #DC2626 |

## 组件
1. `sidebar-nav` 2. `kpi-card` 3. `data-table` 4. `bulk-action-bar` 5. `detail-drawer`

## 键盘路径
Tab 遍历 / Enter 激活 / Esc 关闭抽屉
