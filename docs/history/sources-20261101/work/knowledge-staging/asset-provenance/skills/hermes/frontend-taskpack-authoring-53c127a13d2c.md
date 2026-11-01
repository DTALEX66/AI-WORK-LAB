---
name: frontend-taskpack-authoring
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/frontend-taskpack-authoring/SKILL.md
---

---
name: frontend-taskpack-authoring
description: "Author frontend taskpacks for design agents (OPEN DESIGN)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [frontend, taskpack, open-design, ui, spec, ia]
    related_skills: [desktop-build-verification, user-facing-ingestion-workflows, web-dashboard-delivery]
---

# Frontend Taskpack Authoring (OPEN DESIGN delivery)

## When to Use

- The user asks for a 前端任务包 / frontend taskpack, typically via the OPEN DESIGN prompt template: "HERMES，我需要为前端界面做准备，请把以下信息整理后推送给我…按这个结构输出" (页面/视图清单 → 信息架构 → 交互流程 → 设计约束 → 已有素材)
- Any request to hand a UI/spec inventory to an external design agent or another machine
- Preparing design deliverables that must reflect the REAL current implementation, never invented screens

Do NOT use for: building the UI itself, writing design tokens/components (that's the design agent's job), or restyling.

## Hard rules (user-enforced)

1. **Every claim must come from real project files.** Extract from the actual implementation — do not invent pages, fields, states, or counts.
2. **Unknowable dimensions → 标注「待补充」.** Never fabricate to fill a gap. The user explicitly said: "如果某个维度暂时没有结论，标注「待补充」即可，不要编造成 fake 数据."
3. **禁 FIXTURE 冒充真实、禁幻影 KPI、禁伪进度** — the UI itself forbids fake progress; the taskpack must describe that discipline, not violate it.
4. **不暴露内部 ID** — pages must not show command/package/artifact/internal numbers; no API key/JWT/manual approval/reason fields for the local single-user flow (background audit only).

## Protocol

### 1. Inventory real sources first (parallel reads)

For an ArcheAxis Knowledge / ArcheAxis-Knowledge-OS project, the authoritative sources are:

| Source | What it provides |
|---|---|
| `app/workspace/ui/index.html` | Every page section (`<section class="page" id="page-*">`), shell (header/rail/nav/inspector/activity-dock), modals (`#intake-modal`), buttons (`data-action`/`data-page`), empty/loading states |
| `app/workspace/router.py` | Complete API endpoint list (`@router.get/post/...`), each page's data source |
| `app/main.py` | Core endpoints (`/ingest`, `/convert/*`, `/health`, `/diagnostics`, `/version`) |
| `app/workspace/ui/assets/app.js` | Interaction wiring: `data-action` handlers, `/workspace/api/*` fetch calls, toast/status feedback |
| `desktop/src-tauri/tauri.conf.json` | productName, window-less shell config, frontendDist, bundle/resources |
| `desktop/src-tauri/src/lib.rs` | Window title, sizes, error dialogs, readiness (user-visible surfaces!) |
| `desktop/bootstrap/index.html` | Boot splash text (user-visible!) |
| `app/release-manifest.json` | product name / english_name / workspace_name (name mapping authority) |
| `docs/PRODUCT_STAGE_COMPATIBILITY.md` | UI organization constraints (documents/files/Canvas/learning first, NOT Runtime/Agent/MCP centric) |

Read the HTML with `Path.read_text(encoding='utf-8-sig')` in execute_code — the file tool may refuse it as "binary" while Python decodes it fine. `git grep` is more robust than Python `rglob` for scanning (rglob errors on broken junctions in `.hermes/`).

### 2. Emit the 5-section structure verbatim

