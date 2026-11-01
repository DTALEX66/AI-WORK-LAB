# Open Design visual directory handoff for Obsidian/TALOS

Use this reference when the user asks to push Obsidian/TALOS work to OPEN DESIGN, extract a designer brief, or form a new visual directory based on existing visual design.

## User preference / durable lesson

The user wants OPEN DESIGN to form a **visual usage-layer directory** from the TALOS/Purple Gemstone design, not to reorganize the storage layer.

Key interpretation:

- Build a new IA/navigation layer that looks like a TALOS KnowledgeOS command console.
- Do **not** move, rename, delete, or rewrite real course content under `02_课程库/`.
- Do **not** move or alter `E:/学习数据`; it is the raw learning-material drive.
- Treat `93_导入报告/` as the staging/report/intermediate-output area.
- Treat `99_附件/verified-keyframes`, `99_附件/course-reference-images`, and `99_附件/course-visuals` as asset layers exposed through Evidence UI, not as folders users should browse manually.
- The user cares about visible entry points, no vertical text, and Obsidian shell + content-page design together.

## Workflow

1. Inspect existing TALOS/Open Design context before writing:
   - `TALOS-frontend-design/brand-spec.md`
   - `TALOS-frontend-design/index.html`
   - `TALOS-frontend-design/EXECUTION_BOUNDARY.md`
   - `TALOS-frontend-design/critique.json`
   - `.obsidian/plugins/talos-frontend-ui/preview.html`
   - `00_主页/36_TALOS_UI_UX_Design_Handoff.md`
2. Produce a concise, copy-ready brief under `TALOS-frontend-design/`, e.g. `OPEN_DESIGN_新目录生成任务书.md`.
3. Include a direct OPEN DESIGN prompt plus structured sections:
   - design principles
   - new visual directory tree
   - left navigation / Bookmarks grouping
   - page responsibilities
   - component and state list
   - migration/mapping strategy
   - Figma frame suggestions
   - Obsidian implementation cautions
4. Explicitly label the new structure as **使用层目录 / visual directory**, not the physical storage layout.
5. Verify the written Markdown for:
   - file exists
   - valid frontmatter pair
   - no mojibake markers
   - no dangerous deletion language
   - references to evidence boundaries

## Recommended visual directory skeleton

```text
00_TALOS_Command_Center/
01_TALOS_Learning/
02_TALOS_Evidence/
03_TALOS_Review_AI/
04_TALOS_Project_Atlas/
05_TALOS_OER_Crosswalk/
06_TALOS_Automation_Log/
07_TALOS_Settings_Plugin/
```

## Storage mapping to preserve

| Visual layer | Existing storage/source |
|---|---|
| Command Center | `00_主页/*TALOS*` |
| Learning | `02_课程库/` |
| Evidence | `99_附件/verified-keyframes`, course `12_真实截图与关键帧.md` |
| Review | `04_复习卡片/`, Review pages |
| Project Atlas | course `13_项目转化.md`, TALOS Kanban pages |
| OER | course `14_开放知识交叉对比.md`, OER reports |
| Automation Log | `93_导入报告/` |
| Settings/Plugin | `TALOS-frontend-design/`, `.obsidian/plugins/talos-frontend-ui/` |

## Evidence boundary language to include

- `verified-keyframes` = true screenshots/keyframes/PDF source pages.
- `course-reference-images` = reference images, not verified course evidence.
- `course-visuals` = generated visual/structural graphics, not evidence.
- OER/open websites = crosswalk/context, not local-course evidence.
- AI summaries are not evidence.

## Good deliverable shape

A single Markdown handoff file that the user can paste into OPEN DESIGN, with a first section containing a plain prompt block and later sections containing concrete IA/navigation details.