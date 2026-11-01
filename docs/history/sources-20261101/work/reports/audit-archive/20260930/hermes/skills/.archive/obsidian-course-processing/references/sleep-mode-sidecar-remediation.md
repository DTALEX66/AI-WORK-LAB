# Sleep-mode sidecar remediation for course verification

Use this reference when a course verification run must continue autonomously across many batches while preserving the user's boundary: helper-repo evidence only, no formal vault body writes, no fabricated completion.

## Durable workflow

1. **Batch, then verify**
   - Run bounded batches and emit a batch report under `docs/course-sleep-mode-batches/`.
   - After every batch refresh the audit JSON/Markdown and remediation queue.
   - Run V10 tests, full tests, backend audit, repo-root audit, and pollution checks for `*.wav` / `*.sqlite` before claiming a batch is clean.

2. **Sidecar-only evidence boundary**
   - Write evidence under `docs/course-evidence-sidecars/`, `docs/course-oer-sidecars/`, and helper reports only.
   - Do not write formal vault course bodies.
   - Keep `needs_review` until evidence genuinely satisfies the audit.

3. **Avoid full-disk source false positives**
   - Treat `source_root: E:/学习数据` as a scan boundary, not a concrete course source.
   - Prefer concrete `source_path` / source directory fields.
   - If a concrete explicit source exists, do not also add all same-name fuzzy matches from the full source root; this prevents sidecars sampling unrelated media.

4. **Relevant sidecar sampling**
   - Do not sample first-N files blindly.
   - Rank text/PDF candidates by overlap with non-template formal terms.
   - Skip link-only TXT, cover pages, purchase notices, intro-only videos, and generic download instructions when trying to close content consistency.

5. **OER/public-source sidecars**
   - Public/OER evidence can close `missing_oer_crosscheck`, but it does not replace local raw course evidence.
   - Store public crosscheck reports as helper sidecars and keep provenance clear.

6. **Special formats**
   - `.doc`: extract text with `antiword` when available.
   - `.docx`: extract `word/document.xml` from the OOXML zip; no LibreOffice dependency is required for basic text.
   - `.sz`: may be an MP4-like media container. Probe with `file`/`ffprobe`; try ASR/keyframes, but mark unusable if ffmpeg/ASR cannot obtain meaningful segments.
   - `.rar`/`.zip`: list contents with `7z`; do not full-extract large archives into the repo.
   - `.ape`: treat as audio-source presence; sample/transcode only in small, bounded probes.

7. **ASR attempts and cleanup**
   - If ASR has been attempted but produced zero usable segments, report `audio_video_asr_unusable`, not `audio_video_asr_pending`.
   - Support mid-video ASR via a start offset so repeated batches do not keep transcribing greetings/intros.
   - Always delete temporary `_sample.wav` files on success and on ffmpeg failure. Audit should end with `wav_count: 0`.

8. **When counts stop improving**
   - Stop blindly rerunning ASR/OCR.
   - Produce diagnosis reports that classify remaining rows as:
     - `category_index`: broad directory/index page; split into child resources instead of closing as one course.
     - `concept_mapping_needed`: evidence exists but formal page and source use different abstraction layers.
     - `no_text_extractable_core`: source is video/image/archive-heavy; needs targeted mid-course ASR or archive/lesson inventory.
     - `media_unusable`: media exists but current toolchain cannot obtain usable transcript.
     - `sensitive_hold`: keep isolated; only defensive/ethical evidence, no operational expansion.

## Batch reporting style

The user accepts short sleep-mode updates. Report only:
- batch number / process id if backgrounded;
- before/after verified and needs_review counts;
- risk counts changed;
- guard status;
- next batch focus.

Avoid long narrative while sleep-mode work is ongoing.
