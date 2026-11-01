---
name: obsidian-knowledge-base
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/productivity/obsidian-knowledge-base/SKILL.md
---

---
name: obsidian-knowledge-base
description: Build and maintain Obsidian knowledge bases from course materials — transcribe, OCR, verify, summarize, card-ify, and import. Covers vault structure, plugin config, UI/CSS, template registration, and Windows-specific encoding fixes.
tags:
  - obsidian
  - knowledge-base
  - course-processing
  - vault-maintenance
trigger: user asks to process course materials into Obsidian, set up a vault, fix plugins, or enhance vault UI
---

# Obsidian 知识库搭建 Skill

## When to Use

- User provides course materials (audio/video/PDF/docs) to import into Obsidian
- User asks to set up, fix, or enhance an Obsidian vault
- User wants to automate knowledge-base ingestion pipeline
- User says "全流程跑通，不用我管" or "不用我管" or "全部流通跑通" → switch to FULL AUTOMATION mode (see §1a below)
- User says "关键帧和需要人工的你去找资料进行核对" → self-verify all pending items from available transcripts/OCR, never ask for screenshots or manual confirmation

---

## 1a. Full Automation Mode (用户全自动模式)

**Trigger phrases:** "全流程跑通", "不用我管", "全部流通跑通", "只要最终资料能入库"

When triggered, switch to zero-intervention mode:

| Normal Mode | Full Automation Mode |
|:---|---:|
| Ask user for each decision | Self-resolve from available source data |
| Pause for confirmation at each stage | Only output write plan and final summary |
| Mark A1-A6 as "待人工确认" | Cross-ref transcripts/OCR → resolve automatically |
| Ask user to check screenshots | Extract content from video/audio descriptions |
| Wait for user to choose | Make reasonable default; report what was done |

**Proven technique — transcript cross-referencing replaces screenshots:**
- Multi-platform video transcripts (Mac/Win/iPhone/Android) can be cross-validated against each other
- ASR can be calibrated by course-specific term frequency (e.g. "NK/MK/Aka" → "Anki")
- PDF OCR, even noisy, can extract task descriptions and assignment details
- Course audio alone provides enough context for formula/concept extraction
- Teacher's voice summary in graduation sessions can be cleanly separated from student testimonials

**This session proved ALL 6 "需人工确认" items (A1-A6) could be resolved from transcripts alone.** See `references/auto-verification-2026-06-30.md` for the per-item proof.

**User trust signal:** When user says "人工审核文件还是和你说一样 你自己去对比" or "我只要最终入库的" — proceed with full auto-review. Compare intermediate files vs formal library, archive superseded ones, report final result only. Never loop back for manual confirmation.

## 1b. Bounded Sleep Mode / Long Autonomous Course Loops

When the user asks to "睡觉自动跑", "循环执行任务", "自己给自己列任务", or says they no longer want to choose courses, switch to a bounded autonomous loop **only after an explicit boundary is stated or inherited from the current Obsidian workflow**.

### Safe boundary contract

Use this contract unless the user gives a stricter one:

- Allowed write scope: the Obsidian vault (`E:/BaiduSyncdisk/Obsidian知识库/`) and external backups under `D:/All projects/Obsidian-Assistance/archived-config-backups/`.
- Allowed actions: create/update Markdown notes, Obsidian CSS snippets, bookmarks/appearance/community plugin JSON, reports, local `git add` + `git commit`.
- Forbidden actions: delete or move course body/source material, modify C: system files, modify unrelated D: projects, install software, upload/push/publish/login, edit secrets/API keys, run `rm -rf`, `git reset --hard`, or `git clean -fd`.
- Each round must do: backup changed files outside `.obsidian/plugins/` → write artifacts → validate JSON/hrefs/mojibake → local commit → update task queue.

### Loop protocol

After completing a course, autonomously create the next task queue:

1. Re-scan P1/high-value course candidates.
2. Choose the next course by: relevance to existing vault themes, source completeness, manageable size, and ability to produce a full portal/cards/review/index/report loop.
3. Process the course through material inventory → verification limits → summary → workflows → terms → knowledge cards → review cards → indexes → import report.
4. Commit locally.
5. Repeat until interrupted or blocked.

### Context-compression / preserved-task re-entry

Long autonomous loops often resume after context compression with a preserved task list that may lag behind actual disk/git state. On re-entry:

1. Treat the preserved todo list as a hint, not proof. First verify the vault Git status and latest commit for the course that appears in-progress.
2. If the course was already written, validated, and committed before compression, do **not** repeat the write. Run only lightweight safety checks (JSON/hrefs/mojibake if needed), then mark the stale `in_progress` select/process tasks as `completed` and create the next course tasks.
3. Report the clean safety point and commit hash before starting the next course.
4. Only resume writing when the latest commit/status show the course is genuinely incomplete.

### Self-check / vault health audit mode

When the user says “开始自检” after a course loop, do not continue selecting courses. Switch to audit mode:

When the user asks for a **全面源盘—Vault 映射与用户要求差距审计**, keep the source drive read-only and separate directory-level mapping from file-level evidence. Do not treat a course portal, `source_root`, or a `100%` label as proof of extraction or verification. Audit frontmatter validity, four-way source-path consistency (`source_root` / `source_link` / body path / material report), basic-page completeness, completion-state contradictions, old-path/Dataview drift, static wikilinks/images, OCR noise versus encoding corruption, watermark/promotional residue, and historical mis-merge/archive boundaries. Recount key files at the end; if the vault changed during scanning, report that it was not a stable snapshot and require a frozen rerun before destructive cleanup. Detailed checklist and proven metrics: `references/source-drive-vault-gap-audit-2026-07-10.md`.

1. Check git cleanliness and latest commits.
2. Parse core Obsidian JSON configs.
3. Scan markdown in the main vault areas for empty files, broken `href` links, malformed frontmatter, and mojibake markers.
4. Count formal course portals and import reports to verify course-loop integrity.
5. Distinguish true missing content from older naming conventions (`03_课程完整总结.md`, `03_章节总结.md`, segmented Day summaries, etc.). Do not rename/rewrite complete older courses just to satisfy a rigid filename checker.
6. If mojibake exists only in aggregate/index files, rebuild those from clean authoritative formal-course files or split knowledge cards, backup originals outside the vault plugin tree, re-run checks, and commit a focused fix.

Detailed pattern: `references/selfcheck-and-mojibake-repair-2026-07-01.md`.

