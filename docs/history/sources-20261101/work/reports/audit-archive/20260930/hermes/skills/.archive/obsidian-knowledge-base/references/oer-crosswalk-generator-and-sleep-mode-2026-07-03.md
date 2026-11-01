# OER crosswalk generator + TALOS sleep-mode UI loop (2026-07-03)

Use this reference when continuing TALOS/OER work in the Obsidian formal vault or helper repository.

## What proved useful

- Treat the user's “睡觉模式 / 自己找任务 / 界面优先 / 直到停止命令” as a bounded autonomous loop, not as permission to do unscoped writes.
- State boundaries first, then execute: local-only vault commits, no upload, no fake evidence, no moving/deleting course source paths, no API/secrets, no EXE.
- Interface priority means building/maintaining the usage layer: TALOS pages, course OER portals, FAQ hubs, bookmarks, scoped CSS, execution reports, and training/retro dashboards.
- Prefer reusable tooling once a pattern repeats across courses. After manually applying OER crosswalks to two courses, the right next task was a helper-repo generator.

## OER course crosswalk pattern

For each course, generate or maintain:

- `14_开放知识交叉对比.md` — structural mapping to open-knowledge patterns.
- `15_FAQ问题驱动入口.md` — Stack Exchange-style question hub.
- optional `50_领域知识/开放知识与OER/<course>_OER交叉对比样板.md` — reusable sample.
- course `00_课程总览.md` entry linking the new pages.
- TALOS entries: `15_TALOS开放知识交叉对比.md`, `16_TALOS睡觉模式执行台.md`, `17_TALOS界面导航矩阵.md`, `.obsidian/bookmarks.json`.
- execution report under `93_导入报告/<date>_TALOS_sleep_mode_*` with backups.

## Profiles

- `learning`: OpenStax/Wikibooks + MIT OCW/Wikiversity + Stack Exchange + Wikidata.
- `techdocs`: MDN + Stack Exchange + Wikidata + MIT OCW assignment structure.
- `design`: OpenStax/LibreTexts + Wikimedia Commons/Openverse metadata + design FAQ + project Rubric.
- `general`: Wikipedia/OpenStax/MIT OCW/Stack Exchange/Wikidata baseline.

## Evidence boundary

- If `11_证据索引.md` exists and contains verified evidence, crosswalk pages may link it.
- If no V6 verified evidence exists, explicitly say so. Do not upgrade open websites, UI patterns, or generated FAQs into evidence.
- External open sites provide structure, licensing awareness, metadata fields, and question patterns — not course-specific facts unless separately verified.

## Helper repo generator

The reusable tool lives in the helper repo:

```bash
python scripts/v9/oer_crosswalk_generator.py \
  --vault "E:/BaiduSyncdisk/Obsidian知识库" \
  --course "UI系统全能班" \
  --sample                 # dry-run by default

python scripts/v9/oer_crosswalk_generator.py \
  --vault "E:/BaiduSyncdisk/Obsidian知识库" \
  --course "UI系统全能班" \
  --sample --apply \
  --backup-dir "E:/BaiduSyncdisk/Obsidian知识库/93_导入报告/<date>_TALOS_sleep_mode_ui_oer_rounds/backups"
```

Safety properties to preserve:

- dry-run by default;
- `--apply` required to write;
- overwrite refused unless `--overwrite`;
- path traversal blocked;
- backups before overwrite when backup dir is supplied;
- generated content carries the evidence boundary.

## Validation checklist

Before committing formal vault changes:

1. Parse `.obsidian/bookmarks.json` and any report JSON.
2. Check generated Markdown for replacement characters and balanced fences.
3. Check every HTML `href="...md"` target exists.
4. If Daily Missions are generated, run the V8 training radar and confirm `outputs/` files are not counted as missions.
5. Commit locally; final vault status must be clean.

Before merging helper repo tooling:

```bash
python -m py_compile scripts/*.py scripts/v4/*.py scripts/v5/*.py scripts/v6/*.py scripts/v7/*.py scripts/v8/*.py scripts/v9/*.py pytest.py
python -m pytest tests -q
python scripts/v4/obsidian_v4_audit.py .
```

The lightweight in-repo `pytest.py` does not support `pytest.raises`; use a small `assert_raises` helper in tests.

## Proven outputs from this session

- OER pages applied to: `知识内化训练营`, `大模型应用开发介绍`, `UI系统全能班`.
- Helper repo PR merged: V9 OER crosswalk generator.
- TALOS sleep-mode pages used: `16_TALOS睡觉模式执行台`, `17_TALOS界面导航矩阵`.
