# Source Matching Improvements for Course Verification Audits

Use this when auditing `needs_review` courses, especially `missing_raw_source` from V10/local verification reports.

## Key lesson

`missing_raw_source` often means the matcher failed, not that the source is absent. In the 2026-07-07 audit, 19/38 `needs_review` courses had `missing_raw_source`; the root causes split into:

1. **Open-source/OER courses**: source is a remote GitHub/OER repository, not a local `E:/学习数据` course package.
2. **Local source exists but title differs**: the formal course title is a cleaned/derived name while the source directory includes instructor names, separators, completion markers, prices, level labels, or only a shorter title.

## Required matching order

1. **Explicit source path first**
   - Parse frontmatter and body before fuzzy scanning.
   - Fields/patterns to inspect: `source`, `source_title`, `source_type`, `source_url`, `source_repo`, `source_commit`, `raw_source_path`, `original_source`, `source_paths`, `来源：`, `原始来源`, `素材路径`, `源目录`, `仓库`.
   - Local path regex: `[A-Za-z]:[/\\][^`\n|)]+`.
   - If extracted path exists under the source root, treat it as a high-confidence raw source match.

2. **Model remote/OER sources separately**
   - If `source_type: open-source-oer` or `source: https://github.com/...` appears, do not collapse this into generic `missing_raw_source`.
   - Verify evidence via `93_导入报告`, `50_领域知识`, `source_repo`, `source_commit`, and wikilinks to OER control pages.
   - Use more precise states such as `remote_source_reference`, `local_absorption_report`, `local_oer_index`, and optionally `missing_local_clone` if a local clone is required.

3. **Report/backups can contain source truth**
   - After matching course reports/backups, parse their contents for `E:/...`, GitHub URLs, `source_commit`, and source tables.
   - Useful files include `93_导入报告/**/backups/02_课程库__<course>__00_课程总览.md` and course-specific import/absorption reports.

4. **Normalize Chinese titles aggressively**
   - Apply Unicode NFKC, lowercasing, slash normalization, and separator removal/unification for: `·`, `&`, `丨`, smart quotes, `_`, `-`, `【】`, `（）`, spaces.
   - Strip noise such as `已完结`, `完结`, `全\d+讲`, `\d+节`, `\d+圆`, `年课`, `默认班级`, `番外篇`, `L1/L2/L3`, `五期`, `课程包`.
   - Build aliases from course dir name, frontmatter `course`, `source_title`, source basename, report title, OER repo basename, and linked control page title.

5. **Chinese substring/ngram matching**
   - Do not rely on a single full-title token for Chinese course names.
   - Add 2-8 character Chinese n-grams, longest common substring/LCS ratio, and meaningful substring hits.
   - Examples: `海马记忆法与记忆宫殿` should match source `记忆宫殿`; `记忆圣经学习力合集` should match `记忆圣经`; `清华视觉传达设计思维与方法` should match `_清华大学_视觉传达设计思维与方法_全24讲_陈楠`.

6. **Separate source presence from extractability**
   - Raw-presence file types should include archives/design/legacy media such as `.zip`, `.rar`, `.7z`, `.sz`, `.psd`, `.ai`, `.eps`, `.aep`, `.prproj`, `.fig`, `.sketch`, `.eaglepack`, `.vip`, `.abr`, `.rm`, `.rmvb`, `.mpg`, `.mpeg`, `.dat`.
   - Report separate booleans/counts: `raw_source_present`, `text_extractable_source`, `media_source_present`, `design_asset_source_present`, `archive_source_present`.
   - Do not treat design/archive files as text evidence, but do not mark the course as source-missing just because they are not text-extractable.

## Scoring sketch

- Existing explicit local source path: `+100`
- Normalized full title exact match: `+50`
- `source_title` exact/normalized match: `+40`
- Source basename exact/normalized match: `+40`
- Chinese ngram/Jaccard or LCS above threshold: `+20`
- Same category parent directory: `+10`
- Source repo/commit match: remote/OER evidence, not local raw-source evidence

## Interpretation rule

Fixing source matching may remove `missing_raw_source`, but it does not make a course verified. Keep independent risks such as `raw_text_not_cross_confirmed`, `audio_video_asr_not_available`, `missing_oer_crosscheck`, and `missing_visual_evidence` until separately resolved.