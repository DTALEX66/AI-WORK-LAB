# TALOS 控制台与 V8 主动训练层模式 — 2026-07-02

## Trigger

User asks to “极限增强 OBS/Obsidian 知识库界面”, “成为 TALOS 系统控制台”, or repeatedly says “继续” after V6/V7 evidence/project work.

## Core approach

Treat the vault as two layers:

- **Storage layer**: real course folders, evidence, cards, reports. Do not move/delete/reclassify these just to make the UI look better.
- **Usage/control layer**: TALOS dashboard pages, bookmarks, scoped CSS, Kanban, heatmaps, active-training pages. Improve this aggressively.

Always use true counts from disk; do not keep stale homepage numbers. Back up touched dashboards/config/CSS under `93_导入报告/<date>_<topic>/backups/` before overwrite.

## Proven TALOS page stack

Build/extend in coherent layers, committing after each safe layer:

1. `00_主页/00_知识库总控台.md` — hero, real stats, core module cards.
2. `01_TALOS任务雷达.md` — current boundaries, next actions, risks.
3. `02_TALOS证据矩阵.md` — V6 evidence state; candidate != evidence.
4. `03_TALOS项目推进台.md` — V7 project conversion entry.
5. `04_TALOS课程指挥舱.md` — all formal course entries.
6. `05_TALOS系统日志.md` — reports/audits.
7. `06_TALOS领域作战地图.md` — domains as operating map, not folder moves.
8. `07_TALOS项目Kanban.md` — columns such as Evidence-backed / Project Drafted / Ready / Need Source.
9. `08_TALOS证据热力图.md` — V6/V7/metadata/review/knowledge-card coverage.
10. `09_TALOS主动训练中心.md`, `10_TALOS每日任务生成器.md`, `11_TALOS执行日志.md` — V8 execution loop.

## V8 active-training loop

Use this loop once V6/V7 structure exists:

1. Evidence: choose one real V6 evidence point if available.
2. Recall: answer before looking; then correct.
3. Project: execute one 25-minute action from `13_项目转化.md`.
4. Log: record action, evidence/link, blocker, next step.

V8 pages are execution scaffolds, not new course facts. They must point back to course notes/evidence/project pages.

## Refresh patterns

- After adding project pages, refresh Kanban counts and heatmap stats.
- When V7 project pages are applied in batch, keep V6 cells strict: courses without real source remain “Need Evidence”, not “verified”.
- In Markdown link checks, strip `#anchor` from `href="file.md#^block"` before testing file existence.
- If old short wikilinks in a touched hub point to files in subdirectories, fix them to full vault-relative paths as part of the same verification pass.

## Verification checklist

- JSON parses: `.obsidian/appearance.json`, `.obsidian/bookmarks.json`, `.obsidian/community-plugins.json`.
- Generated `href` targets exist after stripping anchors.
- Generated wikilinks resolve either vault-relative or current-folder relative.
- Markdown fences are balanced.
- No mojibake markers such as `鐭`, `璇`, `鍗`, `绋`, `銆`, `�` in touched notes.
- Local-only git commit. Do not push the formal vault.

## User style/workflow signal

When this user sends repeated “继续”, treat it as permission to continue the next coherent, safe layer without asking micro-choices. Still keep each layer bounded: backup → write → validate → commit → update todo → continue only if safe.