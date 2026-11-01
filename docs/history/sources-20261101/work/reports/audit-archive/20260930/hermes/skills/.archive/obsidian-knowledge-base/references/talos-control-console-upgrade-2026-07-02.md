# TALOS control console upgrade pattern — 2026-07-02

Use when the user asks to make the Obsidian vault a “TALOS 系统控制台”, “极限增强 OBS 知识库界面”, or wants a command-center style KnowledgeOS rather than isolated CSS tweaks.

## Goal

Turn the vault usage layer into a system console while preserving the storage layer:

- `00_主页/00_知识库总控台.md` becomes the command console.
- Add module pages for mission/radar, V6 evidence, V7 projects, courses, and logs.
- Update the scoped CSS snippet and Obsidian bookmarks.
- Keep course folders, source notes, evidence files, and attachments in place.

## Pages that worked

Create or refresh these pages under `00_主页/`:

- `00_知识库总控台.md` — hero, real stats, active course, quick actions.
- `01_TALOS任务雷达.md` — current mission boundaries and next actions.
- `02_TALOS证据矩阵.md` — V6 evidence status and verified evidence links.
- `03_TALOS项目推进台.md` — V7 project conversion status and project pages.
- `04_TALOS课程指挥舱.md` — curated entry list for formal course folders.
- `05_TALOS系统日志.md` — Dataview report/log feed.

## Important implementation rules

1. Re-entry after compression: verify git status and latest commit first. If the TALOS commit already exists and validation passes, do not rewrite; only sync todos.
2. Use real counts, not stale dashboard numbers. Count courses, V6 metadata, V7 project pages, review cards, knowledge cards, and reports from disk.
3. Back up touched pages/configs before writing, outside `.obsidian/plugins/`, e.g. `93_导入报告/<date>_TALOS_ui_backup/backups/`.
4. Keep `.obsidian/appearance.json` focused: enable the `talos-dashboard` snippet and set an accent color; do not scatter many snippets unless needed.
5. Rewrite `.obsidian/bookmarks.json` as the curated left navigation layer: TALOS console, active/demo course, and system modules.
6. Validate before commit:
   - JSON parses: `appearance.json`, `bookmarks.json`.
   - all generated `href="..."` targets exist.
   - Markdown fences are balanced.
   - no obvious mojibake markers.
7. Commit locally only; do not push the formal vault.

## Proven safety checks

A minimal Python check should load both JSON configs, scan all `00_主页/*TALOS*.md` plus `00_知识库总控台.md`, verify fence parity, mojibake markers, and every `href` target under the vault. Fix any typo immediately before committing.

## Styling notes

The scoped `talos-dashboard.css` can include:

- dark command-console background and cyan/purple variables;
- large hero cards with grid overlay and glowing “TALOS” orb;
- `.talos-grid-3/4/5`, `.talos-card`, `.talos-stat`, `.talos-btn`;
- hover lift and cyan border glow;
- responsive collapse to 2 columns / 1 column;
- sidebar active-file highlight and tab accent.

Scope styles to `.knowledgeos-v5` and `.talos-dashboard` so the snippet enhances the command layer without breaking normal notes.

## Boundary language

Make the dashboard explicit:

- raw file tree = storage layer;
- TALOS pages/bookmarks = command/usage layer;
- V6 evidence still requires real local sources;
- V7 project pages organize action but do not add course facts.