### Candidate selection when P1 is exhausted

When remaining P1 courses are all large or have little/no documentation, prefer the least risky high-value candidate:

- Favor lower video count and smaller size over raw priority when source completeness is poor.
- Prefer courses that extend existing vault themes (e.g. design system, psychology/learning) and can still produce a useful title-level portal.
- For no-doc/no-subtitle courses, explicitly label the result as **title-level high confidence** based on folder/video names; do not imply transcript-level coverage.
- Do not unzip RAR/ZIP/part files, run EXE installers, or copy large media just to improve confidence; record those limits in `01_素材识别报告.md` and the import report.

### Interrupt / pause protocol

If the user says `暂停`, `停止`, `打断`, `不要继续`, or equivalent:

1. Stop starting new writes immediately.
2. If in the middle of a file batch, stop at the nearest safe point.
3. Report what was done, what remains, and the exact resume point.
4. Do not select or start the next course until the user says `继续`.

### Approval-system pitfall

Chat-level authorization such as "开启本任务 yolo" is a user workflow signal, but it may not actually change Hermes tool approvals. If a tool returns an approval block (`BLOCKED: ... user has NOT consented ... Do NOT retry`), obey it: do not rephrase or bypass with another tool. Tell the user to actually enable `/yolo` or `approvals.mode smart/off` in Hermes, then resume from the saved task queue.

See `references/bounded-sleep-mode-course-loop-2026-07-01.md` for the concrete session pattern and second-course selection example.

### Workspace & Project Organization

### Project Workspace Layout
```
D:/All projects/<project-name>/
├── work/              ← Raw course materials (mp3/mp4/pdf)
├── outputs/           ← Processing output (transcripts, OCR)
├── github/            ← GitHub auxiliary project
│   └── <repo-name>/   ← Git repo (scripts/CSS/docs only, no vault)
├── demo-vaults/       ← synthetic/smoke-test demo vaults
└── archived-*/        ← Archived intermediate files
```

### Root-spill triage
When the user asks what an unexpected `D:/...` root entry is, do read-only triage before acting: check type, size, timestamps, git markers, lockfiles, `node_modules`, package manifests, and sample config files. Classify it as formal project, generated demo vault, scaffold/temp project, cache/build artifact, or unknown. Do not delete immediately; if it is an out-of-workspace demo/scaffold, move/ask to move it under the appropriate `D:/All projects/<project>/demo-vaults/` or quarantine folder. See `references/root-spill-diagnostics-and-oer-crosswalk-2026-07-02.md`.

### Migration Pattern
When user says "迁移到D:\All projects" or similar:
1. `cp -r` entire workspace to target (or `robocopy` on Windows)
2. Verify git remote still works (`git remote -v` — SSH URLs are path-independent)
3. Update memory with new path
4. Clean up old location after user consent

### CODEX Workspace Cleanup
When user says "清理CODEX工作区" or "清理codex工作区":
- **Keep**: AGENTS.md, CLAUDE.md, .cursorrules — config/rule files
- **Delete**: date-stamped temp dirs (2026-06-*, etc.), generated project dirs
- **Rule**: Keep configuration and conventions; remove session temporary outputs

### Drive-root spillover triage
When the user asks why a folder appeared directly under `D:/` (for example demo vaults or scaffolds such as `OBS-V4-DEMO` / `info@latest`), treat it as a workspace-hygiene diagnostic:
1. Inspect read-only first: type, size, timestamps, top-level files, `package.json`/git markers, and whether it is referenced from the active project.
2. Classify the artifact before acting: Obsidian demo vault, frontend scaffold, generated report, cache, or real project.
3. Do not delete immediately. If it is useful demo evidence, migrate/quarantine under `D:/All projects/<project>/demo-vaults/` or another workspace-owned folder; if disposable, recommend deletion but wait for user direction.
4. If a skill/process caused the root write, patch that skill so future smoke tests use workspace-contained paths.

Reference: `references/workspace-root-spillover-triage-2026-07-02.md`.

### Project Re-entry / Total Audit Pattern
When user says "回到这个项目", "继续这个项目", or "全面梳理，包括课程":
1. Inspect the workspace, vault, course library, pending-review area, and helper Git repo before summarizing.
2. Distinguish formal structured course folders from category-level course index cards; do not treat placeholder/index cards as fully processed courses.
3. Sync stale index-card statuses after a course is formally入库 (e.g. change `未开始` → `已正式入库` and point to the formal course overview/report).
4. Update the course workbench (`02_课程库/01_课程处理工作台.md`) with paths, completed courses, next-course candidates, and Dataview queues.
5. Write a project audit report under `93_导入报告/项目总控梳理_<date>.md`; optionally mirror a concise copy to the helper repo `docs/` and commit/push.

See `references/session-2026-06-30-workspace-audit-and-cleanup.md` for the concrete audit/checklist and intermediate-file archive pattern from the workspace migration + first-course completion session.

### Auxiliary Repository Documentation / Upload Mode

When the user asks to "整理项目经验 / 总结 / 上传到仓库" for this Obsidian project, treat the target as the **auxiliary project repository**, not the real vault:

1. Prefer `D:/All projects/Obsidian-Assistance/` as the current Git repo for the auxiliary helper repository. Older sessions may mention `D:/All projects/Obsidian-Assistance/github/Obsidian-Assistance/`; treat that as a legacy fallback and verify with `git status -sb` before using it.
2. For helper-repo cloud-hygiene cleanup and audit/CI hardening, use `references/helper-repo-cloud-hygiene.md` plus `references/helper-repo-cloud-hygiene-audit-hardening.md` (for forbidden-file boundary checks, case-insensitive artifact detection, dynamic self-audit-script exemption with `Path(__file__).resolve()`, and async reviewer follow-up discipline).
2. Write only脱敏 project docs, scripts, templates, and reusable process notes. Do **not** copy real vault notes, `.obsidian/`, source course files, ASR/OCR full text, transcripts, media, archives, or private configs into the repo.
3. Before committing, run a scoped check that staged files are only expected helper-repo docs/scripts and do not match forbidden patterns: `.obsidian/`, `work/`, `outputs/`, `transcripts/`, `ocr/`, `asr/`, `*.sqlite`, `*.mp3`, `*.mp4`, `*.pdf`, `*.zip`, `*.rar`, `*.7z`, or secret/token patterns.
4. If preserved todo/context says a different vault task is in progress (e.g. deep-check/course loop) but the latest user message asks for documentation upload, obey the latest user message and do not resume stale todos.
5. Commit with a docs-scoped conventional commit and push the auxiliary repo only.

