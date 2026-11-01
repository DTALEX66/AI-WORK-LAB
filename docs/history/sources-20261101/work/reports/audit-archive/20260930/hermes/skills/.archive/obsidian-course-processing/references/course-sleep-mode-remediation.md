# Course Sleep-Mode Remediation Loop

Use this when the user asks for “睡觉模式”, “继续修复所有问题”, or long-running hands-off cleanup for the Obsidian course/vault pipeline.

## Operating boundary

- Default boundary: write only helper-repo artifacts, not formal vault course bodies.
  - OK: `docs/course-evidence-sidecars/`, `docs/course-oer-sidecars/`, audit JSON/MD, remediation queues, batch reports, local task ledger outside the repo.
  - Not OK without an explicit write plan/confirmation: editing `E:/BaiduSyncdisk/Obsidian知识库/02_课程库/**` formal course content.
- Never treat `needs_review` as complete. Only `verified_by_available_methods` can be reported as confirmed.
- Network/OER evidence can cross-check public knowledge, but cannot replace local course sources/transcripts/OCR/teacher-specific content.
- Keep progress reports short during sleep mode: current batch, changed counts, next batch/process id if backgrounded.

## Batch loop

1. Load latest `docs/course-local-verification-audit-YYYY-MM-DD.json` as the status gate.
2. Select a small batch of highest-risk `needs_review` courses:
   - `missing_raw_source`
   - `audio_video_asr_pending`
   - `missing_visual_evidence`
   - `raw_text_not_cross_confirmed`
   - `missing_oer_crosscheck`
3. Generate sidecars with `scripts/v10/course_evidence_sidecar.py` or `scripts/v10/course_sleep_mode_batch.py` if present.
4. Re-run audit with every active sidecar root:
   - `scripts/v10/course_verification_audit.py --sidecar-root docs/course-evidence-sidecars --oer-sidecar-root docs/course-oer-sidecars`
5. Rewrite the remediation queue and a batch report.
6. Run guard checks: V10 tests, full tests when code changed, v4 audit from helper root and repo root, no `.wav`/`.sqlite` artifacts in the repo.
7. Report concise batch status and continue.

## Source-path parsing lessons

Formal course names often differ from raw source folder names. Before declaring `missing_raw_source`, parse explicit source records in course pages/reports:

- YAML fields: `source_path`, `source_root`
- Chinese labels: `来源目录`, `资料位置`, `素材目录`
- Formal entry pointers from inventory notes, e.g. `formal_entry: "02_课程库/.../00_课程总览.md"`

Critical distinction:

- Treat `source_root: E:\学习数据` as metadata / scan root only. Never expand it as an explicit course source, or the sidecar will sample the whole E drive.
- Concrete `source_path` / `来源目录` / `资料位置` entries take precedence.
- If concrete source paths exist, use those paths instead of adding global name matches. This avoids cross-course false positives such as design-system media appearing in unrelated category pages.

## Category page vs course page

Some formal pages are field/category indexes, not single courses. Examples encountered: `传统文化与术数`, `心理记忆学习力`, `新媒体运营与增长`, `考试数学与学习方法`.

For these:

- Verify the category/index mapping separately.
- Do not require one category page to text-overlap with every subcourse/source package.
- Generate sub-course sidecars for the concrete source folders and keep the category page `needs_review` if exact formal/source overlap is structurally inappropriate.

## Sidecar quality rules

- Keep sidecar audio temporary: delete `.wav` samples after ASR and store only transcript text/manifest metadata.
- Do not count an ASR transcript as evidence if it has zero segments or empty transcript text.
- If ASR was attempted but no usable transcript segments were produced, record an “attempted but unusable” risk (e.g. `audio_video_asr_unusable`) instead of repeatedly treating it as `audio_video_asr_pending`.
- When rebuilding sidecars, still re-run ASR for courses with `audio_video_present` + `raw_text_not_cross_confirmed`; otherwise a manifest rebuild can accidentally wipe previous ASR evidence.
- Do not count extracted text shorter than a meaningful threshold as text evidence.
- PDF source-page images and video keyframes are useful visual evidence, but they still do not prove text-level correctness alone.

## OER sidecar rule

When `missing_oer_crosscheck` is the only missing channel for otherwise grounded courses, write helper-sidecar reports under `docs/course-oer-sidecars/` and re-run the audit with `--oer-sidecar-root`. These reports should list official/open sources and their use, and must explicitly state that they calibrate public/common knowledge only; they do not replace local course files, ASR, OCR, or teacher-specific content.

## Relevance-ranked text sampling

If `raw_text_not_cross_confirmed` persists after ASR/OCR/OER/visual gaps are handled, do not keep extending ASR blindly. Rebuild text sidecars by ranking candidate text/PDF files against formal-page terms:

1. Extract terms from formal markdown.
2. Remove template/meta tokens (`课程库`, `type`, `status`, `附件`, `created`, `updated`, etc.).
3. Extract candidate text from explicit `source_path` files and, only if no explicit path exists, name-matched raw files.
4. Score candidates by formal/source term overlap.
5. Write the top-N relevant sidecar texts with `formal_overlap_terms` metadata.
6. Re-run the audit. If overlap is still low, inspect aliases/synthesized terms rather than claiming verification.

For video-heavy courses, ASR should sample mid-course/core lesson segments, not only the first 60–90 seconds. Intro/opening segments often contain self-introduction, platform notices, or silence.

## Typical remaining blockers after sleep batches

After OER/source/ASR/visual gaps are closed, remaining courses often require:

- sub-course split rather than class-page verification;
- support for special formats such as `.sz`, `.doc`, `.rar`, `.ape`;
- concept mapping / term normalization before exact overlap;
- Chinese variant and ASR-noise normalization (e.g. 繁简, `考霸/烤巴`, `职场/知场`, `商业/商業`);
- manual boundary for sensitive content: ethics/defense only, no operational expansion.

## Guard pitfalls

- Helper repo audits may reject hardcoded formal vault paths in scripts. Prefer CLI args or env vars such as `OBS_VAULT` and `OBS_SOURCE_ROOT`.
- A batch that finds no sidecar artifacts is still useful if it proves the course needs source-path repair or manual source matching; report it as not closed.
- Background long ASR batches should use `terminal(background=true, notify_on_complete=true)` and a short progress note, not a long explanation.
