# Batch Content Conversion (PDF + DOCX + ASR)

When the user says "转化转化转化/全部转化入库", they want source files actually processed into course content — not outlines, indexes, or navigation fixes.

## Quick-lookup: what to do per course type

| Source type | Tool | Output |
|---|---|---|
| PDF (text-based) | `fitz.open(path).get_text()` per page | `03_逐节总结/<filename>.md` |
| PDF (image-based) | pdftotext as fallback; if 0 chars → mark as image-only | note in course page |
| DOCX | `zipfile.ZipFile` → `word/document.xml` → strip tags | `03_逐节总结/<filename>.md` |
| MP4/MOV (video) | ffmpeg extract 90s WAV → faster-whisper tiny/zh | `03_逐节总结/<filename>_ASR转写.md` |
| Pure image/software | Cannot extract text | Mark `status: 素材型`, explain in body |

## Batch script pattern

```python
import subprocess, re, fitz
from pathlib import Path

# For each thin course (<3000B main page):
# 1. Extract PDFs (fitz, max 5 pages, limit per-page chars)
# 2. Extract DOCX (zipfile XML + regex strip)
# 3. Run ASR on first 1-2 videos per course (ffmpeg 90s WAV → faster-whisper tiny/zh)
# 4. Merge all extracted text into 00_课程主页.md
# 5. Update status: 待转化 → 已转化 (if >3000B) or 素材型 (if non-extractable)
```

## ASR timeout

faster-whisper on CPU with tiny model takes 30-180s per 90-second clip. Use `terminal(background=True, notify_on_complete=True, timeout=1800)` for batch ASR.

## Status conventions

| Status | When |
|---|---|
| `已转化` | Main page >3000B with real extracted content |
| `素材型` | Source is software/images/audio with no extractable text |
| `待转化` | Still needs processing |

## Merge rule

After extraction, merge snippet into course main page only if `sf.stem not in t` (prevent duplicate append on re-runs). Use `t = t.rstrip() + f'\n\n### {sf.stem}\n\n{st[:2000]}'`.

## Target threshold

A course is "rich" when `00_课程主页.md` exceeds 3000 bytes with real text content. Count and report `rich/total` after each batch.
