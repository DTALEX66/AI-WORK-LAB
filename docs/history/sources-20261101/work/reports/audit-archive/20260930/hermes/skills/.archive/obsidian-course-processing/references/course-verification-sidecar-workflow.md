# Course verification sidecar workflow

Use this when the user asks to continue fixing all Obsidian course verification issues, especially “无幻觉/无识别错误”, “多种识别方式交叉识别”, or “课程不能光有纯文字”.

## Safety rule

Do **not** mark a course verified just because a tool ran. Verification still requires multiple agreeing evidence channels. Keep `needs_review` until the audit reports `verified_by_available_methods`.

## Helper repo scripts

Run from `D:/All projects/Obsidian-Assistance/Obsidian - Backend Assistance`.

- `scripts/v10/course_verification_audit.py`
  - Conservative full-course audit.
  - Use `--sidecar-root docs/course-evidence-sidecars` whenever sidecars exist.
  - Outputs JSON/Markdown reports.
- `scripts/v10/course_evidence_sidecar.py`
  - Generates single-course sidecar evidence only.
  - Writes under `docs/course-evidence-sidecars/<course>/`.
  - Does **not** modify formal vault course bodies.
  - Can create: PDF extracted text, PDF source-page images, video keyframes, optional faster-whisper ASR transcripts.

## Recommended sequence

1. Run or inspect the latest audit JSON:
   - `docs/course-local-verification-audit-YYYY-MM-DD.json`
2. Pick `needs_review` courses by risk:
   - `missing_raw_source` → source matching first.
   - `audio_video_asr_pending` → run sidecar with `--asr` on a better media segment or longer sample.
   - `missing_visual_evidence` → generate PDF source-page images or video keyframes.
   - `missing_oer_crosscheck` → produce OER/official-source crosscheck reports before editing正文.
   - `raw_text_not_cross_confirmed` → inspect sidecar text vs formal page terms; do not assume correctness.
3. Generate sidecars for a small batch, not all media at once:
   ```bash
   export TESSDATA_PREFIX="$HOME/scoop/apps/tesseract-languages/current"
   python scripts/v10/course_evidence_sidecar.py \
     --course "<课程名>" \
     --vault "E:/BaiduSyncdisk/Obsidian知识库" \
     --source-root "E:/学习数据" \
     --output-root docs/course-evidence-sidecars \
     --max-text-files 3 \
     --max-media-files 1 \
     --asr \
     --asr-model tiny \
     --asr-seconds 20
   ```
4. Re-run audit with sidecars:
   ```bash
   python scripts/v10/course_verification_audit.py \
     --vault "E:/BaiduSyncdisk/Obsidian知识库" \
     --source-root "E:/学习数据" \
     --sidecar-root docs/course-evidence-sidecars \
     --sample-limit 4 \
     --format markdown \
     --output docs/course-local-verification-audit-YYYY-MM-DD.md
   ```
5. Update the remediation queue and task ledger, but only close tasks when real evidence exists.
6. Verify:
   - `python -m pytest tests/v10 -q`
   - `python -m pytest tests -q`
   - `python scripts/v4/obsidian_v4_audit.py .`
   - Root audit from repo root.
   - Check repo contains no forbidden generated media such as `.wav`.

## Known useful setup

- Tesseract + language data installed via Scoop can work if `TESSDATA_PREFIX` points to `~/scoop/apps/tesseract-languages/current`.
- faster-whisper can be used from the Hermes Python venv.
- Keep temporary audio samples deleted after transcription; store text transcripts and keyframes, not `.wav` sidecars.

## Pitfalls

- Do not treat a silent/empty ASR transcript as evidence. Count ASR only when transcript has segments/text.
- Do not keep extracted `.wav` samples in the helper repo; the audit rejects forbidden media extensions.
- Do not loosen the audit to make counts look better. If stricter matching lowers verified count, report it as improved credibility.
- Do not use generic tokens like `cn`, `awesome`, `实战课`, `资料`, `素材`, `训练营` as raw-source evidence; they create false positives.
- Sidecars reduce risks but do not automatically make a course verified; OER and term overlap may still be missing.