See `references/auxiliary-repo-doc-upload-2026-07-01.md` for the session pattern and safety checklist.

When the user pastes a broad Obsidian/Hermes/Codex/CC-Switch architecture and says “上传” or “找到这个项目可以吸收的”, convert it into a **sanitized absorption roadmap** in the helper repo: classify immediate/stable-later/concept-only/excluded items, link it from README, and PR it with tests/audit. Do not copy formal vault content. See `references/auxiliary-repo-fullchain-absorption-2026-07-01.md`.

When the user names a large public skill/knowledge repository and asks to “吸收 / 提取知识 / 入知识库” (for example `lingxling/awesome-skills-cn`), treat it as an **open-source knowledge-source absorption** task, not as an install/run task: verify license/commit/file tree via GitHub API, prefer API tree + selected raw Markdown over full clone for huge repos, write a usage-layer node under `50_领域知识/`, create category/candidate/roadmap pages plus `source-summary.json`, update bookmarks/Home Console, and validate JSON/links/no raw HTML before a local commit. Candidate skills are not trusted/installed until individually reviewed. See `references/awesome-skills-cn-absorption-2026-07-03.md`.

When the user says the workflow is not needed yet and asks to “全面分析对比” or “全方位升级 OBS 知识库”, narrow the scope to **Obsidian knowledge-base upgrade assets**: UI/IA, Talos-like dashboard, Dataview/MOC/templates, theme-safe scoped CSS, demo pages, and tests. Do not spend that round on Hermes/CC/Codex workflow templates. Compare prior materials and repo state before claiming what is/isn't absorbed. See `references/v5-obsidian-knowledgeos-absorption-2026-07-02.md`.

### Course Diversity / Anti-Pure-Text Upgrade Mode

When the user says the course library is “全是纯文字”, asks to validate many courses, or says YOLO/全量吸收 for Obsidian course upgrades, treat it as a **course-content diversity and verification problem**, not as another summarization pass. First audit real course folders and quantify modalities (images, tables, Mermaid, Dataview, tasks, callouts, Canvas, review questions, source/evidence, action items). If most courses are thin/text-heavy, say so directly and add usage-layer assets: course diversity report, Talos course cockpit, visual-index/review-practice/verification templates, and scoped CSS. Preserve original course body files; do not invent screenshots or evidence. Commit formal vault changes locally only, and PR helper-repo scripts/templates/tests separately.

Detailed references:
- `references/v5-course-diversity-audit-and-talos-cockpit-2026-07-02.md`
- `references/v5-course-diversity-sleep-loop-2026-07-02.md`
- `references/v5-20-round-course-repair-loop-2026-07-02.md`
- `references/v5-auto-continue-course-diversity-2026-07-02.md`
- `references/v5-20-round-upload-and-repo-sync-2026-07-02.md`
- `references/v6-evidence-keyframe-foundation-2026-07-02.md`
- `references/v6-video-keyframe-extraction-2026-07-02.md`
- `references/talos-control-console-and-v8-training-2026-07-02.md` — TALOS console stack, Kanban/heatmap/V8 active-training loop, and repeated-继续 autonomous layer workflow.

### V6 Evidence / Keyframe Upgrade Mode

Reference: `references/v6-evidence-toolchain-complete-2026-07-02.md` captures the completed V6 toolchain, proven state, and stop/switch boundary.

- `references/v6-evidence-keyframe-foundation-2026-07-02.md`
- `references/v6-evidence-toolchain-complete-2026-07-02.md`
- `references/v6-real-evidence-closed-loop-2026-07-02.md`

When continuing into a real V6 pilot, use a strong course-name local source match, dry-run first, render one page/keyframe, visually verify the produced image, then promote metadata from `pending-verification` to `verified` only after that verification. Write `11_证据索引.md`, `12_真实截图与关键帧.md`, back-link `04_关键图表与课件索引.md`, run image evidence/structure audits, and commit the formal vault locally. See `references/v6-real-evidence-pilot-2026-07-02.md`.

When the user keeps an Obsidian sleep loop running after V6 foundations and specifically wants less pure text / no code exposure / more real visuals, combine three tracks: native-Markdown no-code cleanup, visual-coverage dashboard correction, and progressive promotion from reference images to verified video keyframes/PDF pages/public-source screenshots. Count only real image embeds as visual coverage; path mentions are just candidates. Always label `参考配图/非课程证据` separately from `真实截图/关键帧/PDF源页图`; reject visually mismatched frames instead of forcing them in. Detailed workflow, ffmpeg/PyMuPDF extraction patterns, raw-HTML cleanup rules, and staging safety: `references/visual-evidence-and-nocode-sleep-loop-2026-07-04.md`.

### Open knowledge / OER crosswalk mode

When the user asks to compare course knowledge against open knowledge sites, treat the task as **open knowledge/OER structure and licensing crosswalk**, not as free content scraping. Verify official sources where possible, record license/status, and absorb structures/metadata first: Wikimedia projects for encyclopedia/text/media/knowledge-graph patterns, OpenStax/LibreTexts/Open Textbook Library for textbook structure, MIT OCW/Wikiversity for course package structure, MDN for technical docs, Stack Exchange for Q&A structure, and Commons/Wikisource/Gutenberg for provenance/license metadata. If a source cannot be fetched, mark it as needing browser/manual verification. Course facts must still come from local course sources or V6 evidence. See `references/root-spill-diagnostics-and-oer-crosswalk-2026-07-02.md`.

When the user combines OER work with “睡觉模式 / 自己找任务 / 界面优先 / 直到停止命令”, run a bounded autonomous loop with explicit safety boundaries, then prioritize visible TALOS/course UI outputs over hidden analysis. After two manual applications, switch to reusable tooling instead of continuing by copy/paste: use the helper repo `scripts/v9/oer_crosswalk_generator.py` (dry-run by default, `--apply` required) to generate `14_开放知识交叉对比.md`, `15_FAQ问题驱动入口.md`, and optional OER samples. After 3+ OER sample courses exist, build or refresh an OER coverage dashboard before selecting more courses, so next work is driven by real coverage gaps. Always preserve the evidence boundary: if a course lacks V6 verified evidence, say so in the generated pages and do not promote open websites or generated FAQs to evidence. If the user says “执行完本轮停止”, finish only the current named round to a clean validation+commit point, do not enqueue another round, and report sleep mode stopped. Full patterns and validation checklists: `references/oer-crosswalk-generator-and-sleep-mode-2026-07-03.md` and `references/oer-coverage-dashboard-and-stop-protocol-2026-07-03.md`.

