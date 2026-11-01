---
name: multi-format-pipeline-testing
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/multi-format-pipeline-testing/SKILL.md
---

---
name: multi-format-pipeline-testing
description: "Test multi-format ingestion pipelines with real materials."
version: 1.0.0
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [ingestion, conversion, pdf, ocr, encoding, magika, markitdown, pipeline-testing]
---

# Multi-Format Ingestion/Conversion Pipeline Testing

## When to use

- Testing a conversion/ingestion pipeline (PDF/docx/pptx/xlsx/media/image/HTML/canvas → text) with **real materials** (a user's course-library, downloaded samples) instead of fixtures-only.
- Debugging "No engine could convert X" / empty content / garbled text / wrong-route results in a multi-engine converter.
- Auditing whether the engine chain honestly supports every format it declares.

## Core method: format matrix against a real library

1. **Inventory the real material first**: `find <library> -type f | sed 's/.*\.//' | sort | uniq -c` — the distribution tells you which formats actually matter (e.g. 66 PDF / 24 docx / 64 mp4 / 14 mp3 / 22 canvas).
2. **Classify per format**: text-layer vs scanned PDF (use pdfminer `extract_text` — empty text on a valid PDF = scanned), encoding of txt (try `raw.decode('utf-8')` then `'gbk'`), real binary vs HTML redirect (downloaded "samples" from GitHub raw are often 14-byte 404 pages or HTML — verify with `head -c 4 | od -c`: real PDF starts `%PDF`, epub `PK`, xlsx `PK`).
3. **Run one convert per format through the REAL API/entrypoint** — not the engine directly. That surfaces wiring gaps (see pitfalls) that direct calls hide.
4. **Verify content quality, not just non-empty**: OCR garbled text passes a `len>0` check; eyeball the first 200 chars of a Chinese document for mojibake.

## Pitfalls (all hit on real materials)

### Engine-chain declaration vs dependency drift
`_ENGINES` may route `docx/pptx/xlsx → markitdown` while pyproject only declares `markitdown[pdf]` → "No engine could convert docx file: MissingDependencyException". markitdown extras are per-format: `[pdf,docx,pptx,xlsx]` (docx=mammoth/lxml, pptx=python-pptx, xlsx=openpyxl/pandas). Grep the engine table AND the dependency declaration together; they must name the same format set. After `uv lock`+`uv sync`, restart the server — a killed wrapper process often leaves the OLD uvicorn child serving stale code (see windows-development-environment).

### Scanned PDFs need an OCR fallback in the pdf chain
Text-extract engines (markitdown, pdfminer) return EMPTY on image-only PDFs. A real library typically has several. Add `_via_pdf_ocr` to the chain (after markitdown, before any optional docling): render pages with pymupdf (`fitz`), OCR each with pytesseract using `chi_sim+eng` (TESSDATA_PREFIX must point at the versioned language dir), emit `<!-- page N -->` markers, fail closed (raise) if OCR yields nothing. Verify OCR output is readable Chinese, not mojibake.

### Text encoding cascade — GBK files are real
Chinese-Windows txt files are frequently GBK/GB2312. A naive `read_text(encoding='utf-8', errors='ignore')` silently mangles them (mojibake that passes `len>0`). Use a strict decode cascade: `utf-8 → gb18030 (superset of GBK/GB2312) → utf-16 → latin-1`, strict decodes only, replace as last resort.

### Format detection can misroute text files
Magika (content-based detection) mislabels GBK Chinese txt as `csv` (0.7 confidence) → the txt file gets routed to a csv/markitdown engine and garbled. Fix: for text formats (`.txt/.md/.markdown/.csv/.tsv`) trust the **extension first**; content detection stays authoritative only for ambiguous/binary formats. Verify with `detect_format_from_content()` directly on the failing file.

### Ingest layer vs convert layer wiring
The API may have TWO ingest paths: `/ingest` (text-only, reads `content` field) and `/ingest/file` (full conversion). `/run` may use the text-only one — passing `{"path": ...}` to `/run` silently yields empty content → route DROP (attention 0.0). Also `ingest_file` may whitelist only `.md/.markdown/.txt` while the engine chain supports 12+ formats ("unsupported file extension: .pdf"). Wire `_read_text` through the convert chain; align the extension allowlist with `_ENGINES`. Test BOTH endpoints with a real file.

### Path-boundary guards block outside-project materials
`ingest_file` resolves paths against approved roots and rejects anything outside the project ("path must stay inside the ArcheAxis project root"). That's correct fail-closed behavior — copy real samples into the project's ignored runtime dir (`.hermes/task-runtime/ingest-samples/`) and test there.

**The Hermes terminal guard (pre_tool_call hook) also gates the test session itself**: when it is live, every terminal call must go through `hermes-project-data.py --project . run -- <cmd>` (no `&&`/`|`/`;`, no multi-line `python -c`, no absolute external paths in the child — env assignments included). Write scripts with write_file and execute them; commit with `-F <msgfile>`; expect OCR/ffmpeg tests to skip locally (external toolchain paths are blocked) and rely on CI for full coverage. Full pattern table in `references/terminal-guard-wrapper-mode.md`.

### Spec-compliant samples only
JSON Canvas validation requires edges with BOTH `fromSide`/`toSide` AND `fromEnd`/`toEnd` — a hand-written "valid-looking" canvas gets rejected by the validator. Read the validator's exact field rules before crafting samples; a rejection here is the gate working, not a bug.

### Fake-success: engines that return SOURCE as "content"
markitdown 0.1.6 has NO RTF or ODF converter — `md.convert("x.rtf")` returns the raw RTF source (`{\rtf1\ansi...`) with a non-empty text_content, which sails through a `len>0` success check as "104K chars". Same for ODT (zip bytes). The content map routing `rtf/odt → docx (markitdown)` silently fakes success.
Fix pattern: give each format a real engine group with honest fallback:
- `rtf → striprtf` (`rtf_to_text`, 0.0.32, pure Python) — real control-word decoding.
- `odt → odf-xml` — zipfile read `content.xml` + `defusedxml.ElementTree` (XXE-safe; never stdlib `xml.etree` on external files), walk `text:p` paragraphs.
- Keep markitdown as a LAST fallback in the group; it must never be the only engine for a format it can't actually parse.
Symptom to watch: engine field says `markitdown` but content is raw source/zip bytes — that's fake success, not conversion.

### ffmpeg-missing assertions are brittle
Tests asserting the unavailable error message (`"not installed" in error.lower()`) break the moment the wording changes (`"executable not found in PATH"`). When the local env loses ffmpeg (toolchain relocation, venv rebuild), these tests either skip or fail on phrasing. Fix: accept both phrasings (`"not installed" or "not found"`), and keep the fixture error message and the test assertion in the same commit.

### Toolchain relocation / venv rebuild breaks local test env
Migrating `toolchains/` (ffmpeg/tesseract/scoop) to a new root silently breaks every local test that needs them: ffmpeg tests skip (`ffmpeg is not installed`), OCR silently degrades (TESSDATA_PREFIX points at a vanished dir — tesseract warns "does not exist, ignore it"). After any relocation: update TESSDATA_PREFIX to the new versioned language dir, prepend the new ffmpeg `current/bin` to PATH, then re-run the ffmpeg/OCR test files specifically (not just the full suite — skips hide in `-q` output as a changed skip count). A venv rebuild (e.g. `uv sync` recreating it after the env moved) also drops ffmpeg from PATH even when the binary exists — the PATH prefix is per-shell, re-export it in the same command as the test run.

### Schema drift after identity rename
Renaming the product/repo while a dev DB exists leaves table DDL stale: contract (`storage.py` IR_KB_TABLES) says `target_repo DEFAULT 'ArcheAxis'`, the DB still has the old default → migration/startup fails with `baseline schema does not match core.sqlite owner: mismatched=table:ir_contracts`, fail-closed refuses to boot. Fix path for a DEV DB (verify zero business rows first — `SELECT COUNT(*)` on the drifted table and a sample of core tables): back up the file, delete, re-migrate from scratch. Never hand-edit `sqlite_master`; the migration ledger must stay the single source of schema truth.

### Fake-success engines: raw source returned as "content"
The worst failure mode is NOT an error — it's an engine claiming success with the wrong payload. markitdown 0.1.6 has **no RtfConverter and no OdfConverter** (its converter list is docx/pptx/xls/xlsx/html/zip/plain-text only); for `.rtf`/`.odt` it silently falls back to PlainTextConverter and returns the **raw RTF control words** (`{\rtf1\ansi...`, 104K "chars") or zip bytes as if it were converted text. It passes `len>0`, reports `engine="markitdown"`, and corrupts downstream ingestion. Two defenses:
- **Content-spot-check every new format's preview** — if the first 200 chars look like the file's raw source (`{\rtf`, `PK\x03\x04`, `<!DOCTYPE`), the engine is lying. Verify preview, not just char count.
- **Give unsupported formats real engines instead of tolerating the fallback**: RTF → `striprtf` (`rtf_to_text`, decodes control words); ODT → parse the ODF zip's `content.xml` with **defusedxml** (stdlib `zipfile` + ElementTree, XXE/billion-laughs safe). Route them to their own engine groups in the map (`"rtf": "rtf"`, `"odt": "odt"`, never `→ docx`).
Also verify what the engine *claims* it converted: epub has no dedicated markitdown converter either, but its ZipConverter genuinely extracts the inner xhtml (752K real book text) — so "no converter registered" ≠ "fake"; judge by content, not by converter list.

### Skipped-count drift = optional tooling left PATH
When the full-suite skip count rises (e.g. 5→9) without a code change, don't shrug it off: `-rs` shows which tests silently skipped — typically ffmpeg/tesseract-dependent ones whose binaries left PATH (toolchain dir migration, parallel-session moves). Before declaring a green suite, check the skip reasons: ffmpeg tests skip with `ffmpeg is not installed`; OCR tests warn on TESSDATA_PREFIX. Restore env (`TESSDATA_PREFIX=<lang-dir>`, prepend `ffmpeg current/bin` to PATH) and re-run — a suite that skips its media tests is not fully tested. Error-message phrasing is also coupled: tests may assert substrings like `"not installed"` while the code says `"not found in PATH"` — when unifying an error string, update both the message and the asserting tests (assert either phrasing).

## Structured adapter pattern (AXW-023 family)

When a format needs more than flat text — blocks with anchors for later
Claim/Evidence pinning — follow the structured-adapter pattern used for
docx/pptx/xlsx/ocr/html/media (app/ingestion/*_adapter.py):

- **Shape**: `convert_<fmt>(path) -> AdapterResult` with `content` = flat
  text (callers that only need text still work) and
  `metadata["blocks"]` = list of `{kind, text, anchor}`; `metadata["loss_notes"]`
  = honest list of what the adapter dropped (media, truncated sheets, empty
  OCR pages).
- **Anchors per format**: pptx → `slide_index`; xlsx → `sheet` + A1-style
  `cell.coordinate`; ocr → `page_number`; html → `article` + title/robots/
  fetched_at; media → `start_s`/`end_s` timestamps.
- **Fail-closed everywhere**: file missing → error; engine dependency
  (python-pptx/openpyxl/trafilatura/faster-whisper) missing → clear error,
  NEVER fake success, NEVER auto-download models; empty extraction →
  "treat as degraded" error. Test each: `test_<fmt>_missing_file_fails_closed`
  + `test_<fmt>_without_engine_fails_closed`.
- **Boundaries**: xlsx cap cell count (e.g. 100_000) and record truncation
  as a loss note; media transcriber is optional (heavy) — fail closed when
  absent.
- **Persistence**: `convert_<fmt>_to_run(path, db, ...)` builds a
  ConversionRun (stable IDs from raw SHA) and stores it via
  `create_conversion_run` + `store_conversion_run`.
- **PITFALL — `document_id` is NOT on ConversionRun**: `run.document_id`
  raises AttributeError; the accessor is `run.document.document_id`. The
  original docx adapter had this latent bug; all five new adapters hit it
  at first. When copying the pattern, check every `_to_run` return.
- **Real fixtures beat downloads**: construct samples with the libs you
  control — openpyxl Workbook (sheets + formula cells), python-pptx
  Presentation (slides + table + notes_slide). Commit them to
  `tests/fixtures/` so CI exercises the same files. Note: python-pptx
  `shape.has_table` needs the `getattr(shape, "has_table", False)` guard;
  formula cells surface as `=SUM(...)` (data_type "f").
- **OCR quality metrics**: per-page quality = non-space char ratio
  (rounded 3dp), language hints from regex sets (zh = CJK range, eng =
  3+ ASCII letters); embedded text layer preferred, OCR fallback only on
  empty pages.

## Sample acquisition (real files, not fake)

Many "sample" URLs 404 or return 14-byte HTML redirects — verify with `head -c 4 | od -c` before trusting a download. Known-good sources and the construct-your-own recipe (openpyxl xlsx, python-pptx pptx, zipfile-ODT, JSON Canvas) are in `references/real-samples-and-format-matrix.md`. Generate a real sample with a library you control rather than downloading a fake one.

## Dependency-change lockstep (after adding a dep)

Changing pyproject deps breaks 3 test classes that must move together:
1. **requirements.txt** — tests assert it equals pyproject `project.dependencies` line-for-line (declarative form). `uv export` generates the WRONG shape (pinned+hashes); write the declarative list directly.
2. **release-manifest.json `dependency_lock.digest`** — sha256 of uv.lock; recompute after every lock change.
3. **Test assertions of old dep strings** (e.g. a0-gates asserting `markitdown[pdf]>=0.1` in ci-adapters) — update to the new spec string.
Also: ruff import-order failures on the edited file are common — run `ruff check --fix` on touched files before pushing.

## Verification

- Full suite green (`pytest` + convention gate) after any engine/dep change.
- Format matrix re-run via the real API after restart — confirm the NEW code is served (new routes respond, not 422 from a zombie process).
- For naming/packaging surfaces: cloud metadata (About description) is a separate sync surface from git — see repository-identity-migration.
