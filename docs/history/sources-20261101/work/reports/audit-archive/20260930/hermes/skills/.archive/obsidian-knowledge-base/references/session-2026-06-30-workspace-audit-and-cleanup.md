# Session 2026-06-30 — Workspace audit, cleanup, and project re-entry

## User workflow/preferences reinforced

- When the user says “我只要最终入库的” or “人工审核文件还是和你说一样，你自己去对比”, do not ask them to manually compare intermediate review files. Compare draft/intermediate files against the formal library yourself, then archive superseded drafts outside the vault and report only the final state.
- User expects project cleanup to keep durable config/rules and remove temporary/project clutter. For Codex workspace cleanup, only `AGENTS.md` remained. For Hermes cleanup, preserve Hermes infrastructure (skills/plugins/config/hermes-agent/auth/memories/state/cron) and clean disposable cache/session/log artifacts.
- When user says “回到这个项目” / “全面梳理，包括课程”, perform a real project audit, not just a verbal recap: inspect workspace, vault, course library, pending-review state, Git status, then write/update control notes.

## Obsidian project re-entry checklist

For this Obsidian knowledge-base project, after returning from cleanup/migration:

1. Verify paths:
   - Workspace: `D:/All projects/Obsidian-Assistance/`
   - Git helper repo: `D:/All projects/Obsidian-Assistance/github/Obsidian-Assistance/`
   - Vault: `E:/BaiduSyncdisk/Obsidian知识库/`
2. Inventory vault areas: `00_主页`, `01_收件箱`, `02_课程库`, `03_知识卡片`, `04_复习卡片`, `80_索引数据库`, `90_模板`, `93_导入报告`, `95_待审核`, `99_附件`.
3. Inventory course library and distinguish:
   - Formal structured course folders, e.g. `02_课程库/知识内化训练营/`
   - Course index/placeholder cards under category folders, e.g. `02_课程库/心理记忆学习力/*.md`
4. Sync status of any index card whose formal library has been completed. In this session, `心理记忆学习力/知识内化训练营：21天北大学霸科学记忆系统（完结）.md` had to be changed from `未开始` to `已正式入库`.
5. Update `02_课程库/01_课程处理工作台.md` with:
   - Current project paths
   - Completed courses
   - Recommended next-course candidates
   - P1 Dataview queue
   - Pending-review Dataview
6. Write a project audit report in `93_导入报告/项目总控梳理_<date>.md`.
7. Mirror concise audit docs into the helper repo under `docs/` and commit/push if the repo is clean.

## Intermediate file handling pattern

When drafts/review files are superseded by formal library content:

- Keep the vault clean: `95_待审核/` should contain only management files such as overview, review conclusion, and verification report.
- Move superseded intermediate files to the project workspace, e.g. `D:/All projects/Obsidian-Assistance/archived-待审核中间文件/`.
- Update `95_待审核/00_待审核总览.md` to state that the course is complete and where archived intermediates live.

## Next-course selection heuristic

After the first full pipeline is complete, choose the next course by balancing value and pipeline risk:

1. Same-domain course with reusable templates (best for stability): e.g. `30天考霸训练营` after `知识内化训练营`.
2. Small single-PDF course (best for quick pipeline verification): e.g. `大模型应用开发介绍-0715.pdf`.
3. Closely related thematic course (best for knowledge graph continuity): e.g. `记忆宫殿`.
