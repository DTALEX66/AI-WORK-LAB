# Conversion Toolchain — Full Format Matrix

Last updated: 2026-07-09 from session converting E:/服务器/记忆力与学习力 (13 courses, 67 summaries, SenseVoice+PaddleOCR deployed).

## User requirement

"转化" means **extract real text from source files** (PDF text, DOCX text, video ASR transcript, OCR). Indexing, outlining, renaming, and navigation fixes are preparation — NOT conversion. When the user repeats "转化转化转化", switch immediately to source-file text extraction.

The conversion standard: every extractable file in the `source_root` directory MUST be processed. Material assets (PSD, AI, C4D, ZIP) get `file://` links only.

## Format conversion matrix (benchmarked 2026-07-09)

| Source format | Tool | Accuracy | Speed | Output location | Notes |
|---|---|---|---|---|---|
| .pdf (text-based) | pymupdf (fitz) | 98% | Instant | 03_逐节总结/ | First choice |
| .pdf (scanned CN) | **PaddleOCR** | **90-95%** | ~5s/page | 03_逐节总结/ | Tesseract chi_sim ~70% backup |
| .docx | **pandoc** (primary) / zipfile | 98% | Instant | 03_逐节总结/ | `pandoc file.docx -t markdown --wrap=none`; fallback to zipfile OOXML raw text |
| .pptx | zipfile OOXML | 95% | Instant | 03_逐节总结/ | Read `ppt/slides/slide*.xml` |
| .txt/.md | open('r') | 100% | Instant | 03_逐节总结/ | Direct read |
| .doc (old Chinese) | antiword | 50% | Fast | 03_逐节总结/ | Chinese encoding fails |
| .doc (old Chinese) | LibreOffice Portable | 85% | Slow | 03_逐节总结/ | .paf.exe from PortableApps.com |
| Video/audio (CN) | **FunASR SenseVoice** | CER **~8%** | **14-15x** | 03_逐节总结/ | 60s video → ~4s process |

## ASR Quality Comparison

| Model | Chinese CER | Speed | Size | Output |
|---|---|---|---|---|
| faster-whisper tiny | ~35% | 1x | ~75MB | Garbled |
| **SenseVoice Small** | **~8%** | **15x** | 936MB | Clean + emotion detection |

## Pipeline Engine (tools/pipeline.py)

Located at `D:/All projects/Obsidian-Assistance/tools/pipeline.py`.

**Singleton model loading**: `get_asr_model()` caches SenseVoice across all files — no re-download per video.

```bash
python tools/pipeline.py              # all courses
python tools/pipeline.py --course C0401  # single course
```

Format handlers: `@register('.mp4')`, `@register('.pdf')`, etc. — each format auto-routed.

## Installation

```bash
pip install torch torchaudio funasr paddlepaddle paddleocr pymupdf pdf2image
scoop install pandoc
# LibreOffice: download .paf.exe from portableapps.com, extract to tools/libreoffice_portable/
```

## DOC limitation (46 files, 1.2%)

- MSI extraction fails (DLL load error)
- pandoc only supports .docx, not .doc
- antiword fails on old Chinese binary format
- Solution: manual LibreOffice Portable download from portableapps.com
- .paf.exe >100MB → .gitignore, local-only

## Tools directory convention

All conversion tools live under project `tools/`:
```
tools/
├── pipeline.py              # Full pipeline engine
├── benchmark_accuracy.py    # Accuracy tests
├── crosscheck_accuracy.py   # Network cross-validation
├── ACCURACY_STANDARDS.md    # Accuracy targets
├── accuracy_benchmark.json  # Benchmark results
├── requirements.txt         # Python deps
└── libreoffice_portable/    # Extracted .paf.exe (local, .gitignored)
```

**All tools must be portable/green — no system-wide install.** Large binaries stay local via .gitignore.
