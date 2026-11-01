# Content-Matched Keyframe Engine

## Algorithm

```
1. extract_key_terms(course_dir) → top 8 terms from 03_逐节总结/*.md body
2. match_pdf_pages_to_terms(source_dir, terms) → fitz search terms per page, extract matching pages as PNG
3. match_video_frames_to_terms(source_dir, terms) → parse ASR markdown timestamps, ffmpeg extract frame at term+timestamp
4. write to 课程/12_视觉索引与配图.md + 99_附件_重组/内容匹配截图/
```

## Critical Pitfalls

### Screenshots MUST be evidence of real source extraction
The user explicitly requires screenshots to verify content authenticity — "我要知道你是编的还是根据原始课程转化提取的". Each screenshot must map to a specific source-file concept match:
- PDF: term found on a specific page → that page exported as image
- Video: term in ASR transcript with timestamp → frame extracted at that timestamp
- Random keyframes or decorative images are NOT acceptable
- Every `## 内容证据截图` section must cite the source file + page/timestamp

### Term extraction MUST use summary content, NOT main page frontmatter
- `00_课程主页.md` frontmatter yields metadata terms (课程库, 大字体) → 0 real content matches
- `03_逐节总结/*.md` body yields actual topic words (记忆宫殿, 视觉识别, 版式设计) → real matches
- Implementation: `extract_key_terms_from_summaries(course_dir)` — reads summaries first, falls back to main page body (skip YAML frontmatter with `---` split)

### PDF page matching
- Use `fitz.open(pdf)` then iterate pages with `page.get_text()` and `term in text`
- Export matched pages via `page.get_pixmap(dpi=150)` then `pix.save()`
- Limit: first 20 pages per PDF, first 20 PDFs per course

### Video frame matching
- Parse ASR files: `[120s] text...` → extract timestamp + check if term in text
- `ffmpeg -y -ss {ts} -i {video} -vframes 1 -q:v 2 {output}`
- Find video files by matching stem to ASR filename (strip `_ASR转写`/`_ASR` suffix)

## Output

- Screenshots: `99_附件_重组/内容匹配截图/{pdf_stem}/{term}_p{page}.png`
- Visual index: `10_课程库/{category}/{course}/12_视觉索引与配图.md`
