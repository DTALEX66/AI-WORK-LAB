# Local / no-API open-source toolchain research for OBS course pipeline (2026-07-07)

Use this when upgrading the OBS/Obsidian course-processing backend. The user asked to prioritize tools that can run locally and do not require API keys. Prefer small composable adapters over importing a large RAG platform.

## Core decision

Do **not** make a full RAG platform (AnythingLLM/Khoj/Onyx/PrivateGPT) the primary dependency for OBS. They are useful references, but OBS already needs stricter vault/source/evidence boundaries. Build on the existing helper repo pattern instead:

1. source manifest + SQLite ledger;
2. local document/media extraction;
3. candidate-only OCR/ASR/term/link/evidence outputs;
4. formal vault writes only through safe/dry-run-first tools.

## P0: integrate first

| Need | Recommended project/tool | Why | OBS integration note |
|---|---|---|---|
| Multi-format document to Markdown | MarkItDown | MIT, lightweight enough, handles PDF/Office/HTML basics | First adapter for `document_to_markdown`; output local work/outputs only |
| PDF page snapshots / local text | PyMuPDF / pymupdf4llm | Fast and already used by V6 PDF snapshot tooling | Good for page images and local page evidence; note AGPL/commercial licensing boundary when redistributing |
| DOCX structure | python-docx | Lightweight MIT | Prefer real document parsing over OCR for DOCX |
| PPTX text/notes | python-pptx or MarkItDown | Lightweight for PPTX structure | Extract slide titles/body/notes before any slide-image OCR |
| Web/OER text | trafilatura + readability-lxml fallback | Local scraping/extraction; no API | Feed V9 OER crosswalk pages; record URL/license/provenance |
| Video frame extraction | FFmpeg | Mature local binary | Existing V6 `video_keyframe_extract.py` should remain the execution layer |
| Scene/timestamp planning | PySceneDetect | BSD, local, OpenCV-based | Only generate candidate timestamps; hand frames to FFmpeg extraction |
| ASR | whisper.cpp first, faster-whisper second | whisper.cpp avoids PyTorch and runs locally; faster-whisper is Python-friendly | Store segment JSON with start/end/text/source_hash; no transcript upload |
| Chinese keyword baseline | jieba | Lightweight MIT and enough for first-pass Chinese courses | Use before heavier NLP models |
| Fuzzy matching/dedup | RapidFuzz | MIT, lightweight | Source-course matching, ASR typo normalization, title/link candidate ranking |
| Graph/link candidates | NetworkX | BSD, lightweight | Build candidate-only wikilink/topic graph; do not auto-edit course body |
| Local datastore | SQLite FTS5 + sqlite-utils | Small, durable, already fits ledger direction | Extend `obs_task_ledger.py` with source/artifact/evidence/term/link tables |
| Scheduling | APScheduler or pydoit | Much lighter than Airflow/Dagster/Prefect | APScheduler for local periodic runs; pydoit for file-hash based reruns |

## P1: add when P0 is stable or a course needs it

| Need | Recommended project/tool | Notes |
|---|---|---|
| Scanned PDF OCR | Tesseract + OCRmyPDF | Good default for searchable scanned PDFs; needs language packs/Ghostscript |
| Chinese/image OCR | PaddleOCR | Strong for Chinese screenshots/lecture slides, but heavier |
| Layout/table OCR | Docling or Surya | Use for complex PDFs/tables; not default |
| Strange-file fallback | Apache Tika | Requires Java; useful as fallback only |
| Better Chinese NLP | HanLP | Heavier model dependency; use after jieba proves insufficient |
| Keyword extraction | pytextrank before KeyBERT | pytextrank is lighter; KeyBERT requires embeddings/models |
| Semantic links | sentence-transformers + sqlite-vec | Store embeddings in local SQLite; outputs remain candidate-only |
| JS-heavy pages | Crawl4AI | Requires browser stack; use only when trafilatura fails |
| Offline OER background | Kiwix tools | Useful for offline Wikipedia/StackExchange; never substitute for course evidence |

## P2 / cautious

- MinerU: powerful document parser, but heavy and uses a custom MinerU Open Source License; run only as a pilot after license/dependency review.
- marker-pdf: high-quality PDF-to-Markdown but GPL-3 and model-heavy; do not make default.
- Unstructured: broad document ETL, but heavy; use only if simpler adapters fail.
- ArchiveBox: useful web evidence archival, but heavy; start with trafilatura + URL ledger.
- yt-dlp: only for clearly authorized OER/public media; do not use for private/paid course grabbing.
- Prefect/Dagster/Luigi/Snakemake: overkill for first-stage personal OBS pipeline; consider Snakemake only if reproducible DAGs become a real need.
- Obsidian Smart Connections / plugin-level AI indexing: may be local-first but can bypass OBS evidence/ledger controls; keep as optional UI-side candidate, not backend default.

## Integration sequence

1. **Manifest/ledger first**: source path, hash, mtime, type, course, status, artifacts, errors, evidence grade.
2. **Document adapter**: MarkItDown / python-docx / python-pptx / PyMuPDF / trafilatura with consistent metadata sidecars.
3. **Media adapter**: whisper.cpp or faster-whisper ASR; PySceneDetect timestamp planning; FFmpeg keyframe extraction.
4. **Candidate analysis**: jieba/RapidFuzz/FTS5/NetworkX for terms, duplicate terms, candidate links, isolated notes.
5. **OCR escalation**: Tesseract/OCRmyPDF, then PaddleOCR/Docling/Surya only when needed.
6. **Semantic layer**: sentence-transformers + sqlite-vec only after textual ledger/FTS is reliable.
7. **OER/cross-check**: trafilatura/Crawl4AI/Kiwix with license/provenance; public sources supplement, never replace local course evidence.

## Safety rules

- OCR/ASR full text and media artifacts stay in local work/output folders; never commit or upload.
- All external/open-source material must retain source URL/license/provenance.
- Candidate outputs are not verified evidence. Do not promote `candidate-only` or `pending-verification` to `verified` without source-backed review.
- Heavy tools should be optional extras, not install-time defaults.
