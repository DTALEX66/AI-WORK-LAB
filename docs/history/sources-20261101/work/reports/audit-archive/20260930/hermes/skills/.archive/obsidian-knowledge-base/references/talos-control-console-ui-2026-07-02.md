# TALOS Control Console UI Upgrade — 2026-07-02

## When to use

Use when the user asks to make the Obsidian vault feel like a TALOS/system-control console, says to “极限增强 OBS 知识库界面”, or repeatedly says “继续” after a dashboard upgrade.

## Durable pattern

Treat the vault as two layers:

- **Storage layer**: course notes, evidence pages, cards, reports. Do not move/delete these for aesthetics.
- **Control layer**: dashboard pages, bookmarks, scoped CSS, reports, and backups. Aggressively improve this layer.

## Pages created in the proven TALOS pass

Under `00_主页/`:

- `00_知识库总控台.md` — command-console homepage with real counts, hero, metrics, quick actions.
- `01_TALOS任务雷达.md` — mission/risk/next-action radar.
- `02_TALOS证据矩阵.md` — V6 evidence state panel.
- `03_TALOS项目推进台.md` — V7 project-conversion console.
- `04_TALOS课程指挥舱.md` — all formal courses as a command layer.
- `05_TALOS系统日志.md` — reports/audit log panel.
- `06_TALOS领域作战地图.md` — courses grouped into domains.
- `07_TALOS项目Kanban.md` — Ready / Evidence-backed / Project Drafted / Need Source / Review columns.
- `08_TALOS证据热力图.md` — V6/V7/metadata/review/knowledge-card heatmap.

## Implementation rules

1. Start with git/status and real counts from disk. Do not reuse stale dashboard numbers.
2. Back up changed UI/config files under `93_导入报告/<date>_TALOS_*/backups/` before writing.
3. Update `.obsidian/bookmarks.json` as the curated left navigation. Do not depend on raw file tree UX.
4. Keep CSS scoped through `knowledgeos-v5`, `talos-dashboard`, or page-specific classes. Prefer extending `.obsidian/snippets/talos-dashboard.css` over creating many snippets.
5. Validate JSON (`appearance`, `bookmarks`, `community-plugins`), Markdown fences, mojibake markers, and generated `href="..."` targets before committing.
6. Commit the formal vault locally only; do not upload vault content.

## TALOS modules and next-step logic

- If only the homepage exists, add task radar, evidence matrix, project console, course command, and system log first.
- If the user continues, add field command map, project Kanban, and evidence heatmap in separate verified commits.
- After Kanban + heatmap, the next natural layer is V8: active training / daily task generation / execution logs, or batch V7 `13_项目转化.md` pages.

## Pitfalls discovered

- Bash heredocs can break on large Chinese/HTML/CSS strings. Prefer Python file writes via tools or a Python script rather than huge shell heredocs.
- It is easy to mistype Chinese paths inside `href`. Always run an explicit href-target checker after writing.
- Context compression may preserve stale task state. On re-entry, verify disk/git first; if the TALOS commit already exists and checks pass, mark preserved todos complete instead of rewriting.