### Open-source skill-library → Obsidian course transformation mode

When the user provides a large open-source skills repository (for example `awesome-skills-cn`) and says some knowledge can be absorbed into the OBS/Obsidian course library, do not stop at a source index. Treat it as an **OER/methodology course transformation**:

1. Verify repo metadata first: source URL, license, default branch, commit SHA, file count / Markdown count, and whether the tree/API response is truncated.
2. Do not full-clone or copy huge repositories when API/raw Markdown is sufficient. If clone times out, switch to GitHub API tree + selected raw files; clean partial clone directories afterward.
3. Create a domain source index under `50_领域知识/...` with source summary JSON, category matrix, candidate list, and absorption roadmap.
4. If the user asks to put knowledge into courses, create a formal course folder under `02_课程库/<course>/` with: `00_课程总览.md`, `01_素材识别报告.md`, module lesson pages, `07_实操工作流.md`, `08_术语索引.md`, OER/crosswalk page, project conversion page, and review/training questions.
5. Also create aggregate knowledge cards under `03_知识卡片/课程知识卡片/` and review cards under `04_复习卡片/课程复习卡/`.
6. Preserve evidence boundaries: open-source skill repositories are OER/methodology sources, not V6 verified local-course evidence; candidate skills are not installed/trusted capabilities until individually read and tested.
7. Connect the new course to `02_课程库/00_课程库总览.md`, Home Console, and `.obsidian/bookmarks.json`; validate Markdown fences, raw HTML, mojibake, wikilinks, bookmark paths, JSON, and git diff scope before committing.
8. If the user asks to integrate **all useful analysis** into the project, build a course cluster instead of one giant note: create `02_课程库/<skill family> 课程群导航.md`, 5-10 focused topic courses, aggregate knowledge cards/review cards, and `50_领域知识/<domain>/04_课程化吸收总控.md`; wire all of them into Home Console, course overview, and Bookmarks. Each topic course should include overview, material inventory, module matrix, workflow, term index, project conversion, and review questions while preserving the OER/candidate-not-verified boundary.

### V4 auxiliary-repo engineering mode

When the user supplies a construction plan for the **Obsidian-Assistance helper repository** (for example a V4 learning-system generator plan), execute it as an engineering project in the helper repo, not as a vault modification:

1. Use a feature branch in `D:/All projects/Obsidian-Assistance/` (current helper Git repo; verify with `git status -sb` first).
2. Implement in small batches with one commit per layer when practical: repo audit, docs, templates, CSS, safe writer, generators, demo, tests, README/delivery report.
3. Keep all generated examples synthetic and explicitly marked as demo content; never copy real vault notes, source course materials, transcripts, OCR text, or `.obsidian/` configs.
4. All vault-writing code must default to dry-run and require explicit `--apply`; block path traversal; back up before overwrite; do not include delete-user-file logic.
5. Add tests for dry-run, apply, backup, path traversal, Chinese paths, YAML, Canvas JSON, Mermaid blocks, secret scanning, and formal-vault-path scanning.
6. If `*.canvas` is globally ignored, unignore only the demo canvas path (e.g. `!examples/v4-demo-course/*.canvas`) rather than all Canvas files.
7. Validate with `python -m pytest tests -q` and the repo audit script before pushing the feature branch.
8. After merging V4 into `main`, run a real isolated demo-vault smoke test under the workspace (for example `D:/All projects/Obsidian-Assistance/demo-vaults/OBS-V4-DEMO`, not `D:/OBS-V4-DEMO`) rather than stopping at repo tests: apply once with `--vault --apply`, validate file structure/YAML/Canvas/Mermaid, apply a second time to prove overwrite backups are produced, then commit a concise smoke-test report in the helper repo.
9. Treat generator-created runtime reports in `reports/` as ephemeral unless they are intentional delivery evidence; restore or ignore them before final status if they were only produced during smoke testing.
10. **Evidence-based autonomy rule:** when the user asks for “20 rounds”, “开启循环”, or similar, do not pre-invent a long list of plausible tasks. Start each round by inspecting real repo state (files, tests, CI, git, docs), identify one concrete evidence-backed gap, quote/summarize that evidence, then fix/verify/PR/merge. If no real gap exists, stop and say so rather than filling the requested round count with hallucinated work.
11. **Patch-thrash prevention rule:** if two consecutive patches in the same small file/region delete adjacent required lines, stop using targeted patch for that region. Re-read the whole file or relevant full function, rewrite the complete small file/function with `write_file`, then immediately run syntax checks plus the tight regression command. Record the error pattern in the task report; do not keep stacking micro-patches.
12. **Active skill/plugin use rule:** do not run V4/helper-repo loops on autopilot with one fixed checklist. At the start of each real gap, classify the problem and actively apply the relevant skill/tool: `systematic-debugging` for bugs, `test-driven-development` for behavior changes, `github-pr-workflow` for PR/CI/merge, `requesting-code-review` for pre-commit safety review, `delegate_task` for independent read-only review, and this skill for Obsidian/V4 boundaries. If a skill is loaded, it must change the next action; loading it as decoration does not count.

Detailed references:
- `references/v4-auxiliary-repo-engineering-2026-07-01.md`
- `references/v4-demo-vault-smoke-test-2026-07-01.md`
- `references/v4-autonomous-helper-repo-ci-loop-2026-07-01.md`
- `references/v4-evidence-based-autonomous-loops-2026-07-01.md`
- `references/v4-active-skill-use-and-error-evolution-2026-07-01.md`
- `references/backend-operator-entrypoint-refresh-2026-07-05.md` — treating backend README/scripts README drift as a tested implementation gap; update CI path, workspace demo-vault path, V4–V9 operator index, and add doc-drift regression tests.

## 2. Full Pipeline (8 Stages)

```
原始素材 → 素材识别 → 转写/OCR → 核验 → 总结 → 卡片 → 入库报告 → 清理
    1          2           3          4      5      6       7        8
```

