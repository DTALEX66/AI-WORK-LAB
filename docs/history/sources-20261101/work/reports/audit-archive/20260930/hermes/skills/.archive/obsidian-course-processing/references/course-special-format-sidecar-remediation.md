# Course special-format sidecar remediation

Use this when V10/local course audits still report `raw_text_not_cross_confirmed` after normal PDF/text/ASR sidecars, especially when the remaining source files include legacy or course-platform formats.

## Boundary

- Write helper-repo evidence only (`docs/course-evidence-sidecars/`, reports, queues).
- Do not write formal vault course bodies during sleep-mode remediation.
- Do not extract large archives wholesale into the repo. Treat archive listing as evidence inventory, not content confirmation.
- Do not mark a course verified just because a special-format file exists; it must produce usable text/ASR/OCR or remain `needs_review`.

## Durable format handling lessons

### `.sz`

- Some `.sz` files are ISO Media / MP4-like containers. Probe with `file` and `ffprobe`.
- If `ffprobe` shows video/audio streams, include `.sz` in video-source handling and attempt keyframe/ASR.
- If ffmpeg/ASR emits decode warnings or produces zero transcript segments, record this as `audio_video_asr_unusable`, not `audio_video_asr_pending`.
- Keep the course in `needs_review`; the fix is not to re-run the same empty ASR forever, but to locate another usable segment/source or document that the source is protected/corrupt.

### `.doc`

- On Windows Git-Bash, `antiword` may be available and can extract legacy `.doc` text reliably enough for sidecar text evidence.
- Add `.doc` extraction before declaring text evidence unavailable.

### `.docx`

- `.docx` can be parsed without external packages by reading `word/document.xml` from the zip and stripping XML tags.
- This is sufficient for lightweight sidecar text evidence; keep method labels like `docx-zip` so audit output is traceable.

### `.zip` / `.rar`

- Use `7z l <archive>` to list contents and classify evidence (PDFs, images, source code, design assets).
- Do not bulk extract big archives into the helper repo.
- Archive listings can support `raw_source_present` / `design_asset_source_present`, but they do not count as text confirmation until selected files are extracted or otherwise converted.

### `.ape`

- Treat as audio source presence. Only transcribe after a deliberate small-sample extraction plan; do not run broad all-file transcription by default.

## Audit-state distinctions

- `audio_video_asr_pending`: audio/video exists and no ASR attempt artifact exists yet.
- `audio_video_asr_unusable`: an ASR attempt exists but produced no usable segments/text. This should not be retried blindly.
- `raw_text_not_cross_confirmed`: remains the main blocker until formal terms and real source/sidecar terms overlap enough.

## Recommended test coverage

When adding format support, add unit tests for:

- `.sz` classified as video.
- `.docx` extracted through `word/document.xml` without requiring LibreOffice.
- ASR attempt with zero segments yields `audio_video_asr_unusable` rather than `audio_video_asr_pending`.
- Explicit `source_path` takes precedence over broad same-name scans.

## Reporting pattern

Create a helper report such as `docs/course-special-format-inventory-YYYY-MM-DD.md` with:

- tool availability (`file`, `7z`, `antiword`, ffmpeg/ffprobe);
- remaining `needs_review` courses;
- counts of `.sz/.doc/.docx/.rar/.zip/.ape/.psd/.ai` per course;
- sample paths;
- next action per course (extract text, probe video, archive listing only, split category page, etc.).
