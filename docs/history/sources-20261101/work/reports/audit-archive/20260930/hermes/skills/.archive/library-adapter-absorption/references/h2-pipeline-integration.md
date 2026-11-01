# H2 Pipeline Integration: Wiring Absorbed Modules into the Processing Chain

When ADOPT items have been absorbed (deps + modules + tests), the next step
is wiring them into the **actual product pipeline** — not leaving them as
standalone importable-but-unused modules.

## Pattern: One Integration Point per Module

| Module | Pipeline Stage | Integration Method |
|---|---|---|
| `file_detection.py` (Magika) | Intake routing | New `detect_format_from_content()` → replaces extension-only `detect_format()` in `convert_file` |
| `text_quality.py` (JiWER + RapidFuzz) | Conversion quality gate | `assess_conversion()` called from `convert_file(quality=True)`; CER only when truth provided |
| `evidence_connectors.py` (Crossref/DataCite/OpenAlex/Wikidata) | Cross-validation | `query_public_sources(doi=)` → `enrich_with_public_sources()` in `cross_reference.py` |
| `json_canvas.py` (validator) | Canvas processing | `validate_json_canvas()` inside `_via_canvas()`, replacing ad-hoc checks |
| `learning_scheduler.py` (py-fsrs) | Learning lifecycle | `schedule_next_review(correct: bool)` → FSRS interval from practice score |

## Integration Rules

1. **Minimally invasive**: Add a new function or optional kwarg; don't rewrite existing signatures.
2. **Fail gracefully**: Every integration wraps external calls in try/except with clear fallback.
3. **Honest: no fake metrics**: CER/WER only when truth exists; engine confidence ≠ accuracy.
4. **Test before commit**: Run the full test suite for the affected pipeline stage.
5. **One commit per batch**: Group 3-5 integrations per commit; push and let CI run while you work on the next batch.

## Common Pitfall: Validator Makes Tests Stricter

When you replace ad-hoc validation with a proper spec validator (e.g. JSON Canvas),
**existing test fixtures may break** because they used invalid fixture data that
the old code tolerated. The validator is correct — fix the test fixture, not the
validator. This is not a regression; it's the validator doing its job.

## Common Pitfall: sed replaces `return` across function boundaries

When using `sed` to add a quality-assessment closure (like wrapping every `return X, Y`
with `return _return(X, Y)`), sed matches ALL `return` statements in the file — not
just those inside the target function. If `convert_url()` (a sibling function) also
has the same `return engine, content` pattern, those lines will be rewritten to call
`_return()` — which is only defined inside `convert_file()`. Result: `NameError: name
'_return' is not defined` at runtime.

**Fix**: After sed transformation, grep the file for `_return` and verify every
occurrence is inside the function that defines it. Manually revert any matches
outside that scope. Better yet: use Python AST-based transformation, or add the
closure pattern manually instead of sed.

## Commit Message Convention
```
feat(h2): pipeline integration — <stage1>, <stage2>, ...

Wire absorbed modules into the actual processing pipeline:

1. <module> → <stage> (<tag>)
   - change description
2. ...

Tests: <N> <stage> tests pass, 0 regression.
```
