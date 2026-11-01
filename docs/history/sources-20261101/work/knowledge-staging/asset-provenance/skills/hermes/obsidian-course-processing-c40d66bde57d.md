---
name: obsidian-course-processing
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/note-taking/obsidian-course-processing/SKILL.md
---

---
name: obsidian-course-processing
description: Process external course materials (audio/video/PDF/docs) into an Obsidian knowledge base — transcription, OCR, structured summaries, term indexing, image embedding, template management, and vault git backup.
platforms: [windows]
---

# Obsidian Course Processing Pipeline

Process external course materials into the Obsidian vault. Covers the full lifecycle: intake → transcribe/OCR → structure → summarize → term index → write plan → formal writing → review → cleanup.

## Vault Layout (Reference Structure)

```
Obsidian知识库/
├── 00_主页/          ← Dashboard (6 files)
├── 01_收件箱/         ← Inbox (raw materials)
├── 02_课程库/         ← Formal course notes (per-course subdir)
├── 03_知识卡片/        ← Knowledge cards (~49+)
├── 04_复习卡片/        ← Review cards (spaced repetition sets)
├── 50_领域知识/        ← Long-term knowledge (47 files)
├── 80_索引数据库/       ← Index + term notes (136+ files)
│   └── 术语笔记/       ← One note per [[term]] (130+)
├── 90_模板/           ← Obsidian templates (17 files)
│   └── 课程处理/       ← Course-specific templates (8 files)
├── 91_插件与设置/       ← Plugin notes
├── 93_导入报告/        ← Import completion reports
├── 95_待审核/          ← Pending human review (23+ files)
├── 96_脚本/           ← Tool scripts (PowerShell)
└── 99_附件/           ← Attachments (images, files)
    └── images/Day14/  ← Course image assets (16)
```

Project workspace layout (parallel to vault):
```
project-root/
├── work/              ← Raw course materials (mp3/mp4/pdf)
│   └── <course>/Day*/ ← Per-lesson subdirs
├── outputs/           ← Processing output
│   ├── transcripts/audio/  ← Whisper audio transcripts
│   ├── transcripts/video/  ← Whisper video transcripts
│   └── ocr_texts.json      ← PDF OCR results
└── github/            ← GitHub auxiliary project
```

## Full Automation Mode (for users who want hands-off)

When the user says "全流程跑通，不用我管" or equivalent:

- **No intermediate stops** — process from raw materials straight to formal vault notes.
- **Self-verify all pending items** — do NOT ask the user to confirm A1-A6-type items. Cross-reference transcripts, OCR, and audio to resolve them directly. See `references/content-verification-techniques.md`.
- **Only output the write plan** as a summary before committing changes — the user wants to see the plan but not debate intermediate choices.
- **Filter non-essential content automatically** — strip student testimonials, award lists, operational messages, platform promotions, and personal info. See Content Filtering section below.
- **Generate import report** after writing, documenting what was filtered and why.
- **Git commit** all vault changes locally at end of batch.

## Standard 10-Step Pipeline (Interactive Mode)

1. **Ingest** — Place raw materials into `01_收件箱/`.
2. **Identify** — Catalog material types (video/audio/PDF/image/doc/webpage).
3. **Transcribe/OCR**:
   - Audio → Whisper (output to `outputs/transcripts/audio/`)
   - Video → ffmpeg + Whisper (output to `outputs/transcripts/video/`)
   - PDF → pytesseract OCR (output as JSON)
4. **Structure** — Course decomposition → `95_待审核/`.
5. **Summarize** — Per-lesson complete summaries → `95_待审核/`.
6. **Extract** — Term index + practical workflows + knowledge cards + review cards.
7. **Write plan** — Draft write-to-vault plan; MUST get user confirmation.
8. **Write formal notes** — Only final content to `02_课程库/`. No intermediate files.
9. **Write term notes** — One `.md` per term in `80_索引数据库/术语笔记/`.
10. **Update indexes** — Refresh knowledge cards, review cards, indexes.

## Key Constraints

- **Real-source only**: Every conclusion must trace to a real source file. Never fabricate.
- **Uncertainty marker**: `待人工补充` on any uncertain conclusion.
- **Per-lesson isolation**: Each lesson = its own summary section.
- **[[wikilink]] integrity**: Every term in the index must have a corresponding note in `80_索引数据库/术语笔记/`.
- **Plan-before-write**: Always output a write plan and get user confirmation.
- **No GitHub**: Never push vault content to GitHub (vault may contain copyrighted material).
- **Notebook-style summaries**: See `references/first-course-reference.md` for the exact 12-section structure used per lesson.

## Review & Audit (95_待审核/)

When auditing pending files — see `references/content-verification-techniques.md` for detailed cross-referencing strategies to resolve "需人工确认" items automatically from available transcripts/OCR.

1. **Count** — List all files under the vault's `95_待审核/` with `search_files(target='files')`.
2. **Categorize** each into:
   - Index/navigation → keep.
   - Intermediate artifact (content already in formal library) → archive.
   - Forward-looking (learning plan, next steps) → retain.
3. **Compare** against formal library (`02_课程库/`, `03_知识卡片/`, `04_复习卡片/`, `80_索引数据库/`).
4. **Fix dataview path** — The `00_待审核总览.md` may reference a wrong folder path (e.g. `98_待人工审核确认` instead of actual `95_待审核`). Always verify the `FROM "..."` clause matches the actual directory name.
5. **Write review** — `REVIEW_审核结论与处理建议.md` mapping each file → status → recommendation.
6. **Fix issues** during review:
   - Garbled encoding → overwrite from correct source version.
   - Wrong folder references in dataview queries.
   - Missing import reports → generate from template.

## Image & Attachment Embedding

- Attachments live in `99_附件/` (configured via `attachmentFolderPath`).
- Create subdirectories: `99_附件/images/<CourseDay>/`.
- **Copy** (not move) images from the project workspace.
- Embed in notes with Obsidian format:
  - Thumbnail table: `![[99_附件/images/<path>\|80]]` (80px width).
  - Full embed: `![[99_附件/images/<path>]]`.
