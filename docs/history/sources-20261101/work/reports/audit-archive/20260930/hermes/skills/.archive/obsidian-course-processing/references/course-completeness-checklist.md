# Course Completeness Audit Checklist

Use when the user asks to check all courses for completeness ("该有的任何东西都不要少" / "检查所有课程完整性").
Also use as the FIRST step when the user reports UI/link failures ("OBS列表全乱了/界面不跳转/点击没反应").

## Pre-scan: Vault System Integrity

Before touching any course file, scan these system dimensions:

### 1. Community Plugins
- File: `.obsidian/community-plugins.json` — this vault uses ARRAY format `["plugin-id",...]`, NOT object format `{"plugin-id": true}`. Both are valid in different Obsidian versions. Do not report array format as corruption.
- Check `.obsidian/plugins/<name>/data.json` for known bugs:
  - cmdr: `leftRibbon` is dict `{"items":[]}` → must be bare `[]`
  - spaced-repetition: missing `questionPostponementList`

### 2. CSS Snippets
- 6 expected: `dt-knowledgeos`, `obsidian-deep-ui`, `obsidian-knowledgeos-dashboard`, `obsidian-knowledgeos-pro`, `talos-dashboard`, `talos-purple-gemstone`
- Check `.obsidian/appearance.json` → `enabledCssSnippets` — all 6 should be enabled

### 3. Dataview FROM Clauses
- Scan ALL `.md` files for `FROM "<path>"`
- Common broken references: `"10_项目输出"` → `"50_领域知识/10_项目输出"`, `"01_收集箱"` → `"01_收件箱"`

### 4. Wikilink Pipe in Tables
- `[[path|alias]]` inside markdown table rows: the `|` is ambiguous (wikilink alias vs table column separator)
- Fix: use `[[path\\|alias]]` (backslash-escape). Verify with Python `repr()` — `\\\\|` in repr means single `\\|` in file.
- HTML entity alternative: `[[path&#124;alias]]` — sometimes more reliable than backslash.
- If source file has correct underscores but Obsidian renders without them → CSS/rendering issue, NOT a source bug. Restart Obsidian.

### 5. Backup File Tag Pollution
- `93_导入报告/*/backups/` files inherit frontmatter tags from originals
- Searching `tag:课程库` returns both active pages AND hundreds of stale backup copies
- Fix: add `"93_导入报告/*/backups/**"` to `userIgnoreFilters` in `.obsidian/app.json`
- This also cleans up the file explorer sidebar

### 5. Shell Page Internal Links
- `00_主页/` shell pages may link each other with bare filenames like `[[00_TALOS_Home_Console]]`
- Fix: use absolute paths `[[00_主页/00_TALOS_Home_Console|Home Console]]`

### 6. Navigation Footer Integrity
- Every `02_课程库/<course>/00_课程总览.md` must end with:
```

---

## 🧭 导航

- 📚 [[02_课程库/00_课程库总览|课程库总览]]
- 🧱 [[02_课程库/02_课程卡片墙|课程卡片墙]]
- 🏠 [[02_课程库/<domain>/00_领域主页|<domain>]]
```
- **CRITICAL**: links MUST use vault-root-relative absolute paths. `../00_课程库总览` from a course page resolves to `02_课程库/<course>/00_课程库总览.md` (WRONG).

### 7. Template Artifact Cleaning
- Strip these patterns from course pages before displaying:
  ```
  r'Completed Course · [^\n]+'   # mashed badge text
  r'Active Course · [^\n]+'      # OER badge mashup
  r'\n\d+视频文件\d+核心课题\d+核心术语\d+%[^\n]*\n'  # raw stats dump
  r'\n\d+教材小时\d+模块\d+术语\d+训练天\n'
  r'\n\d+章节\d+PDF[^\n]*\n'
  ```

## What to scan

For each course directory under `02_课程库/`, check:

