# Auxiliary repo upload: absorbing a user-provided Obsidian AI full-chain roadmap

Use this when the user pastes a large architecture/roadmap and says “上传” or “找到这个项目可以吸收的”.

## Session pattern

The user provided a long “本地 Obsidian AI 全链路工作流整合版” covering Obsidian, Hermes, DeepSeek/GPT routing, CC Switch, Codex, MarkItDown/OpenDataLoader, Cognee/GBrain, Dataview/Talos, Agents, DESIGN.md, SECURITY.md, and execution stages. The correct target was the `Obsidian-Assistance` helper repo, not the formal vault.

## Correct interpretation

Treat this as **sanitized helper-repo documentation upload**:

- Extract reusable architecture, templates, safety rules, and staged roadmap.
- Do not upload formal vault files or `.obsidian/` config.
- Do not upload course content, source media, OCR/ASR full text, private paths, or secrets.
- Classify the roadmap into:
  1. immediately absorbable;
  2. stable-later;
  3. concept-only;
  4. not absorbed / explicitly excluded.

## Good deliverable shape

Create a single helper-repo doc such as:

```text
docs/obsidian-ai-fullchain-absorption-plan.md
```

Include:

- helper repo positioning;
- what can live in `docs/`, `templates/`, `scripts/`, `snippets/`, `tests/`, `.github/workflows/`;
- YAML/MOC/Dashboard template plan;
- Hermes skill taxonomy;
- CC Switch modes;
- Codex engineering rules;
- security boundary;
- phased V5 roadmap building on the existing V4 safety foundation;
- explicit non-upload list.

Add a README link only, not real vault content.

## Verification before PR

Run checks in the helper repo:

```bash
python -m pytest tests -q
python scripts/v4/obsidian_v4_audit.py .
```

Also do a small documentation safety scan for:

- secret-like tokens;
- formal vault absolute paths;
- copied `.obsidian/` content;
- media/archive filenames that imply real course content was copied.

False positives may occur for words inside prohibition rules (for example “浏览器 Cookie” in a “禁止读取浏览器 Cookie” rule). Distinguish prohibition text from leaked secrets.

## PR flow

Use the helper repo branch → PR → CI → squash merge path. In the PR body state:

- sanitized architecture docs only;
- no formal vault notes/config copied;
- no source course material or secrets;
- tests/audit results.
