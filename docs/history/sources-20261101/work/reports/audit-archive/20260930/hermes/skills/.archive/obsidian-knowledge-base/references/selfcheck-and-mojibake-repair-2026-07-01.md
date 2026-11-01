# Obsidian vault self-check and mojibake repair pattern — 2026-07-01

## When this applies
Use after a long autonomous course-import loop, after context compression, or when the user says “开始自检”. The goal is to stop further course processing, verify the vault health, repair only confirmed defects, and leave a clean local commit.

## Proven self-check sequence
1. Load `obsidian-knowledge-base` and create a short todo list for the audit.
2. Run read-only checks first:
   - `git status --short` and recent `git log --oneline`.
   - Parse core JSON: `.obsidian/bookmarks.json`, `.obsidian/appearance.json`, `.obsidian/community-plugins.json`, QuickAdd, Obsidian Git, cmdr, Omnisearch, and any known plugin config touched recently.
   - Scan markdown under the user-facing vault areas (`00_主页`, `02_课程库`, `03_知识卡片`, `04_复习卡片`, `80_索引数据库`, `93_导入报告`) for empty files, href targets, broken frontmatter, and mojibake markers.
   - Count formal course directories (`02_课程库/<course>/00_课程总览.md`) and import reports (`93_导入报告/*_导入报告.md`) to ensure the course loop is internally consistent.
3. Treat preserved task lists as hints only. Confirm disk/git state before deciding something is incomplete.

## Mojibake detection
Scan for common UTF-8/GBK corruption markers such as:
`鐭`, `璇`, `鍗`, `绋`, `銆`, `€`, `锟斤拷`, `Â`.

If the scan finds corrupted aggregate/index files:
1. Read the corrupted file to confirm it is truly unreadable.
2. Look for authoritative clean sources already in the formal course folder (e.g. `02_课程库/<course>/08_术语索引.md`, course portal, clean split knowledge cards).
3. Back up the corrupted files outside the vault plugin tree, e.g. `D:/All projects/Obsidian-Assistance/archived-config-backups/selfcheck-mojibake-fix-<timestamp>/`.
4. Rebuild the aggregate/index from the clean formal course artifacts. Do not invent course-specific claims beyond the existing clean material.
5. Re-run JSON/href/mojibake/frontmatter checks.
6. Commit only the repaired files with a focused message, e.g. `fix: repair knowledge internalization mojibake indexes`.

## Important distinction: naming differences are not missing content
Older formally imported courses may use non-new-template filenames such as:
- `01_课程素材识别报告.md` instead of `01_素材识别报告.md`
- `03_课程完整总结.md` or `03_章节总结.md` instead of `03_模块总结.md`
- segmented summaries like `03_逐节课完整总结_Day00-05.md`

Do not rewrite or rename these just to satisfy a rigid checker if links are valid and course content is complete. Report them as naming differences, not defects.

## Final reporting
Report concrete counts: git clean status, latest commit, JSON status, formal course count, import report count, empty files, missing hrefs, frontmatter issues, mojibake count, repaired files, backup path, and commit hash.