| Stage | Output | Notes |
|:---|:---|---:|
| 1. 素材识别 | Material inventory | List all files, types, counts |
| 2. 转写/OCR | Audio/video .txt, PDF OCR .json | Whisper for audio, tesseract/pymupdf for PDF |
| 3. 核验 | Verification report | Cross-reference transcripts, NOT web search |
| 4. 总结 | Lesson-by-lesson summaries | Must cite source transcript |
| 5. 卡片 | Knowledge cards + Review cards | Split into single-file cards |
| 6. 入库 | Write to `02_课程库/` | Plan FIRST, user confirms |
| 7. 入库报告 | Import report → `93_导入报告/` | Document what was written and filtered |
| 8. 清理 | Archive intermediates → `95_待审核/` | User confirms final cleanup |

## 2. Content Filtering Rules

### Keep (write into vault)
- Instructor's main lecture and methods
- Core knowledge points, workflows, procedures
- Terminology and definitions
- Key examples and caution notes
- Convertible card/review content

### Strip (write a report instead)
- Student testimonials with real names
- Award/winner lists and work showcases
- Ops info ("scan QR code", "add WeChat xxx")
- Check-in, lottery, prize notifications
- Platform promotions and discount info
- Personal contact details

### Filter Procedure
```
Raw → Keep → write into formal notes
     → Strip → record in import report (why filtered)
     → Uncertain → mark "待人工补充"
```

## 3. Verification Methods (Priority Order)

1. **Audio transcript cross-ref** — multiple transcripts of same content
2. **Video transcript** — includes screen/UI descriptions
3. **PDF OCR** — task pages, structured content
4. **ASR calibration** — context-driven correction ("NK/MK" → "Anki")
5. **Do NOT rely on web search** for course-specific content — transcript is primary source
6. **Duplicated content** — name it in a section '13. 课件配图' with table of `![[path|80]]` thumbnails

## 4. Vault Directory Structure

```
E:/BaiduSyncdisk/Obsidian知识库/
├── 00_主页/          ← Dashboard (dashboard notes)
├── 01_收件箱/         ← Input inbox
├── 02_课程库/         ← Course library (one subdir per course)
│   └── <课程名>/
│       ├── 00_课程总览.md
│       ├── 03-06_逐节课完整总结.md  (numbered)
│       ├── 07_实操工作流.md
│       ├── 08_术语索引.md
│       └── 09_Anki操作指南.md  (if relevant)
├── 03_知识卡片/        ← Knowledge cards
├── 04_复习卡片/        ← Review cards
├── 50_领域知识/        ← Domain knowledge
├── 80_索引数据库/       ← Index + term notes
├── 90_模板/           ← Templates
│   └── 课程处理/       ← Course-specific templates (7 files)
├── 93_导入报告/        ← Import reports
├── 95_待审核/          ← Pending review
└── 99_附件/           ← Attachments
    └── images/<DayN>/  ← Course images
```

## 5. Plugin Config Fixes

See `references/obsidian-console-plugin-stabilization-2026-06-30.md` for detailed Developer Console error patterns, exact JSON fields, and verification checklist.

### cmdr — leftRibbon Error Fix
```
Error: this.plugin.settings.leftRibbon.forEach is not a function
Fix: leftRibbon must be an ARRAY [], not a dict {items: []}
```

### spaced-repetition — QuestionPostponementList Error
```
Error: this.list.splice is not a function
Root cause: plugin reads pluginData.buryList; if it is false/non-array, clear() calls .splice on a non-array.
Fix: set "buryList": [], "buryDate": "YYYY-MM-DD", and keep "questionPostponementList": [] for compatibility.
```

### omnisearch — Cache/Vacuum Error
```
Error: Cannot read properties of undefined (reading 'keys')
Often appears after deleting/archiving many files while Omnisearch loads stale cache and vacuums removed paths.
Fix: set "useCache": false and keep PDF/Office/Image indexing disabled for a clean rebuild on next restart.
If the same error persists after restart, temporarily disable or reinstall Omnisearch.
```

### templater-obsidian — Obsidian Version Mismatch
```
Plugin failure: templater-obsidian
TypeError: Class extends value undefined is not a constructor or null
```

Before blaming theme/config locks, inspect `.obsidian/plugins/templater-obsidian/manifest.json` and compare `minAppVersion` with the running Obsidian version shown in the console/window. In the 2026-07-01 case, Templater `2.22.1` required Obsidian `>=1.13.0` while the user was on `1.12.7`. The reversible fix is to remove `templater-obsidian` from `.obsidian/community-plugins.json` while preserving the plugin folder, or upgrade Obsidian / downgrade Templater deliberately.

### tasks-plugin Warnings
```
warn[tasks.Cache] Unexpected failure to create a list item from line: ...
Usually non-fatal, but if the user is watching Developer Console, make the reported files parser-friendly:
- normalize to LF line endings
- add blank lines before headings after lists
- replace dashboard tables with ordinary bullets when Tasks repeatedly flags them
```

### obsidian-git Local-Only Vault
```
Error: Aborted. No upstream-branch is set!
If the vault intentionally has no remote, preserve local-only backup:
- disablePush: true
- differentIntervalCommitAndPush: true
- autoPushInterval/autoPullInterval: 0
This keeps 30-min local auto-commit but avoids commitAndSync/push errors.
```

## 6. UI/CSS Enhancement

Default CSS snippets (installed in `.obsidian/snippets/`):
```
dt-knowledgeos.css                 — Base KnowledgeOS layout
obsidian-knowledgeos-dashboard.css — Dashboard card grid
obsidian-deep-ui.css               — Animations, glassmorphism, gradients
obsidian-knowledgeos-pro.css       — Premium dashboard/sidebar/card system
```

### When user says the vault is still ugly / not like expert public vaults

Do **not** just explain or make one small CSS tweak. Run a full UI + navigation + performance audit, then implement a cohesive usage layer:
1. Inspect `.obsidian/appearance.json`, snippets, theme, bookmarks, workspace, enabled plugins, top-level folders, large Markdown files.
2. Treat the raw file tree as the **storage layer** and build a curated **usage layer** with homepage cards, grouped bookmarks, and course maps.
3. Do not move completed course notes just to beautify the sidebar; preserve course paths and links unless user explicitly approves relocation.
4. Replace stale dashboard numbers with actual counts or explicit status labels.
5. If smoothness is the priority, temporarily disable heavy realtime AI plugins such as `smart-connections` and `copilot` in `community-plugins.json`; do not delete plugin folders.
6. Verify JSON parsing, href/link targets, snippet enablement, and git status before reporting done.

