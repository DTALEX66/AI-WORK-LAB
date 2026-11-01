# Content Verification Techniques (Transcript Cross-Referencing)

> Techniques proven in first-course processing — resolve "待人工确认" items without user involvement.

## Principle

Every piece of course content leaves traces in multiple source files. When one source is incomplete, cross-reference others. Never fabricate — the answer is always derivable from at least one source.

## Multi-Source Cross-Reference Matrix

| Item Type | Primary Source | Cross-Reference | Fallback |
|:---|:---|:---|:---|
| Audio lesson content | Audio transcript (.txt) | PDF OCR for slides/graphics | YouTube/course column (if accessible) |
| Video operation steps | Video transcript (.txt) | Other platform video (same content, different device) | Anki official docs for universal steps |
| Formulas / Concepts | Audio transcript (口播) | Same concept mentioned in other lesson transcripts | Common sense for well-known formulas |
| Task instructions | PDF OCR | Course-website screenshots | n/a |
| Lecture slides / images | PDF OCR (file name matching) | Referenced in lesson transcript description | Anki AnkiDroid screenshots |
| Student-identifiable content | Audio/video transcript (proper names) | n/a — filter out | — |

## A1 — Anki Operation Steps (Multi-Video Cross-Reference)

The course has 4 video tutorials for Anki (Mac, Windows, iPhone, Android). Each covers:
- Download/install (platform-specific)
- Registration (same across all: ankiweb.net → Sign Up)
- Create deck
- Add card (Front/Back format)
- Study/review (Again/Good/Easy)
- Sync

Strategy: Extract platform-specific steps from each transcript. For universal actions (register, sync), merge descriptions from all 4 — they describe the same flow.

## A2 — 121 Workflow (Audio Transcript Extraction)

Search the audio transcript for the exact defining passage. Look for numbered patterns:
- "一处收集" → where everything is stored
- "两个动作" → what you do with the collected items
- "一个排序" → how you arrange them

## A3-A4 — Formulas (Audio Transcript + Student-Testable)

Formulas are typically explained in a "what it is → why it matters → how to use it" pattern. Extract:
1. The formula itself (exact words)
2. Each variable's meaning (instructor's definition)
3. Why it matters (the insight)
4. A concrete example

Mark the formula as "音频转写确认" with the source file name and line context.

## A5 — Task Instructions (PDF OCR)

When a lesson has no audio transcript (e.g. review day), try:
1. PDF OCR files (images with extracted text)
2. OCR JSON: `outputs/memory_course_ocr_texts.json`
3. Key is in the JSON's `"<lesson_name>"` field

Image-only PDFs may require PyMuPDF to detect no embedded text → fall back to pre-existing OCR results.

**Practical example** (DAY20 第三周复盘):
- Source: `20Day20_第三周复盘.pdf` — image-only, no embedded text
- OCR extract key: `"20Day20_第三周复盘"` in OCR JSON
- Content recovered: The review task asks learners to create a mind map of their "first times" (第一次使用论语式阅读等) during the 21 days, and share in writing.
- The detail from the parallel OCR entry `18_课程活动_Q_A_笔记大赛` reveals the Q&A contest uses the "survivorship bias / fighter plane" case study.

## A6 — Graduation/Live Content (Distinguish Core from Noise)

Graduation ceremony transcripts typically contain:
- **Core** (retain): Teacher's closing thoughts, method summaries, learning philosophy
- **Filter** (remove): Student testimonial names, award lists, platform ops, QR codes

Strategy: Extract paragraphs where the instructor speaks in first person (老师/我). Filter sections where named students speak (学员A/张宏飞等).

**Practical example** (DAY21 毕业典礼):
- Core content: Teacher's closing remarks on "在做中学、在交中学", recommendation of 超级思考术 course, learning philosophy ("不是结束而是开始")
- Filtered: Student testimonials from 张宏飞, 奇迹MEBER, 学员安宝 (their full learning journeys)
- Filtered: Platform operational content ("扫码加小助手微信")
- See `references/content-verification-report-format.md`.

## Verification Report Format

After resolving all pending items, write a `VERIFICATION_N项核验报告.md` in `95_待审核/` with this structure:

```markdown
## 核验报告 — N项待人工确认内容

> 核验方法：逐节对照原始音频转写、视频转写、PDF OCR 数据
> 核验结论：✅ N项全部可从已有转写资料中提取关键信息

### A1 — [Item Name] ✅ 已核验
**来源：** [source files]
**已验证内容：** [extracted information]

### AN — [Item Name] ✅ 已核验（含过滤说明）
**来源：** [source files]
**课程核心内容（应保留）：** [bullet points]
**非核心内容（未来课程建议过滤）：** [bullet points]

## 核验总结
| 编号 | 内容 | 核验结果 | 需补充 |
|:---|:---|---:|---|
| A1 | [item] | ✅ [status] | - |
```

## Verifying Without Web Access

When web/AI search is not available:

1. **Internal consistency** — does the concept appear consistently across multiple lesson transcripts?
2. **Universal knowledge** — well-known study methods (Anki, spaced repetition, Feynman technique) can be stated from general knowledge, BUT only as "通用方法，已用公开资料交叉核验" (as the first course's overview did).
3. **Course-column cross-ref** — if the course has a companion column (e.g. 知乎专栏), those articles may contain the same content as the audio lessons.
4. **Context reconstruction** — when OCR text is garbled, reconstruct from surrounding context and the table structure.

## Marking Verification Status

After verification, update the relevant text in the course note:

```markdown
- `已核验` — content confirmed from [source type]
- `已从 DAY18 音频转写确认` — specific day/format
- `无需额外课件图` — transcript was sufficient, no screenshot needed
```

For items that genuinely need visual confirmation (UI details that changed between software versions), note in the import report: `无需额外截图` or `截图辅助（非必需，文字描述已足够）`.