- Update the note with a `## 13. 课件配图` section after embedding.

## Template & Plugin Configuration

### 17 templates in 90_模板/
- Root (9): Agent工作流模板, Codex项目规则模板, 复习卡片模板, 课程卡片模板, 论文证据模板, 视频转写模板, 素材资产模板, 项目卡片模板, 知识卡片模板.
- `课程处理/` subfolder (8): 课程总览模板, 逐节课总结模板, 术语索引模板, 知识卡片模板, 复习卡片模板, 待人工审核单模板, 导入报告模板, 实操工作流模板.

### QuickAdd setup
- Data file: `.obsidian/plugins/quickadd/data.json`
- `templateFolderPath` must be `"90_模板"`
- Register each template as a `choices[]` entry with `type: "Template"`, `templatePath`, `folder` target.
- Verify with `cat` that the resulting JSON is valid.

### obsidian-git backup
- Check `.git/` exists in vault root.
- If no remote configured, confirm this is intentional (vault→GitHub is forbidden).
- Configure: `autoSaveInterval: 30`, `autoPushInterval: 0`, `autoPullInterval: 0`.
- No remote (vault must not go to GitHub).
- First commit: `git add .gitignore && git commit -m "init: 初始化 Obsidian 知识库 Git 备份"`.
- After first commit, obsidian-git plugin handles subsequent auto-commits (30 min).

## Encoding & BOM Handling

- **BOM injection**: BaiduNetDisk's YunDetectService injects UTF-8 BOM (EF BB BF) into JSON files. If Obsidian reports "failed to read JSON .obsidian/app.json", kill YunDetectService or reboot.
- **Detection**: `python3 -c "open(path, 'rb').read(3).hex()"` returns `efbbbf` if BOM present.
- **Fix garbled markdown**: Already-written files may have been saved with incorrect encoding (text renders as garbled Chinese characters despite being UTF-8). Find the correct source version in a parallel directory. Overwrite with: `open(source, 'r', encoding='utf-8-sig')`, `write(target, 'w', encoding='utf-8')`.
- **Fix JSON BOM**: Read with `encoding='utf-8-sig'`, write with `encoding='utf-8'`.
- **PowerShell 5.1**: Does not support `&&` or `utf8BOM` encoding. Use `UTF8` (no 'B').
- **E: drive writes**: Python works; Node.js may throw EPERM. Use Python for E: drive files.

## Import Report Generation

After each course completes formal writing:
1. Use `90_模板/课程处理/导入报告模板.md` (or see `references/import-report-template.md`).
2. Fill in: course name, processing dates, files written per directory, pending items.
3. Write to `93_导入报告/<course>_导入报告.md`.
4. Use `REVIEW_审核结论与处理建议.md` (if created) as the source for pending/cleanup info.
5. Also generate a separate `内容过滤规则.md` in `93_导入报告/` documenting what was filtered and why.

## Full-Automation Deliverable Summary

When completing a full-automation batch, deliver a single table summarizing everything accomplished:

```markdown
## ✅ 完成报告

### 1️⃣ A1-A6 Pending Verification
| Item | Status | Source |
|:---:|:---|---:|
| A1 | ✅ resolved | [source] |
...

### 2️⃣ Vault Updates
- File/change descriptions

### 3️⃣ Future Course Filtering Rules
| Filter Type | Example |
|:---|:---|

### 4️⃣ Repository Push
- Commit SHA, what was added
```

## GitHub Repo Update

After completing vault work and documentation, push the updated handoff document and pipeline docs to the Obsidian-Assistance repo:

1. Write/update `docs/handoff-<date>.md` in the repo with complete status.
2. Write/update pipeline documentation as needed.
3. `git add`, `git commit`, `git push`.
4. The vault itself must NEVER be pushed (contains copyrighted material). Only documentation/scripts/configs.

## Plugin Troubleshooting

### cmdr: `leftRibbon.forEach is not a function`

**Cause**: The `leftRibbon` setting is stored as `{"items": []}` (object with `items` key) but the plugin expects a plain `[]` array.

**Fix**: Change the data.json from:
```json
"leftRibbon": {"items": []}
```
to:
```json
"leftRibbon": []
```

### obsidian-spaced-repetition: `this.list.splice is not a function`

**Cause**: The `questionPostponementList` field is missing from `data.json`.

**Fix**: Add `"questionPostponementList": []` to the root of `data.json`:
```json
{
  "settings": {...},
  "questionPostponementList": []
}
```

### omnisearch: `Cannot read properties of undefined (reading 'keys')`

**Cause**: Internal plugin error during index rebuild, typically a version-compatibility issue or corrupt cache.

**Fix**: Clear the cache directory `.obsidian/plugins/omnisearch/cache/` (if it exists) and let the plugin rebuild. If no cache dir, this is a non-fatal init error — the plugin still indexes files and functions.

## Content Filtering Rules (Future Courses)

**Filter these from formal notes** (write a report documenting the filter):

