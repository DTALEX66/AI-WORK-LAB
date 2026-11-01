# Cognitive-Loop-OS → Obsidian-Assistance backend absorption (2026-07-07)

Use this when the user asks to inspect `D:/All projects/Cognitive-Loop-OS` and copy useful backend capabilities into the OBS / Obsidian-Assistance backend.

## Session outcome

The useful low-risk backend capabilities were not copied as runtime services. They were adapted as a helper-repo V10 script:

```text
D:/All projects/Obsidian-Assistance/Obsidian - Backend Assistance/scripts/v10/cognitive_vault_garden.py
D:/All projects/Obsidian-Assistance/Obsidian - Backend Assistance/tests/v10/test_cognitive_vault_garden.py
D:/All projects/Obsidian-Assistance/Obsidian - Backend Assistance/docs/cognitive-loop-os-backend-absorption-2026-07-07.md
```

The script absorbed class-level ideas from Cognitive-Loop-OS:

| Source module | Adapted capability |
|---|---|
| `shared/auto_tagger.py` | zero-dependency keyword extraction, suggested tags, atomic note detection |
| `shared/backlinks.py` | Obsidian-style wikilink/embed/local markdown link parsing |
| `shared/knowledge_gardener.py` | orphan detection, connection suggestions, thin-topic radar |

## Correct workflow pattern

1. Inspect the source repo read-only first (`git status`, top-level dirs, candidate modules). Do not assume previous access errors are still true.
2. Select modules by *capability class*, not by file-copy convenience.
3. Do **not** copy runtime state from Cognitive-Loop-OS: `data/`, `logs/`, caches, DBs, `.env`, tokens, local ledgers.
4. Adapt code to the Obsidian-Assistance helper repo style:
   - standalone CLI scripts under `scripts/vN/`;
   - default read-only / dry-run;
   - `--apply` writes reports only unless explicitly designed otherwise;
   - tests under matching `tests/vN/`;
   - docs + operator index update.
5. Preserve OBS evidence boundaries:
   - candidate tags/links/splits are `candidate-only`;
   - do not create or promote `verified` evidence;
   - do not read/copy source media;
   - do not modify formal course notes during audit tools.
6. Verify with tight tests first, then full backend tests and cloud-boundary audit.

## Commands that verified the V10 absorption

From `D:/All projects/Obsidian-Assistance/Obsidian - Backend Assistance`:

```bash
python -m py_compile scripts/v10/cognitive_vault_garden.py tests/v10/test_cognitive_vault_garden.py
python -m pytest tests/v10/test_cognitive_vault_garden.py -q
python -m pytest tests -q
python scripts/v4/obsidian_v4_audit.py .
```

From repo root:

```bash
python "Obsidian - Backend Assistance/scripts/v4/obsidian_v4_audit.py" .
```

Smoke test against the formal vault stayed read-only and returned real signals on the first 10 course notes: notes=10, links=156, embeds=2, orphans=2, unresolved_notes=7, thin_topics=29, suggestions=16.

## Future absorption candidates

| Cognitive-Loop-OS capability | OBS backend adaptation idea | Boundary |
|---|---|---|
| `shared/sleep_loop_engine.py` | OBS local course-loop ledger requiring real evidence before `done` | Do not copy daemon/runtime DB directly; build a small helper-repo ledger with tests |
| `app/ingestion/multi_format.py` | Unified PDF/DOCX/PPTX/HTML/image intake adapter for course conversion | Heavy deps must be optional; no raw media in repo |
| `shared/dataview.py` | Read-only Markdown/frontmatter query layer for frontend indexes | Query vault metadata only; no broad body scan unless authorized |
| `shared/fact_extractor.py` | Course/OER concept extraction and graph candidates | Needs Chinese-course tests before use; candidate-only |

## Pitfall

The user corrected that OBS backend is not just frontend/Bridge support: it also owns course conversion and formal入库. When absorbing Cognitive-Loop-OS capabilities, map them back to course-pipeline value first (source discovery, evidence, cards, reports, sleep-loop task ledger), then to frontend indexes second.