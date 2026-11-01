# First Course Processing Reference: 知识内化训练营

> Processed: 2026-06-28 ~ 2026-06-30
> Source: 21-day memory system course (audio 16 + video 9 + PDF 22)

## Lesson Summary 12-Section Template

Each lesson summary follows this exact structure (from the working summaries in `02_课程库/`):

1. **原始信息** — Source type (audio/video/PDF), timestamps, corresponding files, recognition status and known ASR/OCR issues.
2. **本节课讲了什么** — Concise narrative of the lesson's core content in 1-2 paragraphs.
3. **核心知识点** — Bulleted list of key takeaways (8-15 items).
4. **关键术语** — Wikilink list: `- [[术语1]]`  `- [[术语2]]`.
5. **操作步骤 / 实操流程** — Numbered actionable steps the learner can follow.
6. **重要案例** — Real examples the instructor gave (2-5 items).
7. **老师强调的重点** — Points the instructor explicitly emphasized.
8. **容易踩坑的地方** — Common mistakes/confusions (6-10 items).
9. **可以转成知识卡片的内容** — Candidate card topics (4-6 items).
10. **可以转成复习卡片的问题** — Q&A pairs for spaced repetition (2-4 questions).
11. **本版核验边界** — What this version validates and what still needs checking (OCR noise, missing frames, etc.).
12. **不收入正式结论的内容** — Explicitly excluded content with reasons.

## Image Embedding Pattern

For course day with supporting images (e.g. Day14 — 16 images):

1. Copy images from workspace to `99_附件/images/<Day>/`.
2. Create a `## 13. 课件配图` section at end of the lesson.
3. Use a table with thumbnail previews:

```markdown
| 编号 | 文件 | 预览 |
|:---:|:---|:---:|
| 01 | Description | ![[99_附件/images/Day14/01.jpg\|80]] |
```

4. Update the parent file's line "依据来源" to mention the image evidence.

## 95_待审核 Review Pattern

Written as `REVIEW_审核结论与处理建议.md`:

```markdown
## 总体结论
Course fully written to formal library. All 23 files are processing intermediates.

## 根目录文件（N个）
| 文件 | 状态 | 建议 |
|:---|:---|:---|

## 子目录（N个）
| 文件 | 正式库对应 | 建议 |
|:---|:---|:---|

## 尚未完成的事项
1. ...
```

## QuickAdd Choices Pattern

8 registered choices covering the pipeline:

| Name | Template Path | Target Folder |
|:---|:---|:---|
| 📚 课程总览 | 90_模板/课程处理/课程总览模板.md | 02_课程库 |
| 📝 逐节总结 | 90_模板/课程处理/逐节课总结模板.md | 02_课程库 |
| 🏷️ 术语索引 | 90_模板/课程处理/术语索引模板.md | 02_课程库 |
| 🛠️ 实操工作流 | 90_模板/课程处理/实操工作流模板.md | 02_课程库 |
| 📇 知识卡片 | 90_模板/课程处理/知识卡片模板.md | 03_知识卡片 |
| 🔄 复习卡片 | 90_模板/课程处理/复习卡片模板.md | 04_复习卡片 |
| 📋 待审核单 | 90_模板/课程处理/待人工审核单模板.md | 95_待审核 |
| 📊 导入报告 | 90_模板/课程处理/导入报告模板.md | 93_导入报告 |

## Plugin Verification Checklist

| Plugin | Key Setting to Verify |
|:---|:---|
| obsidian-git | autoSaveInterval=30, autoPushInterval=0, no remote |
| quickadd | templateFolderPath="90_模板", choices populated |
| templater-obsidian | template directory = 90_模板 |
| obsidian-spaced-repetition | tags include #flashcards #复习卡片 |
| cmdr | QuickAdd added to right ribbon; leftRibbon must be `[]` not `{"items":[]}` |
| text-extractor | Chinese+English OCR enabled |
| omnisearch | PDF indexing enabled |
| obsidian-tasks-plugin | Creation/completion/cancellation dates recorded |

## Plugin Troubleshooting (Known Fixes)

### cmdr loads but errors: `TypeError: this.plugin.settings.leftRibbon.forEach is not a function`