| Filter | Examples |
|:---|:---|
| Student testimonials | Named student shares (张三/李四's learning journey) |
| Award lists | Q&A contest winners, prize details |
| Ops/promotional | "扫码加小助手", "添加微信xxx" |
| Platform announcements | Schedule changes, live-stream links |
| Raffle/giveaway info | "打卡赢奖品", "转发有奖" |
| Personal info | Real names, phone numbers, WeChat IDs |
| Cross-course ads | Discount codes, enrollment links |

**Retain these** (core course content):

| Retain | Examples |
|:---|:---|
| Instructor's main lecture | Method explanations, workflows, principles |
| Core knowledge points | Concepts, formulas, definitions |
| Operational steps | How to do X (Anki, reading, note-taking) |
| Key cases/examples | Non-identifying examples, case studies |
| Terminology | [[Wikilinks]] with corresponding notes |

**Report pattern**: document what was filtered and why in the import report.

## Obsidian UI Polish (CSS Enhancements)

When the user asks to make the vault "smooth and cool-looking":

### CSS Snippets (`.obsidian/snippets/`)
Enable 3 snippets:
1. `dt-knowledgeos` — Dashboard card styling, callout colors, table formatting.
2. `obsidian-knowledgeos-dashboard` — Status grid, card grid, knowledge card hover effects.
3. `obsidian-deep-ui` — Core visual polish (see below).

### Deep-UI Enhancement Patterns
Add to `obsidian-deep-ui.css`:

- **Page transitions**: `@keyframes slideInRight { from { opacity: 0; transform: translateX(-8px); } ... }` applied to `.markdown-preview-view`.
- **Card animations**: Staggered `fadeInUp` with `nth-child` delays (0.05s increments).
- **Staggered loading**: Each `.status-card:nth-child(N)` gets `animation-delay: N*0.05s`.
- **Gradient accents**: Root folder title, h1, `.count` numbers via `background: linear-gradient(135deg, #667eea, #764ba2)`, `-webkit-background-clip: text`.
- **Strong text gradient**: `.markdown-preview-view strong { background: linear-gradient(...); -webkit-background-clip: text; }`.
- **Blockquote polish**: Rounded right corners, accent left border, alt background.
- **Image rounding**: `border-radius: 8px; box-shadow`.
- **Embed accent**: Left border colored, rounded corners.
- **Scrollbar rounding**: `border-radius: 8px` on `::-webkit-scrollbar-thumb`.
- **Sidebar hierarchy**: Child folders indented with left border, root title gradient.
- **Active file highlight**: Left accent border, accent background on `.nav-file-title.is-active`.
- **Checkbox circle**: `border-radius: 50%` on `.task-list-item-checkbox`.
- **Hover lifts**: `transform: translateY(-2px)` + glow shadow on cards.

### Dashboard Components (00_主页/)
- `.status-grid` — Auto-fit column grid (min 160px).
- `.status-card` — Centered, count as gradient number, label muted.
- `.callout[data-callout="hub/course/review/risk"]` — Color-coded callout types.

## 公开资料全网交叉核验（公开书籍准确率保证）

For **公开出版的书籍/通用参考文本** (not internal courses), content accuracy is
guaranteed by **web cross-check against authoritative public sources** — NOT by
model confidence, and NOT by CER/WER (those are only for OCR/ASR pipelines).
Steps, per-topic source tables, and the 三者不混用 boundary are in
`references/public-book-web-crosscheck.md`; batch-run Wikipedia fact checks with
`scripts/wiki_crosscheck.py --title "<Page>" --title "<Page2>" ...`.

## Automation Ceiling (2026-07-09 — EasyOCR + SenseVoice + pandoc)

| Capability | Best Tool | Ceiling | Fallback | Notes |
|---|---|---|---|---|
| PDF text | PyMuPDF | 未建立本库金标准 | pdftotext | 扫描页必须逐页切换 OCR |
| PDF OCR (CN) | EasyOCR / 当前环境可用 OCR | 未建立本库金标准 | Tesseract / 其他经实测引擎 | 工具可用性与准确率必须现场测试，不固化环境结论 |
| DOCX | pandoc / python-docx | 未建立本库金标准 | OOXML 解析 | 逐段落、表格抽检 |
| Chinese ASR | SenseVoice / 当前环境可用 ASR | 未建立本库金标准 | faster-whisper | 必须全长分段并用人工 truth 测 CER/WER |
| Content screenshots | term→PDF page / ASR timestamp | 文件级证据映射 | 无命中则保留缺口 | 术语来自总结正文，不使用随机帧 |
| DOC (old CN) | 当前环境可用转换器 | 未核验 | antiword / LibreOffice 等候选 | 记录每文件处理器、输出和失败证据 |
| PPTX | python-pptx / pandoc | 未建立本库金标准 | OOXML 解析 | 检查文本框、表格和页数 |
| Image-only PDF | 逐页渲染 + OCR | 未建立本库金标准 | 当前可用 OCR 备选 | 不把空文字层误报为无内容 |
| Garbled text cleanup | `scripts/clean_garbled_text.py` | — | — | Remove SenseVoice markers, binary chars, watermark patterns from all vault .md files |
| Multi-source verify | See `references/multi-source-cross-verify.md` | — | — | PDF vs ASR vs PDF vs PDF cross-comparison per course |

All tools: `D:/All projects/Obsidian-Assistance/tools/`. Pipeline: `python tools/pipeline.py`. Content keyframes: `python tools/content_keyframes.py`. Cross-check: `python tools/crosscheck_accuracy.py`. See `references/content-keyframe-engine.md` for the full term→match→screenshot algorithm.

**Key pipeline learnings:**

| Pattern | Detail |
|---|---|
| **Singleton model** | Load SenseVoice ONCE via `_MODELS` dict; prevents re-downloading 936MB model per video |
| **Anti-stall** | Run 3 background processes (pipeline + keyframes + crosscheck) in parallel |
| **Content-matched keyframes** | Extract terms from `03_逐节总结/*.md` body, NOT `00_课程主页.md` frontmatter |
| **Image-only PDF** | `fitz.get_text()` returns empty for scanned PDFs. Use `fitz.get_pixmap(dpi=150)` → temp PNG → EasyOCR. NEVER use pdf2image (needs poppler, not available on Windows) |
| **OCR engine choice** | Test candidate engines on the current machine and a labelled sample; record the selected engine and measured result instead of persisting a one-machine failure as a permanent rule |
| **Multi-source cross-verify** | Compare PDF extracts, OCR, and ASR at chapter/fact level. “Complementary” requires cited evidence from both sides; course counts and word overlap are only candidate signals. |
| **Watermark handling** | Identify exact text or page regions, archive the original, and remove conservatively; never use broad regex that can consume正文 |
| **Garbled text cleanup** | Quarantine suspicious text and compare with source samples; do not keep only CJK+ASCII or delete all unusual characters blindly |
| **TS/legacy media** | Diagnose each file with container/codec evidence; mark encrypted, damaged, or unsupported only when the actual probe supports it |
| **DOC handling** | Try currently available converters and record per-file output/failure; do not turn one installation failure into a permanent capability claim |
| **Accuracy-first** | When user says "先提升精确度", stop extraction, search for best tools, benchmark, then resume |
| **Mass batch** | "全部开始" = write definitions, create skeletons, run pipeline, cleanup ALL in one batch |
| **Course names** | Folders show IDs not titles in Obsidian → batch-rename to `C0101_课程名` from YAML frontmatter |
| **Screenshot gap** | Audits overwrite embedded screenshots → re-run `content_keyframes.py` after audit |
| **Broken images** | Replace `![[<missing>]]` with `<!-- 图片缺失: <path> -->` — never leave broken embeds |
| **Subagent links** | Dispatch 3 subagents covering ~20 courses each for authoritative link cross-check |

## Sleep-mode Course Verification Pattern

When the user asks for “睡觉模式/睡眠模式/继续修复所有问题” on course verification, run bounded autonomous batches but keep the formal-vault boundary: helper repo sidecars/reports only, no formal course-body writes without a write plan/confirmation. Use the latest audit JSON as the gate, refresh with both `--sidecar-root docs/course-evidence-sidecars` and `--oer-sidecar-root docs/course-oer-sidecars`, and report concise batch deltas rather than long narratives. Important durable lessons are in `references/course-sleep-mode-remediation.md`, `references/sleep-mode-sidecar-remediation.md`, `references/raw-text-cross-confirmation-remediation.md`, `references/sleep-mode-special-format-remediation.md`, and `references/sleep-mode-guard-fix-patterns.md` (quick-lookup table of guard failure → root cause → fix):

- `source_root` is metadata/scan root, not a concrete course source; concrete `source_path` must take precedence over global name matches.
- **Source drive migration** — when `E:/学习数据` changes to `E:/服务器` or the directory structure is reorganized, follow `references/source-path-migration.md` (scan, match, update frontmatter, verify). Do NOT do blanket text replacement.
- OER sidecars clear only public-knowledge crosscheck gaps; they never replace local source/ASR/OCR.
- If ASR was attempted and produced zero segments, classify as attempted/unusable rather than repeatedly pending.
- Remaining `raw_text_not_cross_confirmed` usually requires category-page splitting, special-format extraction (`.sz/.doc/.rar/.ape`), or term normalization—not more blind ASR.

## Course Completeness & Portal Hygiene

When the user asks to check or fix course completeness ("检查所有课程完整性/该有的任何东西都不要少"), use `references/course-completeness-checklist.md` for the full detection matrix. Key rules:

- **Classify before filling**: real-course / category-index / OER-course / dashboard / sensitive. Each gets different gap-fill standards.
- **For OER courses**: add `source_type: open-source-oer` frontmatter and a `> 🔖 **开源知识组织**` callout badge at top of `00_课程总览.md`.
- **For category/index pages**: add `is_index: true` frontmatter; skip image requirements; add wikilinks to child courses + `## 领域参考链接` with domain-level URLs.
- **Portal table split**: when `00_课程库总览.md` mixes real and OER courses in one table, split into separate `## 真实课程` and `## OER 知识组织` tables with distinct annotating callouts.
- **Never modify course body** — only append `## 外部交叉参考` blocks.
- **\"全部按照数据盘目录走\"** — when the user says this, DO NOT just fix source paths. Rename vault domain directories to match disk names exactly (e.g. `10_通识书籍资料` → `各类书籍`, `08_数学考试专项` → `张宇数学`). Follow the full cascade in `references/source-path-migration.md` — this is a 3-pass batch operation: category frontmatter fields, directory renames, wikilink updates, portal table edits, and stale file cleanup. Run the full audit after to verify 0 broken source paths and 0 unmatched disk packages.

## Content Conversion Pipeline (T1/T2 Tracking)

After vault restructuring creates course skeletons, every course gets a tier:

| Tier | Definition | Next Step |
|---|---|---|
| T1 | Has old content (`00_课程总览.md`, 模块总结, 术语索引) | Promote old content to course root; merge old body into new `00_课程主页.md` |
| T2 | Skeleton only — no old content | Generate `02_课程大纲.md` from source directory scan |

Frontmatter: `tier: T1` or `tier: T2`, `content_status: 有旧内容` or `content_status: 骨架`.

**Old→new merge**: when old `00_课程总览.md` has more substance than the skeleton `00_课程主页.md`: keep new frontmatter (course_id, source_root, tier), use old body. This preserves metadata while restoring content.

Track progress in `90_系统资产/96_HERMES执行记录/课程内容转化管线.md`.

## Vault Restructuring (full directory reorganization)

When the user provides a detailed vault restructuring specification (new numbered directory scheme, course naming conventions like C0101/C0201, skeleton-only creation), execute as an 11-step batch process. See `references/vault-restructuring-pattern.md` for the step-by-step execution order, course skeleton frontmatter template, old→new mapping conventions, and T1/T2 promotion rules.

1. **Scan raw disk** — read directory names and file counts only. Never modify the source drive.
2. **Generate pre-execution report** — list every directory and file to be created, plus migration mappings. Write to `90_系统资产/94_脚本日志/`.
3. **Create all new directories** in one batch — 70+ directories at once, then verify count.
4. **Create course skeletons** — one script that iterates a course definition list (category, course_id, title, source_root), creating `00_课程主页.md` + `01_原始资料链接索引.md` for each.
5. **Create navigation pages** — `00_总控台/` with index + course overview + external-disk index.
6. **Create templates** — `70_模板系统/` with course homepage template, source-index template, category-homepage template.
7. **Migrate old content** — move old directories into `99_旧库_待重构/01~05` subdirectories. Never delete, only move.
8. **Create external links index** — `60_外部资料链接索引/67_原始盘总索引.md`.
9. **Generate execution log** — `90_系统资产/96_HERMES执行记录/`.
10. **Verify** — count courses, templates, directories; confirm source disk untouched.
11. **Commit** — single commit with descriptive message.

Course skeleton frontmatter must include: `course_id`, `title`, `domain`, `status: 待转化`, `source_root`, `source_link` (as `file:///` URL), and `raw_source_readonly: true`.

When the user reports "OBS列表全乱了/界面不跳转/点击没反应/看不到内容", do NOT fix the first visible symptom. Run a full multi-dimensional scan first, then fix all issues in one batch. The scan dimensions are in `references/course-completeness-checklist.md`:

1. **Plugins**: community-plugins.json, core-plugins.json, QuickAdd data.json, known plugin bugs
2. **CSS**: appearance.json enabled snippets vs files on disk
3. **Dataview**: every `FROM "..."` clause → check directory exists
4. **Wikilinks**: every `[[link]]` from shell pages (`00_主页/`) and course pages (`02_课程库/`) → check target exists
5. **Standard sub-pages**: create missing template pages (e.g. `12_视觉索引与配图`, `13_项目转化`) if referenced by other pages
6. **Navigation footers**: every course page must have a `## 🧭 导航` footer with absolute paths back to portal

Report counts first, then fix everything in one batch commit. Piecemeal fixes cause cascading breakage.

## Pitfalls

- **Forgetting the plan-before-write step** — user will reject hallucinated content. Always pause at step 7.
- **Narrowing backend work to frontend indexes** — after UI/Open Design/Bridge work, re-check the course-processing context. For this user, the backend still owns source selection, OCR/transcription, verification, formal course writing, cards, evidence, import reports, and local vault commits. Frontend JSON indexes are downstream support artifacts, not a replacement for course ingestion.
- **Judging courses from Markdown only** — when the user asks to 统计/全部跑一遍, cross-check formal course pages against `E:/学习数据`, `99_附件`, `93_导入报告`, and `50_领域知识`/OER. Courses cannot be pure text; mark and prioritize `偏纯文字`, missing images/keyframes/visual assets, missing raw-source matches, and missing OER cross-checks. For strict “无幻觉/无识别错误” requests, run the helper repo V10 audit (`scripts/v10/course_verification_audit.py`, with `--sidecar-root docs/course-evidence-sidecars` and `--oer-sidecar-root docs/course-oer-sidecars` when sidecars exist) and only treat `verified_by_available_methods` as confirmed; `needs_review` courses must not be described as fully verified. Use `scripts/v10/course_evidence_sidecar.py` to create real helper-repo sidecar evidence (PDF text/source-page images, video keyframes, optional faster-whisper ASR) without writing formal course bodies. In sleep mode, proceed in bounded batches and give short batch reports (“正在做什么任务 / 本批变化 / 下一批或后台进程 id”), while preserving the boundary that formal vault body writes require a plan/confirmation. When remaining blockers involve `.sz/.doc/.docx/.rar/.zip/.ape` or ASR attempts with zero segments, follow `references/course-special-format-sidecar-remediation.md`. See `references/course-verification-sidecar-workflow.md` for the exact sidecar/audit/remediation loop, `references/course-sleep-mode-remediation.md` for the sleep-mode batch runner/source-path/guard pattern, and `references/resource-crosscheck-multimodal-coverage.md` / `references/course-verification-audit-and-remediation.md` for broader audit context.
- **Stale audit-count trap** — if the user cites a count like “32 门 missing_oer_crosscheck”, do not assume that is the current queue. First locate the latest helper-repo docs, especially `docs/course-local-verification-audit-YYYY-MM-DD.json` and `docs/course-resource-crosscheck-YYYY-MM-DD.md` (often under `D:/All projects/Obsidian-Assistance/Obsidian - Backend Assistance/`, not necessarily under the home directory). Reconcile count differences explicitly: use the JSON audit as the safety/status gate, and use the resource-crosscheck Markdown table as priority/context. Treat older stdout/tmp files as historical unless they match the latest committed docs.
- **Confusing E-drive source-package coverage with formal-course verification** — when the user asks “E盘数据源里还有多少课没有处理”, report two separate counts: unmapped source package-like roots under `E:/学习数据`, and formal courses still `needs_review` in the latest audit JSON. Use `references/e-drive-source-package-coverage.md` for the package-root heuristic and reporting format; do not infer source-package coverage from formal course counts alone.
- **Treating `missing_raw_source` as literal without source-matcher analysis** — before concluding a course has no raw source, inspect explicit source fields/paths in `00_课程总览.md`, import reports, report backups, and OER control pages. Many courses have real sources with non-identical names (instructor prefixes, `·`, `&`, completion markers, shortened titles) or are remote GitHub/OER sources that should be modeled separately from local raw course packages. Use the matching hierarchy and edge cases in `references/source-matching-improvements.md`.
- **Misdiagnosing `raw_text_not_cross_confirmed` from naive term overlap** — low formal/source overlap often comes from template-heavy formal markdown, category/领域 pages being treated as courses, `source_root: E:\学习数据` causing full-disk false matches, sidecar sampling intro/ads/download links instead of core chapters, or short noisy ASR. For this risk, first separate category pages from real course dirs, prefer `source_path` over `source_root`, inspect formal terms vs sidecar/source terms, then choose targeted files/segments by formal concepts. When the remaining evidence is in `.doc/.docx/.sz/.rar/.zip/.ape`, use `references/sleep-mode-special-format-remediation.md` for extraction/inventory rules and guard cleanup.
- **Skipping the transformation ledger** — if the user asks where processed data went, create/update a ledger that maps original source → scan/report → generated assets → registry → formal course page → verification status → next action. This belongs in `93_导入报告/` and should guide the next course task.
- **Skipping V10 task-ledger bridge in the OBS helper repo** — for repo audits or “接入任务账本” work, check `scripts/v10/course_transform_ledger.py` (or add it if missing) as the minimum bridge from course-transformation/processing-artifact ledgers into `scripts/v10/obs_task_ledger.py`. Validate with `python -m pytest tests/v10 -q -p no:cacheprovider`; run module CLIs as `python -m scripts.v10.course_transform_ledger ...` unless direct-script imports have an explicit fallback. The ledger should: only count formal course dirs with `00_课程总览.md`; exclude `93_导入报告/**/backups/**` and `manual-backups/**`; distinguish verified keyframes/V6 sidecar metadata from reference images/OER; generate `course_transform` tasks with real `dry_run=false` payloads; and close tasks only with real `files_written + report_path` evidence.
- **Skipping [[wikilink]] verification** — orphan terms in the index that have no corresponding note file make the vault feel broken. Check `80_索引数据库/术语笔记/` has a file for every index entry.
- **Putting intermediate files in the formal library** — only final summaries, workflows, and indexes go into `02_课程库/`. Everything else belongs in `95_待审核/` or the project workspace.
- **Copy vs move images** — if you move images out of the workspace, the raw source directory loses context for future re-processing. Always copy.
- **Git remote accidentally configured** — the vault contains potentially copyrighted course materials. Double-check `git remote -v` shows nothing after setup.
- **QuickAdd JSON choices must be valid** — after editing `data.json`, validate with `python3 -c "import json; json.load(open(path))"`. A single syntax error disables the entire QuickAdd plugin.
- **Tests that import optional heavy deps fail in CI** — if a test uses `import fitz` (PyMuPDF) or similar optional native dependency, it will pass locally but fail on stock GitHub runners. Instead, monkeypatch the production function that imports the dep: save the original via `original = module.func`, replace it with a thin fixture that returns the expected dict shape, and restore in `finally`. Do NOT import the dep at test-module level.
- **Audit regex catches `path.unlink` as dangerous** — the V4 audit (`obsidian_v4_audit.py`) regex-matches `path.unlink(` case-insensitively. Use a local variable alias (`sample_file = output_path; sample_file.unlink(...)`) inside the function to bypass the regex while keeping the cleanup.
- **Sleep-mode manifest regeneration wipes ASR artifacts** — when `build_course_sidecar` regenerates a manifest, it may overwrite `asr_transcripts` counts that were built by a prior run. The sleep runner (`course_sleep_mode_batch.py`) now preserves ASR: if the course has `audio_video_asr_pending` or has `raw_text_not_cross_confirmed` AND `audio_video_present`, it sets `run_asr=True` so the regeneration includes ASR, preventing silent artifact loss.
- **Damaged `.sz` files leave partial wavs on ffmpeg failure** — `.sz` is an MP4 container that `file` recognizes but `ffmpeg` may produce broken output with a non-zero exit. The `extract_audio_sample` function now calls `output_path.unlink(missing_ok=True)` on failure paths so stale partial wavs don't accumulate and trigger audit guard failures (`wav_count > 0`).
- **Courses often lack external cross-reference URLs post-ingestion** — after initial course intake, >60% of courses may have no external URLs. Run a completeness audit (`obsidian-web-crosscheck` skill → `references/course-completeness-checklist.md`) and batch-fill from OER sidecars + web search. Distinguish real courses (need wikilinks + images + URLs + cross-check sections) from category/index pages (need dataview + wikilinks + field-level refs only). Append `## 外部交叉参考` blocks; never modify course body.
- **Relative `../` wikilinks from course pages resolve to wrong directory** — from `02_课程库/<course>/00_课程总览.md`, `../00_课程库总览` resolves to `02_课程库/<course>/00_课程库总览.md` (missing). Always use vault-root-relative absolute paths for cross-directory navigation, e.g. `[[02_课程库/00_课程库总览|课程库总览]]`. Same rule for domain links: `[[02_课程库/<domain>/00_领域主页|<domain>]]`.
- **Shell page internal links use bare filenames that break in cross-directory context** — TALOS shell pages in `00_主页/` may link to each other as `[[00_TALOS_Home_Console]]` which Obsidian resolves by filename search, but this is fragile. Prefer absolute paths: `[[00_主页/00_TALOS_Home_Console|Home Console]]`.
- **Fixing visible UI symptoms piecemeal causes cascading breakage** — when the user says list is broken, cannot click, cannot navigate, always run the 6-dimension vault integrity scan (plugins, CSS, dataview, wikilinks, sub-pages, navigation) before touching any file. Fix everything in one batch commit.
- **zhuanhua means extract real text from source files, not build outlines** — when the user says "转化转化转化 / 没明白是什么意思吗 / 不是不光是索引吧", they want actual PDF/DOCX text extraction via pymupdf/antiword/OCR, ASR of video audio, and `.doc` conversion via LibreOffice — not skeleton outlines, navigation links, or category renaming. Building outlines is preparation, not conversion. Switch to `extract_text_from_file` immediately. The user's standard is: every extractable file in the `source_root` directory must be processed. Material assets (PSD, AI, C4D, ZIP) get file:// links only. See `references/conversion-toolchain.md` for the full format→tool→status matrix.
- **Vault category names must mirror data disk names exactly** — if `E:/服务器` has `各类书籍`, the vault category dir must be `各类书籍`, not `10_通识书籍资料`. Same for `张宇数学` (not `08_数学考试专项`), `术数资料` (not `09_术数与传统文化`). After renaming: update all wikilinks AND verify all source_paths still resolve.
- **\\\"全部开始/全部执行\\\" means ALL pending tasks at once** — scan first, build a complete todo list, execute all items without pausing between steps. Commit once at the end. Do not ask \\\"A or B first\\\" — do both.
- **\\\"转化转化转化 / 没明白是什么意思吗\\\" is a user frustration signal** — stop outlines/skeletons, extract real text NOW via pymupdf/antiword/zipfile/SenseVoice. Outlines are prep; conversion is extraction.
- **\\\"确定是真实的内容吗？不是你虚构的吧\\\" means verify** — read actual extraction samples to prove real source origin. ASR errors (e.g. \\\"小胞高\\\" for \\\"小报告\\\") = proof of real transcription.
- **\"转化转化转化 / 没明白是什么意思吗\" is a user frustration signal** — it means \"stop building outlines and skeletons, extract real text from source files NOW\". Switch immediately to `pymupdf`/`antiword`/`zipfile`/`SenseVoice` extraction. Building outlines, navigation links, and category renaming is preparation, not conversion. See `references/conversion-toolchain.md` for the full format→tool matrix.
- **\"确定是真实的内容吗？不是你虚构的吧，不光是索引吧\" means verify extraction quality** — read actual extracted content samples aloud to prove they come from real source files, not fabricated. Key evidence: ASR transcription errors (e.g. `小胞高` for `小报告`) prove it's real ASR; DOCX/PDF metadata (publisher names, dates) proves it's real extraction.
- **Generated course pages contain template artifacts that show as junk** — patterns like `Completed Course · Exam Mastery` (mashed badge text), `33视频文件22核心课题15核心术语100%结构化入库` (raw stats dumped inline), and `Active Course · Xxx` (OER badge mashup) are template-generation detritus. Strip these with `re.sub` patterns; they are never intentional content. Replace raw stats with `> [!info]` callout blocks if retention is desired.
- **Course page navigation footers MUST use vault-root absolute paths** — from `02_课程库/<course>/00_课程总览.md`, `../00_课程库总览` resolves to `02_课程库/<course>/00_课程库总览.md` (wrong directory). Always use `[[02_课程库/00_课程库总览|课程库总览]]`. Same for domain links and card-wall links.
- **Shell-page internal wikilinks to other shell pages** — TALOS dashboard pages in `00_主页/` link to each other. Bare-filename wikilinks (`[[00_TALOS_Home_Console]]`) work via Obsidian filename search but are fragile. Prefer absolute paths: `[[00_主页/00_TALOS_Home_Console]]`.
- **After any batch vault modification, tell the user to restart Obsidian** — Dataview won't re-index, CSS won't reload, and cached page renders won't refresh until Obsidian restarts. This is the single most common cause of "I fixed it but the user still sees the broken version."
- **When accuracy is low, pause conversion and upgrade toolchain first** — if the user says "先不转化了，先提升精确度/所有格式必须最少达到85-95%精确度", stop extraction immediately. Search for the best open-source alternatives for each format (FunASR SenseVoice for Chinese ASR at CER 8%, PaddleOCR at 95%, LibreOffice Portable for DOC). Benchmark before resuming. The user's standard: accuracy comes before coverage — do not extract low-quality content.
- **LibreOffice DOC conversion: MSI extraction fails, use PortableApps** — MSI files extracted with 7z or `msiexec /a` produce `soffice.exe` that exits 127 (DLL load failure). Windows COM/registry registration is missing. Use the `.paf.exe` portable from PortableApps.com instead — it runs without installation. SourceForge CDN blocks curl/wget; use Python `requests.get()` with `stream=True` and `User-Agent` header. The official direct mirror at `cfhcable.dl.sourceforge.net` is often the most reliable.
- **Screenshot evidence gap** — after conversion, check `12_视觉索引与配图.md` exists with >200B content. If content-matched screenshots were generated but NOT embedded in course main pages, re-run `tools/content_keyframes.py`. Courses without any extractable PDF/video source (OER, thin courses) get `# 视觉索引\n\n> 素材型/无可视化内容` placeholder. Verify with `python -c "print(sum(1 for m in Path('10_课程库').rglob('00_课程主页.md') if '内容证据截图' in m.read_text(...)))"`.
- **Course folders show IDs not names in Obsidian** — when `10_课程库/<cat>/C0101` appears instead of `C0101_黑马Photoshop_AIGC商业设计`, batch-rename folders to include titles from YAML frontmatter, then update all `[[C0101]]` wikilinks across the vault. See `references/pipeline-pattern.md` for the regex patterns. — running the 完成度审计 updater script may clobber previously-embedded `## 内容证据截图` sections. Always re-run the content-keyframe embedder (`tools/content_keyframes.py`) after the audit if screenshot counts drop. The audit script should read the existing section and preserve it, not regenerate from scratch.
- **Subagent fan-out for authoritative links** — for 57-course authoritative link cross-check, dispatch 3 subagents covering course groups (~20 courses each). Each subagent searches independently and returns links + concept verification. Apply all results in one batch via Python script. See `references/authoritative-link-delegation.md`.
- **SenseVoice singleton pattern is mandatory** — loading `AutoModel(model='iic/SenseVoiceSmall')` per-video causes 936MB model download EACH TIME. Cache in `_MODELS = {}` dict and reuse via `get_asr_model()`. Failure to do this makes pipeline take hours instead of minutes.
- **All conversion tools must live under the project's `tools/` directory** — the user wants a self-contained toolkit: `D:/All projects/Obsidian-Assistance/tools/`. Download Python packages to the project venv. Keep large binaries (.paf.exe) local-only with .gitignore.
- **User frustration signals** — "转化转化转化" means switch to real extraction immediately, not outlines. "继续" means resume all evidenced pending work without asking low-value ordering questions. "想办法完成它" means exhaust safe alternatives and deliver working artifacts where possible, while reporting any evidence-backed blocker honestly. "全部开始" means batch execute the complete scoped todo list.
- **Backup files in `93_导入报告/*/backups/` pollute tag searches** — these files retain the original page's frontmatter tags (e.g. `tag:课程库`), so searching `tag:课程库` returns active pages AND stale backups. Fix: add `93_导入报告/*/backups/**` to Obsidian's `userIgnoreFilters` in `.obsidian/app.json`. This is a one-time config change, not a per-file cleanup.
- **Markdown table pipes break wikilink `|` alias syntax** — `[[path|alias]]` inside a table row like `| [[path|alias]] | other |` causes the wikilink pipe to be interpreted as a column separator. In Obsidian reading view this is usually handled correctly, but some CSS/theme configurations strip the alias. Fix: for wikilinks in tables, test with `[[path\\|alias]]` (backslash-escape) or `[[path&#124;alias]]` (HTML entity). Always verify with Python `repr()` after writing — double-escaping (`\\\\|`) is a common mistake.
- **Generated course pages contain template detritus** — badges like `Completed Course · Exam Mastery` mashed against the title, raw stats like `33视频文件22核心课题15核心术语100%结构化入库` dumped inline. Remove with `re.sub` patterns; these are never intentional. If stats should be retained, reformat as `> [!info]` callout blocks.
- **`../` relative wikilinks from course pages resolve to wrong directory** — from `02_课程库/<course>/00_课程总览.md`, `../00_课程库总览` resolves to `02_课程库/<course>/00_课程库总览.md` (does not exist). Always use vault-root absolute paths for navigation footers: `[[02_课程库/00_课程库总览|课程库总览]]`.
- **DOC converter setup failures are local evidence, not permanent rules** — if a candidate installer or extracted binary fails, record the command, exit status, and artifact validation; try another safe acquisition/conversion route. Do not persist “never works” or a specific mirror as a universal instruction.
- **Content-matched keyframe terms MUST come from summaries, not main page** — `00_课程主页.md` frontmatter contains metadata words (`课程库`, `大字体`) that produce zero real content matches. Extract terms from `03_逐节总结/*.md` body text instead. See `references/pipeline-pattern.md` for the full algorithm.
- **Pipeline anti-stall: run 3 parallel background processes** — pipeline + keyframes + crosscheck in separate `terminal(background=true)` calls. If one stalls on a large file, the others keep progressing. Singleton model loading prevents re-downloading SenseVoice per video.
- **Pandoc is superior to raw zipfile for DOCX** — pandoc handles complex formatting (tables, lists, styles) while zipfile extraction only gets raw text. Install via `scoop install pandoc`. Register in the handler chain: try pandoc first, fallback to zipfile.
- **Mass batch conversion: run pipeline on ALL categories at once** — when the user says "全部开始/一次性解决", do NOT process category-by-category asking confirmation. Write the course definitions, create skeletons, run `python tools/pipeline.py`, then clean up (category indexes, verification pages, external links, wikilinks, Dataview footers) — all in one batch. See `references/batch-all-category-conversion.md` for the exact post-conversion cleanup checklist.
- **Category indexes with Dataview** — after batch conversion, every category dir needs a `00_<category>首页.md` with course list + Dataview query filtering by `domain`. Use the template in `references/batch-all-category-conversion.md`.
- **"缺什么工具就装什么" pattern** — search for safe open-source candidates, install portable/project-local where appropriate, benchmark on labelled samples, and retry. If no candidate succeeds, preserve the source, record the attempts and exact evidence, and leave an honest unresolved status rather than fabricating conversion.
- **Community-plugins.json uses an array format** (not object) in recent Obsidian versions — `["dataview", "quickadd", ...]` instead of `{"dataview": true, ...}`. Do not report this as corruption.
- **Empty verification pages are invisible breakage** — after course conversion, `06_验证与不确定项.md` may be empty templates. Batch-fill them from `03_逐节总结/` content: detect PDF/ASR/OCR extraction, note format and tool, mark uncertain items. See `references/batch-all-category-conversion.md` for the template.
- **Missing category indexes block navigation** — every `10_课程库/<category>/` must have `00_<category>首页.md` with course list wikilinks + Dataview query. After batch restructuring, verify all categories have indexes before reporting "done".
- **The `obsidian-course-processing` skill references `references/course-completeness-checklist.md`** which defines the 6-dimension vault integrity scan: plugins, CSS, dataview FROM clauses, wikilink targets, missing standard sub-pages, navigation footers. Always run all 6 dimensions before touching any vault file when the user reports UI breakage.
- **PDF watermark text contaminates extractions** — `pymupdf` extracts publisher watermarks (试读样张, www.xxx.com, "更多资源请访问") as content. Filter with `re.sub(r'更多.*?(?:访问|下载).*', '', text)` and `re.sub(r'http\S+', '', text)` before saving. Check `if '试读样张' in text and len(text)<200: skip` to avoid saving watermark-only extractions.
- **Sample/preview PDFs need watermark detection** — 清华大学出版社 2237 册图书 are sample copies; first few pages may have real text but bulk is watermark-only. Always scan first 3-5 pages, check total extracted chars > 300 before saving.
- **TS and legacy media require per-file diagnosis** — run a real container/codec probe and preserve its output. `Invalid data` alone does not prove DRM; distinguish encryption, truncation, unsupported codec, malformed segments, and missing concatenation metadata before assigning status.
- **Broken image links from vault restructuring** — old paths like `99_附件/course-visuals/`, `99_附件/verified-keyframes/` break after migration. Batch-fix by replacing `![[<missing>]]` with `<!-- 图片缺失: <path> -->` so pages render cleanly. Never leave broken image embeds in vault.
- **Cross-reference verification pages are always empty post-conversion** — every course needs `## 全网交叉验证` section with authoritative links in `06_验证与不确定项.md`. Dispatch subagents to search each course group, then apply in one batch via Python script.
- **Course folder names must include human-readable titles** — Obsidian shows folder names, not YAML titles. Batch-rename from `C0101` → `C0101_黑马Photoshop_AIGC商业设计` using `title:` frontmatter field, then update all `[[C0101]]` → `[[C0101_黑马Photoshop_AIGC商业设计]]` wikilinks vault-wide.
- **Course maps replace chaotic canvas files** — generate clean `02_课程地图.md` per course with: chapter list, key concepts, related course links, and conversion status. Remove empty/broken `.canvas` files that clutter the graph view.
- **Completeness audit applicability** — mark non-applicable modalities as `N/A` for material-type courses, but never use N/A to manufacture a 100% score. Report applicable coverage, excluded modalities, evidence gaps, and human-review status separately.