See `references/session-2026-06-30-knowledgeos-pro-ui-audit.md` for the concrete KnowledgeOS Pro audit/implementation pattern.

### Theme switching appears to do nothing

When the user says changing themes has no effect or asks whether the vault is locked, do not guess. First inspect `.obsidian/appearance.json`, installed theme folders, file permissions, lock/temp files, and active snippets. If `cssTheme` changes correctly but the UI barely changes, temporarily disable `enabledCssSnippets` after backing up `appearance.json`; large KnowledgeOS snippets can visually mask theme changes. Use a visually distinct theme (e.g. Cupertino) as a pipeline test, close DevTools if it is occupying the window, and restore snippets one by one to find the overriding CSS. Detailed recipe: `references/theme-switch-snippet-override-debug-2026-07-01.md`.

### Deep-UI CSS features to add (proven set from this session):
### Full UI Audit / Redesign Pattern
When the user says the vault is “不好看/不好用/不丝滑”, treat it as a **UI + information architecture + performance** audit, not a CSS-only task. See `references/session-2026-06-30-ui-audit-and-redesign.md`.

Checklist:
1. Inspect appearance/theme/snippets, workspace, bookmarks, plugin list, top-level folders, large markdown files, and existing dashboard notes before writing.
2. Do not move course content as the first response to an unreasonable left file tree. Use curated bookmarks, dashboard cards, and a `00_主页/03_左侧导航与课程地图.md` page to create the user-facing navigation layer while preserving real storage paths.
3. Fix stale homepage numbers/progress. Fake or outdated dashboard stats make the vault feel untrustworthy.
4. Repair stale bookmarks after directory renames (`01_收集箱`→`01_收件箱`, `98_待人工审核确认`→`95_待审核`).
5. If performance is part of “不丝滑”, identify large generated markdown indexes and heavy real-time AI plugins. Prefer reversible disable-from-`community-plugins.json` over deleting plugin directories.
6. Back up changed configs outside `.obsidian/plugins/` so Obsidian does not scan backups as plugins.
7. If a permission confirmation blocks writes, say directly that the write was blocked and ask for the exact confirmation needed; do not appear to hang.

### Deep-UI CSS features to add (proven set from this session):
- Staggered card entrance: `@keyframes fadeInUp` + `.status-card:nth-child(N) { animation-delay: N*0.05s; }` (up to 6 cards)
- Page slide-in: `@keyframes slideInRight` applied to `.markdown-preview-view`
- Gradient strong text: `.markdown-preview-view strong { background: linear-gradient(135deg, var(--text-accent) 0%, #a78bfa 100%); -webkit-background-clip: text; }`
- Blockquote: rounded right corners + accent left border + alt background
- Images: rounded corners + soft shadow (`border-radius: 8px; box-shadow`)
- Embed accent: left colored border + rounded corners
- Workspace tabs: rounded + hover transition
- Sidebar root title: gradient text; child folders: left border indent
- Active file highlight: accent left border + accent background
- Checkbox: `border-radius: 50%` (circular)
- Hover lift: `transform: translateY(-2px)` + glow shadow on status/knowledge/course cards
- Scrollbar: thinner (8px) + rounded thumb

### Graduation Ceremony Content Filtering (proven pattern)
When a course's final day is a graduation/ceremony session:
1. **Keep**: Teacher's summary remarks, learning methodology advice, future-learning recommendations
2. **Filter**: All student testimonial transcripts (named individuals sharing personal experiences), award/winner lists and work showcases, ops/promotional messages, QR codes, WeChat IDs
3. **Report**: Document in the import report exactly what was filtered and why

The student testimonials may contain valuable learning insights — extract the thematic takeaways (e.g., "students reported X technique worked") but remove personally identifying details.

### Check `.obsidian/appearance.json`:
```json
{
  "accentColor": "#0071e3",
  "cssTheme": "Minimal",
  "enabledCssSnippets": ["dt-knowledgeos", "obsidian-knowledgeos-dashboard", "obsidian-deep-ui"],
  "theme": "obsidian"
}
```

### When the user says the vault is not pretty / not like 大佬知识库

Do not stop at small CSS tweaks. The proven pattern is a **usage-layer rebuild** while preserving storage-layer course files:

1. Audit appearance, snippets, bookmarks, workspace, plugins, course frontmatter, and large Markdown indexes.
2. Replace stale dashboard counters/progress with real counts; stale fake progress makes the vault feel unprofessional.
3. Add/refresh a premium dashboard with Hero + stat cards + quick-entry cards + dynamic Dataview sections.
4. Use Bookmarks as the curated left menu; do not treat raw file tree as the user-facing navigation.
5. Create these usage-layer pages when missing:
   - `00_主页/03_左侧导航与课程地图.md`
   - `00_主页/04_领域仪表盘.md`
   - `02_课程库/02_课程卡片墙.md`
   - `02_课程库/<领域>/00_领域主页.md`
6. Do **not** move/delete formal course body files just to make the sidebar look better; preserve course content and links.
7. For smoothness, consider temporarily disabling heavy realtime AI plugins (`smart-connections`, `copilot`) in `community-plugins.json` while keeping plugin files intact.
8. Validate JSON, check generated links, write an audit report, and make a local-only Git commit.

See `references/ui-navigation-upgrade-pattern-2026-07-01.md` for the concrete pattern from the Obsidian UI/navigation overhaul session.

### Full portal-system upgrade when the user keeps saying “继续”

If the first dashboard/sidebar upgrade is accepted and the user keeps asking to continue, expand the usage layer in rounds instead of repeatedly tweaking the same homepage:

1. Generate `02_课程库/<领域>/00_领域主页.md` for each domain folder; skip formal course folders that already have `00_课程总览.md`.
2. Upgrade the completed course’s `00_课程总览.md` into a course portal with Hero, stats, learning route, module cards, timeline, Dataview search, and preserved verification/source section.
3. Upgrade `03_知识卡片/00_知识卡片总览.md` into a knowledge-card hub; if a course card aggregate is mojibake/garbled, back it up and rewrite it as a clean card-wall index pointing to the valid individual cards.
4. Upgrade `04_复习卡片/00_复习中心.md` into a review portal with active-recall guidance and course review-card entries.
5. Upgrade `80_索引数据库/00_课程领域索引.md` into a term/index hub. Use manually curated one-sentence definitions for high-frequency term cards; do not dump noisy term-note context into card descriptions.
6. Update bookmarks and CSS after each round, validate JSON/hrefs/mojibake, and make a local-only Git commit.