**File**: `.obsidian/plugins/cmdr/data.json`

The plugin expects `leftRibbon` (and `editorMenu`, `fileMenu`, `titleBar`) to be plain arrays. If any store `{"items": []}` instead of `[]`, the plugin throws on load.

**Fix**: Replace:
```json
"leftRibbon": {"items": []}
```
with:
```json
"leftRibbon": []
```

Same for `editorMenu`, `fileMenu`, `titleBar` if they also show the error.

**Verify**: Restart Obsidian. The plugin should load without the `forEach is not a function` error.

### spaced-repetition errors: `TypeError: this.list.splice is not a function`

**File**: `.obsidian/plugins/obsidian-spaced-repetition/data.json`

The plugin initializes a `QuestionPostponementList` object that expects `this.list` to be an array. If `questionPostponementList` is missing from `data.json`, `this.list` is `undefined`.

**Fix**: Add to the root of `data.json`:
```json
"questionPostponementList": []
```

**Verify**: Restart Obsidian. The `initOSRCore` error should no longer appear.

### omnisearch: `Cannot read properties of undefined (reading 'keys')`

**Cause**: Version-compatibility issue during index build. The plugin still indexes files (387 files in 2.3s is normal) and search works, but a non-fatal init error appears in console.

**Fix if cache exists**: `rm -rf .obsidian/plugins/omnisearch/cache/` and restart.
**If no cache dir**: This is a non-fatal init error — ignore. The plugin functions.

## CSS Enhancement File Paths & Patterns

The vault's `.obsidian/snippets/` has 3 active CSS files:
1. `dt-knowledgeos` — Dashboard card styling, callout colors, table formatting.
2. `obsidian-knowledgeos-dashboard` — Status grid, card grid, knowledge card hover effects.
3. `obsidian-deep-ui` — Core visual polish (page transitions, gradient text, glassmorphism sidebar, staggered card animations, blockquote/embed/image polish, scrollbar rounding, checkbox circle, hover lifts).

**Key deep-ui patterns** (add to `obsidian-deep-ui.css`):
- `@keyframes slideInRight` for page entry animation
- `.status-card:nth-child(N)` with staggered `animation-delay`
- `-webkit-background-clip: text` gradient on `h1`, `.count`, `strong`, `.nav-folder.mod-root > .nav-folder-title`
- `.markdown-preview-view img { border-radius: 8px; box-shadow: ... }`
- `.markdown-embed { border-left: 3px solid var(--interactive-accent); border-radius: 0 8px 8px 0; }`
- `.task-list-item-checkbox { border-radius: 50% }`

These are enabled via `appearance.json`:
```json
"enabledCssSnippets": ["dt-knowledgeos", "obsidian-knowledgeos-dashboard", "obsidian-deep-ui"]
```

## Workspace Migration Pattern

When moving the entire project workspace from C: to another drive:

1. **Copy** with `cp -r` (git-bash) or `robocopy` (Windows cmd). Cross-drive `mv` on Windows is copy+delete anyway.
2. **Verify** the destination has identical contents (`diff -r` on key subdirectories like `docs/`).
3. **Verify git remotes** — SSH-based remotes (`git@github.com:...`) are path-independent; HTTPS-based might not be. Run `git remote -v` in the new location.
4. **Confirm commit history intact** — `git log --oneline` should show the same commits.
5. **Delete old location** with `rm -rf <old-path>`.
6. **Update memory** to remove stale path entries and add the new one.
7. **Check vault config references** — if vault config references absolute paths in the workspace (e.g. scripts in `96_脚本/`), update those.

## Encoding Repair Pattern

When a markdown file renders as garbled Chinese despite being UTF-8:
1. The bytes are structurally valid UTF-8 but the text doesn't decode to meaningful Chinese.
2. Search sibling directories for the same file written correctly (e.g. the fixed version under a parallel subfolder).
3. Fix: `open(src, 'r', encoding='utf-8-sig')` → `open(dst, 'w', encoding='utf-8')`.

## Dataview Path Fix

The `00_待审核总览.md` dataview block may hardcode a stale folder path (`FROM "98_待人工审核确认"`). Fix to match the actual vault directory (`FROM "95_待审核"`).