| Dimension | Detection | Minimum |
|---|---|---|
| Markdown files | `list(course_dir.rglob('*.md'))` | ≥1 |
| Frontmatter | `re.search(r'^---\n', text, re.MULTILINE)` | yes |
| Wikilinks | `re.findall(r'\[\[([^\]|#]+)', text)` | ≥1 |
| Image embeds | `re.findall(r'!\[\[', text)` | ≥1 (except category pages) |
| External URLs | `re.findall(r'https?://[^\s)\]]+', text)` | ≥1 |
| Cross-check section | `re.search(r'(交叉|比对|核实|验证|OER|外部.*参考)', text)` | yes |
| Attachment dirs | `99_附件/course-reference-images/<course>/` or `99_附件/images/<course>/` | preferred |
| Dataview queries | `re.findall(r'\`\`\`dataview', text)` | category pages only |

## Classification before remediation

Before filling gaps, classify the page type:

| Type | Indicators | Gap strategy |
|---|---|---|
| **Real course** | Has E盘 source, `type: course-portal`, 02_课程库/<name>/00_课程总览.md | Fill all gaps |
| **Category/index** | `is_index: true`, 00_领域主页.md or 00_分类说明.md, dataview queries | Only add wikilinks + 领域参考链接; skip images |
| **OER course** | `source_type: open-source-oer`, from awesome-skills-cn | Add OER badge + external links; visual type is always 结构图（生成式） |
| **Dashboard** | 00_课程库总览.md, 02_课程卡片墙.md, etc. | Skip |
| **Sensitive** | 敏感与待确认 | No changes |

## Gap-fill source priority

1. **Local domain knowledge**: `50_领域知识/` vault entries, OER sidecars in helper repo
2. **Network sources**: Official docs, academic papers, MOOC courses, industry standards
3. **Never fabricate**: Only link to verifiable public sources

## Portal table split

When the course portal mixes real courses and OER courses in one table:

```markdown
## 真实课程
> 📚 **本地源素材课程** — E盘视频/PDF/DOCX原始素材

| 课程 | 领域 | ... |

## OER 知识组织
> 🔖 **开源知识重组** — 非本地视频/PDF课程

| 课程 | 领域 | ... |
```

## Standard Sub-Pages to Create If Missing

These are referenced from shell pages and course templates. If they don't exist, create as placeholders:

| Page | Content Template |
|---|---|
| `12_视觉索引与配图` | `# 视觉索引与配图\n\n> 本页面用于集中展示课程的视觉配图、关键帧和设计资产。\n\n待补充。\n` |
| `13_项目转化` | `# 项目转化\n\n> 本页面记录课程学习后的实践项目转化。\n\n待补充。\n` |
| `04_关键图表与课件索引` | `# 关键图表与课件索引\n\n> 课程核心图表和课件快速索引。\n\n待补充。\n` |
| `06_验证与不确定项` | `# 验证与不确定项\n\n> 课程中待验证或存在不确定性的内容记录。\n\n待补充。\n` |
| `05_复习与检索练习` | `# 复习与检索练习\n\n> 课程复习问题和检索练习。\n\n待补充。\n` |
| `01_素材识别报告` | `# 素材识别报告\n\n> 课程原始素材识别和分类报告。\n\n待补充。\n` |
| `07_实操工作流` | `# 实操工作流\n\n> 课程中可操作的实践工作流。\n\n待补充。\n` |
| `08_术语索引` | `# 术语索引\n\n> 课程核心术语和概念索引。\n\n待补充。\n` |

## Domain Page Course Lists

Each domain page (`00_领域主页.md`) must have manual course links before the dataview block:

```
## 📚 课程入口
### 真实课程
- [[Photoshop AIGC商业设计/00_课程总览|Photoshop AIGC商业设计]]
...
### 🔖 OER 知识组织
- [[UI UX Agent设计系统实战/00_课程总览|UI UX Agent设计系统实战]]
```

## Batch Fix Order
1. Scan all dimensions → report counts
2. Plugin config → CSS → Dataview FROM
3. Missing standard sub-pages → Navigation footers
4. Shell page internal links → Domain page course lists
5. Portal table split → Frontmatter markers
6. Template artifact cleaning → External URL gap-fill
7. **One commit, tell user to restart Obsidian**
8. If user still sees stale rendering (missing underscores, blank pages): close Obsidian, delete `.obsidian/workspace.json`, reopen.
