# Batch All-Category Conversion Pattern

## Trigger

User says "全部开始/一次性解决/所有课程一起转化" or provides a detailed restructuring + conversion specification for all vault categories.

## Pattern

1. **Create skeleton courses** — one script per category, iterate course definitions, write `00_课程主页.md` + `01_原始资料链接索引.md`.
2. **Run pipeline on ALL categories** — `python tools/pipeline.py` processes every source file: PDF→pymupdf/OCR, DOCX→pandoc, video→SenseVoice ASR, TXT→open().
3. **Parallel processing** — run pipeline + keyframes + crosscheck as separate `terminal(background=true)` calls for natural anti-stall.
4. **Commit in batches** — large changes (>1000 files) may timeout git commit; use `git add 10_课程库/` then `git commit`.

## Post-Conversion Cleanup

After mass conversion, run the 7-dimension completeness audit and fix everything in ONE batch:

1. **Category indexes** — each `10_课程库/<category>/` needs `00_<category>首页.md` with course list + Dataview query.
2. **Verification pages** — batch-fill `06_验证与不确定项.md` for all courses, noting extraction format and tool.
3. **External links** — domain-level authoritative URLs for courses lacking `http` references. Use subagent fan-out (3 agents covering ~20 courses each) for deep cross-checking. See `references/authoritative-link-delegation.md`.
4. **Wikilinks + Dataview** — ensure every course main page has `[[cross-links]]` and a Dataview footer.
5. **Visual indexes** — `12_视觉索引与配图.md` for every course (skeleton for material-type).
6. **Navigation footers** — vault-root absolute paths, never `../` relative.
7. **Completeness audit** — `## 完成度审计` 7-dimension table (PDF|ASR|Visual|External|Wiki|Dataview|Verify) with N/A for material-type. Target: 100%.

## Category Index Template

```markdown
---
type: index
domain: <name>
course_count: N
---

# <Name>

## 课程列表
- [[C0xxx|Course Name]]
...

## 原始资料
[[../../60_外部资料链接索引/67_原始盘总索引|原始盘索引]]

\`\`\`dataview
TABLE status, file.mtime as "更新时间"
WHERE domain = "<name>"
SORT file.mtime DESC
\`\`\`
```

## Verification Page Template

```markdown
# 验证与不确定项

## 已验证项
- ✅ PDF文本提取完成 (pymupdf)
- ✅ 视频ASR转写完成 (SenseVoice)

## 待验证/不确定项
- ⚠️ 内容来自源文件提取，教师/作者身份未经独立验证
- ⚠️ 术语定义来源于课程材料，未与权威学术来源交叉比对
```

## Known Limits

- **Old Chinese .doc**: antiword fails (garbled). LibreOffice Portable .paf.exe needed (~150MB, local-only).
- **Image-based PDFs**: pymupdf returns <100 chars → OCR fallback via tesseract/PaddleOCR.
- **Pure video courses**: only ASR via SenseVoice; 199 videos may take hours. Accept sampling if 3+ videos transcribed.
- **Material-type courses**: software (.exe) or image-only (.jpg) packages → mark as `type: material`, no text extraction possible.