Detailed reference: `references/ui-portal-upgrade-pattern-2026-07-01.md`.

### TALOS system console upgrade

When the user asks to make the Obsidian vault a “TALOS 系统控制台” or says to 极限增强 OBS 界面, treat it as a command-layer rebuild, not another small CSS pass. Build a curated usage layer with `00_知识库总控台.md` plus TALOS module pages for task radar, evidence matrix, project console, course command, and system log; update scoped `talos-dashboard.css`, `appearance.json`, and bookmarks; preserve the storage layer. Always use real disk counts, back up touched configs/pages, validate JSON + href targets + Markdown fences, and commit locally only. Full pattern: `references/talos-control-console-upgrade-2026-07-02.md`.

### Purple Gemstone / Obsidian Workspace visual direction

When the user provides polished dark-purple Obsidian Workspace mockups or says those are the “best-looking” references, use **Purple Gemstone KnowledgeOS** as the preferred TALOS visual direction: deep navy/black backgrounds, glassmorphism cards, rounded product-grade panels, thin purple borders, soft violet glow, node-link decorative motifs, left navigation, top tabs/search, right inspector/AI panels, and bottom status bar. Treat earlier neon short-video Obsidian screenshots as module references (heatmap, graph, Calibre, Kanban, Canvas, Excalidraw), not the main visual style. Start with a design-system pass (`talos-purple-gemstone.css` + `28_TALOS设计系统.md`) before upgrading Home Console, Project Atlas, Review+AI, and course reading layouts. Detailed pattern and Codex prompt skeleton: `references/talos-purple-gemstone-visual-system-2026-07-03.md`.

### UI/UX designer handoff mode

When the user asks to extract UI/interface/interaction work for a dedicated designer, stop treating it as another CSS implementation loop. Audit existing TALOS pages, Purple Gemstone snippets, Bookmarks, QA/audit pages, course/evidence/review/project surfaces, then produce a designer-ready brief covering all modules, flows, states, components, Figma file structure, Obsidian implementation constraints, responsive breakpoints, and acceptance criteria. Wire the handoff into Home Console/Bookmarks, validate JSON/links/no raw HTML, and commit locally. Use `references/ui-ux-designer-handoff-2026-07-04.md` for the detailed checklist and proven output shape.

When the user mentions **OPEN DESIGN** or asks to form a new directory from visual design, produce a copy-ready **visual usage-layer directory** brief, not a storage reorganization plan. Preserve `02_课程库/`, `93_导入报告/`, `99_附件/`, and `E:/学习数据` as storage/source layers; ask OPEN DESIGN for IA/navigation/Figma/Bookmarks/page responsibilities over them. Use `references/open-design-visual-directory-handoff-2026-07-05.md` for the prompt shape, directory skeleton, and evidence-boundary wording.

### Cross-project backend absorption into OBS

When the user points to another local backend project and says to inspect/copy useful parts into the OBS backend, treat it as **capability absorption**, not a raw folder copy. Inspect the source repo read-only, identify reusable capability classes, adapt them into helper-repo scripts/tests/docs, and preserve OBS boundaries: no runtime DBs/logs/caches/secrets, no real vault notes/media/OCR dumps, default read-only/dry-run, candidate-only suggestions unless verified by the course pipeline. For the Cognitive-Loop-OS → OBS pattern, V10 absorbed auto-tagging/backlinks/gardener into `scripts/v10/cognitive_vault_garden.py`, sleep-loop real-task rules into `scripts/v10/obs_task_ledger.py` (SQLite local ledger; virtual/preview/dry-run tasks cannot become `done`; completion requires verifiable evidence), course gap orchestration into `scripts/v10/course_transform_ledger.py`, multi-format source manifest/intake into `scripts/v10/course_intake_adapter.py`, Dataview-like read-only queries into `scripts/v10/obs_dataview_query.py`, candidate-only term/fact/graph extraction into `scripts/v10/course_fact_extractor.py`, OBS-safe crossref/pipeline candidates into `scripts/v10/course_pipeline_candidate.py`, and frontend/Bridge lightweight index export into `scripts/v10/obs_v10_index_exporter.py`. See `references/cognitive-loop-os-backend-absorption-2026-07-07.md` for module mapping, verification commands, and next candidates.

### OBS backend scope after frontend/Open Design work

If a session has focused on OPEN DESIGN, plugin UI, Bridge transport, route maps, or lightweight JSON indexes, do **not** narrow “backend responsibility” to frontend support. For this user, OBS backend also owns the primary course pipeline: select sources from `E:/学习数据`, identify/OCR/transcribe/verify, generate summaries/workflows/cards/evidence/project/OER pages, write the formal local vault, produce import reports, and commit locally. After visual/front-end work, re-center the next tasks on a course transformation ledger, stale workbench-path fixes, and the next small source-backed course ingestion before producing UI indexes. Detailed correction and task ordering: `references/obs-backend-course-ingestion-and-frontend-boundary-2026-07-07.md`.

When the user asks for a **read-only OBS frontend / Bridge / Open Design inspection** and a backend V10 index接入清单, use `references/obs-bridge-v10-index-handoff-2026-07-07.md`: inspect the Open Design handoff, deployed `talos-frontend-ui` lightweight indexes, Bridge protocol/transport scripts, and backend V10 scripts; verify the current 5-action/7-route/2-command contract; then produce a compact table of V10 JSON indexes (`course_transform`, `vault_garden`, `source_manifest`, `task_ledger`) with source command, frontend domain, safety boundary, and acceptance check. Do not call `obs_task_ledger.py summary/list/report` in a strictly read-only pass unless local SQLite initialization writes are acceptable.

### Local/no-API open-source toolchain research

When the user asks to research or upgrade the OBS/Obsidian full course pipeline with open-source projects, prioritize directly usable local/no-API tools and composable adapters over full RAG platforms. P0 baseline: manifest/SQLite ledger, MarkItDown + python-docx/python-pptx + PyMuPDF + trafilatura, FFmpeg + PySceneDetect, whisper.cpp/faster-whisper, jieba/RapidFuzz/NetworkX/SQLite FTS5. Escalate to Tesseract/OCRmyPDF/PaddleOCR/Docling/Surya/sentence-transformers/sqlite-vec only when the course needs it. Keep heavy tools optional and all OCR/ASR/full media artifacts local. See `references/local-open-source-toolchain-research-2026-07-07.md` for the researched priority matrix and safety rules.

