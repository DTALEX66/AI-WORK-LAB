# Session 2026-06-30 — Obsidian Plugin Fixes & Proven Patterns

## Plugin Config Repairs

### cmdr: leftRibbon TypeError
**Error:** `TypeError: this.plugin.settings.leftRibbon.forEach is not a function`
**Root cause:** `leftRibbon` was stored as `{"items": []}` (object) but cmdr version expects `[]` (array).
**Fix:** Rewrite `.obsidian/plugins/cmdr/data.json`:
```json
{
  "leftRibbon": [],       // was {"items": []}
  "rightRibbon": [
    {"id": "quickadd:Run Quick Add", "icon": "plus-circle"}
  ],
  "editorMenu": [],
  "fileMenu": [],
  "titleBar": []
}
```

### obsidian-spaced-repetition: QuestionPostponementList
**Error:** `TypeError: this.list.splice is not a function` at `QuestionPostponementList.clear`
**Root cause:** `questionPostponementList` field missing from `data.json`.
**Fix:** Add to root of `data.json`:
```json
{
  "settings": {...},
  "questionPostponementList": []
}
```

### omnisearch: Index init error
**Error:** `Cannot read properties of undefined (reading 'keys')`
**Status:** Non-fatal. No cache directory exists to clear. Plugin still indexes files (387 indexed in this session). Likely a version compatibility issue.

### tasks-plugin: benign warnings
**Error:** `Unexpected failure to create a list item from line: <header/dataview-query>`
**Status:** Harmless. Fires on every line that isn't a task (`- [ ]`). Headers, dataview `TABLE/FROM/WHERE/SORT` lines, image embeds `![[...]]`, and regular paragraphs all trigger it. Only an issue if actual `- [ ]` task lines are being missed.

## Full Automation Verification Pattern

From this session: ALL 6 pending items resolved without user input by cross-referencing the available transcript corpus:

| Item | Source Files Used |
|:---|:---|
| A1 DAY6 Anki | 4 video transcripts (Mac, Windows, iPhone, Android) |
| A2 DAY15 121工作流 | Audio transcript |
| A3 DAY18 卡片指数 | Audio transcript |
| A4 DAY19 成长速度公式 | Audio transcript |
| A5 DAY20 复盘任务 | PDF OCR + event page OCR |
| A6 DAY21 毕业典礼 | Video transcript — core/filter split |

The combined corpus (audio + video + PDF OCR) was sufficient for all items. No web search, no screenshots, no user questions needed.

## CSS Enhancement Patterns Applied

In `.obsidian/snippets/obsidian-deep-ui.css`, these additions were made on top of the existing base:

1. **Keyframes:** `shimmer` (loading), `pulse-glow` (accent pulse), `slideInRight` (page transition)
2. **Staggered cards:** `.status-card:nth-child(2)` through `:nth-child(6)` with 0.05s increments
3. **Sidebar:** Root folder gradient title, child folders indented with left border
4. **Page transition:** `.markdown-preview-view { animation: slideInRight 0.15s ease-out; }`
5. **Strong text:** Gradient color (accent → purple)
6. **Blockquote:** Rounded right corners, accent left border, alt bg
7. **Tabs:** Rounded workspace tab headers with hover
8. **Images:** Rounded corners + soft shadow
9. **Embeds:** Left accent border + rounded corners
10. **Search results:** Bold title, rounded highlight background

## CODEX Workspace Cleanup

After migrating the Obsidian project workspace to `D:/All projects/`, the user asked to clean `Documents/Codex/`.

**What was deleted:** Date-stamped directories (2026-06-26, 2026-06-29, 2026-06-30) plus non-Obsidian project dirs (Cognitive-OS, DEV, OBS本地知识库搭建, Screen-Translation-Assistant, Warehouse integration).

**What was kept:** `AGENTS.md` only — the CODEX behavior rules file.

**Rule of thumb:** CODEX workspace at `Documents/Codex/` contains:
- Session outputs (date-stamped dirs) → safe to clean
- Config/rules (AGENTS.md, CLAUDE.md) → always keep
- Non-CODEX projects → keep unless user explicitly says "都清理"
