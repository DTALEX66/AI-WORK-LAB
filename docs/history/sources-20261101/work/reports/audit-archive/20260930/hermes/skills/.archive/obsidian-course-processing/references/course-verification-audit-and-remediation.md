# Course Verification Audit + Remediation Pattern

Use this when the user asks to “全部跑一遍”, “确认没有幻觉/识别错误”, “修复补充解决所有问题”, or similar strict course verification work.

## Safety posture

- Do **not** claim absolute zero errors. Mark only courses with multiple agreeing evidence channels as `verified_by_available_methods`; all others remain `needs_review`.
- Do not close a task from preview/dry-run/echo/context-pack output. Closing requires real evidence such as source paths, extracted text overlap, generated visual/ASR/OCR sidecars, OER/report paths.
- Network/OER sources can validate public knowledge, but must not replace local course sources.

## Evidence channels

For each course, cross-check:

1. formal course markdown under `02_课程库/<course>/`;
2. raw material matches under `E:/学习数据`;
3. local source indexes linked from course pages or reports, especially `50_领域知识/**` and `93_导入报告/**`;
4. report files under `93_导入报告`;
5. visual evidence under `99_附件` plus embedded images in the course page;
6. OER / official / public cross-check files;
7. text extraction overlap from Markdown/TXT/PDF samples.

## Source matching lessons

- A missing raw source is not always literal. First inspect course frontmatter/body, import reports, report backups, and OER control pages for explicit source links.
- Support alias matching for non-identical source names: instructor prefixes, `·`, `&`, completion markers, shortened titles, platform names, and generated/OER courses.
- Avoid false positives from generic tokens. Single weak tokens such as `cn`, `awesome`, `agent`, `ai`, `pdf`, `资料`, `素材`, `教程`, `实战课`, `训练营` should not create a raw-source match by themselves.
- For generated/OER courses, local vault references like `[[50_领域知识/...]]` can count as a local source index, but should be reported separately from external raw course media.

## OCR / ASR gating

- If Tesseract is installed, verify language data (`eng`, `chi_sim`, `chi_tra`) and `TESSDATA_PREFIX` before trusting OCR availability.
- If faster-whisper imports successfully, mark audio/video work as `audio_video_asr_pending` until real ASR sidecars are produced; do not mark content-level verification complete just because the package is installed.
- Scanned PDFs require OCR sidecars; text-based PDFs can be checked with PyMuPDF/pdftotext, but lack of overlap still remains `raw_text_not_cross_confirmed`.

## Remediation queue

Write a remediation queue report with:

- `verified_by_available_methods` count;
- `needs_review` count;
- environment flags (`tesseract`, `whisper`);
- risk counts;
- per-course actions: `source_match`, `text_crosscheck`, `oer_crosscheck`, `visual_evidence`, `asr_run`, `ocr_run`, `manual_review`.

Also seed the helper repo task ledger for `needs_review` courses, but leave tasks pending until evidence-backed closure.