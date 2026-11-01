# Sleep-mode course remediation: special formats and guardrails

Use this when running long/batch Obsidian course verification remediation against local course materials, especially after `raw_text_not_cross_confirmed` remains even though sidecars exist.

## Boundary rules

- Keep sleep mode writes in the helper repo: sidecars, batch reports, audit JSON/Markdown, and remediation queues.
- Do not write formal vault course bodies while evidence is still `needs_review`.
- Report in small batches: say what batch is running, which risks changed, and whether guards passed.
- Treat delayed background process notifications as stale until the latest audit JSON is refreshed with the current script/options.

## Source-path guardrail

- `source_root` is a scan boundary, not a concrete course source.
- If formal metadata has only `source_root: E:/学习数据`, do not expand that into the whole disk as explicit evidence.
- If concrete `source_path`/`资料位置`/`素材目录` exists, use that first and do not also add broad same-name matches from the global scan root.
- Keep separate counts for explicit source files versus fuzzy/name-matched files so regressions are visible.

## Special-format handling learned from local course runs

- `.doc`: extract text with `antiword` when available; it can recover useful Chinese text from legacy Word files.
- `.docx`: extract text directly from OOXML `word/document.xml`; do not require LibreOffice for basic text evidence.
- `.sz`: first inspect with `file`/`ffprobe`. Some `.sz` course files are MP4 containers with h264/aac streams, so they can be attempted as video sources for keyframes/ASR. If ffmpeg emits NAL warnings or ASR produces no segments, record `audio_video_asr_unusable` rather than looping forever.
- `.zip`/`.rar`: use `7z l` for an inventory/asset evidence report. Do not extract large archives into the helper repo by default.
- `.ape`: count as audio-source presence; only transcode/transcribe intentionally selected small samples.

## ASR temporary-file cleanup

- FFmpeg can leave a partial WAV even when it returns non-zero, especially on malformed `.sz`/MP4 containers.
- Always delete partial `*_sample.wav` on both success and failure paths.
- Run the V4 audit plus explicit `*.wav`/`*.sqlite` checks after each batch; forbidden wav leftovers should fail the batch but not invalidate already written manifest evidence.

## Status interpretation

- `audio_video_asr_pending`: media exists and ASR has not been attempted.
- `audio_video_asr_unusable`: ASR/keyframe extraction was attempted but no usable transcript segments were produced; keep the course in `needs_review` and move to another evidence route.
- `raw_text_not_cross_confirmed` after sidecars often means the formal page is a category/index or uses template/project terms; next step is child-resource splitting or concept mapping, not blindly more ASR.