1. **页面/视图清单** — table: 页面名 / 形态（全屏页/弹窗/抽屉/内嵌面板）/ 优先级（🔴高 🟡中 🟢低）/ 现状（已实现…）。Include the shell skeleton (top bar, rail, subnav, inspector, activity dock) as entries.
2. **信息架构** — per page: modules/cards, fields & data & states, data source (API endpoint names). Map each card to its `GET/POST /workspace/api/...` endpoint — the router.py grep is the evidence.
3. **交互流程** — main path (导入→复核→知识→学习→进化→机器知识), and the state vocabulary the UI already implements: 加载 (`aria-live="polite"` + "加载中/正在读取…"), 成功 (chip `status ok`), 失败 (toast `#toast` + result `<pre aria-live>`), 空状态 (explicit copy, never fake counts), 未接入 (page-unavailable).
4. **设计约束** — target platform (desktop Web in Tauri WebView; window 1280×800 min 960×640; NOT responsive/mobile), theme system (`data-theme`: 紫曜/浅色/曜金/深空), user's hard design preferences (Apple/Linear/Vercel 克制精密; NO purple gradients; NO generic admin template), naming contract (对外=ArcheAxis Knowledge/星环知识平台; internal pill/tab may keep ArcheAxis Learning Workspace; forbidden: 元枢·观心/元枢系统/ArcheAxis Workspace/ArcheAxis OS/星轨学习工作台).
5. **已有素材** — styles.css (CSS vars: `--nav-w:248px`, `--top-h:58px`, `--font-ui:Noto Sans SC/Inter`…), app.js, vendored pdfjs (`pdf.min.js` 3.11.174 + LICENSE), icons (`desktop/src-tauri/icons/`), inline SVG + Unicode glyphs (◈▣➜⚙), FastAPI OpenAPI auto-doc, Obsidian/JSON Canvas compat references. Mark missing items (e.g. final logo) as 待补充.

### 3. Run a naming sweep BEFORE delivering

While reading user-visible surfaces, audit every one of them for forbidden old names. Active surfaces list (all user-visible):

- Window title (`lib.rs` `.title(...)`)
- Boot splash (`bootstrap/index.html` body text + `<title>`)
- Error dialog titles (`lib.rs` `show_startup_error` strings)
- UI buttons/labels/headings (`index.html` — e.g. 返回观心总览→返回总览)
- HTTP User-Agent / protocol strings (`shared/evidence_connectors.py`)
- Installer messages (`verify_nsis_install.ps1`)
- SVG aria-label / NSIS asset names

Allowed contexts (do NOT "fix" these): test rejection fixtures (`protocol.rs`), contract mapping tables (NAMING_CONTRACT), gate forbidden-term definitions (`check_repository_conventions.py`), SUPERSEDED historical docs (check for the SUPERSEDED banner before editing!), fixture file names referencing historical deliveries, old reports.

Sweep full forms: `git grep -n "元枢" -- desktop/ app/ scripts/ shared/ windows/` and `ArcheAxis[-_ ]?Workspace|ArcheAxis[-_ ]?OS|元枢系统|元枢·观心|星轨学习工作台`. Also scan hyphenated variants (`ArcheAxis-Workspace`) — the first sweep missed the User-Agent hit for exactly this reason.

### 4. Gate self-test (when the naming gate was changed)

After editing `check_repository_conventions.py`, prove the gate can actually catch violations: construct a temp file containing each new forbidden term, run `--source worktree` (or head) and assert issues > 0, then remove the temp file. A gate change without this self-test is unverified (this session's gate had been blind to `元枢系统` in `.html` because the suffix whitelist excluded `.html` — verify the suffix list matches the surfaces the project actually uses).

## Pitfalls

1. **SUPERSEDED banner check before editing docs** — PRODUCT_POSITIONING.md, taskpack ADDENDUMs etc. carry a 2026-08-12 SUPERSEDED banner; old names inside them are CORRECT historical context. Editing them would rewrite history.
2. **Scan hyphen variants** — `ArcheAxis-Workspace` (User-Agent) survived the first sweep because the pattern wasn't applied to that surface; sweep all active surfaces with explicit patterns.
3. **read_file binary refusal** — `index.html` with CRLF/BOM can be refused as binary by read_file; use `Path.read_text(encoding='utf-8-sig')` via execute_code.
4. **Don't deliver invented states** — the taskpack's 状态 vocabulary must be the states the UI actually renders (loading/success/fail/empty/unavailable), not a generic UX checklist.
5. **Local single-user flow** — describe the flow WITHOUT API keys, JWT, manual approval, or reason fields; approval actions exist (research approve) but require no user-entered reason — the ledger records it automatically.

## Verification

- Every page/module in sections 1-2 has a matching `<section>` in index.html and a matching API endpoint in router.py (cross-check counts)
- Section 4 forbidden names: `git grep` of all active surfaces returns zero hits
- The taskpack contains no numbers/counts that aren't backed by real reads
