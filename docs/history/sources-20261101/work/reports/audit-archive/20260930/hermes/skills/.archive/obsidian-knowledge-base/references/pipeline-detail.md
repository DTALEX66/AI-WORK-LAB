# 课程处理全流程流水线

## 8-Stage Pipeline

```
原始素材 → 素材识别 → 转写/OCR → 核验 → 总结 → 卡片 → 入库报告 → 清理
    1          2           3          4      5      6       7        8
```

## Stage Details

### Stage 1 — 素材识别
- List all files in source directory (audio/video/PDF/image/doc)
- Categorize by type
- Identify missing components

### Stage 2 — 转写/OCR
- Audio: Whisper → `.txt`
- Video: ffmpeg + Whisper → `.txt`
- PDF: pymupdf (text) or tesseract (image-based)
- Output to `outputs/transcripts/` and `outputs/ocr_*.txt`

### Stage 3 — 核验
- Cross-reference multiple transcripts for same content
- Correct ASR errors using context ("NK" → "Anki")
- Extract task content from OCR (even noisy)
- Filter non-essential content (student names, ops info, awards)

### Stage 4 — 总结
- One lesson summary per section
- Standard structure: 原始信息 → 讲了什么 → 核心知识点 → 关键术语 → 操作步骤 → 案例 → 重点 → 踩坑 → 可转卡片 → 核验边界 → 不收入内容
- Must cite source transcript files

### Stage 5 — 卡片
- Knowledge cards: one concept per card with frontmatter
- Review cards: Q&A format with spaced-repetition tags
- Split into single files under 03_知识卡片/ and 04_复习卡片/

### Stage 6 — 入库
- Write to `02_课程库/<course>/` (final content only)
- Write import plan FIRST → wait for user confirmation
- Only write final summarised content, never raw transcripts

### Stage 7 — 入库报告
- Generate `93_导入报告/<course>_导入报告.md`
- Document: what was written, what was filtered, what is pending

### Stage 8 — 清理
- Move intermediate files to `95_待审核/`
- Generate review report
- User confirms final archive/delete

## Vault Writing Rules
- Python can write E: drives; Node.js REPL throws EPERM
- New files go into existing directory categories
- All Markdown files use Obsidian [[双链]]
- Workflow files include 8 elements: 目标/前置条件/步骤/输入/输出/风险/检查清单/分类

## Verifiable Output Standard
- Every course file has explicit source citation
- Uncertain content marked "待人工补充"
- Every [[term]] has a corresponding note in 80_索引数据库/术语笔记/
- Import report documents all filtering decisions
