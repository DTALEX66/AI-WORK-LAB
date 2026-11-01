# OBS backend responsibility: course ingestion first, frontend indices second (2026-07-07)

## Trigger

During an OBS/Open Design/frontend-bridge discussion, the user corrected the agent: the backend responsibility was described too narrowly as indexes, Bridge, and frontend support. The user pointed out that the agent also owns **course transformation and formal vault ingestion**.

## Durable lesson

When working on this user's OBS/Obsidian system, always distinguish these layers, but do not forget the primary backend responsibility:

1. **Primary backend: course transformation + formal ingestion**
   - Select source course/material from `E:/学习数据`.
   - Identify materials and source completeness.
   - OCR/transcribe/extract PDF/video/audio evidence as needed.
   - Verify from real local sources.
   - Generate course pages, workflows, terms, knowledge cards, review cards, evidence pages, project conversion, OER crosswalk, import reports.
   - Write to the formal local vault only: `E:/BaiduSyncdisk/Obsidian知识库`.
   - Commit the vault locally; never upload the private vault.

2. **Secondary backend: evidence + processing ledger**
   - Maintain where transformed data lives: `93_导入报告`, `99_附件/verified-keyframes`, `99_附件/course-reference-images`, `99_附件/course-visuals`, per-course pages.
   - Produce a transformation/product ledger mapping `source -> scan/report -> generated assets -> registry -> course page -> verification status -> next action`.

3. **Frontend support: safe read-only indices**
   - Generate lightweight files such as `obs-course-index.json`, `obs-evidence-index.json`, `obs-report-index.json`, `obs-transform-ledger.json`.
   - These serve OBS/Open Design/plugin/Bridge UI and must not replace real course ingestion.

4. **Helper repo engineering**
   - Maintain reusable scripts/tests/templates in `D:/All projects/Obsidian-Assistance`.
   - Keep real course content, private vault notes, source media, transcripts/OCR full text, and `.obsidian` runtime configs out of the helper repo.

## Correct next-step ordering after frontend/Open Design work

If the conversation drifts into Open Design, plugin UI, Bridge, or visual directories, re-center the next tasks like this:

1. Create/update a **course transformation + processing ledger** in the vault report area.
2. Update the course processing workbench if it has stale paths or assumptions.
3. Pick the next small, source-backed course/material and run the ingestion loop.
4. Validate and locally commit vault changes.
5. Only then expose the resulting state to frontend via safe lightweight indices.

## Pitfall

Do not answer “backend responsibility” as only:

- front-end state indexes;
- Bridge commands;
- plugin route maps;
- evidence/report JSON for UI.

For this user, those are support layers. The backend also owns the full course pipeline from raw material to formal Obsidian knowledge base.