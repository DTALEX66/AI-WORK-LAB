# TALOS Purple Gemstone adaptive layout + link hygiene — 2026-07-03

## Trigger

Use after building Purple Gemstone / Obsidian Workspace-style pages when the user reports that the UI “didn’t land,” looks misaligned, has text overflow, or may not have been pushed to the knowledge base.

## What happened

A Purple Gemstone UI pass was successfully written to the formal vault, but the user suspected either the changes were not present or text was misaligned. Live inspection showed:

- Files were present under `E:/BaiduSyncdisk/Obsidian知识库`.
- `.obsidian/appearance.json` had `enabledCssSnippets: ["talos-purple-gemstone"]`.
- The issue was not missing files; it was layout/link hygiene:
  - Home Console `Recent Notes` had auto-included backup/report paths from `93_导入报告/.../backups/`, which were too long and visually broke cards.
  - Some HTML `href` values inside `00_主页/*.md` used vault-root-looking paths such as `00_主页/30_TALOS_Review_AI_Center.md`; Obsidian can interpret these as relative to the current note, producing `00_主页/00_主页/...` broken links.
  - Wide three-column mockup layouts need explicit responsive breakpoints for half-screen and narrow windows.

## Durable fix pattern

### 1. Verify landing before rewriting

Check these first:

```bash
cd "E:/BaiduSyncdisk/Obsidian知识库"
git status --short --branch
git log --oneline -5
python - <<'PY'
import json
print(json.dumps(json.load(open('.obsidian/appearance.json', encoding='utf-8')), ensure_ascii=False, indent=2))
PY
```

Confirm key files exist:

```text
.obsidian/snippets/talos-purple-gemstone.css
00_主页/00_TALOS_Home_Console.md
00_主页/28_TALOS设计系统.md
00_主页/29_TALOS_Project_Atlas.md
00_主页/30_TALOS_Review_AI_Center.md
00_主页/31_TALOS_Course_Reading_Layout.md
```

### 2. Do not auto-fill Recent Notes from raw newest files

For dashboard `Recent Notes`, avoid blindly scanning all recent Markdown files. Exclude at minimum:

- `93_导入报告/**/backups/**`
- generated backup copies such as `*.bak` or names containing `__`
- very long report paths that are better linked from a report section

For polished dashboards, prefer curated short entries:

```text
30_TALOS_Review_AI_Center.md
29_TALOS_Project_Atlas.md
31_TALOS_Course_Reading_Layout.md
28_TALOS设计系统.md
18_TALOS_OER覆盖率仪表盘.md
```

### 3. HTML href rules inside Obsidian Markdown

When writing raw HTML links inside a note under `00_主页/`:

- Link to sibling files with short relative paths:
  - `href="30_TALOS_Review_AI_Center.md"`
  - `href="29_TALOS_Project_Atlas.md"`
- Link to parent/other top-level folders with explicit `../`:
  - `href="../02_课程库/知识内化训练营/00_课程总览.md"`
- Avoid vault-root-looking paths inside HTML from the same folder:
  - bad from `00_主页/00_TALOS_Home_Console.md`: `href="00_主页/30_TALOS_Review_AI_Center.md"`

Run a strict href checker that treats non-`../` hrefs as relative to the current note, not as vault-root fallbacks.

### 4. Responsive breakpoints to add

For Purple Gemstone pages, add a scoped adaptive layer:

- `>1500px`: full product-style three columns.
- `<1280px`: search row wraps; right rail moves below as two columns; dashboard grid drops from 12 to 8 columns.
- `<1040px`: app grid becomes one column; left rail becomes flow cards; canvas/review/note workspaces become one column.
- `<760px`: all widgets become one column; hero/gem/calendar shrink.
- `<520px`: list time columns hide; cards compact further.

Key CSS hygiene:

```css
.talos-purple-gemstone .talos-workspace-frame,
.knowledgeos-v5 .talos-workspace-frame {
  width: min(100%, 1680px);
  max-width: 100%;
  box-sizing: border-box;
  container-type: inline-size;
}
.talos-purple-gemstone .talos-widget,
.knowledgeos-v5 .talos-widget,
.talos-purple-gemstone .talos-card,
.knowledgeos-v5 .talos-card {
  box-sizing: border-box;
  min-width: 0;
  overflow-wrap: anywhere;
}
.talos-purple-gemstone .talos-tabs,
.knowledgeos-v5 .talos-tabs {
  overflow-x: auto;
  flex-wrap: nowrap;
}
```

Keep selectors scoped. Do not add `body`, `html`, `:root`, external fonts, or `url()`.

### 5. Validation checklist

Before committing:

- JSON: `.obsidian/appearance.json`, `.obsidian/bookmarks.json` parse.
- CSS: no `body`, `html`, `:root`; no `url()`.
- Markdown: balanced fences and basic HTML div balance.
- Home Console hrefs: sibling links resolve relative to `00_主页/`.
- Home Console leak scan: no `backups/` or backup report paths in visible dashboard cards.
- Git staging: exclude unrelated Obsidian runtime/plugin changes.

## Commit pattern

Use a focused local-only commit such as:

```text
fix: 增加TALOS自适应窗口布局
```
