# external-recovery-2026-09-27 — 来源与归属说明

## 来源
历史 agent 会话在 D:/All projects/DESIGN-LAB 工作期间产生的工作暂存：
- `tmp-commit-msgs/`（57 文件）：PR #139–#158 的 poll 脚本、commit/PR 消息草稿
- `tmp-baseline-main.js` / `tmp-rebuild-main.js`：workbench build 基线/重建快照
- `tmp-legacy-b04.css`：旧 B04 样式快照
- `tmp-orig-settings.txt` / `tmp-mine-settings.txt`：settings 对比暂存

## 归属判定
按 project-data-boundary 规则 4：Hermes 工作流/会话暂存属于全局工作流基础设施，
不因文件内容提及项目名而归入业务项目。这些文件**不是** DESIGN-LAB 任务数据，
最初散落在 `.project-local/` 根属误置；上一轮误归档到 `.project-local/archive/spill-2026-09-27/`
（合规壳但未回到正确归属），本轮撤销并迁入本项目专属恢复区
`.project-local/task-artifacts/external-recovery-2026-09-27/`（项目既有惯例）。

## 保留原因
含历史 PR #139–#158 的 poll/merge 脚本与 commit 证据，属可审计历史，不删除；
仅在确认无引用后由 owner 决定最终处置。

## 校验
每个文件/目录在 move 后已做 SHA-256（文件）或 文件数+字节数（目录）回读，全部通过。
