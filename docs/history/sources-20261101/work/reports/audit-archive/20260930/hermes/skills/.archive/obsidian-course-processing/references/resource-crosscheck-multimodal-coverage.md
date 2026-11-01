# Resource cross-check + multimodal course coverage

Use this when the user asks to “统计现有课程 / 全部跑一遍 / 调取资源库交叉比对” or complains that courses are becoming pure text.

## Durable lesson

Do not evaluate course completeness from `02_课程库` Markdown alone. For this user, course-processing quality must cross-check all available resource libraries and penalize pure-text output.

## Required evidence surfaces

For every course, compare:

1. Formal course pages: `E:/BaiduSyncdisk/Obsidian知识库/02_课程库/<课程名>/`
2. Raw source library: `E:/学习数据`
3. Attachment/visual assets:
   - `99_附件/verified-keyframes`
   - `99_附件/course-reference-images`
   - `99_附件/course-visuals`
4. Processing/import reports: `93_导入报告`
5. OER / public cross-check knowledge: `50_领域知识` and course `14_开放知识交叉对比.md`

## Coverage dimensions

Track at least:

- raw source matches and type distribution: video/audio/pdf/image/slides/word/html/doc
- keyframes, reference images, visual SVGs, and embeds in the course pages
- structural non-text elements: tables, Mermaid diagrams, callouts, code blocks, project/workflow pages
- import/processing reports matched to the course
- OER/public cross-check presence
- missing core course pages

## Risk labels

Use these labels in reports and queues:

- `未匹配原始资料库`
- `缺图片/关键帧/视觉资产`
- `缺OER/公开资料交叉`
- `缺导入/处理报告匹配`
- `偏纯文字`

A course should be marked `偏纯文字` when it lacks meaningful images/keyframes/visual assets and structural elements even if the Markdown text exists.

## Execution pattern

1. Build a matrix for all courses, not just one example.
2. Sort the remediation queue by pure-text risk, missing visual assets, missing OER, missing raw-source match, and missing core pages.
3. Do not let OER/network sources replace local course evidence; use them only for public-knowledge calibration and cross-checking.
4. Sensitive or “待确认” courses should be isolated/audited, not auto-expanded.
5. Write a durable report under the helper repo docs or `93_导入报告` depending on the requested scope.

## Good output shape

- Summary counts: course count, source files by type, asset/report/OER counts
- Top priority table: course, multimodal score, raw matches/types, keyframes/reference images/visuals, reports, OER, missing page count, risk labels
- Full matrix with sample matched raw resources and sample visual assets
