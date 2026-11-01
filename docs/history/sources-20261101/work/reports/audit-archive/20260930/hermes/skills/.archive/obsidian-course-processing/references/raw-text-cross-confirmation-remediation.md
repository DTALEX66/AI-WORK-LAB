# raw_text_not_cross_confirmed remediation

Use this when V10/local course audits report `raw_text_not_cross_confirmed` after sidecars exist. Do not assume the course content is wrong; first diagnose why formal markdown terms and source/sidecar terms do not overlap.

## Common root causes

1. **Formal markdown is template-heavy**
   - Formal terms may be `课程库`, `模块总结`, `附件`, `type`, `status`, `created`, `updated`, `验证与不确定项`, etc.
   - These should not be treated as content evidence. Filter template/frontmatter/navigation terms before judging overlap.

2. **Category/领域 pages are being treated as courses**
   - Examples: broad folders like `心理记忆学习力`, `新媒体运营与增长`, `考试数学与学习方法`, `传统文化与术数` may contain many sub-material pages and source mappings rather than one lesson sequence.
   - For these, verify directory/source mapping separately; do not expect a single sidecar to overlap all category prose.
   - Split into child courses/resources and run content verification per child.

3. **`source_root: E:\学习数据` false-positive scan**
   - `source_root` is a root boundary, not a content source by itself.
   - If collected as an explicit source path, it can produce full-disk `raw_matches` (e.g. 18k+ files) and sidecar may sample unrelated videos/PDFs.
   - Prefer `source_path`, `资料位置`, `素材目录`, or course-specific report paths. Treat `source_root` alone as metadata only.
   - If concrete explicit sources exist, they should take precedence over global name matches; do not merge in same-name files from the whole scan root.

4. **Sidecar samples non-core material**
   - Intro videos, purchase notices, student testimonials, download-address txt files, cover pages, and PDF tables of contents usually do not overlap formal concepts.
   - Select files/segments by formal concepts rather than first-N sorted matches.

5. **ASR/OCR extraction is too shallow, noisy, or unusable**
   - Short first-60-second ASR often captures greetings/intros and may misrecognize core words (`考霸`→`烤巴`, `职场`→`知场`, simplified/traditional drift).
   - PDF text extraction from first pages often captures cover/TOC/URLs rather than content. Use page/segment targeting and OCR where needed.
   - If ASR has been attempted but returns zero segments/empty transcript, mark it as attempted-but-unusable (e.g. `audio_video_asr_unusable`) instead of repeatedly re-queueing as pending. Keep the course `needs_review`.

6. **Unsupported or special formats contain the real course body**
   - `.sz`, `.doc`, `.rar`, `.ape`, design archives, or packaged lessons may be the actual core material.
   - Count them as raw presence/asset evidence only until extracted, converted, or transcribed.

## Diagnostic sequence

1. Load the latest audit JSON and list only rows with `raw_text_not_cross_confirmed`.
2. For each row, print:
   - `text_consistency.overlap_terms`, `overlap_sample`, methods, sample count;
   - `sidecar_evidence` counts;
   - `raw_matches`, `explicit_source_files`, `source_type_counts`, sample raw sources;
   - formal top terms vs source/sidecar top terms.
3. Inspect the course directory shape:
   - has `00_课程总览.md` plus `03_模块总结.md`/`07_*工作流.md` → likely formal course;
   - has many independent material pages with `source_path` fields → likely category/index page.
4. If category/index page, split remediation into child resources and do not score it as a single course-body overlap failure.
5. If formal course, choose next sidecar files by matching formal concepts to source filenames/lesson titles.
6. Re-run audit read-only first; do not claim `verified_by_available_methods` until overlap and other required evidence channels agree.

## Targeted sampling rules

- **Video/audio**: sample mid-course content, not only intros. Prefer multiple segments (e.g. 60–180s and 40–60% into the video). Increase ASR duration/model only for selected high-value files.
- **PDF**: inspect page count and content pages; avoid only page 1 if it is cover/TOC. Use OCR for scanned pages.
- **Text/Markdown**: skip URL-only/download-address files unless the formal claim is about source availability.
- **Design/archive formats** (`.sz`, `.rar`, `.zip`, `.ai`, `.psd`): count as raw presence/asset evidence, but not text evidence unless extracted/unpacked or a paired transcript exists.

## Term normalization before scoring

When exact overlap is too brittle, improve the audit rather than manually waiving failures:

- remove template/meta terms;
- normalize simplified/traditional Chinese;
- add known ASR confusion aliases (`考霸/烤巴`, `职场/知场`, `商业/商業`);
- use Chinese 2–6 character n-grams or LCS-style matching for long concepts;
- preserve the raw exact-overlap count separately so confidence remains auditable.

## Known high-value next-file examples from the 2026-07-07/08 audit

- `30天考霸训练营` / `考试数学与学习方法`: skip purchase notices and link-only `Day*.txt`; sample正课 videos such as `Day10-学习专业知识：费曼的超级阅读法`, `Day15-惠勒提问法`, `Day16-费曼终极学习法`, `Day20-用题目增进理解`, `Day24-触类旁通`.
- `Photoshop AIGC商业设计`: sample 第9章商业/AIGC案例 videos such as `需求分析与关键词编写`, `海报文案创意排版`, `企业IP形象设计`, not just导学视频.
- `品牌全案AI设计实战班`: many core lessons are `.sz`; accessible `第20节 AIGC辅助三维效果图输出.mp4` may produce zero ASR segments and should be treated as `audio_video_asr_unusable`, not pending. Investigate `.sz` extraction/support before expecting text overlap. 作品集 PDF may validate visual assets but not course-body terms.
- `新媒体高阶运营增长实战训练`: target `爆款选题`, `KPI拆解`, `增长活动`, `用户生命周期管理`, `矩阵运营`, `ARPU` PDFs/videos rather than导论前三节 only.
- `牛客算法直通套餐`: target chapters matching formal terms, e.g. `第5章 二叉树`, `第6章 图`, `滑动窗口/单调栈`, `Morris遍历`, plus related课后练习 markdown.
- `记忆圣经学习力合集`: target `01个数字宫殿`, `02利玛窦的记忆宫殿`, `06记忆宫殿-读心术`, `10风靡全球的快速记忆训练教程`; continue ASR on `考试不用记教程` 正课.
- `设计师职业加速营`: target `破局思维`, `大格局`, `结构化思维`, `职场写作`, `职场沟通`, `职业规划`, `面试/作品集指导` rather than download-address txt.
- `设计转岗运营加速版`: target `文案写作三步法`, `完整活动策划工作流程`, `活动复盘`, `新媒体运营/选题/素材`, `短视频指标`, `数据分析/SOP` rather than only先导课.
- `大脑训练`: current PDFs may extract only URLs; try OCR and `.doc` conversion for `《超级记忆法》教材(完整版).doc`, and treat `.rar`/`.ape` as non-text evidence until extracted/transcribed.
- `敏感与待确认`: maintain isolation. Only use defensive/ethical/safety sources, and do not add operational expansion to formal content.

## Reporting style

When the user asks for read-only analysis or sleep-mode progress, explicitly state:

- source files/reports inspected;
- no formal vault writes were made;
- remaining count and why counts may differ from stale reports/stdout;
- concise table of course → overlap reason → next files/segments;
- guard results (tests/audit/pollution) when a batch changed files.