**Proven first-stage implementation pattern:** use a new scoped snippet (`talos-purple-gemstone.css`) rather than patching older global TALOS CSS; enable it in `appearance.json`, add a `💎 TALOS Purple Gemstone` bookmarks group, generate `00_TALOS_Home_Console.md`, `28_TALOS设计系统.md`, `29_TALOS_Project_Atlas.md`, and `30_TALOS_Review_AI_Center.md`, then validate JSON/fences/hrefs/CSS/mojibake and commit locally. If a write script is blocked by Hermes approval timeout, stop, ask for approval, and on “继续” re-verify disk/git state before resuming. Do not stage unrelated Obsidian plugin runtime changes such as spaced-repetition data. Session-specific details: `references/talos-purple-gemstone-first-stage-2026-07-03.md`.

**Adaptive layout and link hygiene pitfall:** after a Purple Gemstone UI pass, if the user says the UI may not have landed or text looks misaligned, first verify the formal vault path, `appearance.json` snippet enablement, and file existence before rewriting. Then check for dashboard-generated long paths and link semantics. Do not auto-populate polished `Recent Notes` from raw newest Markdown files if that can include `93_导入报告/**/backups/**` or very long report paths; use curated short entries or filter backups. In raw HTML inside `00_主页/*.md`, sibling links should be short relative hrefs like `href="30_TALOS_Review_AI_Center.md"`; use `../` for other top-level folders, and avoid vault-root-looking hrefs like `href="00_主页/..."` from within the same folder because Obsidian can interpret them as `00_主页/00_主页/...`. Add responsive breakpoints for 1500/1280/1040/760/520px so three-column workspace mockups degrade cleanly to two-column and single-column layouts. Detailed fix/checklist: `references/talos-purple-gemstone-adaptive-layout-2026-07-03.md`.

### Layered KnowledgeOS UI Upgrade Ladder

When the user keeps asking to continue improving the vault UI after the first dashboard/navigation pass, proceed in coherent layers instead of making isolated CSS tweaks:

1. Premium dashboard + curated bookmarks.
2. Course card wall + domain dashboard.
3. Per-domain homepages (`02_课程库/<领域>/00_领域主页.md`).
4. Completed-course product portal (`02_课程库/<course>/00_课程总览.md`).
5. Knowledge-card hub + review center (`03_知识卡片/00_知识卡片总览.md`, `04_复习卡片/00_复习中心.md`).
6. TALOS control console layer when the user asks for a system-control/TALOS feel: command homepage, task radar, V6 evidence matrix, V7 project console, course command, system log, field command map, project Kanban, and evidence heatmap.

For each round: back up changed files outside the vault plugin tree, generate/patch only the usage layer unless explicitly approved to relocate storage, validate JSON and generated links, check for mojibake markers in touched notes, update the audit report, then make a local-only Git commit.

If a course-card aggregate note is mojibake/乱码 but split independent card files are healthy, preserve the bad aggregate in the external backup archive and replace it with a clean card-wall index linking to the healthy files. This improves search/index quality without deleting course knowledge.

For TALOS console work, use real disk counts instead of stale dashboard numbers, update `.obsidian/bookmarks.json` as the curated left navigation, keep CSS scoped in `talos-dashboard.css`, and run an explicit `href` target checker because Chinese path typos are easy. If context compression preserves stale todos, verify git/disk first and mark completed work rather than rewriting it.

See `references/ui-layered-upgrade-2026-07-01.md` for the full layered UI pattern and `references/talos-control-console-ui-2026-07-02.md` for the TALOS console page set, Kanban/heatmap pattern, and pitfalls.

## 7. QuickAdd Template Registration

In `.obsidian/plugins/quickadd/data.json`:

```json
{
  "choices": [
    {"name": "📚 课程总览", "type": "Template", "templatePath": "90_模板/课程处理/课程总览模板.md", "folder": "02_课程库"},
    {"name": "📝 逐节总结", "type": "Template", ...},
    {"name": "🏷️ 术语索引", "type": "Template", ...},
    {"name": "🛠️ 实操工作流", "type": "Template", ...},
    {"name": "📇 知识卡片", "type": "Template", "folder": "03_知识卡片"},
    {"name": "🔄 复习卡片", "type": "Template", "folder": "04_复习卡片"},
    {"name": "📋 待审核单", "type": "Template", "folder": "95_待审核"},
    {"name": "📊 导入报告", "type": "Template", "folder": "93_导入报告"}
  ],
  "templateFolderPath": "90_模板"
}
```

## 8. Windows-Specific Pitfalls

| Issue | Symptom | Fix |
|:---|---:|:---|
| BOM injection | Obsidian "failed to read JSON" | Kill YunDetectService or reboot |
| E: write | Node.js REPL → EPERM | Use Python instead of Node.js to write E: |
| PowerShell 5.1 | `&&` fails, utf8BOM fails | Use `-Encoding UTF8`, avoid `&&` |
| MSYS path issues | colon in filename fails | Use Windows path (C:\...) not MSYS (/c/...) for some tools |
| .bak file buildup | Plugin config backups in `.obsidian/plugins/` | Move backups out to project workspace archive (e.g. `D:/All projects/Obsidian-Assistance/archived-config-backups/`), then commit local vault cleanup; do not leave stale plugin code under `.obsidian/plugins/` |

## 9. Git Backup

- Local-only (no remote, no GitHub push of vault content)
- obsidian-git plugin: 30-min auto-commit
- `.gitignore` excludes: media files, caches, workspace configs
- Init: `git add .gitignore && git commit -m "init: 初始化备份"`

## 10. Templates Structure

Root level (9 general templates):
- Agent工作流模板.md, Codex项目规则模板.md, 复习卡片模板.md
- 课程卡片模板.md, 论文证据模板.md, 视频转写模板.md
- 素材资产模板.md, 项目卡片模板.md, 知识卡片模板.md

Course subdirectory `90_模板/课程处理/` (8 course-specific templates):
- 待人工审核单模板.md, 导入报告模板.md, 复习卡片模板.md
- 课程总览模板.md, 术语索引模板.md, 知识卡片模板.md
- 逐节课总结模板.md, **实操工作流模板.md** ← commonly missing, create if absent

### Template Format
All templates use YAML frontmatter:
```yaml
---
title:
type: <type>
course:
review_status: needs-review
created:
updated:
tags:
  - <tag>
---
```
