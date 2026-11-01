# Session pattern: Obsidian UI audit + redesign without risking course content

## Trigger
User complains the vault is “不好看/不好用/不丝滑”, asks why other people’s Obsidian knowledge bases look better, or says the left file tree is unreasonable. Treat this as a combined **information architecture + UI + performance** audit, not just CSS polish.

## Safety boundary used in this session
The user explicitly allowed project-level changes but set boundaries:
- Do not delete E: vault/course data.
- Do not touch D: installed software.
- Do not touch C: system files.
- Course content must not be lost; if reorganizing, prefer navigation/bookmarks/index pages over moving course notes.

## What to audit first
Read-only discovery before writes:
1. `.obsidian/appearance.json` — theme, accent, enabled snippets.
2. `.obsidian/app.json`, `core-plugins.json`, `community-plugins.json`, `workspace.json`, `bookmarks.json`.
3. `.obsidian/snippets/*.css` and `.obsidian/themes/`.
4. Top-level vault folders and course folder structure.
5. Large markdown files and large plugin data files.
6. Existing dashboards: `00_主页/00_知识库总控台.md`, `02_课程库/00_课程库总览.md`, `02_课程库/01_课程处理工作台.md`.

## Durable diagnoses from this session
- A vault can have good content but still feel bad if the “use structure” is missing: Hero dashboard, curated entry cards, bookmarks, course map, and a predictable left-nav flow.
- Raw file tree is a storage structure, not a user-facing navigation structure. Do not force the user to browse every folder.
- If formal courses and category/index files are mixed under `02_课程库`, avoid moving content first. Build a `课程地图` page and curated bookmarks instead.
- Stale dashboard numbers make the vault feel untrustworthy. Recompute or simplify counts instead of hard-coding fake progress.
- Very large generated markdown indexes and heavy real-time AI plugins can make the vault feel unsmooth even if CSS is good.
- Old bookmark paths are a common reason the left panel feels broken after renames (`01_收集箱` vs `01_收件箱`, `98_待人工审核确认` vs `95_待审核`).

## Recommended implementation pattern
1. Back up changed config/files outside plugin directories, preferably under the project workspace backup area.
2. Add a class-level CSS snippet such as `obsidian-knowledgeos-pro.css` rather than editing theme files.
3. Enable snippets in order: base → dashboard → deep UI → pro override.
4. Rebuild homepage as a premium dashboard:
   - Hero block
   - live-ish status cards
   - quick entry cards
   - current state / next action callouts
   - Dataview recent updates
5. Add `00_主页/03_左侧导航与课程地图.md` as the curated navigation layer.
6. Rewrite `.obsidian/bookmarks.json` into grouped left-nav sections:
   - 总控
   - 课程处理
   - 学习输出
   - 运维报告
7. Open Obsidian workspace to homepage in preview mode and set left panel to bookmarks when possible.
8. For smoothness, consider disabling heavy real-time plugins from `community-plugins.json` rather than deleting plugin directories. Make this reversible and report it clearly.
9. Verify JSON parses, snippets exist, markdown files are readable, plugin list is valid, and local git status/commit if the vault uses local-only git.

## Important UX lesson
When the user shows frustration (“卡了吗”, “为什么还是不好看”), answer directly and keep moving. Avoid long defensive explanations. State the blocker if any, then provide the next executable step.